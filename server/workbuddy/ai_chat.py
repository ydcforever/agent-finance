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

router = APIRouter(prefix="/yyy/ai", tags=["AI聊天"])

client = CloudAgentClient(api_key="ck_fns0v3cj85c0.wJgHcpGwka0JXdp9wWiYb3SeLASXkrd24IJJtqjXc8M",
                           source_app="formula-finance")

MAX_SSE_CHUNK_SIZE = 1500


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


async def create_runtime():
    manifest = (
        ManifestBuilder()
        .id("agent_01KSSBM63DYZ563SPK088Y3YWW")
        .name("My Agent")
        .version("1.0")
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
                update = notification.update
                if update.session_update == "agent_message_chunk" and getattr(update.content, "type", None) == "text":
                    text = update.content.text or ""
                    for part in _split_text_to_chunks(text, MAX_SSE_CHUNK_SIZE):
                        queue.put_nowait(json.dumps({"type": "chunk", "text": part}, ensure_ascii=False))

            response = await session.prompt(message_blocks, PromptOptions(on_chunk=on_chunk))
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
