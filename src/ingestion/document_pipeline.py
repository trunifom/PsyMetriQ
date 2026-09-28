"""Safe PDF intake, classification, extraction, review, and catalogue promotion.

The pipeline always records source identity and extraction status. Unknown PDFs
are moved to a local review area and produce a draft JSON, not a public catalogue
entry. Form promotion requires a complete Pydantic form, an exact-file rights and
content-review sidecar, one version per PDF, adequate text, and high confidence.
Validation studies use a separate citation-reviewed reference catalogue. Remote
LLM processing is disabled unless the operator opts in explicitly and selects
an installed provider.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, Sequence

import pymupdf
from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator

from schemas.questionnaire_schema import (
    QuestionnaireParent,
    QuestionnaireSourceDocument,
)
from src.ingestion.llm_extractor import (
    LLMProviderName,
    QuestionnaireExtractionDraft,
    QuestionnaireExtractionError,
    QuestionnaireExtractor,
    create_questionnaire_extractor,
)

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUESTIONNAIRE_ROOT = PROJECT_ROOT / "data" / "questionnaires"
DEFAULT_INBOX = QUESTIONNAIRE_ROOT / "inbox"
DEFAULT_REVIEW_ROOT = QUESTIONNAIRE_ROOT / "review"
DEFAULT_CATALOG_JSON = QUESTIONNAIRE_ROOT / "json"
DEFAULT_FORM_ROOT = QUESTIONNAIRE_ROOT / "forms"
DEFAULT_REFERENCE_PDF_ROOT = QUESTIONNAIRE_ROOT / "references" / "pdfs"
DEFAULT_REFERENCE_JSON_ROOT = QUESTIONNAIRE_ROOT / "references" / "json"

DocumentKind = Literal["questionnaire_form", "validation_study", "user_manual", "mixed", "unknown"]
ImportStatus = Literal[
    "catalogued",
    "review_required",
    "ocr_required",
    "duplicate",
    "failed",
]


class ImportPipelineError(RuntimeError):
    """Raised when an intake stage cannot be completed safely."""


class RedistributionApproval(BaseModel):
    """Human-reviewed, file-specific permission evidence stored beside an inbox PDF.

    Name the sidecar ``<filename>.pdf.source.json``. The pipeline will not infer
    permission from public access, extracted copyright text, a journal license,
    or an LLM result. The reviewer and basis are required for promotion.
    """

    source_url: HttpUrl
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license_name: str = Field(min_length=1)
    license_url: HttpUrl | None = None
    permission_basis: str = Field(min_length=20)
    reviewed_by: str = Field(min_length=3)
    reviewed_on: date
    redistribution_permitted: Literal[True]
    study_metadata_reviewed: bool = False
    questionnaire_content_reviewed: bool = False
    document_type: Literal[
        "questionnaire_form", "validation_study", "user_manual", "bibliography", "other"
    ]

    @field_validator("license_name", "permission_basis", "reviewed_by")
    @classmethod
    def reject_approval_placeholders(cls, value: str) -> str:
        """Prevent copied example text from satisfying the human approval gate."""
        normalized = value.casefold()
        placeholder_markers = ("placeholder", "todo", "example.org", "researcher name", "describe ")
        if any(marker in normalized for marker in placeholder_markers):
            raise ValueError("Rights approval fields must contain reviewed, source-specific values")
        return value


class PDFMetadata(BaseModel):
    """Safe, non-content metadata extracted from a PDF container."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    page_count: int = Field(ge=1)
    file_size_bytes: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extracted_character_count: int = Field(ge=0)
    text_truncated: bool = False
    ocr_attempted: bool = False
    ocr_succeeded: bool = False


class QuestionnaireImportDraft(BaseModel):
    """Local review record; an extraction draft is not approved catalog data."""

    draft_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    source_filename: str
    source_document: PDFMetadata
    document_kind: DocumentKind
    suggested_domain: str
    redistribution_approval: RedistributionApproval | None = None
    extraction: QuestionnaireExtractionDraft | None = None
    warnings: list[str] = Field(default_factory=list)
    status: ImportStatus
    draft_json_path: str | None = None
    review_pdf_path: str | None = None
    published_pdf_path: str | None = None
    catalogue_json_path: str | None = None


class ResearchDocumentRecord(BaseModel):
    """Metadata-only index record for a human-reviewed, distributable research PDF."""

    document_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_kind: Literal["validation_study"]
    title: str = Field(min_length=1)
    instrument_family_name: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    domain: str
    language: str
    citations: list[str] = Field(min_length=1)
    source_document: QuestionnaireSourceDocument
    metadata_reviewed_by: str = Field(min_length=3)
    metadata_reviewed_on: date
    extraction_confidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class ExtractedPDF:
    """In-memory PDF text and metadata; raw text is never logged by the pipeline."""

    metadata: PDFMetadata
    text: str
    title: str | None
    author: str | None
    subject: str | None
    ocr_warning: str | None


@dataclass(frozen=True)
class IntakeResult:
    """Result for one file, paired with the persisted draft or final catalogue path."""

    status: ImportStatus
    source_filename: str
    draft_path: Path | None
    catalogue_path: Path | None
    warning: str | None = None


@dataclass(frozen=True)
class PipelineConfig:
    """Filesystem limits and paths for a single local questionnaire collection."""

    project_root: Path = PROJECT_ROOT
    inbox_directory: Path = DEFAULT_INBOX
    review_directory: Path = DEFAULT_REVIEW_ROOT
    catalogue_directory: Path = DEFAULT_CATALOG_JSON
    reference_pdf_directory: Path = DEFAULT_REFERENCE_PDF_ROOT
    reference_json_directory: Path = DEFAULT_REFERENCE_JSON_ROOT
    form_directory: Path = DEFAULT_FORM_ROOT
    maximum_file_size_bytes: int = 40 * 1024 * 1024
    maximum_page_count: int = 500
    maximum_text_characters: int = 120_000
    minimum_text_characters: int = 160
    confidence_threshold: float = 0.92
    ocr_languages: str = "eng+deu"
    enable_ocr: bool = True
    poll_interval_seconds: float = 3.0


DOMAIN_TERMS: dict[str, tuple[str, ...]] = {
    "mental_health": (
        "depression", "depressive", "anxiety", "angst", "stress", "dass", "phq", "gad",
        "wellbeing", "well-being", "loneliness", "einsamkeit", "ocd", "obsessive",
        "adhd", "mental health", "psychische gesundheit",
    ),
    "education": (
        "school", "schule", "absenteeism", "attendance", "schulabsentismus", "student",
        "education", "bildung", "classroom", "lernen",
    ),
    "social_science": (
        "social support", "soziale Unterstützung", "friendship", "freundschaft", "family",
        "familie", "loneliness", "einsamkeit", "socioeconomic", "family affluence",
    ),
    "cognition": (
        "cognition", "cognitive", "memory", "Gedächtnis", "attention", "aufmerksamkeit",
        "dementia", "demenz", "alzheimer", "working memory",
    ),
    "physical_health": (
        "physical health", "health status", "gesundheitszustand", "quality of life", "promis",
        "eq-5d", "whodas",
    ),
    "physical_activity": (
        "physical activity", "körperliche Aktivität", "exercise", "movement", "ipaq",
        "ergotherapy", "ergotherapie",
    ),
    "nutrition": ("nutrition", "Ernährung", "diet", "food frequency", "eating behavior"),
    "occupational_therapy": ("occupational therapy", "ergotherapie", "participation"),
    "substance_use": ("substance", "alcohol", "audit", "addiction", "sucht", "drug use"),
}


def classify_document(text: str, title: str | None = None) -> tuple[str, DocumentKind]:
    """Suggest a domain and document type from title/text; never decides rights.

    The result is a routing hint only. Ambiguous and multiple-domain documents
    remain reviewable, and the source/license decision is handled separately.
    """
    sample = f"{title or ''}\n{text[:20_000]}".casefold()
    scores = {
        domain: sum(1 for term in terms if term in sample)
        for domain, terms in DOMAIN_TERMS.items()
    }
    positive_scores = {domain: score for domain, score in scores.items() if score > 0}
    if not positive_scores:
        domain = "unclassified"
    else:
        domain = max(positive_scores, key=positive_scores.get)

    study_markers = ("abstract", "methods", "participants", "doi:", "doi.org", "validation study")
    questionnaire_markers = (
        "please select", "circle one", "days per week", "response options", "questionnaire",
        "strongly agree", "not at all", "never", "item 1", "question 1",
    )
    has_study_markers = sum(term in sample for term in study_markers) >= 2
    has_form_markers = sum(term in sample for term in questionnaire_markers) >= 2
    if has_form_markers and has_study_markers:
        kind: DocumentKind = "mixed"
    elif has_form_markers:
        kind = "questionnaire_form"
    elif has_study_markers:
        kind = "validation_study"
    elif "manual" in sample or "scoring instructions" in sample:
        kind = "user_manual"
    else:
        kind = "unknown"
    return domain, kind


def _safe_path_segment(value: str, fallback: str = "unclassified") -> str:
    """Make externally extracted labels safe as one local path component."""
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.casefold()).strip("._-")
    return normalized[:64] or fallback


def _pdf_text(path: Path, config: PipelineConfig) -> ExtractedPDF:
    """Read a bounded PDF, attempt OCR for image-only pages, and compute a digest."""
    if path.suffix.casefold() != ".pdf":
        raise ImportPipelineError("Only PDF input is supported")
    try:
        file_size = path.stat().st_size
    except OSError as error:
        raise ImportPipelineError("Could not access the source file") from error
    if file_size < 1:
        raise ImportPipelineError("The source PDF is empty")
    if file_size > config.maximum_file_size_bytes:
        raise ImportPipelineError(
            f"PDF exceeds the configured {config.maximum_file_size_bytes}-byte size limit"
        )

    try:
        pdf_bytes = path.read_bytes()
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except (OSError, pymupdf.FileDataError, pymupdf.EmptyFileError) as error:
        raise ImportPipelineError("The source is not a readable PDF") from error

    with document:
        if document.needs_pass and not document.authenticate(""):
            raise ImportPipelineError("Password-protected PDFs require manual review")
        if document.page_count < 1:
            raise ImportPipelineError("The PDF has no pages")
        if document.page_count > config.maximum_page_count:
            raise ImportPipelineError(
                f"PDF exceeds the configured {config.maximum_page_count}-page limit"
            )

        metadata = document.metadata or {}
        page_count = document.page_count
        page_text: list[str] = []
        ocr_attempted = False
        ocr_succeeded = False
        ocr_warning: str | None = None
        for page_number in range(document.page_count):
            page = document.load_page(page_number)
            text = page.get_text("text", sort=True).strip()
            if len(text) < 24 and config.enable_ocr:
                ocr_attempted = True
                try:
                    text_page = page.get_textpage_ocr(
                        language=config.ocr_languages,
                        dpi=200,
                        full=True,
                    )
                    ocr_text = page.get_text("text", textpage=text_page, sort=True).strip()
                    if len(ocr_text) > len(text):
                        text = ocr_text
                        ocr_succeeded = True
                except Exception as error:
                    # OCR is optional: the document remains available for local review.
                    ocr_warning = f"OCR unavailable or failed ({type(error).__name__})"
            page_text.append(text)

    extracted_text = "\n\n".join(page_text)
    was_truncated = len(extracted_text) > config.maximum_text_characters
    if was_truncated:
        extracted_text = extracted_text[: config.maximum_text_characters]
    return ExtractedPDF(
        metadata=PDFMetadata(
            title=metadata.get("title") or None,
            author=metadata.get("author") or None,
            subject=metadata.get("subject") or None,
            page_count=page_count,
            file_size_bytes=file_size,
            sha256=digest,
            extracted_character_count=len(extracted_text),
            text_truncated=was_truncated,
            ocr_attempted=ocr_attempted,
            ocr_succeeded=ocr_succeeded,
        ),
        text=extracted_text,
        title=metadata.get("title") or None,
        author=metadata.get("author") or None,
        subject=metadata.get("subject") or None,
        ocr_warning=ocr_warning,
    )


def _load_redistribution_approval(
    source_path: Path, source_sha256: str
) -> RedistributionApproval | None:
    """Load the optional human rights-review sidecar without trusting PDF text."""
    sidecar_path = source_path.with_suffix(source_path.suffix + ".source.json")
    if not sidecar_path.is_file():
        return None
    try:
        approval = RedistributionApproval.model_validate_json(
            sidecar_path.read_text(encoding="utf-8")
        )
        if approval.file_sha256 != source_sha256:
            LOGGER.warning("Rights-review sidecar checksum mismatch for %s", source_path.name)
            return None
        return approval
    except (OSError, UnicodeError, ValidationError):
        LOGGER.warning("Invalid rights-review sidecar for %s", source_path.name)
        return None


class QuestionnaireDocumentPipeline:
    """Process inbox PDFs into local extraction drafts or an approved JSON catalog.

    No source PDF or extracted questionnaire text is logged. Draft JSON and
    unapproved PDFs stay under the ignored local review directory. Remote
    extraction requires explicit operator opt-in and a configured extractor.
    """

    def __init__(
        self,
        *,
        config: PipelineConfig | None = None,
        extractor: QuestionnaireExtractor | None = None,
        allow_remote_processing: bool = False,
    ) -> None:
        """Configure local paths and optionally an explicitly enabled extractor."""
        self.config = config or PipelineConfig()
        if extractor is not None and not allow_remote_processing:
            raise ValueError(
                "Remote extraction requires explicit allow_remote_processing=True"
            )
        self.extractor = extractor
        self.allow_remote_processing = allow_remote_processing

    async def process_file(self, source_path: Path) -> QuestionnaireImportDraft:
        """Extract and route one PDF, preserving failed/unclear inputs for review."""
        source_path = await asyncio.to_thread(self._validate_input_path, source_path)
        if source_path.is_symlink():
            return await asyncio.to_thread(self._persist_symlink_failure, source_path)
        approval: RedistributionApproval | None = None
        warnings: list[str] = []
        extraction: QuestionnaireExtractionDraft | None = None
        try:
            extracted_pdf = await asyncio.to_thread(_pdf_text, source_path, self.config)
        except (OSError, ImportPipelineError) as error:
            LOGGER.error(
                "Could not extract PDF %s (%s)", source_path.name, type(error).__name__
            )
            return await asyncio.to_thread(self._persist_failure, source_path, str(error))
        approval = await asyncio.to_thread(
            _load_redistribution_approval,
            source_path,
            extracted_pdf.metadata.sha256,
        )

        if extracted_pdf.ocr_warning:
            warnings.append(extracted_pdf.ocr_warning)
        if extracted_pdf.metadata.text_truncated:
            warnings.append("PDF text exceeded the configured limit and was truncated")
        if len(extracted_pdf.text.strip()) < self.config.minimum_text_characters:
            warnings.append(
                "PDF has too little extractable text; complete form extraction is unavailable"
            )

        suggested_domain, heuristic_kind = classify_document(
            extracted_pdf.text, extracted_pdf.title or source_path.stem
        )
        is_duplicate = await asyncio.to_thread(
            self._is_duplicate, extracted_pdf.metadata.sha256
        )
        if is_duplicate:
            return await asyncio.to_thread(
                self._persist_record,
                source_path=source_path,
                extracted_pdf=extracted_pdf,
                kind=heuristic_kind,
                domain=suggested_domain,
                approval=approval,
                extraction=None,
                warnings=[
                    *warnings,
                    "Exact PDF checksum is already present in the local catalogs",
                ],
                status="duplicate",
                publish=False,
            )

        if len(extracted_pdf.text.strip()) < self.config.minimum_text_characters:
            warnings.append("LLM extraction skipped because the text minimum was not met")
        elif self.extractor is None:
            warnings.append(
                "No LLM extractor configured; only local text and metadata were inspected"
            )
        elif not extracted_pdf.metadata.text_truncated:
            try:
                extraction = await self.extractor.extract(
                    filename=source_path.name,
                    extracted_text=extracted_pdf.text,
                )
            except (QuestionnaireExtractionError, ValueError) as error:
                warnings.append(str(error))

        document_kind = extraction.document_kind if extraction else heuristic_kind
        if extraction and extraction.domain_hints:
            suggested_domain = self._select_domain(extraction.domain_hints, suggested_domain)
        if extraction and extraction.questionnaire:
            suggested_domain = self._select_questionnaire_domain(
                extraction.questionnaire, suggested_domain
            )

        can_publish, publish_warning = self._can_publish(
            extracted_pdf=extracted_pdf,
            kind=document_kind,
            approval=approval,
            extraction=extraction,
        )
        if publish_warning:
            warnings.append(publish_warning)
        status: ImportStatus
        if can_publish:
            try:
                if approval and approval.document_type == "validation_study":
                    return await asyncio.to_thread(
                        self._publish_validation_study,
                        source_path=source_path,
                        extracted_pdf=extracted_pdf,
                        domain=suggested_domain,
                        approval=approval,
                        extraction=extraction,
                        warnings=warnings,
                    )
                return await asyncio.to_thread(
                    self._persist_record,
                    source_path=source_path,
                    extracted_pdf=extracted_pdf,
                    kind=document_kind,
                    domain=suggested_domain,
                    approval=approval,
                    extraction=extraction,
                    warnings=warnings,
                    status="catalogued",
                    publish=True,
                )
            except (OSError, ImportPipelineError, ValidationError) as error:
                LOGGER.exception("Could not publish validated PDF %s", source_path.name)
                return await asyncio.to_thread(
                    self._persist_failure,
                    source_path,
                    f"Could not publish extracted content ({type(error).__name__})",
                    metadata=extracted_pdf.metadata,
                    domain=suggested_domain,
                    kind=document_kind,
                    approval=approval,
                    extraction=extraction,
                    warnings=warnings,
                )

        status = (
            "ocr_required"
            if extracted_pdf.metadata.extracted_character_count
            < self.config.minimum_text_characters
            else "review_required"
        )
        return await asyncio.to_thread(
            self._persist_record,
            source_path=source_path,
            extracted_pdf=extracted_pdf,
            kind=document_kind,
            domain=suggested_domain,
            approval=approval,
            extraction=extraction,
            warnings=warnings,
            status=status,
            publish=False,
        )

    async def process_inbox_once(self) -> list[QuestionnaireImportDraft]:
        """Process all top-level PDFs in sorted order, continuing after file failures."""
        source_paths = await asyncio.to_thread(self._list_inbox)
        results: list[QuestionnaireImportDraft] = []
        for source_path in source_paths:
            try:
                results.append(await self.process_file(source_path))
            except Exception as error:
                LOGGER.exception("Unexpected intake failure for %s", source_path.name)
                results.append(
                    await asyncio.to_thread(
                        self._persist_failure, source_path, type(error).__name__
                    )
                )
        return results

    def _validate_input_path(self, source_path: Path) -> Path:
        """Reject symlinks and inputs outside the configured inbox before reading bytes."""
        absolute_path = Path(os.path.abspath(source_path))
        inbox_directory = Path(os.path.abspath(self.config.inbox_directory))
        if absolute_path.is_symlink():
            return absolute_path
        if not absolute_path.is_relative_to(inbox_directory):
            raise ImportPipelineError("PDF input must be located under the configured inbox")
        return absolute_path

    def _persist_symlink_failure(self, source_path: Path) -> QuestionnaireImportDraft:
        """Create a metadata-only failed draft without dereferencing the symlink target."""
        link_metadata = source_path.lstat()
        digest = hashlib.sha256(source_path.name.encode("utf-8")).hexdigest()
        draft = QuestionnaireImportDraft(
            draft_id=digest,
            created_at=datetime.now(timezone.utc),
            source_filename=source_path.name,
            source_document=PDFMetadata(
                page_count=1,
                file_size_bytes=max(1, link_metadata.st_size),
                sha256=digest,
                extracted_character_count=0,
            ),
            document_kind="unknown",
            suggested_domain="unclassified",
            warnings=[
                "Symbolic-link PDF inputs are not read or moved; replace with a regular file."
            ],
            status="failed",
        )
        return self._write_draft(draft)

    def _list_inbox(self) -> list[Path]:
        """Create the inbox directory and return top-level PDFs in stable order."""
        self.config.inbox_directory.mkdir(parents=True, exist_ok=True)
        return sorted(self.config.inbox_directory.glob("*.pdf"))

    async def watch_inbox(self) -> None:
        """Poll the inbox until cancelled; intended for a local background task."""
        LOGGER.info("Watching questionnaire inbox %s", self.config.inbox_directory)
        while True:
            await self.process_inbox_once()
            await asyncio.sleep(self.config.poll_interval_seconds)

    def _can_publish(
        self,
        *,
        extracted_pdf: ExtractedPDF,
        kind: DocumentKind,
        approval: RedistributionApproval | None,
        extraction: QuestionnaireExtractionDraft | None,
    ) -> tuple[bool, str | None]:
        """Require kind-specific extraction quality and a human-reviewed rights sidecar."""
        if approval is None:
            return False, "Redistribution rights are unknown; manual rights review is required"
        if approval.file_sha256 != extracted_pdf.metadata.sha256:
            return False, "Rights sidecar does not match this PDF checksum"
        if approval.document_type == "questionnaire_form":
            if not approval.questionnaire_content_reviewed:
                return False, "Extracted item content has not been explicitly reviewed"
            if kind != "questionnaire_form":
                return False, "Document is not confidently classified as a questionnaire form"
            if extraction is None or extraction.questionnaire is None:
                return False, "No complete Pydantic questionnaire candidate was extracted"
            if len(extraction.questionnaire.versions) != 1:
                return False, (
                    "One PDF must map to exactly one questionnaire version; "
                    "combined editions require separate source review"
                )
        elif approval.document_type == "validation_study":
            if not approval.study_metadata_reviewed:
                return False, "Validation-study citation metadata has not been reviewed"
            if kind != "validation_study":
                return False, "Document is not confidently classified as a validation study"
            if extraction is None or not extraction.citations:
                return False, "No citation metadata was extracted from the validation study"
        else:
            return False, "This document type is not eligible for automatic publication"
        if extraction.extraction_confidence < self.config.confidence_threshold:
            return False, "Extraction confidence is below the automatic-publication threshold"
        if extraction.limitations:
            return False, "Extraction reports limitations and requires manual review"
        if extracted_pdf.metadata.text_truncated:
            return False, "Truncated source text cannot be automatically catalogued"
        if extracted_pdf.metadata.extracted_character_count < self.config.minimum_text_characters:
            return False, "Insufficient extracted text for automatic cataloguing"
        return True, None

    def _persist_record(
        self,
        *,
        source_path: Path,
        extracted_pdf: ExtractedPDF,
        kind: DocumentKind,
        domain: str,
        approval: RedistributionApproval | None,
        extraction: QuestionnaireExtractionDraft | None,
        warnings: list[str],
        status: ImportStatus,
        publish: bool,
    ) -> QuestionnaireImportDraft:
        """Write either a local review draft or a JSON/PDF pair to the shared catalog."""
        candidate = extraction.questionnaire if extraction else None
        if publish and candidate is not None and approval is not None:
            return self._publish_candidate(
                source_path=source_path,
                extracted_pdf=extracted_pdf,
                candidate=candidate,
                domain=domain,
                approval=approval,
                kind=kind,
                extraction=extraction,
                warnings=warnings,
            )

        review_pdf = self._move_to_review(source_path, domain, extracted_pdf.metadata.sha256)
        draft = QuestionnaireImportDraft(
            draft_id=extracted_pdf.metadata.sha256,
            created_at=datetime.now(timezone.utc),
            source_filename=source_path.name,
            source_document=extracted_pdf.metadata,
            document_kind=kind,
            suggested_domain=domain,
            redistribution_approval=approval,
            extraction=extraction,
            warnings=warnings,
            status=status,
            review_pdf_path=review_pdf.relative_to(self.config.project_root).as_posix(),
        )
        return self._write_draft(draft)

    def _publish_candidate(
        self,
        *,
        source_path: Path,
        extracted_pdf: ExtractedPDF,
        candidate: QuestionnaireParent,
        domain: str,
        approval: RedistributionApproval,
        kind: DocumentKind,
        extraction: QuestionnaireExtractionDraft,
        warnings: list[str],
    ) -> QuestionnaireImportDraft:
        """Promote a complete, explicitly rights-reviewed form atomically enough for local use."""
        instrument_segment = _safe_path_segment(candidate.instrument_id)
        filename = (
            f"{extracted_pdf.metadata.sha256[:12]}_"
            f"{_safe_path_segment(source_path.stem)}.pdf"
        )
        form_destination = (
            self.config.form_directory
            / _safe_path_segment(domain)
            / instrument_segment
        ) / filename
        final_form_relative_path = form_destination.relative_to(
            self.config.project_root
        ).as_posix()

        source_document_language = candidate.versions[0].language
        source_document = QuestionnaireSourceDocument(
            title=extracted_pdf.title or source_path.name,
            document_type=approval.document_type,
            language=source_document_language,
            source_url=approval.source_url,
            local_path=final_form_relative_path,
            license_name=approval.license_name,
            license_url=approval.license_url,
            redistribution_permitted=True,
            permission_basis=(
                f"Reviewed by {approval.reviewed_by} on {approval.reviewed_on.isoformat()}: "
                f"{approval.permission_basis}"
            ),
            accessed_on=date.today(),
            sha256=extracted_pdf.metadata.sha256,
        )
        versions_with_source = []
        for version in candidate.versions:
            if version.source_documents:
                warnings.append(
                    "LLM-extracted source-document/license records were discarded; "
                    "only the human-reviewed source sidecar is published"
                )
            versions_with_source.append(
                version.model_copy(update={"source_documents": [source_document]})
            )
        candidate = candidate.model_copy(update={"versions": versions_with_source})
        candidate = self._merge_with_existing(candidate)
        candidate = QuestionnaireParent.model_validate(candidate.model_dump(mode="json"))

        catalog_path = self.config.catalogue_directory / f"{instrument_segment}.json"
        form_destination.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_pdf = form_destination.with_suffix(".pdf.tmp")
        if form_destination.exists():
            raise ImportPipelineError("A file already exists at the generated form destination")
        try:
            shutil.copy2(source_path, temporary_pdf)
            os.replace(temporary_pdf, form_destination)
            self._write_json_atomically(catalog_path, candidate.model_dump(mode="json"))
        except OSError:
            temporary_pdf.unlink(missing_ok=True)
            form_destination.unlink(missing_ok=True)
            raise
        try:
            source_path.unlink()
            self._move_sidecar(source_path, form_destination)
        except OSError:
            LOGGER.warning(
                "Catalogued %s but could not clean up its inbox original/sidecar",
                source_path.name,
            )

        return QuestionnaireImportDraft(
            draft_id=extracted_pdf.metadata.sha256,
            created_at=datetime.now(timezone.utc),
            source_filename=source_path.name,
            source_document=extracted_pdf.metadata,
            document_kind=kind,
            suggested_domain=domain,
            redistribution_approval=approval,
            extraction=extraction,
            warnings=warnings,
            status="catalogued",
            published_pdf_path=final_form_relative_path,
            catalogue_json_path=catalog_path.relative_to(
                self.config.project_root
            ).as_posix(),
        )

    def _publish_validation_study(
        self,
        *,
        source_path: Path,
        extracted_pdf: ExtractedPDF,
        domain: str,
        approval: RedistributionApproval,
        extraction: QuestionnaireExtractionDraft,
        warnings: list[str],
    ) -> QuestionnaireImportDraft:
        """Publish a redistribution-approved study as a reference, never as a form.

        The LLM supplies provisional title/citation/instrument metadata; the human
        sidecar confirms those bibliographic fields were reviewed. Study text is
        kept in the PDF, not copied into questionnaire items or a second plaintext
        file. The reference JSON contains only searchable, source-linked metadata.
        """
        document_id = extracted_pdf.metadata.sha256
        reference_directory = self.config.reference_pdf_directory / _safe_path_segment(domain)
        reference_filename = (
            f"{document_id[:12]}_{_safe_path_segment(source_path.stem)}.pdf"
        )
        pdf_destination = reference_directory / reference_filename
        relative_pdf_path = pdf_destination.relative_to(self.config.project_root).as_posix()
        language = extraction.detected_languages[0] if extraction.detected_languages else "und"
        study_source = QuestionnaireSourceDocument(
            title=extraction.document_title or extracted_pdf.title or source_path.name,
            document_type="validation_study",
            language=language,
            source_url=approval.source_url,
            local_path=relative_pdf_path,
            license_name=approval.license_name,
            license_url=approval.license_url,
            redistribution_permitted=True,
            permission_basis=(
                f"Study metadata and rights reviewed by {approval.reviewed_by} on "
                f"{approval.reviewed_on.isoformat()}: {approval.permission_basis}"
            ),
            accessed_on=date.today(),
            sha256=document_id,
        )
        record = ResearchDocumentRecord(
            document_id=document_id,
            document_kind="validation_study",
            title=extraction.document_title or extracted_pdf.title or source_path.stem,
            instrument_family_name=extraction.instrument_family_name,
            authors=extraction.document_authors
            or ([extracted_pdf.author] if extracted_pdf.author else []),
            publication_year=extraction.publication_year,
            doi=extraction.doi,
            domain=domain,
            language=language,
            citations=[citation.strip() for citation in extraction.citations if citation.strip()],
            source_document=study_source,
            metadata_reviewed_by=approval.reviewed_by,
            metadata_reviewed_on=approval.reviewed_on,
            extraction_confidence=extraction.extraction_confidence,
        )
        json_path = self.config.reference_json_directory / f"{document_id}.json"
        if pdf_destination.exists() or json_path.exists():
            raise ImportPipelineError("A file for this validation-study checksum already exists")

        pdf_destination.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_pdf = pdf_destination.with_suffix(".pdf.tmp")
        try:
            shutil.copy2(source_path, temporary_pdf)
            os.replace(temporary_pdf, pdf_destination)
            self._write_json_atomically(json_path, record.model_dump(mode="json"))
        except OSError:
            temporary_pdf.unlink(missing_ok=True)
            pdf_destination.unlink(missing_ok=True)
            raise
        try:
            source_path.unlink()
            self._move_sidecar(source_path, pdf_destination)
        except OSError:
            LOGGER.warning(
                "Published validation reference %s but could not clean its review copy",
                source_path.name,
            )

        return QuestionnaireImportDraft(
            draft_id=document_id,
            created_at=datetime.now(timezone.utc),
            source_filename=source_path.name,
            source_document=extracted_pdf.metadata,
            document_kind="validation_study",
            suggested_domain=domain,
            redistribution_approval=approval,
            extraction=extraction,
            warnings=warnings,
            status="catalogued",
            published_pdf_path=relative_pdf_path,
            catalogue_json_path=json_path.relative_to(
                self.config.project_root
            ).as_posix(),
        )

    async def approve_review_draft(self, draft_path: Path) -> QuestionnaireImportDraft:
        """Promote a corrected draft without blocking an async caller's event loop."""
        return await asyncio.to_thread(self._approve_review_draft_sync, draft_path)

    def _approve_review_draft_sync(self, draft_path: Path) -> QuestionnaireImportDraft:
        """Promote a manually corrected draft without re-sending its PDF to an LLM.

        The reviewer edits the ignored draft JSON, places a matching
        ``<reviewed-pdf>.source.json`` approval sidecar beside the PDF, and runs
        this method. Both draft and PDF are constrained to the configured review
        tree, the sidecar hash is checked against the exact bytes, and all Pydantic
        validation plus automatic-promotion gates are re-applied.
        """
        draft_root = (self.config.review_directory / "drafts").resolve()
        draft_path = Path(os.path.abspath(draft_path))
        if not draft_path.is_relative_to(draft_root):
            raise ImportPipelineError("Draft must be inside the configured review/drafts directory")
        try:
            draft = QuestionnaireImportDraft.model_validate_json(
                draft_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, ValidationError):
            raise ImportPipelineError("Review draft is unreadable or invalid") from None

        if draft.status == "catalogued":
            raise ImportPipelineError("Review draft has already been catalogued")
        if draft.extraction is None:
            raise ImportPipelineError("Review draft contains no structured extraction candidate")
        if (
            draft.extraction.questionnaire is None
            and draft.document_kind != "validation_study"
        ):
            raise ImportPipelineError(
                "Review draft contains no complete questionnaire or validation-study candidate"
            )
        if draft.review_pdf_path is None:
            raise ImportPipelineError("Review draft has no associated PDF")

        review_forms_root = (self.config.review_directory / "forms").resolve()
        source_path = (self.config.project_root / draft.review_pdf_path).resolve()
        if not source_path.is_relative_to(review_forms_root) or source_path.is_symlink():
            raise ImportPipelineError(
                "Review PDF must be a regular file under the review/forms directory"
            )
        if not source_path.is_file():
            raise ImportPipelineError("Review PDF is missing")
        approval = _load_redistribution_approval(source_path, draft.source_document.sha256)
        if approval is None:
            raise ImportPipelineError(
                "A valid human-reviewed rights sidecar matching the PDF checksum is required"
            )

        document_text = ""  # The retained extraction draft is reused; no remote call is made.
        extracted_pdf = ExtractedPDF(
            metadata=draft.source_document,
            text=document_text,
            title=draft.source_document.title,
            author=draft.source_document.author,
            subject=draft.source_document.subject,
            ocr_warning=None,
        )
        can_publish, reason = self._can_publish(
            extracted_pdf=extracted_pdf,
            kind=draft.document_kind,
            approval=approval,
            extraction=draft.extraction,
        )
        if not can_publish:
            raise ImportPipelineError(
                reason or "Draft does not meet catalogue promotion requirements"
            )

        if approval.document_type == "validation_study":
            published = self._publish_validation_study(
                source_path=source_path,
                extracted_pdf=extracted_pdf,
                domain=draft.suggested_domain,
                approval=approval,
                extraction=draft.extraction,
                warnings=draft.warnings,
            )
        else:
            candidate = draft.extraction.questionnaire
            if candidate is None:
                raise ImportPipelineError("Questionnaire review draft has no questionnaire model")
            published = self._publish_candidate(
                source_path=source_path,
                extracted_pdf=extracted_pdf,
                candidate=candidate,
                domain=draft.suggested_domain,
                approval=approval,
                kind=draft.document_kind,
                extraction=draft.extraction,
                warnings=draft.warnings,
            )
        published = published.model_copy(
            update={
                "draft_json_path": draft_path.relative_to(
                    self.config.project_root
                ).as_posix()
            }
        )
        self._write_json_atomically(draft_path, published.model_dump(mode="json"))
        return published

    def _merge_with_existing(self, candidate: QuestionnaireParent) -> QuestionnaireParent:
        """Append genuinely new versions without replacing existing content."""
        instrument_segment = _safe_path_segment(candidate.instrument_id)
        existing_path = self.config.catalogue_directory / f"{instrument_segment}.json"
        if not existing_path.is_file():
            return candidate
        try:
            existing = QuestionnaireParent.model_validate_json(
                existing_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, ValidationError):
            raise ImportPipelineError(
                "Existing catalog JSON is invalid; refusing to overwrite it"
            ) from None
        if existing.instrument_id != candidate.instrument_id:
            raise ImportPipelineError(
                "Instrument identifier conflicts with the existing catalog file"
            )
        if existing.is_commercial != candidate.is_commercial:
            raise ImportPipelineError(
                "Commercial-use metadata conflicts with the existing family"
            )
        existing_version_ids = {version.version_id for version in existing.versions}
        candidate_version_ids = {version.version_id for version in candidate.versions}
        if existing_version_ids & candidate_version_ids:
            raise ImportPipelineError(
                "Candidate contains a version_id already in the catalog; manual merge is required"
            )
        merged = existing.model_copy(
            update={"versions": [*existing.versions, *candidate.versions]}
        )
        return QuestionnaireParent.model_validate(merged.model_dump(mode="json"))

    def _find_catalogued_duplicate(self, digest: str) -> bool:
        """Compare a PDF hash with registered source PDFs without opening content."""
        for catalog_path in sorted(self.config.catalogue_directory.glob("*.json")):
            try:
                questionnaire = QuestionnaireParent.model_validate_json(
                    catalog_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, ValidationError):
                LOGGER.warning(
                    "Skipping invalid catalog file during duplicate check: %s",
                    catalog_path.name,
                )
                continue
            if any(
                source.sha256 == digest
                for version in questionnaire.versions
                for source in version.source_documents
            ):
                return True
        for reference_path in sorted(self.config.reference_json_directory.glob("*.json")):
            try:
                record = ResearchDocumentRecord.model_validate_json(
                    reference_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, ValidationError):
                LOGGER.warning(
                    "Skipping invalid research-reference JSON during duplicate check: %s",
                    reference_path.name,
                )
                continue
            if record.document_id == digest or record.source_document.sha256 == digest:
                return True
        return False

    def _is_duplicate(self, digest: str) -> bool:
        """Expose duplicate checks to the intake path without logging document text."""
        return self._find_catalogued_duplicate(digest)

    def _move_to_review(self, source_path: Path, domain: str, digest: str) -> Path:
        """Move an unapproved original to an ignored local review folder."""
        review_directory = self.config.review_directory / "forms" / _safe_path_segment(domain)
        review_directory.mkdir(parents=True, exist_ok=True)
        destination = review_directory / f"{digest[:12]}_{_safe_path_segment(source_path.stem)}.pdf"
        if source_path.resolve() != destination.resolve():
            shutil.move(str(source_path), str(destination))
        self._move_sidecar(source_path, destination)
        return destination

    @staticmethod
    def _move_sidecar(source_path: Path, pdf_destination: Path) -> None:
        """Keep the human rights declaration next to its archived original."""
        sidecar_path = source_path.with_suffix(source_path.suffix + ".source.json")
        if sidecar_path.is_file():
            destination = pdf_destination.with_suffix(pdf_destination.suffix + ".source.json")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sidecar_path), str(destination))

    def _write_draft(self, draft: QuestionnaireImportDraft) -> QuestionnaireImportDraft:
        """Persist a local Pydantic draft atomically under the ignored review tree."""
        draft_directory = self.config.review_directory / "drafts"
        draft_directory.mkdir(parents=True, exist_ok=True)
        draft_path = draft_directory / f"{draft.draft_id}.json"
        persisted_draft = draft.model_copy(
            update={
                "draft_json_path": draft_path.relative_to(
                    self.config.project_root
                ).as_posix()
            }
        )
        self._write_json_atomically(draft_path, persisted_draft.model_dump(mode="json"))
        return persisted_draft

    def _persist_failure(
        self,
        source_path: Path,
        safe_error: str,
        *,
        metadata: PDFMetadata | None = None,
        domain: str = "unclassified",
        kind: DocumentKind = "unknown",
        approval: RedistributionApproval | None = None,
        extraction: QuestionnaireExtractionDraft | None = None,
        warnings: list[str] | None = None,
    ) -> QuestionnaireImportDraft:
        """Move failed inputs to review and persist a safe failure record."""
        digest = (
            metadata.sha256
            if metadata
            else hashlib.sha256(source_path.name.encode()).hexdigest()
        )
        if metadata is None:
            try:
                source_bytes = source_path.read_bytes()
            except OSError:
                source_bytes = source_path.name.encode()
            digest = hashlib.sha256(source_bytes).hexdigest()
            metadata = PDFMetadata(
                title=None,
                author=None,
                subject=None,
                page_count=1,
                file_size_bytes=max(1, len(source_bytes)),
                sha256=digest,
                extracted_character_count=0,
            )
        review_path: str | None = None
        if source_path.is_file():
            review_path = (
                self._move_to_review(source_path, domain, digest)
                .relative_to(self.config.project_root)
                .as_posix()
            )
        draft = QuestionnaireImportDraft(
            draft_id=digest,
            created_at=datetime.now(timezone.utc),
            source_filename=source_path.name,
            source_document=metadata,
            document_kind=kind,
            suggested_domain=domain,
            redistribution_approval=approval,
            extraction=extraction,
            warnings=[*(warnings or []), safe_error],
            status="failed",
            review_pdf_path=review_path,
        )
        return self._write_draft(draft)

    @staticmethod
    def _write_json_atomically(path: Path, payload: dict[str, object]) -> None:
        """Write JSON through a sibling temporary file to avoid partial catalogs."""
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_path, path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _select_domain(hints: Sequence[str], fallback: str) -> str:
        """Map known extracted hint terms to a stable domain folder when possible."""
        text = " ".join(hints).casefold()
        for domain, terms in DOMAIN_TERMS.items():
            if any(term in text for term in terms):
                return domain
        return fallback

    @classmethod
    def _select_questionnaire_domain(
        cls, questionnaire: QuestionnaireParent, fallback: str
    ) -> str:
        """Route from Pydantic metadata and names, keeping unknowns in review."""
        hints = [
            questionnaire.instrument_id,
            questionnaire.name_full,
            *questionnaire.construct_ontology,
            *questionnaire.metadata.keywords,
            *questionnaire.metadata.search_aliases,
        ]
        for version in questionnaire.versions:
            hints.extend(version.metadata.keywords)
            hints.extend(version.metadata.search_aliases)
        return cls._select_domain(hints, fallback)


async def process_inbox(
    *,
    config: PipelineConfig | None = None,
    allow_remote_processing: bool = False,
    provider: LLMProviderName = "openai",
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
) -> list[QuestionnaireImportDraft]:
    """Run one local inbox pass, optionally using a selected provider after consent."""
    extractor: QuestionnaireExtractor | None = None
    if allow_remote_processing:
        extractor = _create_remote_extractor(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
        )
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=extractor,
        allow_remote_processing=allow_remote_processing,
    )
    return await pipeline.process_inbox_once()


async def _watch(
    config: PipelineConfig,
    allow_remote_processing: bool,
    provider: LLMProviderName,
    model: str | None,
    base_url: str | None,
    api_key_env: str | None,
) -> None:
    """Keep polling for user-dropped PDFs until cancelled."""
    pipeline_extractor: QuestionnaireExtractor | None = None
    if allow_remote_processing:
        pipeline_extractor = _create_remote_extractor(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key_env=api_key_env,
        )
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=pipeline_extractor,
        allow_remote_processing=allow_remote_processing,
    )
    await pipeline.watch_inbox()


def _create_remote_extractor(
    *,
    provider: LLMProviderName,
    model: str | None,
    base_url: str | None,
    api_key_env: str | None,
) -> QuestionnaireExtractor:
    """Resolve provider-specific settings from environment without exposing secrets."""
    key_environment = api_key_env or {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "alpineai": "ALPINEAI_API_KEY",
        "openai-compatible": "LLM_API_KEY",
    }[provider]
    api_key = os.environ.get(key_environment, "")
    if provider == "alpineai" and not api_key:
        api_key = os.environ.get("SWISSGPT_API_KEY", "")
        if api_key:
            key_environment = "SWISSGPT_API_KEY"
    if not api_key:
        raise ValueError(f"{key_environment} is required for remote extraction")

    default_models = {
        "openai": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "alpineai": os.environ.get(
            "ALPINEAI_MODEL", "mistral-large-3-675b-nvfp4"
        ),
        "openai-compatible": os.environ.get("LLM_MODEL", ""),
    }
    selected_model = model or default_models[provider]
    if not selected_model:
        raise ValueError("Set --model or LLM_MODEL for the OpenAI-compatible provider")
    selected_base_url = None
    if provider == "alpineai":
        selected_base_url = base_url or os.environ.get(
            "ALPINEAI_BASE_URL", "https://api.prod.alpineai.ch/v1"
        )
    elif provider == "openai-compatible":
        selected_base_url = base_url or os.environ.get("LLM_BASE_URL")
    if provider == "openai-compatible" and not selected_base_url:
        raise ValueError(
            "Set --base-url or LLM_BASE_URL for the OpenAI-compatible provider"
        )
    return create_questionnaire_extractor(
        provider=provider,
        api_key=api_key,
        model=selected_model,
        base_url=selected_base_url,
    )


def main() -> None:
    """Expose a one-shot or polling command for PDFs placed in the local inbox."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--catalog-json", type=Path, default=DEFAULT_CATALOG_JSON)
    parser.add_argument("--forms", type=Path, default=DEFAULT_FORM_ROOT)
    parser.add_argument("--reference-pdfs", type=Path, default=DEFAULT_REFERENCE_PDF_ROOT)
    parser.add_argument("--reference-json", type=Path, default=DEFAULT_REFERENCE_JSON_ROOT)
    parser.add_argument("--watch", action="store_true", help="Poll the inbox continuously.")
    parser.add_argument(
        "--approve-draft",
        type=Path,
        help="Promote a manually reviewed draft using its local, hash-matched rights sidecar.",
    )
    parser.add_argument(
        "--allow-remote-processing",
        action="store_true",
        help="Explicitly allow PDF text to be sent to the selected provider.",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "anthropic", "alpineai", "openai-compatible"),
        default="openai",
        help="Remote extraction provider: openai, anthropic, alpineai, or openai-compatible.",
    )
    parser.add_argument(
        "--model",
        help="Provider model identifier; AlpineAI's API lists account-visible IDs at /v1/models.",
    )
    parser.add_argument(
        "--base-url",
        help="API base URL for AlpineAI override or an OpenAI-compatible provider.",
    )
    parser.add_argument(
        "--api-key-env",
        help="Environment variable containing the selected provider's API key.",
    )
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if arguments.allow_remote_processing:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
    config = PipelineConfig(
        inbox_directory=arguments.inbox,
        review_directory=arguments.review,
        catalogue_directory=arguments.catalog_json,
        form_directory=arguments.forms,
        reference_pdf_directory=arguments.reference_pdfs,
        reference_json_directory=arguments.reference_json,
        poll_interval_seconds=max(0.5, arguments.poll_seconds),
    )
    try:
        if arguments.approve_draft is not None:
            pipeline = QuestionnaireDocumentPipeline(config=config)
            result = asyncio.run(pipeline.approve_review_draft(arguments.approve_draft))
            LOGGER.info(
                "Approved questionnaire %s into %s",
                result.source_filename,
                result.catalogue_json_path,
            )
            return
        if arguments.watch:
            asyncio.run(
                _watch(
                    config,
                    arguments.allow_remote_processing,
                    arguments.provider,
                    arguments.model,
                    arguments.base_url,
                    arguments.api_key_env,
                )
            )
        else:
            results = asyncio.run(
                process_inbox(
                    config=config,
                    allow_remote_processing=arguments.allow_remote_processing,
                    provider=arguments.provider,
                    model=arguments.model,
                    base_url=arguments.base_url,
                    api_key_env=arguments.api_key_env,
                )
            )
            for result in results:
                LOGGER.info(
                    "PDF intake %s: %s (draft=%s, catalog=%s)",
                    result.status,
                    result.source_filename,
                    result.draft_path,
                    result.catalogue_path,
                )
    except (OSError, ValueError, ImportPipelineError):
        LOGGER.exception("Questionnaire PDF intake could not be completed")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
