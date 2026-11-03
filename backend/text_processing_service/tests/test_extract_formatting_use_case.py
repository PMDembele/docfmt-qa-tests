"""Unit-тесты ExtractFormattingUseCase и доменных сущностей (text_processing_service).

Внешние зависимости (LLM-провайдер, парсер, Redis) заменены тестовыми двойниками,
поэтому тесты не требуют сети и ключей API.
"""
import asyncio
import hashlib

import pytest

from app.application.interfaces.cache_client import ICacheClient
from app.application.interfaces.llm_client import LLMClient
from app.application.interfaces.response_parser import ResponseParser
from app.application.use_cases.extract_formatting import ExtractFormattingUseCase
from app.domain.entities.document_format import DocumentFormat
from app.domain.entities.formatting_requirement import FormattingRequirement

PROMPT = "system prompt"
TEXT = "Шрифт: Times New Roman, 14 пт"


class FakeLLM(LLMClient):
    def __init__(self, answer="FONT_SIZE: 14 [document]", error=None):
        self.answer, self.error, self.calls = answer, error, []

    def generate(self, system_prompt, user_content):
        self.calls.append((system_prompt, user_content))
        if self.error:
            raise self.error
        return self.answer


class FakeParser(ResponseParser):
    def __init__(self, result=None, error=None):
        self.result = result if result is not None else [
            FormattingRequirement("FONT_SIZE", "14", category="font", scope="document")
        ]
        self.error, self.calls = error, []

    def parse(self, response_text):
        self.calls.append(response_text)
        if self.error:
            raise self.error
        return self.result


class FakeCache(ICacheClient):
    def __init__(self, stored=None):
        self.store = dict(stored or {})
        self.set_calls = []

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, data, ttl):
        self.set_calls.append((key, data, ttl))
        self.store[key] = data
        return True

    async def close(self):
        pass


def run(coro):
    return asyncio.run(coro)


# ---------- Основной сценарий ----------

def test_extract_requirements_success():
    llm, parser = FakeLLM(), FakeParser()
    result = run(ExtractFormattingUseCase(llm, parser).execute(TEXT, PROMPT))
    assert isinstance(result, DocumentFormat)
    assert [r.parameter for r in result.requirements] == ["FONT_SIZE"]
    assert llm.calls == [(PROMPT, TEXT)]


def test_extract_requirements_llm_mock_receives_raw_answer_in_parser():
    llm, parser = FakeLLM(answer="RAW ANSWER"), FakeParser()
    run(ExtractFormattingUseCase(llm, parser).execute(TEXT, PROMPT))
    assert parser.calls == ["RAW ANSWER"]


def test_extract_requirements_empty_result():
    uc = ExtractFormattingUseCase(FakeLLM(answer=""), FakeParser(result=[]))
    assert run(uc.execute(TEXT, PROMPT)).requirements == []


# ---------- Кэширование ----------

def test_extract_requirements_cache_miss_saves_result():
    cache = FakeCache()
    uc = ExtractFormattingUseCase(FakeLLM(), FakeParser(), cache)
    run(uc.execute(TEXT, PROMPT))
    assert len(cache.set_calls) == 1
    key, data, ttl = cache.set_calls[0]
    assert key == "formatting:" + hashlib.md5(TEXT.encode("utf-8")).hexdigest()
    assert data[0]["parameter"] == "FONT_SIZE"
    assert ttl == 3600


def test_extract_requirements_cache_hit_skips_llm():
    key = "formatting:" + hashlib.md5(TEXT.encode("utf-8")).hexdigest()
    cache = FakeCache({key: [{"parameter": "MARGIN_LEFT", "value": "30 мм", "category": None, "scope": "document"}]})
    llm = FakeLLM()
    result = run(ExtractFormattingUseCase(llm, FakeParser(), cache).execute(TEXT, PROMPT))
    assert llm.calls == []
    assert result.requirements[0].parameter == "MARGIN_LEFT"
    assert result.requirements[0].value == "30 мм"


def test_extract_requirements_cache_key_depends_on_text():
    uc = ExtractFormattingUseCase(FakeLLM(), FakeParser())
    assert uc._compute_cache_key("a") == uc._compute_cache_key("a")
    assert uc._compute_cache_key("a") != uc._compute_cache_key("b")


# ---------- Ошибки внешних зависимостей ----------

def test_extract_requirements_llm_error_is_propagated():
    uc = ExtractFormattingUseCase(FakeLLM(error=RuntimeError("LLM недоступна")), FakeParser())
    with pytest.raises(RuntimeError):
        run(uc.execute(TEXT, PROMPT))


def test_extract_requirements_parser_error_does_not_fill_cache():
    cache = FakeCache()
    uc = ExtractFormattingUseCase(FakeLLM(), FakeParser(error=ValueError("bad format")), cache)
    with pytest.raises(ValueError):
        run(uc.execute(TEXT, PROMPT))
    assert cache.set_calls == []


# ---------- Доменные сущности ----------

def _format():
    fmt = DocumentFormat()
    fmt.add_requirement(FormattingRequirement("FONT_SIZE", "14", "font", "document"))
    fmt.add_requirement(FormattingRequirement("ALIGN", "center", "layout", "heading:level=1"))
    return fmt


def test_document_format_get_by_parameter():
    assert _format().get_by_parameter("ALIGN").value == "center"
    assert _format().get_by_parameter("NOPE") is None


def test_document_format_filters_by_scope_and_category():
    fmt = _format()
    assert [r.parameter for r in fmt.get_by_scope("document")] == ["FONT_SIZE"]
    assert [r.parameter for r in fmt.get_by_category("layout")] == ["ALIGN"]
    assert fmt.get_by_scope("paragraph") == []


def test_document_format_to_dict_structure():
    d = _format().to_dict()
    assert set(d) == {"requirements"}
    assert d["requirements"][0] == {"parameter": "FONT_SIZE", "value": "14", "category": "font", "scope": "document"}
