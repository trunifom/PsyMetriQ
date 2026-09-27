# PDF Intake Inbox

Drop PDFs to be inspected in this folder. The pipeline never publishes arbitrary incoming content by default.

## One-shot and watch modes

From the repository root:

```powershell
python -m src.ingestion.document_pipeline
python -m src.ingestion.document_pipeline --watch
```

The first command processes current top-level PDFs once. Watch mode polls for new PDFs and can stay running locally while the folder is used as an upload/drop target. OCR is attempted for image-only pages through the installed PyMuPDF/Tesseract OCR support; if OCR is unavailable or text remains insufficient, the PDF is routed to review with `ocr_required` status. The pipeline applies file-size, page-count, and extracted-text limits.

## Optional structured extraction

Without extra options, the pipeline extracts local PDF text/metadata and creates a draft record. To ask an LLM for a provisional Pydantic questionnaire candidate, configure the selected provider's key in the ignored local `.env`/environment and explicitly opt in. OpenAI is the default:

```powershell
python -m src.ingestion.document_pipeline --watch --allow-remote-processing --provider openai
python -m src.ingestion.document_pipeline --allow-remote-processing --provider anthropic --model claude-sonnet-4-6
python -m src.ingestion.document_pipeline --allow-remote-processing --provider openai-compatible --base-url <BASE_URL_FROM_PROVIDER> --model <MODEL_ID> --api-key-env SWISSGPT_API_KEY
```

Provider keys use `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `LLM_API_KEY` by default; `--api-key-env` selects a different environment variable without exposing its value in command history. OpenAI-compatible endpoints additionally require a provider-supplied base URL and model ID. Alpine AI/SwissGPT can use this option only if Alpine provides an OpenAI-compatible endpoint; this project has not verified a public SwissGPT endpoint. PDF text is sent to the selected provider only with the explicit opt-in flag. The model is instructed to preserve source wording, report uncertainty, and never decide licensing or validation status. Review all extracted items, answer choices, version/population metadata, and scoring before promotion. Raw extracted text is not written to logs or saved as a separate plaintext file.

## Rights sidecar

Automatic promotion requires a sidecar next to the PDF named `<filename>.pdf.source.json`, based on [`source_approval.example.json`](../source_approval.example.json). The sidecar must include:

- The exact PDF's SHA-256 (`file_sha256`); the pipeline rejects a mismatch.
- The official source URL and exact license/permission statement.
- A real reviewer identity/role and review date; placeholders are rejected.
- `redistribution_permitted: true` plus the review flag matching the document type.
- `questionnaire_content_reviewed: true` for a form; `study_metadata_reviewed: true` for a validation study.
- `document_type: questionnaire_form` or `validation_study`.

The rights and content booleans are human attestations, not conclusions drawn from OCR/LLM. Never assert these flags based only on a publicly accessible file or an article's general license.

## Automatic promotion gates

A questionnaire form moves to `forms/<domain>/<instrument>/` and its family JSON is created/updated only when the source PDF is readable, text is complete, the extractor returns a complete valid `QuestionnaireParent` above the confidence threshold, the result is classified as a form without reported limitations, and the checksum-bound sidecar confirms rights and human item-content review. A validation study with citation metadata and a sidecar confirming redistribution rights and bibliographic review moves to `references/pdfs/<domain>/`, with a metadata-only record in `references/json/`. Study full text is not copied into instrument items.

All other files move to the local, Git-ignored `review/forms/` tree with a Pydantic draft under `review/drafts/`. Manuals, mixed documents, unknown rights, duplicate version IDs, low-confidence extraction, incomplete/scanned files, and validation errors stay in review; the pipeline does not fabricate final JSON or overwrite existing forms.

## Review and promote a draft

Edit a draft JSON only after checking the original PDF. Add a matching `<reviewed-pdf>.pdf.source.json` sidecar with verified permission and item review, then run:

```powershell
python -m src.ingestion.document_pipeline --approve-draft data/questionnaires/review/drafts/<sha256>.json
```

Promotion revalidates the Pydantic model, source checksum, file location, and version merge. Existing version-ID collisions are refused rather than overwritten. If license terms do not allow public redistribution, keep the document out of the shared catalogue and record only a permitted citation/link.

## Privacy and security

`inbox/` and `review/` are excluded from Git by default. Keep participant data, private/licensed articles, API credentials, and unauthorized item text out of the shared repository. Remote extraction is opt-in because it transmits document text to a third party. Do not run it on confidential or unlicensed material without the required institutional and provider approvals.
