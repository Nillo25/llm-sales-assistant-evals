"""The Claude responder, with a fake Anthropic client."""
from types import SimpleNamespace

import pytest

from sales_assistant.client import AnthropicResponder, responder_for
from sales_assistant.payload import build_payload


class FakeMessages:
    def __init__(self, stop_reason="end_turn"):
        self.stop_reason = stop_reason
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            stop_details=SimpleNamespace(category="cyber"),
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="It costs $34.99.")],
            usage=SimpleNamespace(input_tokens=900, output_tokens=40),
        )


def payload():
    history = [("user", "Hi"), ("assistant", "Hello! How can I help?")]
    return build_payload("How much is the Slim 5K?", "faq", "catalog", history, model="claude-haiku-5-5")


def test_payload_maps_to_system_prompt_and_dialog():
    request = AnthropicResponder.to_messages(payload())
    assert request["model"] == "claude-haiku-5-5"
    assert request["system"].endswith("Product catalog:\ncatalog")
    assert request["messages"] == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! How can I help?"},
        {"role": "user", "content": "How much is the Slim 5K?"},
    ]


def test_reply_text_skips_thinking_blocks_and_keeps_usage():
    messages = FakeMessages()
    reply = AnthropicResponder(client=SimpleNamespace(messages=messages))(payload())
    assert reply.raw == "It costs $34.99."
    assert (reply.input_tokens, reply.output_tokens) == (900, 40)
    assert messages.request["output_config"] == {"effort": "low"}
    assert "temperature" not in messages.request and "thinking" not in messages.request


def test_a_safety_refusal_is_an_error_not_an_answer():
    responder = AnthropicResponder(client=SimpleNamespace(messages=FakeMessages(stop_reason="refusal")))
    with pytest.raises(RuntimeError, match="refusal"):
        responder(payload())


def test_temperature_is_refused_for_claude():
    with pytest.raises(ValueError, match="temperature"):
        AnthropicResponder.to_messages({**payload(), "temperature": 0.2})


def test_claude_models_get_the_anthropic_responder():
    assert isinstance(responder_for("claude-haiku-5-5", client=object()), AnthropicResponder)
