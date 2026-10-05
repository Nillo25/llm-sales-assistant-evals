"""Thin wrapper over the OpenAI Responses API."""
import time
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelReply:
    raw: str
    input_tokens: int
    output_tokens: int
    latency_s: float


class Responder(Protocol):
    def __call__(self, payload: dict) -> ModelReply: ...


class OpenAIResponder:
    """Sends a payload to the Responses API.

    API errors are raised, not swallowed: an eval run must tell "the model
    answered badly" apart from "the request failed".
    """

    def __init__(self, client=None, timeout_s: float = 60.0, max_retries: int = 3):
        if client is None:
            from openai import OpenAI  # reads OPENAI_API_KEY from the environment

            client = OpenAI(timeout=timeout_s, max_retries=max_retries)
        self._client = client

    def __call__(self, payload: dict) -> ModelReply:
        started = time.perf_counter()
        response = self._client.responses.create(**payload)
        usage = response.usage
        return ModelReply(
            raw=response.output_text or "",
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            latency_s=time.perf_counter() - started,
        )
