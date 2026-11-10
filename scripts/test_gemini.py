from app.ai.llm.client import generate_response


if __name__ == "__main__":
    answer = generate_response(
        "Explain what IPL cricket is in three sentences."
    )

    print("\n========== GEMINI RESPONSE ==========")
    print(answer)