from app.ai.query_router.router import route_question

questions = [
    "Who won match 335982?",
    "Tell me the result of match 335982",
    "What was the winning margin in match 335982?",
    "Who is the highest run scorer in IPL?",
]

for question in questions:
    print(f"\nQuestion: {question}")
    print("Answer:", route_question(question))