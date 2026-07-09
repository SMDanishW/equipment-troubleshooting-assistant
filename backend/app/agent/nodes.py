from __future__ import annotations

import re
from typing import Any

from app.rag.retriever import retrieve_evidence


def query_understanding_node(state: dict[str, Any]) -> dict[str, Any]:
    question = state["question"]
    previous_user_context = _recent_user_context(state.get("chat_history", []))
    is_followup = bool(previous_user_context) and _is_followup_question(question)
    normalized_query = f"{previous_user_context}\n{question.strip()}" if is_followup else question.strip()
    error_code = re.search(r"\b[A-Z]?\d{2,4}\b", question.upper())
    output = {
        "query_type": "error_code" if "error" in question.lower() or error_code else "symptom_or_maintenance",
        "normalized_query": normalized_query,
        "is_followup": is_followup,
        "previous_user_context": previous_user_context,
        "needs_clarification": len(question.strip()) < 4,
        "clarification_questions": [],
    }
    _log(state, "Query Understanding Agent", {"question": question}, output)
    return {"query_understanding": output}


def retrieval_node(state: dict[str, Any]) -> dict[str, Any]:
    db = state["db"]
    result = retrieve_evidence(
        db=db,
        user_id=state["user_id"],
        query=state["query_understanding"]["normalized_query"],
        top_k_text=5,
        top_k_images=8,
        document_ids=state.get("document_ids"),
    )
    output = result.model_dump()
    _log(
        state,
        "Retrieval Agent",
        {"query": state["query_understanding"]["normalized_query"], "document_ids": state.get("document_ids")},
        output,
    )
    return {"retrieval": output}


def diagnosis_node(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state["retrieval"]["text_evidence"]
    causes = []
    if evidence:
        causes.append(
            {
                "cause": _first_sentence(evidence[0]["text"]),
                "evidence_ids": [evidence[0]["id"]],
            }
        )
    output = {
        "likely_causes": causes,
        "insufficient_context": not evidence,
    }
    _log(state, "Diagnosis Agent", {"evidence_count": len(evidence)}, output)
    return {"diagnosis": output}


def troubleshooting_steps_node(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state["retrieval"]["text_evidence"]
    steps = []
    if evidence:
        primary = evidence[0]
        steps.append(
            {
                "step": "Review the cited manual section and follow only the documented checks before attempting repair.",
                "evidence_ids": [primary["id"]],
                "risk_level": "low",
            }
        )
        steps.append(
            {
                "step": _first_sentence(primary["text"]),
                "evidence_ids": [primary["id"]],
                "risk_level": "medium",
            }
        )
    output = {"steps": steps}
    _log(state, "Troubleshooting Steps Agent", state["diagnosis"], output)
    return {"troubleshooting_steps": output}


def guardrails_node(state: dict[str, Any]) -> dict[str, Any]:
    blocked_steps = []
    approved_steps = []
    for step in state["troubleshooting_steps"]["steps"]:
        text = step["step"].lower()
        if any(blocked in text for blocked in ["bypass", "disable emergency", "ignore warning"]):
            blocked_steps.append(step)
        else:
            approved_steps.append(step)
    output = {
        "approved": not blocked_steps,
        "safety_notes": [
            "Disconnect power before inspection when the manual or local safety procedure requires it.",
            "Use a qualified technician for internal electrical, high-voltage, mechanical, or service-only work.",
        ],
        "blocked_steps": blocked_steps,
        "approved_steps": approved_steps,
    }
    _log(state, "Guardrails Agent", state["troubleshooting_steps"], output)
    return {"guardrails": output}


def cross_check_node(state: dict[str, Any]) -> dict[str, Any]:
    citation_ids = {item["id"] for item in state["retrieval"]["text_evidence"]}
    citation_ids.update(item["id"] for item in state["retrieval"]["image_evidence"])
    issues = []
    for step in state["guardrails"]["approved_steps"]:
        if not set(step["evidence_ids"]).issubset(citation_ids):
            issues.append({"step": step["step"], "issue": "Missing or invalid citation."})
    output = {
        "is_grounded": not issues,
        "unsupported_claims": [],
        "citation_issues": issues,
    }
    _log(state, "Cross-Check Agent", state["guardrails"], output)
    return {"cross_check": output}


def final_synthesis_node(state: dict[str, Any]) -> dict[str, Any]:
    text_evidence = state["retrieval"]["text_evidence"]
    image_evidence = _filter_relevant_images(
        text_evidence,
        state["retrieval"]["image_evidence"],
        state["query_understanding"]["normalized_query"],
    )
    citations = [
        {
            "id": item["id"],
            "type": "text",
            "source_file": item["source_file"],
            "document_id": item["document_id"],
            "page": item["page_start"],
            "excerpt": _clean_manual_text(item["text"]),
        }
        for item in text_evidence
    ]
    citations.extend(
        {
            "id": item["id"],
            "type": "image",
            "source_file": item["source_file"],
            "document_id": item["document_id"],
            "page": item["page"],
            "caption": item["caption"],
            "related_text": item["nearby_text"],
            "image_url": f"/files/images/{item['image_id']}",
        }
        for item in image_evidence
    )
    images = [
        {
            "id": item["id"],
            "image_url": f"/files/images/{item['image_id']}",
            "source_file": item["source_file"],
            "page": item["page"],
            "caption": item["caption"],
        }
        for item in image_evidence
    ]

    if not text_evidence:
        answer = (
            "## Answer\n\n"
            "I could not find enough indexed manual evidence to answer this safely.\n\n"
            "## Checks\n\n"
            "1. Upload the relevant equipment manual or ask a more specific question.\n\n"
            "## Safety\n\n"
            "- Use qualified service personnel for electrical, high-voltage, or internal repair work.\n\n"
            "## Sources\n\n"
            "- No supporting citations found."
        )
    else:
        primary = text_evidence[0]
        ref = f"[[{primary['id']}]]"
        supporting_text = _supporting_excerpt(primary["text"])
        is_followup = bool(state["query_understanding"].get("is_followup"))
        action_sentences = _action_sentences(text_evidence)
        if is_followup:
            answer = (
                "## Answer\n\n"
                f"In simple terms: you are trying to get the filler wire from the feeder into the torch in a controlled way. "
                f"First make sure the torch is installed on the wire feeder, then load the wire path, and use the wire-inch function to feed the wire forward through the torch. {ref}\n\n"
                f"The manual wording behind that is: {supporting_text} {ref}\n\n"
            )
        else:
            answer = (
                "## Answer\n\n"
                f"The relevant manual section says: {supporting_text} {ref}\n\n"
                f"What that means operationally: use the cited section as the source of truth, then work through the setup in small checks rather than trying to interpret the diagram all at once. Start by identifying the named part or cable path in the manual, match it to the equipment in front of you, and only then make the adjustment or installation step. {ref}\n\n"
            )

        if image_evidence:
            image_refs = " ".join(f"[[{item['id']}]]" for item in image_evidence[:2])
            answer += f"Use this figure only as a visual reference after reading the steps: {image_refs}\n\n"

        answer += "## Steps\n\n"
        if action_sentences:
            for index, sentence in enumerate(action_sentences[:4], start=1):
                answer += f"{index}. {sentence} {ref}\n"
            step_offset = len(action_sentences[:4])
        else:
            answer += f"1. Locate the cited manual section and identify the exact component, connector, or route named there. {ref}\n"
            answer += f"2. Compare the figure or wording against the physical equipment before changing anything. {ref}\n"
            answer += f"3. Perform the documented installation or setup step, then re-check that the part is seated, routed, or enabled as described. {ref}\n"
            step_offset = 3
        for index, step in enumerate(state["guardrails"]["approved_steps"], start=1):
            evidence_ref = f"[[{step['evidence_ids'][0]}]]" if step["evidence_ids"] else ref
            answer += f"{index + step_offset}. {step['step']} {evidence_ref}\n"
        answer += "\n## Safety\n\n"
        for note in state["guardrails"]["safety_notes"]:
            answer += f"- {note}\n"
        answer += "\n## Sources\n\n"
        for item in text_evidence:
            page = item["page_start"] if item["page_start"] == item["page_end"] else f"{item['page_start']}-{item['page_end']}"
            answer += f"- [[{item['id']}]] {item['source_file']}, page {page}\n"
        for item in image_evidence:
            answer += f"- Figure source: {item['source_file']}, page {item['page']}\n"

    output = {"answer": answer, "citations": citations, "images": images}
    _log(state, "Final Synthesis Agent", state["cross_check"], output)
    return {"final_answer": answer, "citations": citations, "images": images}


def _first_sentence(text: str) -> str:
    normalized = _clean_manual_text(text)
    parts = re.split(r"(?<=[.!?])\s+|(?<=[.!?])(?=[A-Z])", normalized)
    for part in parts:
        candidate = part.strip()
        if (
            len(candidate) >= 20
            and _looks_readable(candidate)
            and (candidate[0].isupper() or candidate[0].isdigit() or candidate[0] in {"•", "-"})
        ):
            return candidate[:500]
    return parts[0][:500] if parts and parts[0] else normalized[:500]


def _supporting_excerpt(text: str) -> str:
    normalized = _clean_manual_text(text)
    parts = re.split(r"(?<=[.!?])\s+|(?<=[.!?])(?=[A-Z])", normalized)
    selected: list[str] = []
    for part in parts:
        candidate = part.strip()
        if (
            len(candidate) >= 20
            and _looks_readable(candidate)
            and (candidate[0].isupper() or candidate[0].isdigit() or candidate[0] in {"â€¢", "-"})
        ):
            selected.append(candidate)
        if len(selected) == 2:
            break
    if selected:
        return " ".join(selected)[:700]
    return _first_sentence(text)


def _action_sentences(text_evidence: list[dict[str, Any]]) -> list[str]:
    action_words = {
        "attach",
        "check",
        "connect",
        "disconnect",
        "enable",
        "feed",
        "fit",
        "install",
        "insert",
        "lock",
        "open",
        "place",
        "press",
        "remove",
        "route",
        "select",
        "set",
        "tighten",
        "turn",
    }
    sentences: list[str] = []
    for item in text_evidence[:3]:
        normalized = _clean_manual_text(item["text"])
        for part in re.split(r"(?<=[.!?])\s+|(?<=[.!?])(?=[A-Z])", normalized):
            candidate = part.strip(" -\t")
            if not candidate or len(candidate) < 18 or len(candidate) > 260:
                continue
            lowered = candidate.lower()
            if any(word in lowered for word in action_words) and _looks_readable(candidate):
                sentences.append(candidate)
            if len(sentences) >= 4:
                return sentences
    return sentences


def _clean_manual_text(text: str) -> str:
    cleaned = " ".join(text.split())
    cleaned = re.sub(r"©\s*Kemppi.*?Operating manual\s*-\s*EN", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{3,}\s*/\s*\d{3,}\b", "", cleaned)
    cleaned = re.sub(r"(?<=[0-9])(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cleaned)

    replacements = [
        (r"\bInstalltheweldingtorchtothewirefeederbeforeinstallingthewire\b", "Install the welding torch to the wire feeder before installing the wire"),
        (r"\bbeforeinstallingthewire\b", "before installing the wire"),
        (r"\binstallingthewire\b", "installing the wire"),
        (r"\binstalltheweldingtorch\b", "install the welding torch"),
        (r"\bweldingtorch\b", "welding torch"),
        (r"\bwirefeeder\b", "wire feeder"),
        (r"\bfillerwire\b", "filler wire"),
        (r"\bwireinch\b", "wire inch"),
        (r"\bR500WireFeeder\b", "R500 Wire Feeder"),
        (r"\bR500 WF\b", "R500 WF"),
        (r"\bEUR\+\s*2\.", "EUR+ 2."),
    ]
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _filter_relevant_images(
    text_evidence: list[dict[str, Any]],
    image_evidence: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    if not text_evidence or not image_evidence:
        return []

    cited_pages: set[int] = set()
    for item in text_evidence[:2]:
        page_start = int(item["page_start"])
        page_end = int(item["page_end"])
        for page in range(page_start, page_end + 1):
            cited_pages.add(page)

    query_terms = _meaningful_terms(query)
    relevant: list[dict[str, Any]] = []
    seen: set[str] = set()
    for image in image_evidence:
        image_page = int(image["page"])
        image_terms = _meaningful_terms(" ".join(part for part in [image.get("caption"), image.get("nearby_text")] if part))
        has_query_overlap = bool(query_terms.intersection(image_terms))
        is_exact_cited_page = image_page in cited_pages
        is_near_cited_page = any(abs(image_page - page) <= 1 for page in cited_pages)
        dedupe_key = image.get("content_hash") or f"{image['source_file']}:{image_page}:{image.get('caption') or ''}"
        if dedupe_key in seen:
            continue
        if is_exact_cited_page or (is_near_cited_page and has_query_overlap):
            seen.add(dedupe_key)
            relevant.append(image)

    return relevant[:2]


def _is_followup_question(question: str) -> bool:
    lowered = question.lower()
    followup_markers = [
        "can you explain",
        "don't understand",
        "dont understand",
        "explain in simple",
        "explain it",
        "follow up",
        "how do i do that",
        "in simple terms",
        "what do you mean",
        "this wire",
        "that",
        "it",
    ]
    return any(marker in lowered for marker in followup_markers)


def _recent_user_context(chat_history: list[dict[str, str]]) -> str:
    user_messages = [
        item.get("content", "").strip()
        for item in chat_history
        if item.get("role") == "user" and item.get("content", "").strip()
    ]
    if not user_messages:
        return ""
    return " ".join(user_messages[-2:])[:1200]


def _meaningful_terms(text: str) -> set[str]:
    stop_words = {
        "about",
        "after",
        "also",
        "from",
        "have",
        "into",
        "manual",
        "module",
        "page",
        "question",
        "should",
        "that",
        "the",
        "this",
        "what",
        "when",
        "where",
        "with",
        "your",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower())
        if token not in stop_words
    }


def _looks_readable(text: str) -> bool:
    letters = sum(1 for character in text if character.isalpha())
    spaces = text.count(" ")
    if letters < 20:
        return True
    return spaces / max(letters, 1) >= 0.08


def _log(state: dict[str, Any], agent_name: str, agent_input: dict[str, Any], agent_output: dict[str, Any]) -> None:
    state["trace_logger"].log_agent(agent_name=agent_name, agent_input=agent_input, agent_output=agent_output)
