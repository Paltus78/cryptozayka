import pytest

@pytest.fixture(autouse=True)
def no_real_gpt(monkeypatch):
    """Mock chat completion to avoid external OpenAI calls."""
    from cryptozayka.core import gpt_client

    async def _fake_chat(messages, *, model="gpt-4o-mini", **kwargs):
        # simple heuristic reply based on project mention
        user_content = " ".join(m["content"] for m in messages if m["role"] == "user").lower()
        if "scamchain" in user_content:
            return "Это откровенный скам. Не участвовать."
        return "Проект выглядит перспективным, риски умеренные. Рекомендуется участвовать."

    monkeypatch.setattr(gpt_client, "chat", _fake_chat)
