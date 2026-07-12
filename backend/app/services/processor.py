from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.config import Settings
from app.models import DocumentStructure, ExtractedDocument, TaskStatus
from app.services.consistency import build_consistency_report
from app.services.deepseek import analyze_structure, validate_structure
from app.services.extractor import extract_docx
from app.services.generator import generate_docx
from app.services.task_store import TaskStore


PROCESSING_LIMIT = asyncio.Semaphore(2)


def _write_model(path: Path, model) -> None:
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def load_extracted(task_dir: Path) -> ExtractedDocument:
    return ExtractedDocument.model_validate_json((task_dir / "extracted.json").read_text(encoding="utf-8"))


def load_structure(task_dir: Path) -> DocumentStructure:
    return DocumentStructure.model_validate_json((task_dir / "structure.json").read_text(encoding="utf-8"))


async def analyze_task(task_id: str, store: TaskStore, settings: Settings) -> None:
    async with PROCESSING_LIMIT:
        record = store.get(task_id)
        if record is None:
            return
        task_dir = store.directory(task_id)
        try:
            record.status = TaskStatus.EXTRACTING
            record.stage = "正在提取原始内容"
            record.progress = 20
            store.save(record)

            extracted = await asyncio.to_thread(
                extract_docx,
                task_dir / "source.docx",
                task_dir / "media",
                record.filename,
            )
            _write_model(task_dir / "extracted.json", extracted)

            record.status = TaskStatus.ANALYZING
            record.stage = "正在智能识别文档结构"
            record.progress = 55
            record.summary = {
                "paragraphs": extracted.paragraph_count,
                "tables": extracted.table_count,
                "images": extracted.image_count,
            }
            store.save(record)

            structure, engine = await analyze_structure(extracted.blocks, settings)
            structure = validate_structure(structure, extracted.blocks)
            _write_model(task_dir / "structure.json", structure)

            record.status = TaskStatus.NEEDS_CONFIRMATION
            record.stage = "结构识别完成，请确认"
            record.progress = 72
            record.summary.update(
                {
                    "document_type": structure.document_type,
                    "uncertain_count": len(structure.uncertain_items),
                    "analysis_engine": engine,
                }
            )
            store.save(record)
        except Exception as exc:
            record.status = TaskStatus.FAILED
            record.stage = "处理失败"
            record.error = f"{type(exc).__name__}: {exc}"
            store.save(record)


async def generate_task(task_id: str, store: TaskStore) -> None:
    async with PROCESSING_LIMIT:
        record = store.get(task_id)
        if record is None:
            return
        task_dir = store.directory(task_id)
        try:
            record.status = TaskStatus.ANALYZING
            record.stage = "正在按模板生成规范文档"
            record.progress = 82
            record.error = None
            store.save(record)

            extracted = load_extracted(task_dir)
            structure = load_structure(task_dir)
            output_path = task_dir / "result.docx"
            counts = await asyncio.to_thread(
                generate_docx,
                extracted,
                structure,
                task_dir / "media",
                output_path,
            )

            record.stage = "正在校验内容一致性"
            record.progress = 94
            store.save(record)
            consistency = await asyncio.to_thread(build_consistency_report, extracted, output_path)
            (task_dir / "consistency_report.json").write_text(
                json.dumps(consistency, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            format_report = {
                "template_id": structure.template_id,
                "page": ["A4", "上边距37 mm", "下边距35 mm", "左右边距27 mm"],
                "roles": counts,
                "warnings": extracted.warnings,
            }
            (task_dir / "format_report.json").write_text(
                json.dumps(format_report, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            record.status = TaskStatus.READY if consistency["passed"] else TaskStatus.FAILED
            record.stage = "规范文档已生成" if consistency["passed"] else "内容一致性校验未通过"
            record.progress = 100
            record.error = None if consistency["passed"] else "输出结果未通过内容一致性校验，不建议作为正式文件使用。"
            record.summary["consistency_passed"] = consistency["passed"]
            store.save(record)
        except Exception as exc:
            record.status = TaskStatus.FAILED
            record.stage = "生成失败"
            record.error = f"{type(exc).__name__}: {exc}"
            store.save(record)

