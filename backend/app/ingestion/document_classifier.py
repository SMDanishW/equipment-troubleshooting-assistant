import json

from app.config import settings
from app.llm.groq_client import GroqClient, LLMUnavailableError

DOCUMENT_TYPE_OPTIONS = {
    "operating_manual",
    "maintenance_guide",
    "error_code_reference",
    "reference_document",
}


def classify_document_type(pages: list[tuple[int, str]]) -> str:
    llm_result = _classify_with_llm(pages)
    if llm_result:
        return llm_result
    return _classify_with_keywords(pages)


def _classify_with_llm(pages: list[tuple[int, str]]) -> str | None:
    if not settings.groq_api_key:
        return None

    sample = "\n\n".join(f"Page {page}: {text[:1800]}" for page, text in pages[:8] if text.strip())[:9000]
    if not sample:
        return None

    messages = [
        {
            "role": "system",
            "content": (
                "Classify equipment PDF documents. Return only JSON with document_type set to one of: "
                "operating_manual, maintenance_guide, error_code_reference, reference_document."
            ),
        },
        {"role": "user", "content": sample},
    ]
    try:
        result = GroqClient().complete_json(messages=messages, temperature=0.0)
    except (LLMUnavailableError, json.JSONDecodeError, RuntimeError):
        return None

    document_type = str(result.get("document_type", "")).strip()
    if document_type in DOCUMENT_TYPE_OPTIONS:
        return document_type
    return None


def _classify_with_keywords(pages: list[tuple[int, str]]) -> str:
    text = " ".join(page_text.lower() for _, page_text in pages[:15])
    if any(term in text for term in ["error code", "error codes", "fault code", "troubleshooting"]):
        return "error_code_reference"
    if any(term in text for term in ["maintenance", "service interval", "cleaning", "annual maintenance"]):
        return "maintenance_guide"
    if any(term in text for term in ["operating manual", "operation", "installation", "user manual"]):
        return "operating_manual"
    return "reference_document"
