import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def _patch_env_for_settings():
    """
    Подставляет минимальный набор переменных, чтобы Settings() валидировался
    во время тестов. Работает автоматически для всей тест-сессии.
    """
    orig = os.environ.copy()
    os.environ.setdefault("ETH_RPC_URL", "https://dummy.rpc")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test")
    os.environ.setdefault("TELEGRAM_ADMIN_CHAT", "0")

    yield
    # восстанавливаем окружение
    os.environ.clear()
    os.environ.update(orig)
