from pathlib import Path

import pytest

from data.generate_mock_data import generate_mock_data
from schemas.questionnaire_schema import QuestionnaireParent
from src.gui.catalog_store import CatalogStoreError, QuestionnaireCatalogStore


@pytest.fixture
def synthetic_family(tmp_path: Path) -> QuestionnaireParent:
    path = generate_mock_data(tmp_path)[0]
    return QuestionnaireParent.model_validate_json(path.read_text(encoding="utf-8"))


def test_catalog_store_loads_and_imports_validated_family(
    synthetic_family: QuestionnaireParent, tmp_path: Path
) -> None:
    store = QuestionnaireCatalogStore(tmp_path / "catalog")

    imported = store.import_families([synthetic_family])
    loaded = store.load()

    assert imported == [synthetic_family]
    assert loaded[0][0] == synthetic_family
    assert loaded[0][1].name == "bdi_ii_demo.json"


def test_catalog_store_merges_new_versions_without_replacing_existing(
    synthetic_family: QuestionnaireParent, tmp_path: Path
) -> None:
    store = QuestionnaireCatalogStore(tmp_path / "catalog")
    store.import_families([synthetic_family])
    existing, path = store.load()[0]
    added_version = existing.versions[0].model_copy(update={"version_id": "additional_v2"})
    candidate = existing.model_copy(update={"versions": [added_version]})

    merged = store.import_families([candidate])[0]

    assert [version.version_id for version in merged.versions] == [
        existing.versions[0].version_id,
        "additional_v2",
    ]
    assert QuestionnaireParent.model_validate_json(path.read_text(encoding="utf-8")) == merged


def test_catalog_store_refuses_version_collision_without_modifying_file(
    synthetic_family: QuestionnaireParent, tmp_path: Path
) -> None:
    store = QuestionnaireCatalogStore(tmp_path / "catalog")
    store.import_families([synthetic_family])
    _existing, path = store.load()[0]
    original_json = path.read_text(encoding="utf-8")

    with pytest.raises(CatalogStoreError, match="Version conflict"):
        store.import_families([synthetic_family])

    assert path.read_text(encoding="utf-8") == original_json


def test_catalog_store_rejects_invalid_existing_catalog_before_import(
    synthetic_family: QuestionnaireParent, tmp_path: Path
) -> None:
    catalog_directory = tmp_path / "catalog"
    catalog_directory.mkdir()
    (catalog_directory / "broken.json").write_text("{broken", encoding="utf-8")
    store = QuestionnaireCatalogStore(catalog_directory)

    with pytest.raises(CatalogStoreError, match="broken.json is invalid"):
        store.import_families([synthetic_family])

    assert not (catalog_directory / "bdi_ii_demo.json").exists()


def test_catalog_store_detects_safe_filename_collisions(tmp_path: Path) -> None:
    store = QuestionnaireCatalogStore(tmp_path / "catalog")
    first_data = {
        "instrument_id": "family/name",
        "name_full": "First family",
        "versions": [
            {
                "version_id": "v1",
                "language": "en",
                "items": [
                    {
                        "item_id": "i1",
                        "variable_name": "q1",
                        "dimension": "general",
                        "prompt_text": "Example item",
                        "response_mode": "text",
                    }
                ],
            }
        ],
    }
    second_data = {**first_data, "instrument_id": "family?name", "name_full": "Second family"}
    first = QuestionnaireParent.model_validate(first_data)
    second = QuestionnaireParent.model_validate(second_data)

    store.import_families([first])
    with pytest.raises(CatalogStoreError, match="conflicts with another instrument"):
        store.import_families([second])
