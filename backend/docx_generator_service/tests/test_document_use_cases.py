"""Unit-тесты use case'ов управления документами (docx_generator_service).

Внешние зависимости (MinIO, БД, генератор) заменены тестовыми двойниками,
поэтому тесты не требуют запущенной инфраструктуры.
"""
import asyncio
from uuid import UUID

import pytest

from app.application.dtos.document_dto import (
    DocumentGenerationRequest,
    DocumentGenerationResponse,
    SaveDocumentDto,
)
from app.application.use_cases.generate_and_save_document import GenerateAndSaveDocumentUseCase
from app.application.use_cases.generate_document import GenerateDocumentUseCase
from app.application.use_cases.get_documents import GetDocumentsUseCase
from app.application.use_cases.save_document import SaveDocumentUseCase


class FakeMinio:
    def __init__(self):
        self.uploaded = {}

    async def upload_file(self, file_data, object_name, content_type=""):
        self.uploaded[object_name] = file_data
        return object_name


class FakeRepo:
    def __init__(self, docs=None):
        self.created = []
        self.docs = docs or []
        self.last_args = None

    async def create(self, document):
        self.created.append(document)
        return document

    async def get_by_user_id(self, user_id, limit=20, offset=0):
        self.last_args = (user_id, limit, offset)
        return [d for d in self.docs if d.user_id == user_id]


class FakeGenerator:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.response


def run(coro):
    return asyncio.run(coro)


# ---------- GenerateDocumentUseCase ----------

def test_generate_document_delegates_to_generator():
    resp = DocumentGenerationResponse(success=True, file_path="/x.docx", file_name="x.docx")
    gen = FakeGenerator(resp)
    req = DocumentGenerationRequest(data={"a": 1}, preview=True)
    result = GenerateDocumentUseCase(gen).execute(req)
    assert result is resp
    assert gen.requests == [req]


# ---------- SaveDocumentUseCase ----------

def test_save_document_uploads_and_creates_record():
    minio, repo = FakeMinio(), FakeRepo()
    dto = SaveDocumentDto(user_id=7, file_name="a.docx", file_data=b"DATA", requirements=[{"p": 1}])
    doc = run(SaveDocumentUseCase(repo, minio).execute(dto))
    assert doc.file_path.startswith("documents/7/") and doc.file_path.endswith(".docx")
    assert minio.uploaded[doc.file_path] == b"DATA"
    assert doc.file_size == 4
    assert repo.created == [doc]


def test_save_document_id_matches_object_name():
    dto = SaveDocumentDto(user_id=1, file_name="a.docx", file_data=b"x", requirements=[])
    doc = run(SaveDocumentUseCase(FakeRepo(), FakeMinio()).execute(dto))
    assert isinstance(doc.id, UUID)
    assert doc.file_path == f"documents/1/{doc.id}.docx"


def test_save_document_keeps_requirements_and_name():
    reqs = [{"font_size": 14}]
    dto = SaveDocumentDto(user_id=2, file_name="report.docx", file_data=b"abc", requirements=reqs)
    doc = run(SaveDocumentUseCase(FakeRepo(), FakeMinio()).execute(dto))
    assert doc.file_name == "report.docx"
    assert doc.requirements == reqs


# ---------- GetDocumentsUseCase ----------

def test_get_documents_returns_only_user_documents():
    from app.domain.entities.document import Document
    repo = FakeRepo([Document(user_id=1), Document(user_id=2), Document(user_id=1)])
    result = run(GetDocumentsUseCase(repo).execute(user_id=1))
    assert len(result) == 2


def test_get_documents_passes_pagination_defaults():
    repo = FakeRepo()
    run(GetDocumentsUseCase(repo).execute(user_id=5))
    assert repo.last_args == (5, 20, 0)


def test_get_documents_passes_custom_pagination():
    repo = FakeRepo()
    run(GetDocumentsUseCase(repo).execute(user_id=5, limit=3, offset=6))
    assert repo.last_args == (5, 3, 6)


def test_get_documents_empty_for_unknown_user():
    assert run(GetDocumentsUseCase(FakeRepo()).execute(user_id=99)) == []


# ---------- GenerateAndSaveDocumentUseCase ----------

def _file(tmp_path, content=b"DOCX-BYTES"):
    p = tmp_path / "gen.docx"
    p.write_bytes(content)
    return str(p)


def test_generate_and_save_success(tmp_path):
    gen = FakeGenerator(DocumentGenerationResponse(success=True, file_path=_file(tmp_path)))
    minio, repo = FakeMinio(), FakeRepo()
    uc = GenerateAndSaveDocumentUseCase(gen, minio, repo)
    doc = run(uc.execute(raw_json={"requirements": [{"a": 1}]},
                         tech_json={"data": {"main": {}}}, user_id=3))
    assert doc.user_id == 3
    assert doc.file_size == len(b"DOCX-BYTES")
    assert doc.requirements == [{"a": 1}]
    assert doc.tech_requirements == {"data": {"main": {}}}
    assert minio.uploaded[doc.file_path] == b"DOCX-BYTES"
    assert repo.created == [doc]


def test_generate_and_save_passes_data_and_preview_to_generator(tmp_path):
    gen = FakeGenerator(DocumentGenerationResponse(success=True, file_path=_file(tmp_path)))
    uc = GenerateAndSaveDocumentUseCase(gen, FakeMinio(), FakeRepo())
    run(uc.execute(raw_json={}, tech_json={"data": {"k": "v"}}, user_id=1, preview=True))
    assert gen.requests[0].data == {"k": "v"}
    assert gen.requests[0].preview is True


def test_generate_and_save_generator_failure_raises_and_saves_nothing():
    gen = FakeGenerator(DocumentGenerationResponse(success=False, error="boom"))
    minio, repo = FakeMinio(), FakeRepo()
    uc = GenerateAndSaveDocumentUseCase(gen, minio, repo)
    with pytest.raises(Exception, match="boom"):
        run(uc.execute(raw_json={}, tech_json={}, user_id=1))
    assert minio.uploaded == {} and repo.created == []


def test_generate_and_save_missing_requirements_defaults_to_empty(tmp_path):
    gen = FakeGenerator(DocumentGenerationResponse(success=True, file_path=_file(tmp_path)))
    uc = GenerateAndSaveDocumentUseCase(gen, FakeMinio(), FakeRepo())
    doc = run(uc.execute(raw_json={}, tech_json={}, user_id=1))
    assert doc.requirements == []