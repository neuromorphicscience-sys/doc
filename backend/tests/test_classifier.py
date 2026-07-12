from app.models import ParagraphBlock, TableBlock
from app.services.classifier import heuristic_structure


def test_heuristic_preserves_every_source_id() -> None:
    blocks = [
        ParagraphBlock(id="block_0001", order=1, text="关于开展有关工作的通知"),
        ParagraphBlock(id="block_0002", order=2, text="各单位："),
        ParagraphBlock(id="block_0003", order=3, text="一、工作安排"),
        TableBlock(id="table_0001", order=4, rows=[["序号", "任务"]]),
    ]
    result = heuristic_structure(blocks)
    assert [item.source_id for item in result.items] == [block.id for block in blocks]
    assert [item.role for item in result.items] == ["title", "recipient", "heading_level_1", "table"]

