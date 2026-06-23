# -*- coding: utf-8 -*-
# 参考 workbuddy.py 实现的流式接口

import asyncio
import io
import os
import logging
from typing import List, Optional, Union, IO
from urllib.parse import unquote
from fastapi import APIRouter, UploadFile, Form, File, HTTPException, Query
from fastapi.responses import StreamingResponse
import httpx
import json
import pandas as pd

from cloud_agent_sdk import (
    CloudAgentClient,
    RuntimeCreateOptions,
    ManifestBuilder,
    PromptOptions,
    Runtime,
)
from pydantic.fields import FieldInfo
from acp import PromptResponse
from acp.schema import (
    SessionNotification,
    TextContentBlock,
    Usage,
)

# 修复 agent-client-protocol/ACP 返回 usage 时缺少 totalTokens 的兼容问题
field = Usage.model_fields['total_tokens']
Usage.model_fields['total_tokens'] = FieldInfo(
    default=None,
    annotation=Optional[int],
    alias=field.alias,
    alias_priority=field.alias_priority,
    description=field.description,
    metadata=field.metadata,
)
Usage.model_rebuild(force=True)
PromptResponse.model_rebuild(force=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yyy/workbuddy", tags=["AI聊天"])

client = CloudAgentClient(api_key="ck_fns0v3cj85c0.wJgHcpGwka0JXdp9wWiYb3SeLASXkrd24IJJtqjXc8M",
                           source_app="formula-finance")

MAX_SSE_CHUNK_SIZE = 4096

# 持活 runtime 引用，供文件下载代理使用
_active_runtimes: dict[str, Runtime] = {}


def _split_text_to_chunks(text: str, max_chunk: int) -> List[str]:
    if not text:
        return []
    return [text[i:i + max_chunk] for i in range(0, len(text), max_chunk)]


def build_message_with_excel(
    question: str,
    excel_source: Union[bytes, bytearray, IO[bytes]],
    filename: Optional[str] = None,
) -> List[TextContentBlock]:
    """将 Excel 解析为 Markdown 文本，并与问题一起注入到 prompt 中。"""
    excel_name = filename or "uploaded_file.xlsx"
    markdown_content = ""

    if isinstance(excel_source, (bytes, bytearray)):
        file_stream = io.BytesIO(excel_source)
    elif hasattr(excel_source, "read"):
        if hasattr(excel_source, "seek"):
            try:
                excel_source.seek(0)
            except Exception:
                pass
        raw = excel_source.read()
        bytes_data = raw.encode("utf-8") if isinstance(raw, str) else raw
        file_stream = io.BytesIO(bytes_data)
        if filename is None and hasattr(excel_source, "name"):
            excel_name = os.path.basename(getattr(excel_source, "name"))
    else:
        raise ValueError("excel_source must be bytes or a binary file-like object")

    try:
        ext = os.path.splitext(excel_name)[1].lower()
        engine = None
        if ext in ('.xlsx', '.xlsm', '.xltx', '.xltm'):
            engine = 'openpyxl'
        elif ext == '.xls':
            engine = 'xlrd'

        if ext == '.csv':
            excel_sheets = {'Sheet1': pd.read_csv(file_stream)}
        else:
            if engine:
                excel_sheets = pd.read_excel(file_stream, sheet_name=None, engine=engine)
            else:
                excel_sheets = pd.read_excel(file_stream, sheet_name=None)

        markdown_content += f"以下是文件 [{excel_name}] 的内容结构：\n\n"
        for sheet_name, df in excel_sheets.items():
            markdown_content += f"### 工作表 (Sheet): {sheet_name}\n"
            markdown_content += df.fillna("").to_markdown(index=False)
            markdown_content += "\n\n"
    except ImportError as e:
        raise RuntimeError(
            f"解析 Excel 失败：当前环境缺少必要库。请安装 openpyxl (xlsx) 或 xlrd (xls)，错误信息: {e}"
        )
    except Exception as e:
        raise RuntimeError(
            f"解析 Excel 失败，请检查文件格式或是否安装 openpyxl/xlrd 库。错误信息: {e}"
        )

    full_prompt = (
        f"<uploaded_file name=\"{excel_name}\">\n"
        f"{markdown_content}"
        f"</uploaded_file>\n\n"
        f"请基于上方提供的文件内容，回答以下问题：\n"
        f"{question}"
    )

    logger.info("已成功将 Excel [%s] 解析为纯文本并注入上下文", excel_name)
    return [TextContentBlock(type="text", text=full_prompt)]


_SYSTEM_PROMPT = (
    "你是一个专业的财务数据分析助手。请遵循以下规则：\n\n"
    "## 核心工作流程\n"
    "当用户上传 Excel 文件并要求分析时，你**必须**按以下步骤操作：\n\n"
    "### 第1步：保存 Excel 数据\n"
    "将用户提供的 Excel 数据保存为文件到工作目录（如 /workspace/data.xlsx）。\n\n"
    "### 第2步：生成 HTML 报告文件\n"
    "使用 write_file 工具生成一份完整的财务分析 HTML 报告文件。报告应包含以下内容：\n"
    "- 带 CSS 样式的专业排版（表格、卡片、颜色标识）\n"
    "- 盈利能力分析（营收、利润、毛利率、净利率、ROE、ROA 趋势表）\n"
    "- 资产负债分析（总资产、负债、权益、资产负债率趋势表）\n"
    "- 现金流分析（经营/投资/筹资现金流、自由现金流、现金余额趋势表）\n"
    "- 每股指标（EPS、每股净资产、资产周转率）\n"
    "- 风险与机遇分析\n"
    "- 每个指标表格附带文字分析解读\n"
    "文件保存路径：/workspace/reports/financial_report.html\n\n"
    "### 第3步：返回文件链接\n"
    "报告文件生成后，**必须**使用 resource_link 类型将文件的 URI 返回给用户。\n"
    "URI 格式：file:///workspace/reports/financial_report.html\n"
    "mime_type 设为 \"text/html\"，name 设为 \"financial_report.html\"。\n\n"
    "### 第4步：输出文字摘要\n"
    "同时在文字回复中给出报告的核心摘要（营收、利润、关键发现、风险提示等），方便用户快速了解要点。\n\n"
    "## 重要规则\n"
    "- 必须使用 resource_link 返回文件，**禁止**使用 resource 内嵌 base64（会导致传输中断）\n"
    "- 文字摘要要简洁，详细数据在 HTML 报告里查看\n"
    "- 必须先写文件再用 resource_link 返回，不要只在文字中输出报告内容\n"
    "- HTML 报告要美观专业，支持移动端和打印"
)


async def create_runtime():
    manifest = (
        ManifestBuilder()
        .id("agent_01KSSBM63DYZ563SPK088Y3YWW")
        .name("My Agent")
        .version("1.0")
        .system_prompt(_SYSTEM_PROMPT)
        .build()
    )
    return await client.runtimes.create(
        RuntimeCreateOptions(runtime_name="demo", agent_manifest=manifest)
    )


@router.post("/chat")
async def stream_ai_chat(
    content: str = Form(""),
    files: List[UploadFile] = File([]),
):
    """流式返回 AI 对话结果，支持可选的 Excel 文件上传。"""
    prompt_blocks: List[TextContentBlock] = []
    if files:
        for upload in files:
            if not upload.filename:
                continue
            file_content = await upload.read()
            if not file_content:
                continue
            prompt_blocks.extend(
                build_message_with_excel(content, file_content, filename=upload.filename)
            )

    if prompt_blocks:
        message_blocks = prompt_blocks
    else:
        message_blocks = content

    queue: asyncio.Queue = asyncio.Queue()

    async def prompt_task():
        runtime = None
        try:
            runtime = await create_runtime()
            runtime_id = runtime.id
            _active_runtimes[runtime_id] = runtime
            logger.info("Runtime %s 已创建并缓存", runtime_id)

            session = runtime.sessions.default()

            # 收集 agent 完整回复文本（类似 workbuddy.py 中的 agent_response）
            agent_response_text = ""

            def on_chunk(notification: SessionNotification) -> None:
                """将每个 ACP SessionNotification 的 update 完整序列化为 SSE 事件。
                
                不再手动 getattr 抽取字段 —— 直接用 Pydantic model_dump()
                保留 ACP 协议原生完整结构，前端可以拿到：
                - agent_message_chunk / agent_thought_chunk: content + messageId + _meta
                - tool_call: toolCallId + title + kind + status + content + locations + rawInput + _meta
                - tool_call_update: toolCallId + content + kind + locations + rawInput + rawOutput + status + title + _meta
                - plan: entries[] (每个 entry: content + priority + status + _meta)
                - usage_update: used + size + cost + _meta
                - current_mode_update / config_option_update / available_commands_update / session_info_update
                """
                nonlocal agent_response_text
                update = notification.update

                # 序列化完整的 update 模型（Pydantic by_alias=False 使用 Python 字段名）
                update_dict = update.model_dump(mode="json", exclude_none=True, by_alias=False)

                # 提取 session_update 类型作为 SSE 事件类型标识
                session_update = update_dict.get("session_update")

                # ---- 文本内容：对大文本做分片处理，防止单条 SSE 过大 ----
                if session_update in ("agent_message_chunk", "agent_thought_chunk", "user_message_chunk"):
                    content = update_dict.get("content", {})
                    content_type = content.get("type")

                    if content_type == "text":
                        text = content.get("text", "") or ""

                        # 累积 agent_message_chunk 文本到完整回复（不含 thought）
                        if session_update == "agent_message_chunk":
                            agent_response_text += text

                        # 文本分片推送：将 update 中的 text 替换为分片后逐条发送
                        parts = _split_text_to_chunks(text, MAX_SSE_CHUNK_SIZE)
                        if len(parts) <= 1:
                            # 无需分片，直接发送完整 update
                            queue.put_nowait(json.dumps(update_dict, ensure_ascii=False))
                        else:
                            for i, part in enumerate(parts):
                                chunk_dict = dict(update_dict)
                                chunk_dict["content"] = dict(content)
                                chunk_dict["content"]["text"] = part
                                chunk_dict["_chunk_index"] = i
                                chunk_dict["_chunk_total"] = len(parts)
                                queue.put_nowait(json.dumps(chunk_dict, ensure_ascii=False))
                    else:
                        # 非文本类型（resource_link / resource / image / audio）
                        # 注入 runtime_id 方便前端构造下载代理 URL
                        if runtime_id:
                            update_dict["_runtime_id"] = runtime_id
                        queue.put_nowait(json.dumps(update_dict, ensure_ascii=False))

                # ---- tool_call / tool_call_update / plan / usage_update / 其他 ----
                else:
                    # 对 tool_call_update 也注入 runtime_id（可能包含 resource_link）
                    if runtime_id and session_update in ("tool_call_update",):
                        update_dict["_runtime_id"] = runtime_id
                    # 直接发送完整 update 字典
                    queue.put_nowait(json.dumps(update_dict, ensure_ascii=False))

            response = await session.prompt(
                message_blocks,
                PromptOptions(on_chunk=on_chunk, timeout_ms=120_000),
            )
            # 发送完成事件：包含 stop_reason、完整 agent 回复文本、usage 信息、runtime_id
            queue.put_nowait(json.dumps({
                "type": "done",
                "stop_reason": response.stop_reason,
                "agent_response": agent_response_text,
                "runtime_id": runtime_id,
                "usage": response.usage.model_dump(mode="json", exclude_none=True, by_alias=False) if response.usage else None,
            }, ensure_ascii=False))
        except Exception as exc:
            queue.put_nowait(json.dumps({"type": "error", "message": str(exc)}))
        finally:
            queue.put_nowait(None)

    prompt_runner = asyncio.create_task(prompt_task())

    async def event_generator():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            if not prompt_runner.done():
                prompt_runner.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/download/{runtime_id}")
async def download_file(
    runtime_id: str,
    uri: str = Query(..., description="沙箱内文件 URI，如 file:///workspace/report.xlsx"),
):
    """通过沙箱数据面代理下载 Agent 生成的文件。
    
    Agent 在沙箱内生成文件后通过 resource_link 返回 URI，
    浏览器无法直接访问沙箱内部路径，需要后端通过数据面代理拉取。
    """
    runtime = _active_runtimes.get(runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail=f"Runtime {runtime_id} 不存在或已过期")

    # 从 runtime info 中获取沙箱数据面端点
    runtime_info = runtime.runtime_info
    if runtime_info.links is None or runtime_info.links.sandbox_link is None:
        raise HTTPException(status_code=400, detail="Runtime 未提供沙箱数据面连接信息")

    sandbox = runtime_info.links.sandbox_link
    data_plane = sandbox.data_plane_endpoint.rstrip("/")
    sandbox_id = sandbox.sandbox_id

    # 从 URI 中提取文件路径
    file_path = uri
    # 去掉常见的 URI scheme 前缀
    for prefix in ("file://", "oss://", "sandbox://"):
        if file_path.startswith(prefix):
            file_path = file_path[len(prefix):]
            break

    # 确保路径以 / 开头
    if not file_path.startswith("/"):
        file_path = "/" + file_path

    # 提取文件名用于 Content-Disposition
    file_name = os.path.basename(file_path) or "download"

    # 尝试多种数据面 URL 格式访问文件
    url_candidates = [
        f"{data_plane}/files?path={file_path}",
        f"{data_plane}/v1/sandboxes/{sandbox_id}/files?path={file_path}",
        f"{data_plane}/download?path={file_path}",
    ]

    last_error = None
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        for candidate_url in url_candidates:
            try:
                logger.info("尝试从沙箱下载: %s", candidate_url)
                response = await http_client.get(candidate_url)
                if response.status_code == 200 and response.content:
                    content_type = response.headers.get("content-type", "application/octet-stream")
                    # URL 编码文件名，处理中文
                    encoded_name = file_name.encode("ascii", "ignore").decode("ascii") or "download"
                    if not encoded_name.strip():
                        encoded_name = "download"
                    content_disp = f'attachment; filename="{encoded_name}"; filename*=UTF-8\'\'{unquote(file_name)}'
                    return StreamingResponse(
                        io.BytesIO(response.content),
                        media_type=content_type,
                        headers={"Content-Disposition": content_disp},
                    )
                elif response.status_code == 200 and not response.content:
                    logger.warning("沙箱返回 200 但内容为空: %s", candidate_url)
                    continue
                else:
                    logger.warning("沙箱返回 %d: %s", response.status_code, candidate_url)
                    continue
            except Exception as exc:
                last_error = exc
                logger.warning("沙箱下载失败 %s: %s", candidate_url, exc)
                continue

    if last_error:
        raise HTTPException(
            status_code=502,
            detail=f"无法从沙箱下载文件 '{file_path}'，已尝试 {len(url_candidates)} 种 URL 格式。最后错误: {last_error}",
        )
    else:
        raise HTTPException(status_code=502, detail=f"无法从沙箱下载文件 '{file_path}'，所有 URL 格式均失败")
