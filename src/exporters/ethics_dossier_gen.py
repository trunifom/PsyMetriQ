"""Assemble a battery ethics/IRB planning dossier from existing catalog metadata.

This never invents ethics text, consent wording, or legal advice. It only
compiles source-grounded fields already present on selected
``QuestionnaireParent``/``QuestionnaireVersion`` records -- licensing and
permission basis, citations, target populations, COSMIN metrics -- plus the
completion-time estimate from ``battery_time_estimator``, into one Markdown
document a researcher can paste into or attach to an ethics-committee
submission. A missing field is rendered as ``"Nicht dokumentiert"`` rather
than guessed, matching the catalog's existing convention (see
``docs/instrument_library.md``): it means the catalog record has not yet
supplied a source-grounded statement, not that the information does not
exist. The document always opens with an explicit disclaimer that it is a
planning aid, not legal or ethical advice, and that every field must be
verified against the current source before submission.
"""

from __future__ import annotations

from datetime import date

from schemas.questionnaire_schema import QuestionnaireParent, QuestionnaireVersion
from src.core.battery_time_estimator import estimate_battery_time, estimate_version_time

_NOT_DOCUMENTED = "Nicht dokumentiert"


class EthicsDossierError(RuntimeError):
    """Raised when a battery cannot be assembled into an ethics dossier."""


def _yes_no(value: bool | None) -> str:
    if value is None:
        return _NOT_DOCUMENTED
    return "Ja" if value else "Nein"


def _license_summary(version: QuestionnaireVersion) -> str:
    form_documents = [
        document
        for document in version.source_documents
        if document.document_type == "questionnaire_form"
    ]
    documents = form_documents or version.source_documents
    if not documents:
        return _NOT_DOCUMENTED
    parts: list[str] = []
    for document in documents:
        permission = (
            "Weitergabe/Nutzung laut Quelle erlaubt"
            if document.redistribution_permitted
            else "Weitergabe/Nutzung laut Quelle eingeschraenkt oder nicht erlaubt"
        )
        parts.append(f"{document.license_name} ({permission}; Basis: {document.permission_basis})")
    return "; ".join(parts)


def _citation_summary(version: QuestionnaireVersion) -> str:
    parts: list[str] = []
    if version.source_citation:
        parts.append(version.source_citation)
    if version.publication_year:
        parts.append(f"Jahr: {version.publication_year}")
    if version.source_doi:
        parts.append(f"DOI: {version.source_doi}")
    return "; ".join(parts) if parts else _NOT_DOCUMENTED


def _format_age(value: float | None) -> str:
    if value is None:
        return "?"
    return str(int(value)) if value == int(value) else str(value)


def _population_summary(version: QuestionnaireVersion) -> str:
    if not version.target_populations:
        return _NOT_DOCUMENTED
    parts: list[str] = []
    for population in version.target_populations:
        age = ""
        if population.minimum_age_years is not None or population.maximum_age_years is not None:
            low = _format_age(population.minimum_age_years)
            high = _format_age(population.maximum_age_years)
            age = f", {low}-{high} Jahre"
        parts.append(f"{population.group_name}{age}")
    return "; ".join(parts)


def _cosmin_summary(version: QuestionnaireVersion) -> str:
    if not version.cosmin_metrics:
        return _NOT_DOCUMENTED
    return "; ".join(f"{key}: {value}" for key, value in version.cosmin_metrics.items())


def _time_estimate_line(
    minimum_minutes: float | None, maximum_minutes: float | None, basis: str
) -> str:
    if minimum_minutes is None:
        return "unbekannt"
    return f"ca. {minimum_minutes:.0f}–{maximum_minutes:.0f} Minuten ({basis})"


def build_ethics_dossier(
    selections: list[tuple[QuestionnaireParent, QuestionnaireVersion, list[str]]],
    *,
    project_name: str | None = None,
    project_description: str | None = None,
    generated_on: date | None = None,
) -> str:
    """Render a Markdown ethics/IRB planning dossier for a selected battery."""
    if not selections:
        raise EthicsDossierError("No versions selected; nothing to assemble into a dossier")

    generated = generated_on or date.today()
    battery = estimate_battery_time(selections)

    lines: list[str] = [
        f"# Fragebogenbatterie – Planungsübersicht ({generated.isoformat()})",
        "",
        "> **Hinweis:** Dieses Dokument fasst bereits im Katalog hinterlegte, "
        "quellenbasierte Angaben zusammen (Lizenz, Zitation, Populationsangaben, "
        "psychometrische Kennwerte, Bearbeitungszeit). Es ist eine Planungshilfe, "
        "keine Rechts- oder Ethikberatung, und ersetzt keine Ethikkommission. Jede "
        "Angabe muss vor Einreichung gegen die aktuelle Quelle geprüft werden; "
        f'"{_NOT_DOCUMENTED}" bedeutet nur, dass der Katalog dazu aktuell keine Angabe '
        "enthält, nicht dass die Information nicht existiert.",
        "",
    ]
    if project_name:
        lines.append(f"**Projekt:** {project_name}")
    if project_description:
        lines.append(f"**Beschreibung:** {project_description}")
    if project_name or project_description:
        lines.append("")

    total_items = sum(
        len(item_ids) if item_ids else len(version.items) for _, version, item_ids in selections
    )
    lines.append(f"**Anzahl Instrumente:** {len(selections)}")
    lines.append(f"**Anzahl Items (ausgewählt):** {total_items}")
    battery_basis = (
        "Summe"
        if not battery.has_unknown_entries
        else "Summe, ohne Instrument(e) mit unbekannter Zeit"
    )
    lines.append(
        f"**Geschätzte Gesamtbearbeitungszeit:** "
        f"{_time_estimate_line(battery.minimum_minutes, battery.maximum_minutes, battery_basis)}"
    )
    lines.append("")

    for family, version, item_ids in selections:
        time_estimate = estimate_version_time(family, version, item_ids)
        time_basis = {
            "source_reported": "Quellenangabe",
            "heuristic_item_count": "Schätzung",
            "unknown": "unbekannt",
        }[time_estimate.source]
        selected_count = len(item_ids) if item_ids else len(version.items)
        total_count = len(version.items) or version.source_reported_item_count or selected_count

        lines.append(f"## {family.name_full} ({version.display_name or version.version_id})")
        lines.append("")
        lines.append(
            f"- **Instrument-ID / Version-ID:** `{family.instrument_id}` / `{version.version_id}`"
        )
        locale_suffix = f" ({version.locale})" if version.locale else ""
        lines.append(f"- **Sprache/Locale:** {version.language}{locale_suffix}")
        lines.append(f"- **Formtyp:** {version.form_type}")
        item_count_line = f"- **Itemanzahl:** {selected_count} ausgewählt"
        if total_count and total_count != selected_count:
            item_count_line += f" von {total_count}"
        if not version.item_text_included:
            item_count_line += " (Metadatenreferenz, Itemtext nicht im Katalog enthalten)"
        lines.append(item_count_line)
        lines.append(
            "- **Geschätzte Bearbeitungszeit:** "
            + _time_estimate_line(
                time_estimate.minimum_minutes, time_estimate.maximum_minutes, time_basis
            )
        )
        lines.append(f"- **Kommerzielle Nutzung eingeschränkt:** {_yes_no(family.is_commercial)}")
        lines.append(f"- **Lizenz/Rechtebasis:** {_license_summary(version)}")
        lines.append(f"- **Zitation:** {_citation_summary(version)}")
        lines.append(f"- **Zielpopulation(en):** {_population_summary(version)}")
        lines.append(f"- **Psychometrische Kennwerte:** {_cosmin_summary(version)}")
        if version.psychometric_summary:
            lines.append(f"- **Zusammenfassung:** {version.psychometric_summary}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"
