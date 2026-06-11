from cozepy import ChatEventType, Coze, TokenAuth, Message, COZE_CN_BASE_URL


import requests
from fastapi import UploadFile
from typing import Dict, Any

def upload_file_to_coze(file: UploadFile, token: str) -> Dict[str, Any]:
    """
    将前端上传的文件流转发至 Coze 平台

    Args:
        file (UploadFile): FastAPI 接收到的文件对象 (包含 .filename, .file, .content_type)
        token (str): Coze API 鉴权 Token (如 cztei_...)

    Returns:
        dict: Coze 接口返回的 JSON 数据 (包含 id, file_name, bytes 等字段)

    Raises:
        Exception: 如果网络请求失败或 Coze 返回错误码
    """
    url = "https://api.coze.cn/v1/files/upload"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # 构造 multipart/form-data 格式
    # file.file 是类文件对象 (SpooledTemporaryFile)，可以直接被 requests 读取
    files_payload = {
        'file': (file.filename, file.file, file.content_type or 'application/octet-stream')
    }

    try:
        response = requests.post(url, headers=headers, files=files_payload, timeout=30)
        response.raise_for_status()  # 如果 HTTP 状态码不是 200，抛出异常

        result = response.json()

        # 检查 Coze 业务层面的状态码 (code != 0 表示业务失败)
        if result.get("code") != 0:
            raise Exception(f"Coze Upload Failed: {result.get('msg')}")

        return result

    except requests.exceptions.RequestException as e:
        # 处理网络超时、连接错误等
        raise Exception(f"Network Error during Coze upload: {str(e)}")
    
coze = Coze(
    auth=TokenAuth(token="pat_drMX4Qduj6NNcrU4WaOU4Pcp4wi9NWhHaetLW1ud3h8Va2z9RelLUrLBIYiKqx5x"),
    base_url=COZE_CN_BASE_URL,
)

for event in coze.chat.stream(
    bot_id="7643694491697922082",
    user_id="3137323286157770",
    additional_messages=[
        Message.build_user_question_text(content="分析一下上海氢枫能源科技有限公司的财务状况"),
    ]
):
    if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
        print(event.message.content, end="", flush=True)

    if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
        print()
        print("token usage:", event.chat.usage.token_count)

        