# -*- coding: utf-8 -*-
"""
Coze AI 流式对话模块
- upload_file_to_coze: 上传文件到 Coze，返回 file_id
- router: FastAPI 路由，提供 /coze/chat 流式接口
- 当上传 Excel 文件时，自动解析并入库
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

import requests
from cozepy import (
    COZE_CN_BASE_URL,
    ChatEventType,
    Coze,
    Message,
    MessageObjectString,
    MessageRole,
    MessageType,
    TokenAuth,
)
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from server.service.excel_import_service import import_uploaded_file_to_db
from server.util.database import get_db

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


# ───────────────────────── 流式对话接口（合并上传） ─────────────────────────
@router.post("/chat", summary="Coze 流式对话（文件流直传，Excel 自动解析入库）")
async def coze_stream_chat(
    content: str = Form(..., description="用户消息内容"),
    files: List[UploadFile] = File(default=[], description="要上传的文件列表，自动上传到 Coze 并附加到对话"),
    db: Session = Depends(get_db),
):
    """
    Coze 流式对话接口（SSE）

    - **content**：对话内容（必填）
    - **files**：文件列表（可选），后端自动上传到 Coze 获取 file_id 后附加到对话
    - **Excel 文件（.xlsx）**：上传后自动解析并入库到对应业务表

    返回 `text/event-stream`，事件类型：
    - `{"type": "answer_chunk", "text": "..."}` — 流式回答片段
    - `{"type": "reasoning_chunk", "text": "..."}` — 思考过程片段
    - `{"type": "done", "token_count": 123}` — 对话结束
    - `{"type": "error", "message": "..."}` — 发生错误
    """
    # ── 第一步：上传文件，收集 file_id ──
    file_ids: List[str] = []
    upload_errors: List[dict] = []

    for f in files:
        # 读取文件内容（后面可能用于 Excel 解析）
        file_bytes = await f.read()
        await f.seek(0)  # 重置指针，供 Coze 上传使用

        # ── Excel 文件：先解析入库 ──
        if f.filename and f.filename.lower().endswith(".xlsx"):
            try:
                import_uploaded_file_to_db(file_bytes, f.filename, db)
                logger.info("[coze_chat] Excel 入库完成: %s", f.filename)
            except Exception as e:
                logger.exception("[coze_chat] Excel 入库异常: %s", f.filename)

        # ── 上传到 Coze ──
        try:
            result = upload_file_to_coze(f, _COZE_TOKEN)
            data = result.get("data", {})
            fid = data.get("id", "")
            if fid:
                file_ids.append(fid)
                logger.info("[coze_chat] 上传成功: %s → %s", f.filename, fid)
            else:
                upload_errors.append({"file_name": f.filename, "error": "Coze 未返回 file_id"})
        except Exception as e:
            upload_errors.append({"file_name": f.filename, "error": str(e)})
            logger.error("[coze_chat] 上传失败: %s, error=%s", f.filename, str(e))

    # 如果上传全部失败且没有任何 file_id，返回错误
    if upload_errors and not file_ids:
        return JSONResponse(
            content={"error": "所有文件上传失败", "details": upload_errors},
            status_code=400,
        )

    # ── 第二步：构造 additional_messages ──
    additional_messages: List[Any] = []

    if file_ids:
        objects = [MessageObjectString.build_text(content)]
        for fid in file_ids:
            objects.append(MessageObjectString.build_file(file_id=fid))
        additional_messages.append(
            Message.build_user_question_objects(objects=objects)
        )
        logger.info("[coze_chat] 附加 %d 个文件: %s", len(file_ids), file_ids)
    else:
        additional_messages.append(
            Message.build_user_question_text(content=content)
        )

    # ── 第三步：流式对话 ──
    queue: asyncio.Queue = asyncio.Queue()

    def stream_task():
        try:
            for event in coze.chat.stream(
                bot_id=_BOT_ID,
                user_id=_USER_ID,
                additional_messages=additional_messages,
            ):
                if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                    msg = event.message
                    if msg.role == MessageRole.ASSISTANT and msg.type == MessageType.ANSWER:
                        text = msg.content or ""
                        queue.put_nowait(
                            json.dumps({"type": "answer_chunk", "text": text}, ensure_ascii=False)
                        )
                    elif msg.reasoning_content:
                        queue.put_nowait(
                            json.dumps({"type": "reasoning_chunk", "text": msg.reasoning_content}, ensure_ascii=False)
                        )

                elif event.event == ChatEventType.CONVERSATION_MESSAGE_COMPLETED:
                    msg = event.message
                    if msg.type == MessageType.ANSWER and msg.content:
                        queue.put_nowait(
                            json.dumps({"type": "answer_completed", "text": msg.content}, ensure_ascii=False)
                        )
                    elif msg.reasoning_content:
                        queue.put_nowait(
                            json.dumps({"type": "reasoning_completed", "text": msg.reasoning_content}, ensure_ascii=False)
                        )

                elif event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                    token_count = 0
                    if event.chat and event.chat.usage:
                        token_count = event.chat.usage.token_count or 0
                    # 上传警告作为 info 附带
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
            queue.put_nowait(None)

    loop = asyncio.get_event_loop()
    runner = loop.run_in_executor(None, stream_task)

    async def event_generator():
        try:
            # 发送上传结果（如果有文件）
            if files:
                uploaded_info = {
                    "type": "upload_result",
                    "uploaded": [{"file_name": f.filename, "file_id": fid} for f, fid in zip(files, file_ids)],
                    "errors": upload_errors,
                }
                yield f"data: {json.dumps(uploaded_info, ensure_ascii=False)}\n\n"

            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {item}\n\n"
        finally:
            if not runner.done():
                runner.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ───────────────────────── 文件上传接口（保留兼容） ─────────────────────────
@router.post("/upload", summary="上传文件到 Coze，返回 file_id（独立上传接口，兼容旧版）")
async def coze_upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
):
    """
    独立上传文件到 Coze 平台，返回 file_id。

    如果只需要一次对话，建议直接用 /chat 接口传文件，无需分两步。
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
