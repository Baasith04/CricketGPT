from app.ai.llm.client import generate_response
from app.ai.prompts.system_prompt import CRICKETGPT_SYSTEM_PROMPT

question = "Who won the first IPL match?"

prompt = f"""
{CRICKETGPT_SYSTEM_PROMPT}

User question:
{question}

No database records or retrieved documents have been provided.
"""

print(generate_response(prompt))