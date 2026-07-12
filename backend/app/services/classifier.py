from __future__ import annotations

import re

from app.models import ContentBlock, DocumentStructure, StructureItem, UncertainItem


LEVEL_PATTERNS = (
    (re.compile(r"^[一二三四五六七八九十百]+、"), "heading_level_1"),
    (re.compile(r"^（[一二三四五六七八九十百]+）"), "heading_level_2"),
    (re.compile(r"^\d+[.．、]"), "heading_level_3"),
    (re.compile(r"^（\d+）"), "heading_level_4"),
)
DATE_PATTERN = re.compile(r"(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")


def heuristic_structure(blocks: list[ContentBlock], reason: str | None = None) -> DocumentStructure:
    items: list[StructureItem] = []
    uncertain: list[UncertainItem] = []
    paragraph_ids = [block.id for block in blocks if block.type == "paragraph" and block.text.strip()]
    first_paragraph_id = paragraph_ids[0] if paragraph_ids else None

    for block in blocks:
        if block.type == "table":
            items.append(StructureItem(source_id=block.id, role="table"))
            continue
        if block.type == "image":
            items.append(StructureItem(source_id=block.id, role="image"))
            continue

        text = block.text.strip()
        role = "body_paragraph"
        confidence = 0.78
        if block.id == first_paragraph_id:
            role, confidence = "title", 0.7
        elif not text:
            role, confidence = "other", 1.0
        elif text.startswith("附件：") or text.startswith("附件:"):
            role, confidence = "attachment_note", 0.94
        elif DATE_PATTERN.search(text) and len(text) <= 30:
            role, confidence = "document_date", 0.9
        elif text.endswith(("：", ":")) and len(text) <= 50 and len(items) < 5:
            role, confidence = "recipient", 0.84
        else:
            for pattern, heading_role in LEVEL_PATTERNS:
                if pattern.match(text):
                    role, confidence = heading_role, 0.95
                    break

        items.append(StructureItem(source_id=block.id, role=role, confidence=confidence, reason=reason))
        if confidence < 0.75 and text:
            uncertain.append(
                UncertainItem(
                    source_id=block.id,
                    suggested_role=role,
                    alternatives=["title", "recipient", "body_paragraph"],
                    reason=reason or "规则识别置信度较低，请确认该段落角色。",
                )
            )

    return DocumentStructure(items=items, uncertain_items=uncertain)

