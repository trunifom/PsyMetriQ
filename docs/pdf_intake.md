# PDF Intake and Extraction

## Purpose and boundary

The intake pipeline turns PDFs into inspectable, source-linked drafts and can promote either a completed questionnaire form into the instrument catalogue or an approved validation study into a separate reference-document catalogue. It does not assume that a PDF is an instrument, that a translation is validated, or that a document may be redistributed. Articles, manuals, forms, and mixed PDFs are routed for review unless the document type, extracted content/metadata, and exact redistribution rights have been explicitly approved.

The workflow is implemented as a CLI vertical slice in `src/ingestion/document_pipeline.py`, with its optional Structured Outputs adapter in `src/ingestion/llm_extractor.py`. The Flet GUI does not yet implement file upload or review controls.

## Local Folder Workflow

1. Drop a PDF into `data/questionnaires/inbox/`.
2. Run one pass or leave the local watcher running:

```powershell
python -m src.ingestion.document_pipeline
python -m src.ingestion.document_pipeline --watch
```

3. The importer checks file size, page count, PDF readability/encryption, extracts text and PDF metadata using PyMuPDF, computes SHA-256, and attempts OCR on image-only pages if PyMuPDF's Tesseract OCR support is available.
4. It classifies the content and suggests a domain using conservative text heuristics. The classification is a routing hint, not a clinical or licensing conclusion.
5. Without LLM opt-in, it writes a metadata/detection draft. With opt-in, it may submit the extracted text to OpenAI for a provisional Pydantic extraction; all extracted prompts still require review.
6. Uncertain, incomplete, scanned-without-OCR, mixed, manual, or unlicensed files move to `data/questionnaires/review/forms/<domain>/`; a Pydantic draft is written under `data/questionnaires/review/drafts/`.
7. A complete, high-confidence form moves to `forms/<domain>/<instrument>/` and merges into `json/<instrument_id>.json` only after item-content review and exact-file rights approval. One source PDF must map to exactly one concrete version; combined editions remain in review. A validation study with reviewed title, authors, publication year, DOI/citation metadata, and exact-file rights moves to `references/pdfs/<domain>/` with a separate metadata-only record under `references/json/`.

The `inbox/` and `review/` directories are Git-ignored. Their contents may still be sensitive on the local disk; use appropriate filesystem access controls and do not place confidential participant records there.

## Optional OpenAI extraction

The pipeline is local-only by default. To opt in to remote extraction, place `OPENAI_API_KEY` in the ignored root `.env` file or set it in the process environment, then pass the explicit flag:

```powershell
python -m src.ingestion.document_pipeline --watch --allow-remote-processing
```

The default model is `gpt-4o-mini`; override it with `OPENAI_MODEL` or `--model`. The SDK is asynchronous. The system instruction treats PDF text as untrusted data, asks for exact transcription, and forbids inference of license, clinical validity, age suitability, scoring, or citations. Refusals, incomplete structured responses, API errors, and extraction limitations do not produce a catalogue entry.

Before enabling remote processing, verify institutional privacy/security rules, data-processing terms, source license restrictions, and whether the document may be transmitted to that provider. A public PDF URL alone is not permission to submit its full text to an external service.

## Rights and Content Review Sidecar

The rights gate requires a sibling file named `questionnaire.pdf.source.json`. Copy [`source_approval.example.json`](../data/questionnaires/source_approval.example.json), replace the example values, and set `file_sha256` to the SHA-256 hash of the exact PDF. Minimum fields include:

- The PDF's exact `file_sha256`; a mismatch invalidates the approval.
- `source_url`, `license_name`, and `permission_basis`, naming the precise redistribution grant or written permission.
- `reviewed_by` and `reviewed_on` for the person who checked the rights.
- `redistribution_permitted: true` only when public redistribution is allowed.
- For a questionnaire form, `questionnaire_content_reviewed: true` only after checking transcription, versions, response choices, scoring, source population, and omissions against the PDF.
- For a validation study, `study_metadata_reviewed: true` only after checking title/citation, instrument identity, language, and extracted bibliographic metadata against the article.
- `document_type` must match `questionnaire_form` or `validation_study`; manuals, bibliographies, and mixed documents are not automatically catalogued.

The sidecar is a local human attestation, not something the LLM can generate or override. Placeholder/example values are rejected. A valid sidecar does not establish translation validity or clinical suitability.

## Review and Promote

Review drafts in the ignored `review/drafts/` and original files under `review/forms/`. You may correct the draft JSON with a suitable editor, but all edits must still pass the Pydantic schema. Place the hash-matched approval sidecar next to the review PDF, then promote without calling the LLM again:

```powershell
python -m src.ingestion.document_pipeline --approve-draft data/questionnaires/review/drafts/<sha256>.json
```

Promotion accepts a reviewed questionnaire form or validation-study reference. It refuses missing/incorrect sidecars, unscored items included in score targets, malformed source paths, low confidence, truncated extraction, existing `version_id` collisions, or invalid existing family JSON. Existing instrument data is merged only when the candidate adds new versions; it is never silently replaced.

A `catalogued` result contains relative paths to the final PDF and JSON. A `review_required`, `ocr_required`, `duplicate`, or `failed` result is not public catalogue content.

## OCR, Limits, and Logging

- Default limits: 40 MiB per PDF, 500 pages, and 120,000 extracted text characters.
- OCR languages default to `eng+deu`. If Tesseract language data is missing or OCR fails, the file remains in `review/` with a warning; the pipeline does not fabricate recognized text.
- Password-protected, unreadable, unsupported, or oversized PDFs are recorded as failed/review items.
- The watcher polls every three seconds by default; change with `--poll-seconds`.
- Logs include filenames, failure categories, and safe identifiers, never API keys or full PDF/questionnaire text.

The importer does not yet support DOCX, web scraping, handwritten-form recognition, reliable table reconstruction for every publisher layout, multi-instrument disambiguation without review, or automatic legal assessment. These cases remain review tasks rather than being silently forced into a schema.
