"""Unit-тесты DocumentGenerator и реестра компонентов (docx_generator_service)."""
import os
import zipfile

import pytest

from app.infrastructure.components import component_registry, ComponentRegistry


def _document_xml(path):
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


# ---------- Позитивные сценарии ----------

def test_generate_paragraph_success(generator, make_request):
    resp = generator.generate(make_request([{"paragraph": {"text": "Привет, мир"}}]))
    assert resp.success is True
    assert resp.file_name == "generated.docx"
    assert os.path.exists(resp.file_path)
    assert "Привет, мир" in _document_xml(resp.file_path)


def test_generate_heading_uses_heading_style(generator, make_request):
    resp = generator.generate(make_request([{"heading": {"text": "Введение", "level": 2}}]))
    xml = _document_xml(resp.file_path)
    assert resp.success is True
    assert "Введение" in xml
    assert 'w:val="Heading2"' in xml


def test_generate_multiple_blocks_keep_order(generator, make_request):
    content = [{"paragraph": {"text": "первый"}}, {"paragraph": {"text": "второй"}}]
    resp = generator.generate(make_request(content))
    xml = _document_xml(resp.file_path)
    assert xml.index("первый") < xml.index("второй")


def test_generate_applies_formatting(generator, make_request):
    para = {"text": "формат", "formatting": {"font_family": "Times New Roman", "font_size": 14, "bold": True}}
    resp = generator.generate(make_request([{"paragraph": para}]))
    xml = _document_xml(resp.file_path)
    assert "Times New Roman" in xml
    assert "<w:b" in xml


def test_generated_file_is_valid_docx(generator, make_request, read_docx):
    resp = generator.generate(make_request([{"paragraph": {"text": "проверка открытия"}}]))
    doc = read_docx(resp.file_path)  # python-docx откроет только корректный DOCX
    assert any("проверка открытия" in p.text for p in doc.paragraphs)


def test_generate_document_has_sect_pr(generator, make_request):
    """Проверка обязательного тега w:sectPr в итоговом документе."""
    resp = generator.generate(make_request([{"paragraph": {"text": "x"}}]))
    assert "<w:sectPr" in _document_xml(resp.file_path)


# ---------- Негативные и граничные сценарии ----------

def test_generate_empty_content(generator, make_request):
    resp = generator.generate(make_request([]))
    assert resp.success is True  # пустой документ допустим
    assert os.path.exists(resp.file_path)


@pytest.mark.xfail(strict=True, reason="Дефект: неизвестный тип блока молча игнорируется, success=True")
def test_generate_unknown_component_reports_error(generator, make_request):
    resp = generator.generate(make_request([{"unknown_block": {"text": "?"}}]))
    assert resp.success is False
    assert resp.error


def test_generate_to_missing_directory_reports_error(tmp_path, make_request):
    from app.infrastructure.docx.document_generator import DocumentGenerator
    gen = DocumentGenerator(output_dir=str(tmp_path / "нет" / "такой" / "папки"))
    resp = gen.generate(make_request([{"paragraph": {"text": "x"}}]))
    assert resp.success is False
    assert resp.file_path == ""


# ---------- Реестр компонентов ----------

def test_registry_contains_basic_components():
    names = component_registry.list_components()
    for expected in ("paragraph", "heading", "section"):
        assert expected in names


def test_registry_get_is_case_and_digit_insensitive():
    assert component_registry.get("Paragraph") is component_registry.get("paragraph")
    assert component_registry.get("paragraph1") is component_registry.get("paragraph")


def test_registry_unknown_component_raises():
    with pytest.raises(ValueError):
        component_registry.get("does_not_exist")


def test_registry_register_decorator_adds_component():
    reg = ComponentRegistry()

    @reg.register("Custom")
    class Custom:  # noqa: D401
        pass

    assert reg.get("custom") is Custom
    assert reg.list_components() == ["custom"]