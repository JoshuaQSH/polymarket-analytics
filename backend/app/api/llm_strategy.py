"""LLM inference API routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.strategies.llm_strategy import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_REMOTE_MODEL,
    LlmInferenceError,
    infer_with_cache,
)

router = APIRouter(prefix="/llm", tags=["llm"])


class LlmInferRequest(BaseModel):
    prompt: str = Field(min_length=1)
    model: str | None = None
    api_key: str | None = None
    use_cache: bool = True


class LlmInferResponse(BaseModel):
    provider: Literal["local", "remote", "claude"]
    model: str
    content: str
    cached: bool


@router.post("/infer/local", response_model=LlmInferResponse)
async def infer_local(payload: LlmInferRequest) -> LlmInferResponse:
    """Run local-model inference through an Ollama-compatible server."""
    model = payload.model or DEFAULT_LOCAL_MODEL
    try:
        content, cached = await infer_with_cache(
            payload.prompt,
            provider="local",
            model=model,
            ttl_seconds=3600 if payload.use_cache else 0,
        )
    except LlmInferenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LlmInferResponse(provider="local", model=model, content=content, cached=cached)


@router.post("/infer/remote", response_model=LlmInferResponse)
async def infer_remote(payload: LlmInferRequest) -> LlmInferResponse:
    """Run remote-model inference through an OpenAI-compatible API."""
    model = payload.model or DEFAULT_REMOTE_MODEL
    try:
        content, cached = await infer_with_cache(
            payload.prompt,
            provider="remote",
            model=model,
            api_key=payload.api_key,
            ttl_seconds=3600 if payload.use_cache else 0,
        )
    except LlmInferenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LlmInferResponse(provider="remote", model=model, content=content, cached=cached)


@router.post("/infer/claude", response_model=LlmInferResponse)
async def infer_claude(payload: LlmInferRequest) -> LlmInferResponse:
    """Run Claude inference through the Anthropic Messages API."""
    model = payload.model or DEFAULT_CLAUDE_MODEL
    try:
        content, cached = await infer_with_cache(
            payload.prompt,
            provider="claude",
            model=model,
            api_key=payload.api_key,
            ttl_seconds=3600 if payload.use_cache else 0,
        )
    except LlmInferenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LlmInferResponse(provider="claude", model=model, content=content, cached=cached)
