# test_llm.py
from langchain_mistralai import ChatMistralAI
from langchain.schema import SystemMessage, HumanMessage

chat = ChatMistralAI(model="mistral-small", temperature=0.0)

messages = [
    SystemMessage(content="Return only: '--- a/file.py\\n+++ b/file.py\\n@@\\n-foo\\n+bar'"),
    HumanMessage(content="OK")
]
print(chat.invoke(messages).content)
