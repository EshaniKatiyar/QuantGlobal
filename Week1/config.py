from crewai import LLM

MOCK_USERS = {"admin": "alphahire2024", "eshani": "week1pass"}

def get_llm():
    return LLM(
        model="openai/llama-3.2-3b-instruct",  # LM Studio uses openai-compatible prefix
        base_url="http://127.0.0.1:1234/v1",   # LM Studio endpoint
        api_key="lm-studio",                    # any non-empty string works
        timeout=120,
        temperature=0.1,
        max_tokens=1024,
    )