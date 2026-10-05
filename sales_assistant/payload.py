"""Builds a request body for the OpenAI Responses API."""
from sales_assistant.prompts import load_prompt

_CONTENT_TYPE_BY_ROLE = {"user": "input_text", "assistant": "output_text"}


def build_payload(
    question: str,
    faq_context: str,
    catalog_context: str,
    history: list[tuple[str, str]] | None = None,
    *,
    model: str,
    prompt_version: str = "v1",
) -> dict:
    """Assemble the request: system prompt with grounding context, dialog history, question.

    history holds earlier turns as (role, text) pairs, oldest first, where role
    is "user" or "assistant". It lets the assistant resolve follow-ups such as
    "what colors does it come in?".
    """
    system_text = f"{load_prompt(prompt_version)}\n\nFAQ:\n{faq_context}\n\nProduct catalog:\n{catalog_context}"
    messages = [{"role": "system", "content": [{"type": "input_text", "text": system_text}]}]

    for role, text in history or []:
        if role not in _CONTENT_TYPE_BY_ROLE:
            raise ValueError(f"Unsupported history role {role!r}; expected 'user' or 'assistant'")
        clean = (text or "").strip()
        if clean:
            messages.append({"role": role, "content": [{"type": _CONTENT_TYPE_BY_ROLE[role], "text": clean}]})

    messages.append({"role": "user", "content": [{"type": "input_text", "text": question}]})
    return {"model": model, "input": messages}
