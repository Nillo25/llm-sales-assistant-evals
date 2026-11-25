"""Thin wrappers over the model APIs: OpenAI Responses and Anthropic Messages.

The payload is built once, in the Responses API shape (sales_assistant.payload);
AnthropicResponder translates it, so prompts, retrieval and history are
identical whichever model answers.
"""
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


class AnthropicResponder:
    """Sends the same payload to the Anthropic Messages API.

    The system message becomes the top-level system prompt and the dialog maps
    one to one. Current Claude models think adaptively; effort sets how much,
    and "low" fits a chat reply. They reject sampling parameters, so a payload
    with a temperature is refused here rather than at the API.

    A safety refusal (stop_reason "refusal") is raised as an error: the
    customer would get no reply, and the run must show that apart from a bad
    answer.
    """

    def __init__(self, client=None, effort: str = "low", max_tokens: int = 4000, timeout_s: float = 60.0, max_retries: int = 3):
        if client is None:
            import anthropic  # reads ANTHROPIC_API_KEY from the environment

            client = anthropic.Anthropic(timeout=timeout_s, max_retries=max_retries)
        self._client = client
        self.effort = effort
        self.max_tokens = max_tokens

    @staticmethod
    def to_messages(payload: dict) -> dict:
        if "temperature" in payload:
            raise ValueError("Claude models take no temperature; leave --temperature unset")
        system, messages = "", []
        for item in payload["input"]:
            text = "".join(part["text"] for part in item["content"])
            if item["role"] == "system":
                system = text
            else:
                messages.append({"role": item["role"], "content": text})
        return {"model": payload["model"], "system": system, "messages": messages}

    def __call__(self, payload: dict) -> ModelReply:
        request = self.to_messages(payload)
        started = time.perf_counter()
        response = self._client.messages.create(
            max_tokens=self.max_tokens, output_config={"effort": self.effort}, **request
        )
        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise RuntimeError(f"refusal: the model declined to answer (category: {category})")
        usage = response.usage
        return ModelReply(
            raw="".join(block.text for block in response.content if block.type == "text"),
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            latency_s=time.perf_counter() - started,
        )


def responder_for(model: str, **kwargs) -> Responder:
    """Claude models go to Anthropic, everything else to OpenAI."""
    return AnthropicResponder(**kwargs) if model.startswith("claude-") else OpenAIResponder()
