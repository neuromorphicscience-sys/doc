from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.security import validate_docx


def test_rejects_non_docx_extension(tmp_path: Path) -> None:
    path = tmp_path / "sample.zip"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "x")
        archive.writestr("word/document.xml", "x")
    with pytest.raises(HTTPException) as error:
        validate_docx(path, "sample.zip", Settings(task_data_dir=tmp_path / "tasks"))
    assert error.value.status_code == 415


def test_rejects_macro_payload(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "x")
        archive.writestr("word/document.xml", "x")
        archive.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(HTTPException) as error:
        validate_docx(path, path.name, Settings(task_data_dir=tmp_path / "tasks"))
    assert error.value.status_code == 400

