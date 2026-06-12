# -*- coding: utf-8 -*-
# 参考 workbuddy.py 实现的流式接口

import asyncio
import io
import os
import logging
from typing import List, Optional, Union, IO
from fastapi import APIRouter, UploadFile, Form, File
from fastapi.responses import StreamingResponse
import json
import pandas as pd

from cloud_agent_sdk import (
    CloudAgentClient,
    RuntimeCreateOptions,
    ManifestBuilder,
    PromptOptions,
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


_RESOURCE_LINK_HINT = (
    "当你需要向用户返回文件（如 Excel、PDF、图片等）时，"
    "请始终使用 resource_link 类型（只返回文件的访问 URI），"
    "不要将文件内容以 base64 编码直接内嵌在消息体中（即不使用 resource 内嵌类型）。"
    "直接内嵌大文件会使单条 SSE 消息超过服务端 64KB 传输限制，导致连接中断。"
    "文件 URI 示例：oss://bucket/path/to/file.xlsx 或 https://cdn.example.com/file.pdf"
)


async def create_runtime():
    manifest = (
        ManifestBuilder()
        .id("agent_01KSSBM63DYZ563SPK088Y3YWW")
        .name("My Agent")
        .version("1.0")
        .system_prompt(_RESOURCE_LINK_HINT)
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
        try:
            runtime = await create_runtime()
            session = runtime.sessions.default()

            def on_chunk(notification: SessionNotification) -> None:
                try:
                    _on_chunk_impl(notification)
                except Exception:
                    # 单个 chunk 解析失败不应中断整个流
                    logger.exception("[ai_chat] on_chunk 回调异常，已跳过")

            def _on_chunk_impl(notification: SessionNotification) -> None:
                """基于 ACP 官方协议 SessionUpdate 变体处理通知。
                
                SessionUpdate 联合类型（由 session_update 字段区分）：
                - agent_message_chunk (AgentMessageChunk): content: ContentBlock (text/resource_link/resource/image/audio)
                - agent_thought_chunk (AgentThoughtChunk): 同上（思维链）
                - user_message_chunk  (UserMessageChunk):  同上（回显用户消息）
                - tool_call           (ToolCallStart):      tool_call_id, title, kind, status, content, locations, raw_input
                - tool_call_update    (ToolCallProgress):    tool_call_id + 可选 content/status/raw_input/raw_output/locations
                - plan                (AgentPlanUpdate):    entries[]
                - usage_update        (UsageUpdate):        used, size, cost?
                - current_mode_update (CurrentModeUpdate):  current_mode_id
                - config_option_update(ConfigOptionUpdate): config_options
                - available_commands_update: available_commands
                - session_info_update: session 元信息
                """
                update = notification.update
                session_update = getattr(update, "session_update", None)

                # ---- agent_message_chunk / agent_thought_chunk ----
                # 流式输出：文本 / resource_link / resource
                if session_update in ("agent_message_chunk", "agent_thought_chunk"):
                    content = getattr(update, "content", None)
                    if content is None:
                        return
                    content_type = getattr(content, "type", None)

                    # 纯文本
                    if content_type == "text":
                        text = getattr(content, "text", "") or ""
                        for part in _split_text_to_chunks(text, MAX_SSE_CHUNK_SIZE):
                            queue.put_nowait(json.dumps(
                                {"type": "chunk", "text": part}, ensure_ascii=False
                            ))

                    # 制品引用 —— 官方 ContentBlock: resource_link
                    elif content_type == "resource_link":
                        queue.put_nowait(json.dumps({
                            "type":        "artifact",
                            "name":        getattr(content, "name", ""),
                            "uri":         getattr(content, "uri", ""),
                            "mime_type":   getattr(content, "mime_type", None),
                            "title":       getattr(content, "title", None),
                            "description": getattr(content, "description", None),
                            "size":        getattr(content, "size", None),
                        }, ensure_ascii=False))

                    # 内嵌资源 —— 官方 ContentBlock: resource
                    elif content_type == "resource":
                        resource = getattr(content, "resource", None)
                        if resource is not None:
                            mime = getattr(resource, "mime_type", None)
                            uri = getattr(resource, "uri", "")
                            blob = getattr(resource, "blob", None)
                            text_res = getattr(resource, "text", None)
                            data_val = blob or text_res or ""
                            enc = "base64" if blob is not None else "text"
                            queue.put_nowait(json.dumps({
                                "type":      "artifact_embedded",
                                "mime_type": mime,
                                "uri":       uri,
                                "data":      data_val,
                                "encoding":  enc,
                            }, ensure_ascii=False))

                # ---- tool_call: 工具调用开始 ----
                elif session_update == "tool_call":
                    kind = getattr(update, "kind", None)
                    title = getattr(update, "title", "")
                    tool_call_id = getattr(update, "tool_call_id", "")
                    locations = getattr(update, "locations", None) or []
                    raw_input = getattr(update, "raw_input", None) or {}

                    # 从 raw_input 提取 file_path（Write 工具）
                    file_path = (
                        raw_input.get("file_path", "")
                        if isinstance(raw_input, dict)
                        else ""
                    )

                    # 从 locations 提取路径
                    paths = (
                        [loc.path for loc in locations if hasattr(loc, "path")]
                        if locations else []
                    )
                    if not paths and file_path:
                        paths = [file_path]

                    for p in paths:
                        queue.put_nowait(json.dumps({
                            "type":         "artifact_writing",
                            "tool_call_id": tool_call_id,
                            "path":         p,
                            "title":        title,
                            "kind":         kind,
                        }, ensure_ascii=False))

                # ---- tool_call_update: 工具调用状态更新 ----
                elif session_update == "tool_call_update":
                    status = getattr(update, "status", None)
                    tool_call_id = getattr(update, "tool_call_id", "")

                    # 工具完成
                    if status == "completed":
                        queue.put_nowait(json.dumps({
                            "type":         "artifact_done",
                            "tool_call_id": tool_call_id,
                        }, ensure_ascii=False))

                        # 同时检查 tool_call_update.content 里是否有 resource_link 制品
                        tc_content = getattr(update, "content", None) or []
                        for item in tc_content:
                            if hasattr(item, "type") and item.type == "content":
                                inner = getattr(item, "content", None)
                                if inner is not None and getattr(inner, "type", None) == "resource_link":
                                    queue.put_nowait(json.dumps({
                                        "type":        "artifact",
                                        "name":        getattr(inner, "name", ""),
                                        "uri":         getattr(inner, "uri", ""),
                                        "mime_type":   getattr(inner, "mime_type", None),
                                        "title":       getattr(inner, "title", None),
                                        "description": getattr(inner, "description", None),
                                        "size":        getattr(inner, "size", None),
                                    }, ensure_ascii=False))

                    # 工具失败
                    elif status == "failed":
                        queue.put_nowait(json.dumps({
                            "type":         "artifact_failed",
                            "tool_call_id": tool_call_id,
                        }, ensure_ascii=False))

            response = await session.prompt(
                message_blocks,
                PromptOptions(on_chunk=on_chunk, timeout_ms=120_000),
            )
            queue.put_nowait(json.dumps({"type": "done", "stop_reason": response.stop_reason}))
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
