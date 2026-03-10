from __future__ import annotations

import json
from datetime import date

import pytest

from app.exporters.finetune_exporter import export_live_finetune_dataset


@pytest.mark.asyncio
async def test_demo_export_pipeline_creates_one_jsonl_row(tmp_path) -> None:
    async def fake_events_fetcher(limit: int):
        return [
            {
                "id": "evt-demo",
                "title": "Demo event",
                "participantCount": 12,
                "markets": [{"clobTokenIds": ["demo-token"]}],
            }
        ]

    async def fake_strategies_fetcher(events):
        return [
            {
                "event_id": "evt-demo",
                "signal": "hold",
                "confidence": 0.5,
                "expected_return_pct": 0.0,
                "rationale": "demo rationale",
            }
        ]

    async def fake_price_history_fetcher(market_id: str):
        return [{"timestamp": 1, "price": 0.5}, {"timestamp": 2, "price": 0.51}]

    output_path = await export_live_finetune_dataset(
        limit=5,
        output_dir=tmp_path,
        as_of=date(2026, 3, 10),
        events_fetcher=fake_events_fetcher,
        strategies_fetcher=fake_strategies_fetcher,
        price_history_fetcher=fake_price_history_fetcher,
    )

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][2]["role"] == "assistant"
