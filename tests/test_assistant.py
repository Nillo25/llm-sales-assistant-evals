from types import SimpleNamespace

from sales_assistant.assistant import answer
from sales_assistant.catalog import load_catalog, load_faq
from sales_assistant.client import ModelReply, OpenAIResponder

CATALOG = load_catalog()
FAQ = load_faq()


class RecordingResponder:
    def __init__(self, raw: str):
        self.raw = raw
        self.payloads = []

    def __call__(self, payload: dict) -> ModelReply:
        self.payloads.append(payload)
        return ModelReply(raw=self.raw, input_tokens=100, output_tokens=20, latency_s=0.5)


def test_answer_strips_the_marker_and_flags_non_answers():
    turn = answer("Weather?", (), products=CATALOG, faq=FAQ, responder=RecordingResponder("NO_ANSWER\nSorry."), model="m")
    assert (turn.text, turn.is_non_answer) == ("Sorry.", True)


def test_answer_sends_retrieved_context_history_and_model():
    responder = RecordingResponder("It has a kickstand.")
    history = (("user", "Hi"), ("assistant", "Hello!"))
    turn = answer(
        "Does the 10K power bank have a stand?",
        history,
        products=CATALOG,
        faq=FAQ,
        responder=responder,
        model="gpt-test",
        prompt_version="v1",
    )
    payload = responder.payloads[0]
    assert payload["model"] == "gpt-test"
    assert [m["role"] for m in payload["input"]] == ["system", "user", "assistant", "user"]
    assert "AW-PB-10M" in turn.context
    assert turn.retrieved[0] == "AW-PB-10M"
    assert turn.context in payload["input"][0]["content"][0]["text"]
    assert turn.reply.input_tokens == 100


def fake_sdk(output_text: str, input_tokens: int = 11, output_tokens: int = 7):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
        return SimpleNamespace(output_text=output_text, usage=usage)

    return SimpleNamespace(responses=SimpleNamespace(create=create)), calls


def test_openai_responder_passes_the_payload_and_reads_text_and_usage():
    sdk, calls = fake_sdk("Hello!")
    reply = OpenAIResponder(client=sdk)({"model": "m", "input": []})
    assert calls == [{"model": "m", "input": []}]
    assert (reply.raw, reply.input_tokens, reply.output_tokens) == ("Hello!", 11, 7)
    assert reply.latency_s >= 0


def test_openai_responder_treats_missing_usage_as_zero():
    sdk, _ = fake_sdk("Hi")
    sdk.responses.create = lambda **kw: SimpleNamespace(output_text="Hi", usage=None)
    reply = OpenAIResponder(client=sdk)({"model": "m", "input": []})
    assert (reply.input_tokens, reply.output_tokens) == (0, 0)
