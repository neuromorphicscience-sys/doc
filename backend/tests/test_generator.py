from pathlib import Path

from app.models import (
    DocumentStructure,
    ExtractedDocument,
    InlineSpan,
    ParagraphBlock,
    StructureItem,
    TableBlock,
)
from app.services.consistency import build_consistency_report
from app.services.generator import generate_docx


def test_generated_text_and_table_are_identical(tmp_path: Path) -> None:
    extracted = ExtractedDocument(
        filename="sample.docx",
        blocks=[
            ParagraphBlock(
                id="block_0001",
                order=1,
                text="关于开展2026年度有关工作的通知",
                spans=[InlineSpan(text="关于开展2026年度有关工作的通知")],
            ),
            ParagraphBlock(
                id="block_0002",
                order=2,
                text="各单位：",
                spans=[InlineSpan(text="各单位：")],
            ),
            TableBlock(id="table_0001", order=3, rows=[["序号", "任务"], ["1", "检查"]]),
        ],
        paragraph_count=2,
        table_count=1,
        image_count=0,
    )
    structure = DocumentStructure(
        items=[
            StructureItem(source_id="block_0001", role="title"),
            StructureItem(source_id="block_0002", role="recipient"),
            StructureItem(source_id="table_0001", role="table"),
        ]
    )
    output = tmp_path / "result.docx"
    generate_docx(extracted, structure, tmp_path, output)
    report = build_consistency_report(extracted, output)
    assert report["passed"] is True

