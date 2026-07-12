from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    NEEDS_CONFIRMATION = "needs_confirmation"
    READY = "ready"
    FAILED = "failed"


class InlineSpan(BaseModel):
    text: str
    bold: bool = False
    underline: bool = False
    superscript: bool = False
    subscript: bool = False


class ParagraphBlock(BaseModel):
    id: str
    type: Literal["paragraph"] = "paragraph"
    order: int
    text: str
    spans: list[InlineSpan] = Field(default_factory=list)
    page_break_before: bool = False


class TableBlock(BaseModel):
    id: str
    type: Literal["table"] = "table"
    order: int
    rows: list[list[str]]


class ImageBlock(BaseModel):
    id: str
    type: Literal["image"] = "image"
    order: int
    filename: str
    content_type: str
    sha256: str
    width_emu: int | None = None
    height_emu: int | None = None


ContentBlock = ParagraphBlock | TableBlock | ImageBlock


class ExtractedDocument(BaseModel):
    filename: str
    blocks: list[ContentBlock]
    paragraph_count: int
    table_count: int
    image_count: int
    warnings: list[str] = Field(default_factory=list)


StructureRole = Literal[
    "title",
    "subtitle",
    "recipient",
    "body_paragraph",
    "heading_level_1",
    "heading_level_2",
    "heading_level_3",
    "heading_level_4",
    "attachment_note",
    "attachment_body",
    "issuer_name",
    "document_date",
    "note",
    "table",
    "image",
    "other",
]


class StructureItem(BaseModel):
    source_id: str
    role: StructureRole
    confidence: float = Field(default=1.0, ge=0, le=1)
    reason: str | None = None


class UncertainItem(BaseModel):
    source_id: str
    suggested_role: StructureRole
    alternatives: list[StructureRole] = Field(default_factory=list)
    reason: str


class DocumentStructure(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    document_type: str = "unknown"
    template_id: str = "sdu_simplified_v1"
    items: list[StructureItem]
    uncertain_items: list[UncertainItem] = Field(default_factory=list)


class TaskRecord(BaseModel):
    id: str
    filename: str
    status: TaskStatus
    stage: str
    progress: int = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    summary: dict[str, int | str | bool] = Field(default_factory=dict)


class TaskCreated(BaseModel):
    task_id: str
    status: TaskStatus


class StructureUpdate(BaseModel):
    items: list[StructureItem]

