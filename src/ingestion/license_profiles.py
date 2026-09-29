"""Reusable license boilerplate for fast, still human-confirmed rights sidecars.

An institution that already holds a license for an instrument (for example
through a physical/negotiated test library) can save its recurring license
details once as a named profile. Generating a sidecar from a profile fills in
the license name/URL and permission basis automatically, but it never sets
``questionnaire_content_reviewed`` or ``study_metadata_reviewed`` on its own:
those still require an explicit flag from the person confirming this exact
file, and the file hash is always computed fresh from the exact PDF bytes.
This module never grants rights by itself; it only reduces repetitive typing
for a rights review a human still has to perform and confirm per file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, ValidationError

from src.ingestion.document_pipeline import RedistributionApproval

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILES_PATH = (
    PROJECT_ROOT / "data" / "questionnaires" / "review" / "license_profiles.json"
)


class LicenseProfileError(RuntimeError):
    """Raised when a license profile or sidecar generation request is invalid."""


class LicenseProfile(BaseModel):
    """Recurring, institution-specific license boilerplate for one licensor/agreement."""

    profile_id: str = Field(min_length=1, pattern=r"^[a-z0-9_-]+$")
    license_name: str = Field(min_length=1)
    license_url: HttpUrl | None = None
    permission_basis_template: str = Field(
        min_length=20,
        description=(
            "Reusable permission statement, for example naming the institutional test "
            "library or the study-specific purchase agreement."
        ),
    )
    default_reviewed_by: str | None = Field(
        default=None,
        description="Default reviewer name/role, such as a librarian; overridable per file.",
    )
    document_type: Literal[
        "questionnaire_form", "validation_study", "user_manual", "bibliography", "other"
    ] = "questionnaire_form"
    notes: str | None = None


def load_profiles(path: Path = DEFAULT_PROFILES_PATH) -> dict[str, LicenseProfile]:
    """Load named license profiles, or an empty mapping if none are configured yet."""
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LicenseProfileError("License profiles file is unreadable or invalid") from error
    if not isinstance(payload, list):
        raise LicenseProfileError("License profiles file must contain a JSON list")
    profiles: dict[str, LicenseProfile] = {}
    for entry in payload:
        try:
            profile = LicenseProfile.model_validate(entry)
        except ValidationError as error:
            raise LicenseProfileError(f"Invalid license profile entry: {error}") from error
        if profile.profile_id in profiles:
            raise LicenseProfileError(f"Duplicate license profile id {profile.profile_id!r}")
        profiles[profile.profile_id] = profile
    return profiles


def build_rights_sidecar(
    profile: LicenseProfile,
    pdf_path: Path,
    *,
    reviewed_by: str,
    reviewed_on: date,
    questionnaire_content_reviewed: bool = False,
    study_metadata_reviewed: bool = False,
    source_url: str | None = None,
) -> RedistributionApproval:
    """Combine a saved license profile with this exact PDF's hash and reviewer.

    ``questionnaire_content_reviewed``/``study_metadata_reviewed`` default to
    False and must be explicitly requested by the caller: a profile can never
    substitute for someone actually checking this file's extracted content.
    """
    if not pdf_path.is_file():
        raise LicenseProfileError(f"PDF not found: {pdf_path}")
    resolved_source_url = source_url or (
        str(profile.license_url) if profile.license_url else None
    )
    if resolved_source_url is None:
        raise LicenseProfileError(
            "Profile has no license_url; pass source_url for this exact document"
        )
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    return RedistributionApproval(
        source_url=resolved_source_url,
        file_sha256=digest,
        license_name=profile.license_name,
        license_url=profile.license_url,
        permission_basis=profile.permission_basis_template,
        reviewed_by=reviewed_by,
        reviewed_on=reviewed_on,
        redistribution_permitted=True,
        study_metadata_reviewed=study_metadata_reviewed,
        questionnaire_content_reviewed=questionnaire_content_reviewed,
        document_type=profile.document_type,
    )


def write_sidecar(pdf_path: Path, approval: RedistributionApproval) -> Path:
    """Write the sidecar atomically beside the PDF, as the intake pipeline expects it."""
    sidecar_path = pdf_path.with_suffix(pdf_path.suffix + ".source.json")
    temporary_path = sidecar_path.with_suffix(sidecar_path.suffix + ".tmp")
    try:
        temporary_path.write_text(approval.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary_path, sidecar_path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        raise
    return sidecar_path


def main() -> None:
    """Generate one rights sidecar from a saved license profile for one exact PDF."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="profile_id from the profiles file.")
    parser.add_argument("--pdf", type=Path, required=True, help="Exact PDF to approve.")
    parser.add_argument("--reviewed-by", required=True, help="Person confirming this file.")
    parser.add_argument(
        "--reviewed-on",
        type=date.fromisoformat,
        default=date.today(),
        help="ISO date; defaults to today.",
    )
    parser.add_argument(
        "--content-reviewed",
        action="store_true",
        help="Confirm you have checked this file's extracted item content.",
    )
    parser.add_argument(
        "--study-metadata-reviewed",
        action="store_true",
        help="Confirm you have checked this file's validation-study citation metadata.",
    )
    parser.add_argument("--source-url", help="Overrides the profile's license URL as the source.")
    parser.add_argument("--profiles-file", type=Path, default=DEFAULT_PROFILES_PATH)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        profiles = load_profiles(arguments.profiles_file)
        if arguments.profile not in profiles:
            raise LicenseProfileError(
                f"Unknown profile {arguments.profile!r}; available: {sorted(profiles)}"
            )
        approval = build_rights_sidecar(
            profiles[arguments.profile],
            arguments.pdf,
            reviewed_by=arguments.reviewed_by,
            reviewed_on=arguments.reviewed_on,
            questionnaire_content_reviewed=arguments.content_reviewed,
            study_metadata_reviewed=arguments.study_metadata_reviewed,
            source_url=arguments.source_url,
        )
        sidecar_path = write_sidecar(arguments.pdf, approval)
    except (LicenseProfileError, ValidationError) as error:
        LOGGER.error("Could not generate rights sidecar: %s", error)
        raise SystemExit(1) from None

    LOGGER.info("Wrote rights sidecar %s", sidecar_path)
    if not arguments.content_reviewed and not arguments.study_metadata_reviewed:
        LOGGER.warning(
            "Neither --content-reviewed nor --study-metadata-reviewed was set; "
            "the intake pipeline will not promote this draft yet."
        )


if __name__ == "__main__":
    main()
