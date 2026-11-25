"""One assistant turn: retrieve context, call the model, parse the reply."""
from dataclasses import dataclass

from sales_assistant.catalog import FaqItem, Product
from sales_assistant.client import ModelReply, Responder
from sales_assistant.guard import guard_reply
from sales_assistant.marker import split_no_answer_marker
from sales_assistant.payload import build_payload
from sales_assistant.prompts import load_prompt
from sales_assistant.retriever import build_context


@dataclass(frozen=True)
class Turn:
    text: str
    is_non_answer: bool
    context: str
    retrieved: tuple[str, ...]
    reply: ModelReply
    guard_actions: tuple[str, ...] = ()


def answer(
    question: str,
    history: tuple[tuple[str, str], ...],
    *,
    products: list[Product],
    faq: list[FaqItem],
    responder: Responder,
    model: str,
    prompt_version: str = "v1",
    temperature: float | None = None,
    guard: bool = False,
) -> Turn:
    """One turn. With guard=True the reply is checked in code before it is returned (sales_assistant.guard)."""
    context = build_context(question, products, faq, history=tuple(history))
    payload = build_payload(
        question, context.faq, context.catalog, list(history), model=model, prompt_version=prompt_version,
        temperature=temperature,
    )
    reply = responder(payload)
    text, is_non_answer = split_no_answer_marker(reply.raw)
    actions: tuple[str, ...] = ()
    if guard:
        checked = guard_reply(text, system_prompt=load_prompt(prompt_version), context=context.as_text(), question=question)
        text, actions = checked.text, checked.actions
    return Turn(
        text=text,
        is_non_answer=is_non_answer,
        context=context.as_text(),
        retrieved=context.skus,
        reply=reply,
        guard_actions=actions,
    )
