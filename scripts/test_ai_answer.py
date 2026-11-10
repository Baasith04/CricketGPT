from app.ai.answer_service import answer_match_question

answer = answer_match_question(
    335982,
    "Who won this match?"
)

print("\n========== CRICKETGPT ANSWER ==========")
print(answer)   