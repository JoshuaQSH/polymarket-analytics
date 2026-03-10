from __future__ import annotations

import json
from datetime import date

import pytest

from app.exporters.finetune_exporter import (
    build_finetune_record,
    export_live_finetune_dataset,
)


def _extract_embedded_json(text: str) -> dict[str, object]:
    return json.loads(text.split("\n", 1)[1])


def test_build_finetune_record_matches_expected_schema() -> None:
    event = {
        "id": "evt-123",
        "title": "Will it rain tomorrow?",
        "description": "Weather market",
        "participantCount": 42,
        "yesProbability": 0.51,
        "volume": 1234.5,
        "tags": ["weather", "daily"],
        "markets": [{"clobTokenIds": ["token-yes", "token-no"]}],
    }
    strategy = {
        "event_id": "evt-123",
        "signal": "buy_yes",
        "confidence": 0.72,
        "expected_return_pct": 4.5,
        "rationale": "Mean reversion edge",
    }
    history = [
        {"t": 1700000000, "p": 0.48},
        {"t": 1700086400, "p": 0.50},
        {"t": 1700172800, "p": 0.52},
    ]

    record = build_finetune_record(event, strategy, price_history=history)

    assert "messages" in record
    assert len(record["messages"]) == 3
    assert [message["role"] for message in record["messages"]] == ["system", "user", "assistant"]

    user_payload = _extract_embedded_json(record["messages"][1]["content"])
    assert user_payload["event_id"] == "evt-123"
    assert user_payload["title"] == "Will it rain tomorrow?"
    assert user_payload["num_traders"] == 42
    assert user_payload["tags"] == ["weather", "daily"]
    assert len(user_payload["probability_history_30d"]) == 3

    assistant_payload = json.loads(record["messages"][2]["content"])
    assert assistant_payload["signal"] == "buy_yes"
    assert assistant_payload["confidence"] == 0.72


@pytest.mark.asyncio
async def test_export_live_finetune_dataset_writes_jsonl(tmp_path) -> None:
    async def fake_events_fetcher(limit: int) -> list[dict[str, object]]:
        assert limit == 10
        return [
            {
                "id": "evt-1",
                "title": "Minor event",
                "participantCount": 123,
                "markets": [{"clobTokenIds": ["token-1", "token-2"]}],
                "tags": [{"name": "politics"}],
            }
        ]

    async def fake_strategies_fetcher(events) -> list[dict[str, object]]:
        assert len(events) == 1
        return [
            {
                "event_id": "evt-1",
                "signal": "hold",
                "confidence": 0.55,
                "expected_return_pct": 1.2,
                "rationale": "No clear edge",
            }
        ]

    async def fake_price_history_fetcher(market_id: str) -> list[dict[str, float | int]]:
        assert market_id == "token-1"
        return [{"timestamp": i, "price": 0.4 + (i * 0.001)} for i in range(1, 36)]

    output_path = await export_live_finetune_dataset(
        limit=10,
        output_dir=tmp_path,
        as_of=date(2026, 3, 10),
        events_fetcher=fake_events_fetcher,
        strategies_fetcher=fake_strategies_fetcher,
        price_history_fetcher=fake_price_history_fetcher,
    )

    assert output_path.name == "events_20260310.jsonl"
    assert output_path.exists()

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    user_payload = _extract_embedded_json(record["messages"][1]["content"])
    assert user_payload["market_id"] == "token-1"
    assert len(user_payload["probability_history_30d"]) == 30
