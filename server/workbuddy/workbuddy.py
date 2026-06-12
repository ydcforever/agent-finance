# pip install codebuddy-cloud-agent-sdk
import asyncio
import io
import os
from typing import Optional, Union, IO
import base64
import pandas as pd

from cloud_agent_sdk import (
    CloudAgentClient, RuntimeCreateOptions,
    ManifestBuilder, PromptOptions,
)
from pydantic.fields import FieldInfo
from acp import PromptResponse
from acp.helpers import text_block, resource_block, embedded_text_resource

from acp.schema import (
    BlobResourceContents,
    EmbeddedResourceContentBlock,
    SessionNotification,
    TextContentBlock,
    Usage
)

# 修复 agent-client-protocol/ACP 返回 usage 时缺少 totalTokens 的兼容问题
# 这个问题源于当前库中 Usage.totalTokens 为必填字段，但部分 SDK 返回值只包含 inputTokens/outputTokens。
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



def build_message_with_excel(
    question: str,
    excel_source: Union[bytes, bytearray, IO[bytes]],
    filename: Optional[str] = None,
):
    """【直接注入上下文版本】
    在本地将 Excel 解析为 Markdown 文本，并将其与用户问题直接拼接注入上下文。
    """
    excel_name = filename or "financial_data.xlsx"
    markdown_content = ""

    # 1. 统一将输入转换为 pandas 可读取的字节流
    if isinstance(excel_source, (bytes, bytearray)):
        file_stream = io.BytesIO(excel_source)
    elif hasattr(excel_source, "read"):
        if hasattr(excel_source, "seek"):
            try:
                excel_source.seek(0)
            except Exception:
                pass
        raw = excel_source.read()
        # 确保是 bytes 格式
        bytes_data = raw.encode("utf-8") if isinstance(raw, str) else raw
        file_stream = io.BytesIO(bytes_data)
        if filename is None and hasattr(excel_source, "name"):
            excel_name = os.path.basename(getattr(excel_source, "name"))
    else:
        raise ValueError("excel_source must be bytes or a binary file-like object")

    # 2. 使用 pandas 读取 Excel 的所有工作表（Sheets），并转化为 Markdown 文本
    try:
        # read_excel(..., sheet_name=None) 会读取所有 sheet，返回一个字典 {sheet_name: dataframe}
        excel_sheets = pd.read_excel(file_stream, sheet_name=None)
        
        # 组装格式化文本
        markdown_content += f"以下是文件 [{excel_name}] 的内容结构：\n\n"
        for sheet_name, df in excel_sheets.items():
            markdown_content += f"### 工作表 (Sheet): {sheet_name}\n"
            # 转换为 Markdown 表格，空值填补为空字符串
            markdown_content += df.fillna("").to_markdown(index=False)
            markdown_content += "\n\n"
            
    except Exception as e:
        raise RuntimeError(f"解析 Excel 失败，请检查文件格式或是否安装 openpyxl 库。错误信息: {e}")

    # 3. 将解析出来的文本内容与用户提问拼接成一个纯文本的系统级/用户级上下文块
    full_prompt = (
        f"<uploaded_file name=\"{excel_name}\">\n"
        f"{markdown_content}"
        f"</uploaded_file>\n\n"
        f"请基于上方提供的文件内容，回答以下问题：\n"
        f"{question}"
    )

    print(f"✓ 已成功将 Excel [{excel_name}] 解析为纯文本并直接注入上下文提示词")
    
    # 返回纯文本内容块列表
    return [TextContentBlock(type="text", text=full_prompt)]


async def main():
    # 认证方式：通过 x-api-key 头传递
    client = CloudAgentClient(
        api_key="ck_fns0v3cj85c0.wJgHcpGwka0JXdp9wWiYb3SeLASXkrd24IJJtqjXc8M",
        source_app="formula-finance",  # 来源应用标识，用于 runtimes 可见性过滤
    )

    # 步骤 1：创建 Runtime（自动创建初始 Session）
    manifest = (
        ManifestBuilder()
        .id("agent_01KSSBM63DYZ563SPK088Y3YWW")
        .name("My Agent")
        .version("1.0")
        .build()
    )
    rt = await client.runtimes.create(
        RuntimeCreateOptions(runtime_name="demo", agent_manifest=manifest)
    )


    # 步骤 2：与 Agent 对话（流式输出）
    # ACP 协议文档：https://agentclientprotocol.com/get-started/introduction
    # Runtime 默认 Session ID 值与 Runtime ID 相同
    session = rt.sessions.default()

    question = "请分析这个 Excel 文件中公司的财务状况"
    agent_response = ""

    def on_chunk(n: SessionNotification) -> None:
        nonlocal agent_response
        u = n.update
        if u.session_update == "agent_message_chunk" and u.content.type == "text":
            agent_response += u.content.text
            print(u.content.text, end="", flush=True)

    # 方案 1: 仅发送文本
    # response = await session.prompt(question, PromptOptions(on_chunk=on_chunk))
    
    # 方案 2: 发送 Excel 文件
    # 这里演示文件流方式；`build_message_with_excel` 仅接收 bytes 或文件流对象。
    with open(r"d:\workspace\VS\agent\financial_data.xlsx", "rb") as excel_file:
      message_blocks = build_message_with_excel(
        question,
        excel_file,
        filename="financial_data.xlsx",
    )
    response = await session.prompt(message_blocks, PromptOptions(on_chunk=on_chunk))
    print("\n")                    # 换行
    print("Agent 回复:", agent_response)  # agent 回复的完整文本
    print("停止原因:", response.stop_reason)    # "end_turn"

    await client.aclose()

asyncio.run(main())