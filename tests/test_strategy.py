import os

os.environ.update(
    {
        "ETH_RPC_URL": "https://dummy.rpc",
        "OPENAI_API_KEY": "sk-test",
        "TELEGRAM_ADMIN_CHAT": "0",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
    }
)

import json
import pytest
from unittest.mock import AsyncMock, patch

from cryptozayka.core.strategy import analyze_project, Verdict


@pytest.mark.asyncio
async def test_analyze_project_green():
    async def fake_call(_: str):
        return json.dumps({"verdict": "green", "explanation": "Ok"}), 100

    with patch(
        "cryptozayka.core.strategy._call_gpt",
        new=AsyncMock(side_effect=fake_call),
    ):
        res = await analyze_project("LayerZero", "Cross-chain")

    assert res.verdict is Verdict.GREEN
    assert res.tokens == 100
