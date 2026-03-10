from app.api.events import fetch_ranked_events, rank_events


class StubGammaClient:
    def __init__(self, events: list[dict]):
        self.events = events
        self.last_limit: int | None = None

    async def get_events(self, *, limit: int = 100, order: str = "volume", ascending: bool = False):
        self.last_limit = limit
        return self.events


def test_rank_events_orders_by_participants_then_near_fifty() -> None:
    events = [
        {"id": "a", "numTraders": 20, "bestBid": 0.20},
        {"id": "b", "numTraders": 20, "bestBid": 0.49},
        {"id": "c", "numTraders": 100, "bestBid": 0.75},
    ]

    ranked = rank_events(events, minor_incident_max_traders=None)

    assert [event["id"] for event in ranked] == ["c", "b", "a"]
    assert ranked[1]["isNearFiftyProbability"] is True
    assert ranked[2]["isNearFiftyProbability"] is False


def test_rank_events_applies_minor_incident_filter() -> None:
    events = [
        {"id": "small", "numTraders": 100, "bestBid": 0.50},
        {"id": "large", "numTraders": 900, "bestBid": 0.50},
    ]

    ranked = rank_events(events, minor_incident_max_traders=500)

    assert [event["id"] for event in ranked] == ["small"]
    assert ranked[0]["participantCount"] == 100


def test_rank_events_extracts_probability_from_outcome_prices_string() -> None:
    events = [
        {
            "id": "outcomes-json",
            "numTraders": "10",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.52", "0.48"]',
        }
    ]

    ranked = rank_events(events, minor_incident_max_traders=None)

    assert ranked[0]["yesProbability"] == 0.52
    assert ranked[0]["isNearFiftyProbability"] is True


def test_rank_events_extracts_probability_from_nested_markets() -> None:
    events = [
        {
            "id": "nested-market",
            "numTraders": 25,
            "markets": [
                {
                    "outcomes": '["Yes", "No"]',
                    "outcomePrices": '["0.47", "0.53"]',
                }
            ],
        }
    ]

    ranked = rank_events(events, minor_incident_max_traders=None)

    assert ranked[0]["yesProbability"] == 0.47
    assert ranked[0]["isNearFiftyProbability"] is True


async def test_fetch_ranked_events_uses_gamma_client_and_ranks() -> None:
    stub = StubGammaClient(
        [
            {"id": "evt-1", "numTraders": 5, "bestBid": 0.50},
            {"id": "evt-2", "numTraders": 50, "bestBid": 0.20},
        ]
    )

    ranked = await fetch_ranked_events(limit=25, gamma_client=stub, minor_incident_max_traders=None)

    assert stub.last_limit == 25
    assert [event["id"] for event in ranked] == ["evt-2", "evt-1"]
