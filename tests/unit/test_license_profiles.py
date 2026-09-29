import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from src.ingestion.license_profiles import (
    LicenseProfile,
    LicenseProfileError,
    build_rights_sidecar,
    load_profiles,
    write_sidecar,
)


def _profile(**overrides: object) -> LicenseProfile:
    defaults: dict[str, object] = {
        "profile_id": "acme_library",
        "license_name": "Acme Test Library Institutional Agreement",
        "license_url": "https://library.example.org/acme-agreement",
        "permission_basis_template": (
            "Licensed through the institutional test library for this study."
        ),
        "default_reviewed_by": "Test library staff",
    }
    defaults.update(overrides)
    return LicenseProfile.model_validate(defaults)


def test_build_rights_sidecar_hashes_the_exact_file_and_defaults_reviews_to_false(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "form.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")
    expected_digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    approval = build_rights_sidecar(
        _profile(),
        pdf_path,
        reviewed_by="Dr. Reviewer",
        reviewed_on=date(2026, 1, 15),
    )

    assert approval.file_sha256 == expected_digest
    assert approval.license_name == "Acme Test Library Institutional Agreement"
    assert approval.redistribution_permitted is True
    assert approval.questionnaire_content_reviewed is False
    assert approval.study_metadata_reviewed is False


def test_build_rights_sidecar_can_mark_content_as_reviewed_explicitly(tmp_path: Path) -> None:
    pdf_path = tmp_path / "form.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")

    approval = build_rights_sidecar(
        _profile(),
        pdf_path,
        reviewed_by="Dr. Reviewer",
        reviewed_on=date(2026, 1, 15),
        questionnaire_content_reviewed=True,
    )

    assert approval.questionnaire_content_reviewed is True


def test_build_rights_sidecar_requires_a_missing_pdf_to_fail_clearly(tmp_path: Path) -> None:
    with pytest.raises(LicenseProfileError):
        build_rights_sidecar(
            _profile(),
            tmp_path / "missing.pdf",
            reviewed_by="Dr. Reviewer",
            reviewed_on=date(2026, 1, 15),
        )


def test_build_rights_sidecar_requires_a_source_url_when_profile_has_none(tmp_path: Path) -> None:
    pdf_path = tmp_path / "form.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")
    profile = _profile(license_url=None)

    with pytest.raises(LicenseProfileError):
        build_rights_sidecar(
            profile, pdf_path, reviewed_by="Dr. Reviewer", reviewed_on=date(2026, 1, 15)
        )

    approval = build_rights_sidecar(
        profile,
        pdf_path,
        reviewed_by="Dr. Reviewer",
        reviewed_on=date(2026, 1, 15),
        source_url="https://publisher.example.org/exact-form.pdf",
    )
    assert str(approval.source_url) == "https://publisher.example.org/exact-form.pdf"


def test_write_sidecar_places_a_matching_source_json_beside_the_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "form.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")
    approval = build_rights_sidecar(
        _profile(), pdf_path, reviewed_by="Dr. Reviewer", reviewed_on=date(2026, 1, 15)
    )

    sidecar_path = write_sidecar(pdf_path, approval)

    assert sidecar_path == pdf_path.with_suffix(".pdf.source.json")
    saved = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert saved["file_sha256"] == approval.file_sha256


def test_load_profiles_returns_empty_mapping_when_file_is_absent(tmp_path: Path) -> None:
    assert load_profiles(tmp_path / "missing.json") == {}


def test_load_profiles_rejects_duplicate_profile_ids(tmp_path: Path) -> None:
    profiles_path = tmp_path / "license_profiles.json"
    profiles_path.write_text(
        json.dumps(
            [
                _profile().model_dump(mode="json"),
                _profile().model_dump(mode="json"),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(LicenseProfileError):
        load_profiles(profiles_path)


def test_load_profiles_reads_a_valid_file(tmp_path: Path) -> None:
    profiles_path = tmp_path / "license_profiles.json"
    profiles_path.write_text(
        json.dumps([_profile().model_dump(mode="json")]), encoding="utf-8"
    )

    profiles = load_profiles(profiles_path)

    assert set(profiles) == {"acme_library"}
    assert profiles["acme_library"].license_name == "Acme Test Library Institutional Agreement"
