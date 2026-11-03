# DocFMT QA tests

Unit tests for two microservices of the DocFMT project (Tyumen State University, School of Computer Science, practice report).

- `backend/text_processing_service/tests` — 11 tests of the requirements-extraction use case (pytest, fakes for LLM / parser / cache)
- `backend/docx_generator_service/tests` — 25 tests of the DOCX generator and document-management use cases (24 pass, 1 xfail documents a defect)

Results (Python 3.14.7, pytest 9.2.0, pytest-cov 7.1.0): docx_generator_service 24 passed + 1 xfailed, coverage 40 %; text_processing_service 11 passed, coverage 54 %.

Run: see `TESTING.md`.
