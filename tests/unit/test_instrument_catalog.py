import hashlib
import json
from pathlib import Path

import pytest

from data.questionnaires.build_catalog import (
    build_real_questionnaire_catalog,
)
from schemas.questionnaire_schema import QuestionnaireParent
from src.core.search_engine import QuestionnaireSearchEngine, QuestionnaireSearchFilters


@pytest.fixture
def generated_real_catalog(tmp_path: Path) -> Path:
    """Build the real, permission-cleared forms into an isolated JSON directory."""
    build_real_questionnaire_catalog(output_directory=tmp_path)
    return tmp_path


def test_catalog_contains_real_phq9_and_gad7_versions(
    generated_real_catalog: Path,
) -> None:
    phq9 = QuestionnaireParent.model_validate_json(
        (generated_real_catalog / "phq9.json").read_text(encoding="utf-8")
    )
    gad7 = QuestionnaireParent.model_validate_json(
        (generated_real_catalog / "gad7.json").read_text(encoding="utf-8")
    )

    assert {version.locale for version in phq9.versions} == {"en-US", "de-DE"}
    assert {version.locale for version in gad7.versions} == {"en-US", "de-AT", "de-CH"}
    assert len(phq9.versions[0].items) == 10
    assert len(gad7.versions[0].items) == 7


def test_phq9_functional_impact_item_is_not_in_total_score(
    generated_real_catalog: Path,
) -> None:
    phq9 = QuestionnaireParent.model_validate_json(
        (generated_real_catalog / "phq9.json").read_text(encoding="utf-8")
    )

    for version in phq9.versions:
        impact_item = next(item for item in version.items if item.dimension == "functional_impact")
        sensitive_item = next(
            item for item in version.items if item.dimension == "self_harm_thoughts"
        )
        target_ids = set(version.scoring_algorithms[0].target_items)
        assert impact_item.is_scored is False
        assert impact_item.item_id not in target_ids
        assert len(target_ids) == 9
        assert "suicide-related-thoughts" in sensitive_item.metadata.characteristics


def test_bundled_questionnaire_pdfs_have_permission_provenance_and_hashes(
    tmp_path: Path,
) -> None:
    catalog_paths = build_real_questionnaire_catalog(output_directory=tmp_path)
    assert len(catalog_paths) == 2

    for catalog_path in catalog_paths:
        questionnaire = QuestionnaireParent.model_validate_json(
            catalog_path.read_text(encoding="utf-8")
        )
        for version in questionnaire.versions:
            bundled_documents = [
                source for source in version.source_documents if source.local_path is not None
            ]
            assert len(bundled_documents) == 1
            document = bundled_documents[0]
            assert document.redistribution_permitted is True
            pdf_path = Path(document.local_path)
            assert pdf_path.is_file()
            assert document.sha256 == hashlib.sha256(pdf_path.read_bytes()).hexdigest()


def test_json_catalog_search_supports_regional_forms_and_real_items(
    generated_real_catalog: Path,
) -> None:
    search_engine = QuestionnaireSearchEngine(generated_real_catalog)

    gad7_anxiety = search_engine.search_items("Anspannung")
    swiss_locale = search_engine.search_items(
        filters=QuestionnaireSearchFilters(locales=["de-CH"])
    )
    phq9_depression = search_engine.search_items(
        "Hoffnungslosigkeit",
        QuestionnaireSearchFilters(languages=["de"], form_types=["full"]),
    )

    assert any(result.item_id == "gad7_de_ch_01" for result in gad7_anxiety)
    assert swiss_locale
    assert all(result.locale == "de-CH" for result in swiss_locale)
    assert any(result.item_id == "phq9_de_02" for result in phq9_depression)


def test_catalog_json_is_valid_json_and_keeps_source_language_wording(
    generated_real_catalog: Path,
) -> None:
    phq9_data = json.loads((generated_real_catalog / "phq9.json").read_text(encoding="utf-8"))
    german_version = next(
        version for version in phq9_data["versions"] if version["locale"] == "de-DE"
    )

    assert "Niedergeschlagenheit" in german_version["items"][1]["prompt_text"]
    assert german_version["source_documents"][0]["redistribution_permitted"] is True
