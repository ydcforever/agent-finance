# -*- coding: utf-8 -*-
"""
Coze AI 流式对话模块
- upload_file_to_coze: 上传文件到 Coze，返回 file_id
- router: FastAPI 路由，提供 /coze/chat 流式接口
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import requests
from cozepy import (
    COZE_CN_BASE_URL,
    ChatEventType,
    Coze,
    Message,
    MessageObjectString,
    MessageType,
    TokenAuth,
)
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

# ───────────────────────── 日志 ─────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ───────────────────────── Coze 客户端 ─────────────────────────
_COZE_TOKEN = "pat_drMX4Qduj6NNcrU4WaOU4Pcp4wi9NWhHaetLW1ud3h8Va2z9RelLUrLBIYiKqx5x"
_BOT_ID     = "7643694491697922082"
_USER_ID    = "3137323286157770"

coze = Coze(
    auth=TokenAuth(token=_COZE_TOKEN),
    base_url=COZE_CN_BASE_URL,
)

router = APIRouter(prefix="/yyy/coze", tags=["Coze AI 对话"])


# ───────────────────────── 文件上传 ─────────────────────────
def upload_file_to_coze(file: UploadFile, token: str) -> Dict[str, Any]:
    """
    将前端上传的文件流转发至 Coze 平台

    Args:
        file (UploadFile): FastAPI 接收到的文件对象 (包含 .filename, .file, .content_type)
        token (str): Coze API 鉴权 Token (如 pat_...)

    Returns:
        dict: Coze 接口返回的 JSON 数据，结构如下：
            {
              "code": 0,
              "data": {
                "bytes": 152236,
                "created_at": 1715847583,
                "file_name": "1120.jpeg",
                "id": "736949598110202****"   ← 这是 file_id
              },
              "msg": ""
            }

    Raises:
        Exception: 如果网络请求失败或 Coze 返回错误码
    """
    url = "https://api.coze.cn/v1/files/upload"
    headers = {"Authorization": f"Bearer {token}"}

    # 构造 multipart/form-data 格式
    files_payload = {
        "file": (file.filename, file.file, file.content_type or "application/octet-stream")
    }

    try:
        response = requests.post(url, headers=headers, files=files_payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get("code") != 0:
            raise Exception(f"Coze Upload Failed: {result.get('msg')}")

        return result

    except requests.exceptions.RequestException as e:
        raise Exception(f"Network Error during Coze upload: {str(e)}")


# ───────────────────────── 流式对话接口 ─────────────────────────
@router.post("/chat", summary="Coze 流式对话（可选附件）")
async def coze_stream_chat(
    content: str = Form(..., description="用户消息内容"),
    file_ids: Optional[str] = Form(
        None,
        description=(
            "可选，Coze 文件 ID 列表，多个 ID 用英文逗号分隔。"
            "可通过 /coze/upload 接口上传文件后获取。"
            "示例：736949598110202001,736949598110202002"
        ),
    ),
):
    """
    Coze 流式对话接口（SSE）

    - **content**：对话内容（必填）
    - **file_ids**：Coze 文件 ID，逗号分隔（可选）。每个 file_id 对应一条 MessageObjectString 文件消息。

    返回 `text/event-stream`，每行格式为 `data: <json>\\n\\n`，事件类型：
    - `{"type": "chunk", "text": "..."}` — 流式文本片段
    - `{"type": "done", "token_count": 123}` — 对话结束
    - `{"type": "error", "message": "..."}` — 发生错误
    """
    # 构造 additional_messages
    additional_messages: List[Any] = []

    if file_ids:
        # 有文件时：文本 + 文件放在同一个 build_user_question_objects 里
        # 参考官方示例 chat_multimode_stream.py
        ids = [fid.strip() for fid in file_ids.split(",") if fid.strip()]
        objects = [MessageObjectString.build_text(content)]
        for fid in ids:
            objects.append(MessageObjectString.build_file(file_id=fid))
        additional_messages.append(
            Message.build_user_question_objects(objects=objects)
        )
        logger.info("[coze_chat] 附加文件消息 %d 个 file_ids: %s", len(ids), ids)
    else:
        # 纯文本消息
        additional_messages.append(
            Message.build_user_question_text(content=content)
        )

    queue: asyncio.Queue = asyncio.Queue()

    def stream_task():
        """在线程池中执行同步的 Coze 流式调用，结果放入队列"""
        try:
            for event in coze.chat.stream(
                bot_id=_BOT_ID,
                user_id=_USER_ID,
                additional_messages=additional_messages,
            ):
                logger.info("[coze_chat] event=%s", event.event)

                if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                    msg = event.message
                    # 直接看 _raw_response 里的原始数据
                    raw_body = ""
                    if hasattr(event, '_raw_response') and event._raw_response:
                        try:
                            raw_body = event._raw_response.text[:500]
                        except:
                            raw_body = "read failed"
                    logger.info(
                        "[coze_chat] DELTA raw=%s", raw_body
                    )
                    logger.info(
                        "[coze_chat] DELTA type=%s content_type=%s content=%s reasoning=%s",
                        msg.type, msg.content_type,
                        repr(msg.content[:200]) if msg.content else None,
                        repr(msg.reasoning_content[:200]) if msg.reasoning_content else None,
                    )
                    chunk_text = msg.content or msg.reasoning_content or ""
                    queue.put_nowait(
                        json.dumps({"type": "chunk", "text": chunk_text}, ensure_ascii=False)
                    )

                elif event.event == ChatEventType.CONVERSATION_MESSAGE_COMPLETED:
                    msg = event.message
                    logger.info(
                        "[coze_chat] MESSAGE_COMPLETED type=%s content_type=%s content=%s",
                        msg.type, msg.content_type, repr(msg.content[:200]) if msg.content else None,
                    )
                    # Bot 最终回复走 ANSWER 类型，可能非流式地一次性返回
                    if msg.type == MessageType.ANSWER and msg.content:
                        queue.put_nowait(
                            json.dumps({"type": "chunk", "text": msg.content}, ensure_ascii=False)
                        )

                elif event.event == ChatEventType.UNKNOWN:
                    logger.info("[coze_chat] UNKNOWN raw=%s", repr(event.unknown) if hasattr(event, 'unknown') else "N/A")

                elif event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                    token_count = 0
                    if event.chat and event.chat.usage:
                        token_count = event.chat.usage.token_count or 0
                    logger.info("[coze_chat] CHAT_COMPLETED token_count=%d", token_count)
                    queue.put_nowait(
                        json.dumps({"type": "done", "token_count": token_count}, ensure_ascii=False)
                    )

                elif event.event == ChatEventType.CONVERSATION_CHAT_FAILED:
                    logger.error("[coze_chat] CHAT_FAILED chat=%s", event.chat.model_dump() if event.chat else None)
                    queue.put_nowait(
                        json.dumps({"type": "error", "message": "Coze chat failed"}, ensure_ascii=False)
                    )

        except Exception as exc:
            logger.exception("[coze_chat] 流式调用异常")
            queue.put_nowait(
                json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            )
        finally:
            queue.put_nowait(None)  # 哨兵：通知 generator 结束

    # 在事件循环的线程池中运行同步阻塞的 stream_task
    loop = asyncio.get_event_loop()
    runner = loop.run_in_executor(None, stream_task)

    async def event_generator():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            if not runner.done():
                runner.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ───────────────────────── 文件上传接口 ─────────────────────────
@router.post("/upload", summary="上传文件到 Coze，返回 file_id")
async def coze_upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
):
    """
    上传文件到 Coze 平台，返回 file_id。

    返回示例：
    ```json
    {
      "file_id": "736949598110202001",
      "file_name": "report.xlsx",
      "bytes": 152236
    }
    ```
    """
    try:
        result = upload_file_to_coze(file, _COZE_TOKEN)
        data = result.get("data", {})
        return {
            "file_id": data.get("id", ""),
            "file_name": data.get("file_name", ""),
            "bytes": data.get("bytes", 0),
        }
    except Exception as e:
        return {"error": str(e)}
