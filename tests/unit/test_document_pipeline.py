import asyncio
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pymupdf
import pytest
from pydantic import ValidationError

from schemas.questionnaire_schema import (
    ItemSchema,
    QuestionnaireParent,
    QuestionnaireSourceDocument,
    QuestionnaireVersion,
    ResponseOption,
)
from src.ingestion.document_pipeline import (
    ImportPipelineError,
    PipelineConfig,
    QuestionnaireDocumentPipeline,
    QuestionnaireImportDraft,
    RedistributionApproval,
    ResearchDocumentRecord,
)
from src.ingestion.llm_extractor import (
    ExtractedQuestionnaireFamily,
    ExtractedQuestionnaireVersion,
    ExtractedResponseSet,
    OpenAIQuestionnaireExtractionResponse,
    OpenAIQuestionnaireExtractor,
    QuestionnaireExtractionDraft,
)

SAMPLE_TEXT = "\n".join(
    [
        "Synthetic Demonstration Scale",
        "Questionnaire form about mental health and wellbeing.",
        "Please select one response for each item.",
        "Response options: Never, Sometimes, Often, Always.",
        "1. I feel supported by people around me.",
        "2. I can manage my daily responsibilities.",
        "3. I feel calm when facing everyday demands.",
        "Developed by the Synthetic Research Group.",
    ]
)


class FixedExtractor:
    """Test double that returns a validated draft without making a network call."""

    def __init__(self, draft: QuestionnaireExtractionDraft) -> None:
        self.draft = draft
        self.received_filename: str | None = None
        self.received_text: str | None = None

    async def extract(
        self, *, filename: str, extracted_text: str
    ) -> QuestionnaireExtractionDraft:
        self.received_filename = filename
        self.received_text = extracted_text
        return self.draft


def create_pdf(path: Path, text: str = SAMPLE_TEXT) -> Path:
    """Create a temporary text PDF with PyMuPDF for deterministic pipeline tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(48, 48, 560, 740), text, fontsize=11)
    document.save(path)
    document.close()
    return path


def create_blank_pdf(path: Path) -> Path:
    """Create a valid image/text-free page for the OCR-required path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()
    return path


def create_candidate() -> QuestionnaireParent:
    """Create a complete but synthetic domain object for a successful extraction test."""
    item = ItemSchema(
        item_id="demo_01",
        variable_name="demo_01",
        dimension="wellbeing",
        prompt_text="I feel supported by people around me.",
        response_set_ref="frequency_4",
    )
    version = QuestionnaireVersion(
        version_id="demo_en_v1",
        language="en",
        locale="en-US",
        response_sets={
            "frequency_4": [
                ResponseOption(code=0, label="Never", score=0),
                ResponseOption(code=1, label="Sometimes", score=1),
                ResponseOption(code=2, label="Often", score=2),
                ResponseOption(code=3, label="Always", score=3),
            ]
        },
        items=[item],
    )
    return QuestionnaireParent(
        instrument_id="demo_scale",
        name_full="Synthetic Demonstration Scale",
        is_commercial=False,
        versions=[version],
    )


def create_extraction_draft() -> QuestionnaireExtractionDraft:
    """Build a high-confidence questionnaire candidate for injected-extractor tests."""
    return QuestionnaireExtractionDraft(
        document_kind="questionnaire_form",
        document_title="Synthetic Demonstration Scale",
        instrument_family_name="Synthetic Demonstration Scale",
        domain_hints=["mental health", "wellbeing"],
        detected_languages=["en"],
        questionnaire=create_candidate(),
        citations=["Synthetic source citation; used only in unit testing."],
        limitations=[],
        extraction_confidence=0.99,
    )


def create_study_extraction_draft() -> QuestionnaireExtractionDraft:
    """Return citation metadata for a synthetic validation-study PDF."""
    return QuestionnaireExtractionDraft(
        document_kind="validation_study",
        document_title="Synthetic Study of a Wellbeing Measure",
        instrument_family_name="Synthetic Demonstration Scale",
        domain_hints=["wellbeing", "mental health"],
        detected_languages=["en"],
        document_authors=["Researcher One", "Researcher Two"],
        publication_year=2025,
        doi="10.1234/synthetic.study",
        questionnaire=None,
        citations=["Author A. Synthetic study citation. Journal of Testing. 2025."],
        limitations=[],
        extraction_confidence=0.98,
    )


def create_openai_extraction_response() -> OpenAIQuestionnaireExtractionResponse:
    """Create the API's strict list-based DTO for conversion tests."""
    candidate = create_candidate()
    version = candidate.versions[0]
    return OpenAIQuestionnaireExtractionResponse(
        document_kind="questionnaire_form",
        document_title="Synthetic Demonstration Scale",
        instrument_family_name=candidate.name_full,
        domain_hints=["mental health", "wellbeing"],
        detected_languages=["en"],
        questionnaire=ExtractedQuestionnaireFamily(
            instrument_id=candidate.instrument_id,
            name_full=candidate.name_full,
            is_commercial=None,
            versions=[
                ExtractedQuestionnaireVersion(
                    version_id=version.version_id,
                    language=version.language,
                    locale=version.locale,
                    response_sets=[
                        ExtractedResponseSet(
                            name="frequency_4",
                            options=version.response_sets["frequency_4"],
                        )
                    ],
                    items=version.items,
                )
            ],
        ),
        citations=[],
        limitations=[],
        extraction_confidence=0.99,
    )


def create_approval(
    pdf_path: Path,
    *,
    document_type: str = "questionnaire_form",
) -> RedistributionApproval:
    """Return explicit test-only permission tied to one exact PDF hash."""
    import hashlib

    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    return RedistributionApproval(
        source_url="https://example.org/synthetic-questionnaire.pdf",
        file_sha256=digest,
        license_name="Synthetic test-only permission",
        license_url="https://example.org/license",
        permission_basis=(
            "Unit test fixture has explicit permission for public redistribution."
        ),
        reviewed_by="Unit test reviewer",
        reviewed_on=date(2026, 9, 27),
        redistribution_permitted=True,
        questionnaire_content_reviewed=document_type == "questionnaire_form",
        study_metadata_reviewed=document_type == "validation_study",
        document_type=document_type,
    )


def make_config(root: Path, *, minimum_text_characters: int = 80) -> PipelineConfig:
    """Point every pipeline artifact into one isolated temporary project root."""
    return PipelineConfig(
        project_root=root,
        inbox_directory=root / "inbox",
        review_directory=root / "review",
        catalogue_directory=root / "json",
        form_directory=root / "forms",
        reference_pdf_directory=root / "references" / "pdfs",
        reference_json_directory=root / "references" / "json",
        minimum_text_characters=minimum_text_characters,
        enable_ocr=False,
    )


def test_pdf_reader_extracts_text_metadata_pages_and_checksum(tmp_path: Path) -> None:
    import hashlib

    from src.ingestion.document_pipeline import _pdf_text

    pdf_path = create_pdf(tmp_path / "input.pdf")
    extracted = _pdf_text(pdf_path, make_config(tmp_path))

    assert extracted.metadata.page_count == 1
    assert extracted.metadata.extracted_character_count >= 80
    assert "Synthetic Demonstration Scale" in extracted.text
    assert extracted.metadata.sha256 == hashlib.sha256(pdf_path.read_bytes()).hexdigest()


def test_unlicensed_extraction_is_saved_to_review_not_public_catalog(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    source_path = create_pdf(config.inbox_directory / "scale.pdf")
    extractor = FixedExtractor(create_extraction_draft())
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=extractor,
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(source_path))

    assert result.status == "review_required"
    assert result.redistribution_approval is None
    assert result.draft_json_path is not None
    assert not (config.catalogue_directory / "demo_scale.json").exists()
    assert not source_path.exists()
    assert (tmp_path / result.review_pdf_path).is_file()
    assert extractor.received_filename == "scale.pdf"
    assert "Synthetic Demonstration Scale" in (extractor.received_text or "")
    persisted_draft = QuestionnaireImportDraft.model_validate_json(
        (tmp_path / result.draft_json_path).read_text(encoding="utf-8")
    )
    assert persisted_draft.extraction is not None


def test_hash_matched_rights_approval_promotes_pdf_and_questionnaire_atomically(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    source_path = create_pdf(config.inbox_directory / "scale.pdf")
    approval_path = source_path.with_suffix(".pdf.source.json")
    approval_path.write_text(
        create_approval(source_path).model_dump_json(indent=2), encoding="utf-8"
    )
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_extraction_draft()),
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(source_path))

    assert result.status == "catalogued"
    assert result.catalogue_json_path == "json/demo_scale.json"
    assert not source_path.exists()
    published_pdf = tmp_path / result.published_pdf_path
    assert published_pdf.is_file()
    assert Path(f"{published_pdf}.source.json").is_file()
    catalogue = QuestionnaireParent.model_validate_json(
        (tmp_path / result.catalogue_json_path).read_text(encoding="utf-8")
    )
    assert catalogue.versions[0].source_documents[0].redistribution_permitted is True
    assert catalogue.versions[0].source_documents[0].local_path == result.published_pdf_path


def test_one_pdf_cannot_automatically_publish_multiple_questionnaire_versions(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    source_path = create_pdf(config.inbox_directory / "combined_editions.pdf")
    source_path.with_suffix(".pdf.source.json").write_text(
        create_approval(source_path).model_dump_json(), encoding="utf-8"
    )
    single_version_candidate = create_candidate()
    second_version = single_version_candidate.versions[0].model_copy(
        update={"version_id": "demo_en_v2"}
    )
    combined_candidate = single_version_candidate.model_copy(
        update={"versions": [*single_version_candidate.versions, second_version]}
    )
    extraction = create_extraction_draft().model_copy(
        update={"questionnaire": combined_candidate}
    )
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(extraction),
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(source_path))

    assert result.status == "review_required"
    assert any("exactly one questionnaire version" in warning for warning in result.warnings)
    assert not (config.catalogue_directory / "demo_scale.json").exists()


def test_human_review_can_promote_a_saved_draft_without_llm_reprocessing(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    source_path = create_pdf(config.inbox_directory / "scale.pdf")
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_extraction_draft()),
        allow_remote_processing=True,
    )

    draft = asyncio.run(pipeline.process_file(source_path))
    draft_path = tmp_path / draft.draft_json_path
    reviewed_pdf = tmp_path / draft.review_pdf_path
    approval_path = reviewed_pdf.with_suffix(reviewed_pdf.suffix + ".source.json")
    approval_path.write_text(
        create_approval(reviewed_pdf).model_dump_json(indent=2), encoding="utf-8"
    )

    approved = asyncio.run(pipeline.approve_review_draft(draft_path))

    assert approved.status == "catalogued"
    assert approved.catalogue_json_path == "json/demo_scale.json"
    assert not reviewed_pdf.exists()
    assert (tmp_path / approved.published_pdf_path).is_file()
    saved_status = QuestionnaireImportDraft.model_validate_json(
        draft_path.read_text(encoding="utf-8")
    )
    assert saved_status.status == "catalogued"


def test_rights_cleared_validation_study_is_stored_as_reference_not_form(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    study_text = (
        "Synthetic Study of a Wellbeing Measure\nAbstract\nMethods\nParticipants\n"
        "The questionnaire was evaluated. DOI: 10.0000/example"
    )
    source_path = create_pdf(config.inbox_directory / "study.pdf", text=study_text)
    source_path.with_suffix(".pdf.source.json").write_text(
        create_approval(source_path, document_type="validation_study").model_dump_json(),
        encoding="utf-8",
    )
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_study_extraction_draft()),
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(source_path))

    assert result.status == "catalogued"
    assert result.catalogue_json_path.startswith("references/json/")
    assert result.published_pdf_path.startswith("references/pdfs/")
    assert not (config.catalogue_directory / "demo_scale.json").exists()
    study_record = ResearchDocumentRecord.model_validate_json(
        (tmp_path / result.catalogue_json_path).read_text(encoding="utf-8")
    )
    assert study_record.document_kind == "validation_study"
    assert study_record.citations == [
        "Author A. Synthetic study citation. Journal of Testing. 2025."
    ]
    assert study_record.source_document.redistribution_permitted is True


def test_validation_study_without_reviewed_citation_metadata_stays_private(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    study_text = (
        "Synthetic validation study\nAbstract\nMethods\nParticipants\n" + SAMPLE_TEXT
    )
    source_path = create_pdf(config.inbox_directory / "study.pdf", text=study_text)
    approval = create_approval(source_path, document_type="validation_study").model_copy(
        update={"study_metadata_reviewed": False}
    )
    source_path.with_suffix(".pdf.source.json").write_text(
        approval.model_dump_json(), encoding="utf-8"
    )
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_study_extraction_draft()),
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(source_path))

    assert result.status == "review_required"
    assert "metadata has not been reviewed" in " ".join(result.warnings)
    assert not config.reference_json_directory.exists()


def test_validation_study_reference_hash_deduplicates_before_llm_call(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    previously_published = create_pdf(tmp_path / "previous.pdf")
    import hashlib

    digest = hashlib.sha256(previously_published.read_bytes()).hexdigest()
    record = ResearchDocumentRecord(
        document_id=digest,
        document_kind="validation_study",
        title="Previously reviewed synthetic study",
        domain="mental_health",
        language="en",
        citations=["A. Previously reviewed synthetic citation."],
        source_document=QuestionnaireSourceDocument(
            title="Previously reviewed synthetic study",
            document_type="validation_study",
            language="en",
            source_url="https://example.org/study.pdf",
            local_path=f"data/questionnaires/references/pdfs/mental_health/{digest}.pdf",
            license_name="Synthetic test permission",
            redistribution_permitted=True,
            permission_basis="A test fixture with reviewed rights for the test case.",
            accessed_on=date(2026, 9, 27),
            sha256=digest,
        ),
        metadata_reviewed_by="Test reviewer",
        metadata_reviewed_on=date(2026, 9, 27),
        extraction_confidence=0.99,
    )
    config.reference_json_directory.mkdir(parents=True)
    (config.reference_json_directory / f"{digest}.json").write_text(
        record.model_dump_json(), encoding="utf-8"
    )
    duplicate_path = create_pdf(config.inbox_directory / "same.pdf")
    duplicate_path.write_bytes(previously_published.read_bytes())
    extractor = FixedExtractor(create_study_extraction_draft())
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=extractor,
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(duplicate_path))

    assert result.status == "duplicate"
    assert extractor.received_filename is None


def test_reviewed_validation_study_can_be_promoted_to_separate_reference_catalog(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    study_text = (
        "Synthetic validation study\nAbstract\nMethods\nParticipants\n" + SAMPLE_TEXT
    )
    source_path = create_pdf(config.inbox_directory / "study.pdf", text=study_text)
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_study_extraction_draft()),
        allow_remote_processing=True,
    )
    draft = asyncio.run(pipeline.process_file(source_path))
    reviewed_pdf = tmp_path / draft.review_pdf_path
    reviewed_pdf.with_suffix(reviewed_pdf.suffix + ".source.json").write_text(
        create_approval(reviewed_pdf, document_type="validation_study").model_dump_json(),
        encoding="utf-8",
    )

    promoted = asyncio.run(
        pipeline.approve_review_draft(tmp_path / draft.draft_json_path)
    )

    assert promoted.status == "catalogued"
    assert promoted.catalogue_json_path.startswith("references/json/")
    research_record = ResearchDocumentRecord.model_validate_json(
        (tmp_path / promoted.catalogue_json_path).read_text(encoding="utf-8")
    )
    assert research_record.title == "Synthetic Study of a Wellbeing Measure"
    assert research_record.authors == ["Researcher One", "Researcher Two"]
    assert research_record.publication_year == 2025
    assert research_record.doi == "10.1234/synthetic.study"
    assert research_record.metadata_reviewed_by == "Unit test reviewer"


def test_manual_promotion_rejects_a_sidecar_with_wrong_hash(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source_path = create_pdf(config.inbox_directory / "scale.pdf")
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_extraction_draft()),
        allow_remote_processing=True,
    )
    draft = asyncio.run(pipeline.process_file(source_path))
    draft_path = tmp_path / draft.draft_json_path
    reviewed_pdf = tmp_path / draft.review_pdf_path
    wrong_hash_approval = create_approval(reviewed_pdf).model_copy(
        update={"file_sha256": "0" * 64}
    )
    reviewed_pdf.with_suffix(reviewed_pdf.suffix + ".source.json").write_text(
        wrong_hash_approval.model_dump_json(), encoding="utf-8"
    )

    with pytest.raises(ImportPipelineError, match="rights sidecar matching the PDF checksum"):
        asyncio.run(pipeline.approve_review_draft(draft_path))

    assert reviewed_pdf.is_file()
    assert not (config.catalogue_directory / "demo_scale.json").exists()


def test_unverified_llm_source_documents_are_not_published(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    source_path = create_pdf(config.inbox_directory / "scale.pdf")
    approval_path = source_path.with_suffix(".pdf.source.json")
    approval_path.write_text(
        create_approval(source_path).model_dump_json(indent=2), encoding="utf-8"
    )
    candidate = create_candidate()
    version = candidate.versions[0].model_copy(
        update={
            "source_documents": [
                {
                    "title": "LLM-invented permission",
                    "document_type": "questionnaire_form",
                    "language": "en",
                    "source_url": "https://example.org/unverified.pdf",
                    "license_name": "Public domain",
                    "redistribution_permitted": True,
                    "permission_basis": "Unverified model claim",
                    "accessed_on": date(2026, 9, 27),
                }
            ]
        }
    )
    candidate = candidate.model_copy(update={"versions": [version]})
    draft = create_extraction_draft().model_copy(update={"questionnaire": candidate})
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(draft),
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(source_path))
    catalog = QuestionnaireParent.model_validate_json(
        (tmp_path / result.catalogue_json_path).read_text(encoding="utf-8")
    )

    assert result.status == "catalogued"
    assert len(catalog.versions[0].source_documents) == 1
    assert catalog.versions[0].source_documents[0].permission_basis.startswith("Reviewed by")


def test_symlinked_pdf_is_rejected_without_following_or_moving_target(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    outside_pdf = create_pdf(tmp_path / "outside.pdf")
    config.inbox_directory.mkdir(parents=True, exist_ok=True)
    linked_pdf = config.inbox_directory / "linked.pdf"
    try:
        linked_pdf.symlink_to(outside_pdf)
    except OSError as error:
        pytest.skip(f"Symlink creation is unavailable on this system: {type(error).__name__}")
    pipeline = QuestionnaireDocumentPipeline(config=config)

    result = asyncio.run(pipeline.process_file(linked_pdf))

    assert result.status == "failed"
    assert any("Symbolic-link" in warning for warning in result.warnings)
    assert linked_pdf.is_symlink()
    assert outside_pdf.is_file()


def test_rights_sidecar_for_another_pdf_cannot_approve_current_file(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source_path = create_pdf(config.inbox_directory / "scale.pdf")
    approval = create_approval(source_path).model_dump(mode="json")
    approval["file_sha256"] = "0" * 64
    source_path.with_suffix(".pdf.source.json").write_text(
        json.dumps(approval), encoding="utf-8"
    )
    pipeline = QuestionnaireDocumentPipeline(
        config=config,
        extractor=FixedExtractor(create_extraction_draft()),
        allow_remote_processing=True,
    )

    result = asyncio.run(pipeline.process_file(source_path))

    assert result.status == "review_required"
    assert result.redistribution_approval is None
    assert any("rights are unknown" in warning for warning in result.warnings)
    assert not (config.catalogue_directory / "demo_scale.json").exists()


def test_scanned_or_textless_pdf_is_routed_to_ocr_review(tmp_path: Path) -> None:
    config = make_config(tmp_path, minimum_text_characters=30)
    source_path = create_blank_pdf(config.inbox_directory / "scan.pdf")
    pipeline = QuestionnaireDocumentPipeline(config=config)

    result = asyncio.run(pipeline.process_file(source_path))

    assert result.status == "ocr_required"
    assert result.extraction is None
    assert any("too little extractable text" in warning for warning in result.warnings)
    assert any("LLM extraction skipped" in warning for warning in result.warnings)
    assert (tmp_path / result.review_pdf_path).is_file()


def test_batch_keeps_processing_after_an_invalid_pdf(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.inbox_directory.mkdir(parents=True)
    (config.inbox_directory / "broken.pdf").write_bytes(b"not a PDF")
    create_pdf(config.inbox_directory / "valid.pdf")
    pipeline = QuestionnaireDocumentPipeline(config=config)

    results = asyncio.run(pipeline.process_inbox_once())

    assert [result.source_filename for result in results] == ["broken.pdf", "valid.pdf"]
    assert results[0].status == "failed"
    assert results[1].status == "review_required"
    assert all(result.draft_json_path for result in results)


def test_pipeline_requires_explicit_opt_in_for_any_remote_extractor() -> None:
    with pytest.raises(ValueError, match="explicit allow_remote_processing"):
        QuestionnaireDocumentPipeline(extractor=FixedExtractor(create_extraction_draft()))


def test_inbox_rejects_files_outside_the_configured_drop_folder(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    outside_pdf = create_pdf(tmp_path / "outside.pdf")
    pipeline = QuestionnaireDocumentPipeline(config=config)

    with pytest.raises(ImportPipelineError, match="under the configured inbox"):
        asyncio.run(pipeline.process_file(outside_pdf))

    assert outside_pdf.is_file()


def test_rights_approval_rejects_example_placeholder_values(tmp_path: Path) -> None:
    source_path = create_pdf(tmp_path / "form.pdf")
    approval_data = create_approval(source_path).model_dump(mode="json")
    approval_data["reviewed_by"] = "Researcher name or institutional role"

    with pytest.raises(ValidationError, match="reviewed, source-specific values"):
        RedistributionApproval.model_validate(approval_data)


def test_openai_structured_extractor_uses_strict_dto_and_injected_async_client() -> None:
    api_response = create_openai_extraction_response()
    expected = api_response.to_extraction_draft()

    class FakeParseEndpoint:
        async def parse(self, **kwargs: Any) -> Any:
            assert kwargs["response_format"] is OpenAIQuestionnaireExtractionResponse
            assert kwargs["messages"][1]["content"].endswith(SAMPLE_TEXT)
            message = SimpleNamespace(refusal=None, parsed=api_response)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    fake_client = SimpleNamespace(
        beta=SimpleNamespace(
            chat=SimpleNamespace(
                completions=FakeParseEndpoint(),
            )
        )
    )
    extractor = OpenAIQuestionnaireExtractor(api_key="", client=fake_client)  # type: ignore[arg-type]

    result = asyncio.run(extractor.extract(filename="input.pdf", extracted_text=SAMPLE_TEXT))

    assert result == expected


def test_openai_response_schema_has_no_dynamic_json_maps() -> None:
    schema = OpenAIQuestionnaireExtractionResponse.model_json_schema()
    dynamic_objects: list[str] = []

    def visit_schema(node: object, path: str = "root") -> None:
        if isinstance(node, dict):
            additional_properties = node.get("additionalProperties")
            if additional_properties is True or isinstance(additional_properties, dict):
                dynamic_objects.append(path)
            for key, value in node.items():
                visit_schema(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                visit_schema(value, f"{path}[{index}]")

    visit_schema(schema)
    assert dynamic_objects == []
