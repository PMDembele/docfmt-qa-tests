"""Общие фикстуры для тестов docx_generator_service."""
import os
import sys

import pytest

# Корень сервиса в sys.path, чтобы работал импорт пакета app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docx import Document  # noqa: E402

from app.application.dtos.document_dto import DocumentGenerationRequest  # noqa: E402
from app.infrastructure.docx.document_generator import DocumentGenerator  # noqa: E402


@pytest.fixture
def generator(tmp_path):
    """Генератор, пишущий файл во временный каталог."""
    return DocumentGenerator(output_dir=str(tmp_path))


@pytest.fixture
def make_request():
    def _make(content, preview=False, **extra):
        data = {"main": {"content": content}}
        data.update(extra)
        return DocumentGenerationRequest(data=data, preview=preview)
    return _make


@pytest.fixture
def read_docx():
    def _read(path):
        return Document(path)
    return _read
