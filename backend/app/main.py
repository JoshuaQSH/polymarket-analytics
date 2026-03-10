"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.events import router as events_router
from app.api.llm_strategy import router as llm_router
from app.api.prices import router as prices_router
from app.api.strategies import router as strategies_router


def create_app() -> FastAPI:
    app = FastAPI(title="Polymarket Analytics API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(events_router)
    app.include_router(prices_router)
    app.include_router(strategies_router)
    app.include_router(llm_router)
    return app


app = create_app()
