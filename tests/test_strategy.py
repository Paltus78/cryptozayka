import json, pytest
from unittest.mock import AsyncMock, patch
from cryptozayka.core.strategy import analyze_project, Verdict

@pytest.mark.asyncio
async def test_analyze_project_green():
    async def fake_call(prompt):  # noqa: D401
        return json.dumps({"verdict": "green", "explanation": "Ok"}), 100
    with patch("cryptozayka.core.strategy._call_gpt", new=AsyncMock(side_effect=fake_call)):
        res = await analyze_project("LayerZero", "Cross-chain")
    assert res.verdict is Verdict.GREEN
    assert res.tokens == 100
