import httpx
import pytest
import respx

from app.api.prices import fetch_price_history, normalize_price_history
from app.services.clob_client import ClobClient, ClobClientError


@pytest.mark.asyncio
@respx.mock
async def test_get_price_history_success() -> None:
    mocked = respx.get("https://clob.polymarket.com/prices-history").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"t": 1700000000, "p": 0.48},
                {"t": 1700086400, "p": 0.51},
            ],
        )
    )

    async with ClobClient() as client:
        history = await client.get_price_history("condition-123", interval="1d")

    assert mocked.called
    assert len(history) == 2
    request = mocked.calls[0].request
    assert request.url.params["market"] == "condition-123"
    assert request.url.params["interval"] == "1d"


@pytest.mark.asyncio
@respx.mock
async def test_get_price_history_http_error_raises_clob_client_error() -> None:
    respx.get("https://clob.polymarket.com/prices-history").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )

    async with ClobClient() as client:
        with pytest.raises(ClobClientError, match="CLOB request failed"):
            await client.get_price_history("missing-condition")


@pytest.mark.asyncio
@respx.mock
async def test_get_price_history_accepts_history_object_shape() -> None:
    mocked = respx.get("https://clob.polymarket.com/prices-history").mock(
        return_value=httpx.Response(
            200,
            json={"history": [{"t": 1700000000, "p": 0.48}]},
        )
    )

    async with ClobClient() as client:
        history = await client.get_price_history("condition-123")

    assert mocked.called
    assert history == [{"t": 1700000000, "p": 0.48}]


def test_normalize_price_history_sorts_and_filters_invalid_points() -> None:
    raw = [
        {"t": "1700086400", "p": "0.51"},
        {"timestamp": 1700000000, "price": 0.48},
        {"time": 1700172800, "value": 0.55},
        {"t": "bad", "p": 0.6},
        {"t": 1700259200},
    ]

    normalized = normalize_price_history(raw)

    assert normalized == [
        {"timestamp": 1700000000, "price": 0.48},
        {"timestamp": 1700086400, "price": 0.51},
        {"timestamp": 1700172800, "price": 0.55},
    ]


class StubClobClient:
    def __init__(self, history: list[dict[str, object]]) -> None:
        self.history = history
        self.calls: list[tuple[str, str]] = []

    async def get_price_history(
        self,
        condition_id: str,
        *,
        interval: str = "1d",
    ) -> list[dict[str, object]]:
        self.calls.append((condition_id, interval))
        return self.history


@pytest.mark.asyncio
async def test_fetch_price_history_uses_injected_client_and_normalizes() -> None:
    stub = StubClobClient(
        history=[
            {"t": 3, "p": 0.53},
            {"t": 1, "p": 0.49},
            {"t": 2, "p": 0.51},
        ]
    )

    history = await fetch_price_history(
        "condition-xyz",
        interval="1h",
        clob_client=stub,  # type: ignore[arg-type]
    )

    assert stub.calls == [("condition-xyz", "1h")]
    assert history == [
        {"timestamp": 1, "price": 0.49},
        {"timestamp": 2, "price": 0.51},
        {"timestamp": 3, "price": 0.53},
    ]
