from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi import HTTPException, status

from app.config import Settings


FORBIDDEN_PARTS = (
    "vbaproject.bin",
    "word/embeddings/",
    "activex/",
)


def validate_docx(path: Path, original_name: str, settings: Settings) -> None:
    if not original_name.lower().endswith(".docx"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "当前仅支持 .docx 文件")
    if path.stat().st_size > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "文件不能超过 20 MB")
    if not zipfile.is_zipfile(path):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件不是有效的 DOCX 文档")

    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = {entry.filename.lower() for entry in entries}
            if "[content_types].xml" not in names or "word/document.xml" not in names:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件缺少必要的 Word 文档结构")
            if len(entries) > 5000:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "文档包含过多内部对象")
            total_size = sum(entry.file_size for entry in entries)
            if total_size > settings.max_uncompressed_bytes:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "文档解压后体积过大")
            for entry in entries:
                lowered = entry.filename.lower()
                if entry.flag_bits & 0x1:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "不支持加密文档")
                if any(part in lowered for part in FORBIDDEN_PARTS):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "文档包含宏、嵌入对象或不受支持的活动内容")
                if entry.compress_size and entry.file_size / entry.compress_size > 150:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "文档包含异常压缩内容")
    except zipfile.BadZipFile as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文件已损坏，无法读取") from exc

