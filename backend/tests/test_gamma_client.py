import httpx
import pytest
import respx

from app.services.gamma_client import GammaClient, GammaClientError


@pytest.mark.asyncio
@respx.mock
async def test_get_events_success() -> None:
    mocked = respx.get("https://gamma-api.polymarket.com/events").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "event-1", "title": "Will X happen?"},
                {"id": "event-2", "title": "Will Y happen?"},
            ],
        )
    )

    async with GammaClient() as client:
        events = await client.get_events(limit=2)

    assert mocked.called
    assert len(events) == 2
    request = mocked.calls[0].request
    assert request.url.params["limit"] == "2"
    assert request.url.params["order"] == "volume"
    assert request.url.params["ascending"] == "false"
    assert request.url.params["closed"] == "false"


@pytest.mark.asyncio
@respx.mock
async def test_get_markets_success() -> None:
    mocked = respx.get("https://gamma-api.polymarket.com/markets").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": "mkt-1", "event_id": "evt-1", "conditionId": "cond-1"}],
        )
    )

    async with GammaClient() as client:
        markets = await client.get_markets("evt-1")

    assert mocked.called
    assert markets[0]["conditionId"] == "cond-1"
    request = mocked.calls[0].request
    assert request.url.params["event_id"] == "evt-1"


@pytest.mark.asyncio
@respx.mock
async def test_get_events_http_error_raises_gamma_client_error() -> None:
    respx.get("https://gamma-api.polymarket.com/events").mock(
        return_value=httpx.Response(500, json={"error": "server"})
    )

    async with GammaClient() as client:
        with pytest.raises(GammaClientError, match="Gamma request failed"):
            await client.get_events()
