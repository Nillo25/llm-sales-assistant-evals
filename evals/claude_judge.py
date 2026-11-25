"""Claude as the judge model behind DeepEval's metrics.

DeepEval asks its model for JSON that matches a Pydantic schema (claims,
verdicts, a score with a reason). Here that request goes to the Anthropic
Messages API with structured outputs, so the reply is decoded against the
schema instead of being parsed out of free text.

The assistant under test stays on OpenAI: it mirrors a production bot. Judging
it with a model from another vendor also avoids a judge that favours replies
written in its own style.
"""
import threading

from pydantic import BaseModel

try:  # DeepEval is only needed for judging; the rest of this module is plain Python.
    from deepeval.models import DeepEvalBaseLLM
except ImportError:  # pragma: no cover - judge extras not installed
    DeepEvalBaseLLM = object

# USD per million tokens (input, output), from the Anthropic price list, 2026-11.
# Thinking tokens are billed as output and are included in usage.output_tokens.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),  # prompts up to 100K tokens; judge prompts are far below that
}
# Server-side fallback on a policy decline. Claude Haiku 5.5 has none.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_NO_FALLBACK = ("claude-haiku-5-5",)


class JudgeRefusal(RuntimeError):
    """The model declined to grade; recorded as a failed judgment, never as a pass or fail."""


def is_claude(model: str) -> bool:
    return model.startswith("claude-")


class ClaudeJudge(DeepEvalBaseLLM):
    """A DeepEval model backed by Claude.

    effort controls how much the model thinks before it grades. Grading one
    short reply against a rubric is a small task, so "low" is the default;
    raise it if calibration shows the judge missing things.
    """

    def __init__(self, model: str = "claude-sonnet-5-5", effort: str = "low", client=None, max_tokens: int = 8000):
        if model not in PRICES:
            raise ValueError(f"unknown Claude judge model {model}; known: {', '.join(PRICES)}")
        self.model_id = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = client
        self._lock = threading.Lock()
        self.cost = 0.0
        self.input_tokens = 0
        self.output_tokens = 0
        super().__init__(model)

    # DeepEval interface ------------------------------------------------------------

    def load_model(self, *args, **kwargs):
        if self._client is None:
            import anthropic  # reads ANTHROPIC_API_KEY from the environment

            self._client = anthropic.Anthropic(max_retries=4, timeout=120.0)
        return self._client

    def get_model_name(self, *args, **kwargs) -> str:
        return self.model_id

    def generate(self, prompt: str, schema: type[BaseModel] | None = None):
        client = self.load_model()
        kwargs = dict(
            model=self.model_id,
            max_tokens=self.max_tokens,
            output_config={"effort": self.effort},
            messages=[{"role": "user", "content": prompt}],
        )
        if self.model_id not in _NO_FALLBACK:
            kwargs.update(betas=[_FALLBACK_BETA], fallbacks="default")
        if schema is not None:
            response = client.beta.messages.parse(output_format=schema, **kwargs)
        else:
            response = client.beta.messages.create(**kwargs)
        self._account(response.usage)
        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise JudgeRefusal(f"the judge declined to grade (category: {category})")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("the judge hit max_tokens before finishing its verdict")
        if schema is not None:
            if response.parsed_output is None:
                raise RuntimeError("the judge returned no parseable verdict")
            return response.parsed_output
        return "".join(block.text for block in response.content if block.type == "text")

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None):
        import asyncio

        return await asyncio.to_thread(self.generate, prompt, schema)

    # Cost ------------------------------------------------------------------------------

    def _account(self, usage) -> None:
        price_in, price_out = PRICES[self.model_id]
        tokens_in = (
            (getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        )
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        with self._lock:
            self.input_tokens += tokens_in
            self.output_tokens += tokens_out
            self.cost += (tokens_in * price_in + tokens_out * price_out) / 1_000_000
