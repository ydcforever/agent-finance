from cozepy import ChatEventType, Coze, TokenAuth, Message, COZE_CN_BASE_URL

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

        