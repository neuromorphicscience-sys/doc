from __future__ import annotations

import asyncio
import json
import shutil
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.responses import JSONResponse

from app.config import get_settings
from app.models import (
    DocumentStructure,
    StructureUpdate,
    TaskCreated,
    TaskRecord,
    TaskStatus,
)
from app.services.deepseek import validate_structure
from app.services.processor import analyze_task, generate_task, load_extracted, load_structure
from app.services.security import validate_docx
from app.services.task_store import TaskStore


settings = get_settings()
store = TaskStore(settings.task_data_dir, settings.task_retention_hours)
upload_attempts: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.cleanup_expired()
    stop_cleanup = asyncio.Event()

    async def cleanup_loop() -> None:
        while not stop_cleanup.is_set():
            try:
                await asyncio.wait_for(stop_cleanup.wait(), timeout=3600)
            except asyncio.TimeoutError:
                await asyncio.to_thread(store.cleanup_expired)

    cleanup_task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        stop_cleanup.set()
        await cleanup_task


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.middleware("http")
async def security_and_rate_limit(request, call_next):
    if request.method == "POST" and request.url.path == "/api/tasks":
        client_host = request.client.host if request.client else "unknown"
        if client_host in {"127.0.0.1", "::1"}:
            client_host = request.headers.get("cf-connecting-ip", client_host)
        now = time.monotonic()
        attempts = upload_attempts[client_host]
        while attempts and now - attempts[0] > 3600:
            attempts.popleft()
        if len(attempts) >= 10:
            return JSONResponse(status_code=429, content={"detail": "上传过于频繁，请稍后再试"})
        attempts.append(now)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


def _record_or_404(task_id: str) -> TaskRecord:
    try:
        uuid.UUID(task_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在") from exc
    record = store.get(task_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在或已过期")
    return record


@app.get("/")
async def root() -> dict:
    return {"service": settings.app_name, "status": "ok", "docs": "/docs"}


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model_configured": bool(settings.deepseek_api_key),
        "model": settings.deepseek_model,
    }


@app.post("/api/tasks", response_model=TaskCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    security_confirmed: bool = Form(...),
) -> TaskCreated:
    if not security_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先确认文件不包含禁止上传的敏感信息")
    original_name = Path(file.filename or "document.docx").name
    task_id = str(uuid.uuid4())
    record = TaskRecord(
        id=task_id,
        filename=original_name,
        status=TaskStatus.UPLOADED,
        stage="文件已上传",
        progress=8,
    )
    task_dir = store.create(record)
    source_path = task_dir / "source.docx"
    try:
        with source_path.open("wb") as destination:
            total = 0
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "文件不能超过 20 MB")
                destination.write(chunk)
        validate_docx(source_path, original_name, settings)
    except Exception:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise
    finally:
        await file.close()

    background_tasks.add_task(analyze_task, task_id, store, settings)
    return TaskCreated(task_id=task_id, status=record.status)


@app.get("/api/tasks/{task_id}", response_model=TaskRecord)
async def get_task(task_id: str) -> TaskRecord:
    return _record_or_404(task_id)


@app.get("/api/tasks/{task_id}/structure")
async def get_structure(task_id: str) -> dict:
    record = _record_or_404(task_id)
    task_dir = store.directory(task_id)
    if not (task_dir / "structure.json").exists():
        raise HTTPException(status.HTTP_409_CONFLICT, "结构识别尚未完成")
    extracted = load_extracted(task_dir)
    structure = load_structure(task_dir)
    block_lookup = {block.id: block.model_dump(mode="json") for block in extracted.blocks}
    return {
        "task": record.model_dump(mode="json"),
        "structure": structure.model_dump(mode="json"),
        "blocks": block_lookup,
        "warnings": extracted.warnings,
    }


@app.put("/api/tasks/{task_id}/structure", status_code=status.HTTP_202_ACCEPTED)
async def update_structure(task_id: str, payload: StructureUpdate, background_tasks: BackgroundTasks) -> dict:
    record = _record_or_404(task_id)
    if record.status not in {TaskStatus.NEEDS_CONFIRMATION, TaskStatus.FAILED}:
        raise HTTPException(status.HTTP_409_CONFLICT, "当前任务状态不能更新结构")
    task_dir = store.directory(task_id)
    extracted = load_extracted(task_dir)
    expected = {block.id for block in extracted.blocks}
    submitted = [item.source_id for item in payload.items]
    if len(submitted) != len(set(submitted)) or set(submitted) != expected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "每个原始内容块必须且只能保留一次")

    current = load_structure(task_dir)
    updated = DocumentStructure(
        document_type=current.document_type,
        template_id=current.template_id,
        items=payload.items,
        uncertain_items=[],
    )
    updated = validate_structure(updated, extracted.blocks)
    (task_dir / "structure.json").write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    background_tasks.add_task(generate_task, task_id, store)
    return {"task_id": task_id, "status": "generating"}


@app.get("/api/tasks/{task_id}/reports")
async def get_reports(task_id: str) -> dict:
    _record_or_404(task_id)
    task_dir = store.directory(task_id)
    paths = {
        "consistency": task_dir / "consistency_report.json",
        "format": task_dir / "format_report.json",
    }
    if not all(path.exists() for path in paths.values()):
        raise HTTPException(status.HTTP_409_CONFLICT, "报告尚未生成")
    return {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}


@app.get("/api/tasks/{task_id}/download")
async def download_result(task_id: str) -> FileResponse:
    record = _record_or_404(task_id)
    if record.status != TaskStatus.READY:
        raise HTTPException(status.HTTP_409_CONFLICT, "结果未通过校验，暂不可下载")
    path = store.directory(task_id) / "result.docx"
    stem = Path(record.filename).stem
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{stem}_格式规范版.docx",
    )


@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str) -> None:
    _record_or_404(task_id)
    store.delete(task_id)
