# Тестирование (Дембеле Малик)

Unit-тесты на Python (pytest) для двух микросервисов проекта DocFMT.
Внешние зависимости (LLM, Redis, MinIO, БД) заменены тестовыми двойниками.

## Запуск

```bash
# из корня клонированного репозитория
python -m venv venv && venv\Scripts\activate        # Windows
pip install -r backend/text_processing_service/requirements.txt
pip install -r backend/docx_generator_service/requirements.txt
pip install -r requirements-test.txt

cd backend/text_processing_service
python -m pytest tests -v
python -m pytest tests --cov=app --cov-report=term-missing

cd ../docx_generator_service
python -m pytest tests -v -rx
python -m pytest tests --cov=app --cov-report=term-missing
```

## Состав

| Сервис | Файл | Тест-кейсов |
|---|---|---|
| text_processing_service | tests/test_extract_formatting_use_case.py | 11 |
| docx_generator_service | tests/test_document_generator.py | 13 (12 проходят, 1 фиксирует найденный дефект: xfail) |

## Найденный дефект
Неизвестный тип блока в JSON (например `{"unknown_block": ...}`) молча игнорируется:
генератор возвращает `success=True`, а не ошибку.
