# ruff: noqa: E501 -- Long UI help sentences are kept intact for readable dialogs.
"""Flet workspace for questionnaire discovery, curation, import, and export."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import flet as ft
from dotenv import load_dotenv
from pydantic import ValidationError

from schemas.questionnaire_schema import QuestionnaireParent, QuestionnaireVersion
from src.core.battery_time_estimator import estimate_battery_time, estimate_version_time
from src.core.external_sources import ExternalSourceError, NIHCDEClient, PubMedClient
from src.core.nlp_engine import NLPEngineError, find_matching_instruments, find_similar_constructs
from src.exporters.data_exchange import (
    DataExchangeError,
    build_redcap_metadata_records,
    export_questionnaire,
    import_questionnaire_content,
    import_questionnaire_file,
    select_questionnaire_items,
)
from src.exporters.ethics_dossier_gen import EthicsDossierError, build_ethics_dossier
from src.exporters.redcap_api import (
    RedcapApiError,
    RedcapProjectSummary,
    pull_questionnaire_from_project,
    push_questionnaire_to_project,
)
from src.exporters.redcap_api import connect as redcap_connect
from src.exporters.redcap_api import describe_project as redcap_describe_project
from src.gui.admin_config import AdminConfig, AdminConfigError, AdminConfigStore
from src.gui.catalog_store import CatalogStoreError, QuestionnaireCatalogStore
from src.gui.views import dashboard as dashboard_view
from src.gui.workspace import (
    ItemAdaptation,
    VersionSelection,
    WorkspacePersistenceError,
    WorkspaceProject,
    WorkspaceSettings,
    WorkspaceStore,
)
from src.ingestion.provider_models import ModelDiscoveryError, list_available_models
from src.ingestion.zotero_source import (
    ZoteroSourceError,
    ZoteroSyncConfig,
    push_questionnaire_to_zotero,
)

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PROJECT_ROOT / "data" / "psymetriq-settings.json"
ADMIN_CONFIG_PATH = Path(
    os.environ.get("PSYMETRIQ_ADMIN_CONFIG_PATH", str(PROJECT_ROOT / "data" / "admin_config.json"))
)
DEFAULT_INBOX = PROJECT_ROOT / "data" / "questionnaires" / "inbox"
DEFAULT_REVIEW = PROJECT_ROOT / "data" / "questionnaires" / "review"
EXPORT_FORMATS = {
    "PsyMetriQ JSON": "psymetriq_json",
    "FHIR R4 Questionnaire JSON": "fhir_json",
    "XLSX Arbeitsmappe": "xlsx",
    "Item CSV": "item_csv",
    "REDCap Data Dictionary CSV": "redcap_csv",
    "R-Scoring-Syntax": "r_syntax",
    "LimeSurvey TSV (Best-Effort, unverifiziert)": "limesurvey_tsv",
    "Unipark Paste-Text (Best-Effort, nur Text/Auswahl)": "unipark_txt",
    "Qualtrics QSF (Best-Effort, unverifiziert)": "qualtrics_qsf",
}
LIGHT_DARK_COLORS = {
    "#F3F6F5": "#111B19",
    "#153C36": "#102A25",
    "#173D36": "#E0ECE8",
    "#1B4941": "#193A34",
    "#203F39": "#DDE9E5",
    "#28685D": "#2B7768",
    "#36554E": "#BFCFC9",
    "#55716A": "#AEC2BB",
    "#8A4A2E": "#E5A783",
    "#9B3E35": "#F0A098",
    "#C4D8D2": "#C4D8D2",
    "#D7E8E3": "#D7E8E3",
    "#DDE6E3": "#354742",
    "#E8EFEC": "#1C2B27",
    "#EEF3F1": "#293834",
    "#F7F9F8": "#202E2A",
    "#FFFFFF": "#192622",
    "#146B5A": "#278471",
}
FONT_SIZE_SCALE = {"small": 0.88, "normal": 1.0, "large": 1.18}


def _icon(name: str) -> Any:
    """Resolve an optional icon name across Flet/Material icon-set revisions."""
    return getattr(ft.Icons, name, ft.Icons.INFO_OUTLINE)


def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _safe_filename(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_-")
    return safe[:80] or "questionnaire"


AGE_GROUP_RANGES: dict[str, tuple[int, int | None]] = {
    "children": (0, 11),
    "adolescents": (12, 17),
    "adults": (18, 64),
    "older_adults": (65, None),
}
AGE_GROUP_LABELS = {
    "children": "Kinder (0-11)",
    "adolescents": "Jugendliche (12-17)",
    "adults": "Erwachsene (18-64)",
    "older_adults": "Ältere Erwachsene (65+)",
    "unknown": "Altersangabe unbekannt",
}
POPULATION_AGE_KEYWORDS = {
    "children": ("child", "children", "pediatric", "paediatric", "kind", "kinder"),
    "adolescents": ("adolescent", "youth", "teen", "jugend", "schüler", "schueler"),
    "adults": ("adult", "erwachsen", "general population", "allgemeinbevölkerung"),
    "older_adults": ("older adult", "elderly", "senior", "ältere", "aeltere"),
}


def _population_age_groups(group_name: str) -> set[str]:
    normalized = group_name.casefold()
    return {
        group
        for group, keywords in POPULATION_AGE_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    }


class PsyMetriQApplication:
    """Own UI state and connect Flet views to validated local services."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.page.title = "PsyMetriQ | Questionnaire Workspace"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        self.page.bgcolor = "#F3F6F5"
        self.page.window.min_width = 900
        self.page.window.min_height = 650

        self.workspace_store = WorkspaceStore(SETTINGS_PATH)
        self.startup_warning: str | None = None
        try:
            self.settings = self.workspace_store.load_settings()
        except WorkspacePersistenceError as error:
            self.settings = WorkspaceSettings()
            self.startup_warning = str(error) + "; Standardwerte werden verwendet."

        self.admin_config_store = AdminConfigStore(ADMIN_CONFIG_PATH)
        try:
            self.admin_config = self.admin_config_store.load()
        except AdminConfigError as error:
            self.admin_config = AdminConfig()
            admin_warning = str(error) + "; Admin-Standardwerte werden verwendet."
            self.startup_warning = (
                f"{self.startup_warning}; {admin_warning}"
                if self.startup_warning
                else admin_warning
            )
        self.dark_mode = self.settings.theme_mode == "dark"
        self.font_size = self.settings.font_size
        self._font_size_bases: dict[int, tuple[Any, float]] = {}
        self.catalog_store = QuestionnaireCatalogStore(
            _resolve_path(self.settings.catalogue_directory)
        )
        self.catalog_records: list[tuple[QuestionnaireParent, Path]] = []
        self.catalog_error: str | None = None
        self.active_version_key: tuple[str, str] | None = None
        self._reload_catalog(silent=True)
        LOGGER.info(
            "GUI catalog initialized: families=%d versions=%d error=%s",
            len(self.catalog_records),
            sum(len(family.versions) for family, _path in self.catalog_records),
            self.catalog_error is not None,
        )

        self.project = WorkspaceProject(
            name="Neues Projekt",
            catalogue_directory=self.settings.catalogue_directory,
        )
        self.project_path: Path | None = None
        default_visible_views = [
            view
            for view in ("catalog", "research", "project", "exchange", "intake", "settings")
            if view not in self.admin_config.hidden_views
        ]
        self.active_view = default_visible_views[0] if default_visible_views else "catalog"
        self.search_query = ""
        self.language_filter = "all"
        self.locale_filter = "all"
        self.form_type_filter = "all"
        self.form_type_filters: set[str] = set()
        self.population_filter = "all"
        self.population_filters: set[str] = set()
        self.commercial_filter = "all"
        self.commercial_filters: set[str] = set()
        self.license_filter = "all"
        self.item_content_filter = "with_items"
        self.export_format = self.settings.default_export_format
        self.redcap_project: Any = None
        self.redcap_project_summary: RedcapProjectSummary | None = None
        self.redcap_status_message = "Nicht verbunden."
        self.similarity_matches: list[Any] | None = None
        self.similarity_status = "Noch nicht ausgeführt."
        self.research_query = ""
        self.research_matches: list[Any] | None = None
        self.research_status = "Noch keine Recherche durchgeführt."
        self.research_external_candidates: list[Any] | None = None
        self.research_external_evidence: list[Any] | None = None
        self.research_external_status = "Noch keine externe Recherche durchgeführt."
        self.available_models: list[str] = []
        self.active_provider = self.settings.llm_provider
        self.status_message = self.startup_warning or self._catalog_status()
        self.status_is_error = bool(self.startup_warning or self.catalog_error)

        self.file_picker = ft.FilePicker()
        self.page.services.append(self.file_picker)
        self.content_host = ft.Column(expand=True, spacing=0, scroll=ft.ScrollMode.AUTO)
        self.status_text = ft.Text(size=12, color="#36554E")
        self.nav_buttons: dict[str, ft.Button] = {}
        self._build_shell()
        self._render()

    def _build_shell(self) -> None:
        self.page.add(
            ft.Row(
                expand=True,
                spacing=0,
                controls=[
                    ft.Container(
                        width=232,
                        bgcolor="#153C36",
                        padding=ft.Padding(left=14, top=18, right=12, bottom=14),
                        content=self._build_sidebar(),
                    ),
                    ft.VerticalDivider(width=1, color="#DDE6E3"),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            self._build_header(),
                            ft.Container(
                                expand=True,
                                padding=ft.Padding(left=24, top=20, right=24, bottom=12),
                                content=self.content_host,
                            ),
                            ft.Container(
                                padding=ft.Padding(left=24, top=8, right=24, bottom=12),
                                content=self.status_text,
                                bgcolor="#E8EFEC",
                            ),
                        ],
                    ),
                ],
            )
        )

    def _build_sidebar(self) -> ft.Control:
        destinations = [
            ("catalog", "Bibliothek", "LIBRARY_BOOKS", "Katalog durchsuchen und Items auswählen."),
            (
                "research",
                "Recherche",
                "TRAVEL_EXPLORE",
                "Passende Instrumente zu einer Fragestellung oder einem Konstrukt finden.",
            ),
            (
                "project",
                "Projekt",
                "WORKSPACES_OUTLINED",
                "Ausgewählte Versionen und Item-Schritte speichern oder laden.",
            ),
            (
                "exchange",
                "Import & Export",
                "IMPORT_EXPORT",
                "JSON, FHIR, REDCap oder CSV einlesen und exportieren.",
            ),
            (
                "intake",
                "PDF-Posteingang",
                "PICTURE_AS_PDF_OUTLINED",
                "Lokale PDF-Dateien prüfen und bei expliziter Freigabe optional LLM-Extraktion starten.",
            ),
            (
                "settings",
                "Einstellungen",
                "TUNE",
                "Katalogpfade, Exportstandard und optionale LLM-Konfiguration verwalten.",
            ),
        ]
        rows: list[ft.Control] = [
            ft.Text("PsyMetriQ", size=24, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ft.Text("Questionnaire workspace", size=12, color="#C4D8D2"),
            ft.Container(height=16),
        ]
        for view, label, icon_name, description in destinations:
            if view in self.admin_config.hidden_views:
                continue
            rows.append(self._nav_button(view, label, icon_name, description))
        rows.extend(
            [
                ft.Container(expand=True),
                ft.Text("Lokale Arbeitsumgebung", size=11, color="#C4D8D2"),
                ft.Text("Keine Datenbank erforderlich", size=11, color="#C4D8D2"),
            ]
        )
        return ft.Column(expand=True, spacing=8, controls=rows)

    def _nav_button(self, view: str, label: str, icon_name: str, explanation: str) -> ft.Control:
        selected = self.active_view == view
        button = ft.Button(
            expand=True,
            content=ft.Text(label, color="#FFFFFF"),
            icon=_icon(icon_name),
            icon_color="#D7E8E3",
            bgcolor="#28685D" if selected else "#1B4941",
            on_click=lambda _event, target=view: self._navigate(target),
            tooltip=label,
        )
        self.nav_buttons[view] = button
        return ft.Row(
            spacing=2,
            controls=[
                button,
                self._help_button(label, explanation),
            ],
        )

    def _build_header(self) -> ft.Control:
        self.header_title = ft.Text(size=22, weight=ft.FontWeight.BOLD, color="#173D36")
        self.header_summary = ft.Text(size=12, color="#55716A")
        return ft.Container(
            bgcolor="#FFFFFF",
            padding=ft.Padding(left=24, top=16, right=24, bottom=14),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            self.header_title,
                            self.header_summary,
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Text(
                                Path(self.settings.catalogue_directory).name or "Katalog",
                                size=12,
                                color="#55716A",
                            ),
                            self._help_button(
                                "Dunkles Design" if not self.dark_mode else "Helles Design",
                                "Wechselt zwischen hellem und dunklem Farbschema. Die Auswahl wird lokal gespeichert.",
                            ),
                            self._appearance_theme_button(),
                            self._help_button(
                                "Aktiver Katalog",
                                "Der Katalog ist ein Ordner mit validierten PsyMetriQ-JSON-Dateien. "
                                "Der vollständige Pfad und weitere Optionen stehen unter Einstellungen.",
                                "Beispiel: data/questionnaires/json",
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _appearance_theme_button(self) -> ft.IconButton:
        self.theme_button = ft.IconButton(
            icon=_icon("DARK_MODE" if not self.dark_mode else "LIGHT_MODE"),
            tooltip="Dunkles Design aktivieren"
            if not self.dark_mode
            else "Helles Design aktivieren",
            on_click=self._toggle_dark_mode,
        )
        return self.theme_button

    def _iter_controls(self, value: Any):
        if isinstance(value, ft.Control):
            yield value
            for attribute in ("content", "controls", "actions", "overlay"):
                child = getattr(value, attribute, None)
                if child is not None:
                    yield from self._iter_controls(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from self._iter_controls(child)

    def _apply_appearance(self, root: Any | None = None) -> None:
        scale = FONT_SIZE_SCALE[self.font_size]
        text_theme = ft.TextTheme(
            body_large=ft.TextStyle(size=16 * scale),
            body_medium=ft.TextStyle(size=14 * scale),
            body_small=ft.TextStyle(size=12 * scale),
            label_large=ft.TextStyle(size=14 * scale),
            label_medium=ft.TextStyle(size=12 * scale),
            label_small=ft.TextStyle(size=11 * scale),
            title_large=ft.TextStyle(size=22 * scale),
            title_medium=ft.TextStyle(size=16 * scale),
            title_small=ft.TextStyle(size=14 * scale),
        )
        self.page.theme_mode = ft.ThemeMode.DARK if self.dark_mode else ft.ThemeMode.LIGHT
        self.page.theme = ft.Theme(color_scheme_seed="#146B5A", text_theme=text_theme)
        self.page.dark_theme = ft.Theme(color_scheme_seed="#39A994", text_theme=text_theme)
        self.page.bgcolor = "#111B19" if self.dark_mode else "#F3F6F5"

        palette = (
            LIGHT_DARK_COLORS
            if self.dark_mode
            else {dark: light for light, dark in LIGHT_DARK_COLORS.items()}
        )
        seen_font_controls: set[int] = set()
        appearance_root = (
            (self.page.controls, getattr(self.page, "overlay", [])) if root is None else root
        )
        for control in self._iter_controls(appearance_root):
            for attribute in ("color", "bgcolor", "icon_color"):
                value = getattr(control, attribute, None)
                if isinstance(value, str) and value.upper() in palette:
                    setattr(control, attribute, palette[value.upper()])
            if isinstance(control, (ft.Text, ft.TextField, ft.Dropdown)):
                attribute = "size" if isinstance(control, ft.Text) else "text_size"
                value = getattr(control, attribute, None)
                if isinstance(value, (int, float)):
                    control_id = id(control)
                    cached = self._font_size_bases.get(control_id)
                    base_size = (
                        cached[1] if cached is not None and cached[0] is control else float(value)
                    )
                    self._font_size_bases[control_id] = (control, base_size)
                    seen_font_controls.add(control_id)
                    setattr(control, attribute, base_size * scale)
        self._font_size_bases = {
            control_id: cached
            for control_id, cached in self._font_size_bases.items()
            if control_id in seen_font_controls
        }
        self.theme_button.icon = _icon("LIGHT_MODE" if self.dark_mode else "DARK_MODE")
        self.theme_button.tooltip = (
            "Helles Design aktivieren" if self.dark_mode else "Dunkles Design aktivieren"
        )

    def _show_dialog(self, dialog: ft.AlertDialog) -> None:
        self.page.show_dialog(dialog)
        self._apply_appearance(dialog)
        self.page.update()

    def _requires_license_acknowledgment(self, family: QuestionnaireParent) -> bool:
        """Gate only definitely commercial instruments; unclear/free ones stay frictionless.

        An administrator can disable this gate deployment-wide (test/debug, or a
        trusted single-admin deployment) via ``admin_config.json``; that never
        changes what the intake pipeline treats as a rights-approved document.
        Listing an instrument_id under ``institutionally_licensed_instruments``
        skips the per-user click-through for exactly that instrument, for every
        user -- e.g. once a librarian has confirmed a valid institutional
        license -- while every other commercial instrument still gates normally.
        """
        if not self.admin_config.license_acknowledgment_enabled:
            return False
        if family.instrument_id in self.admin_config.institutionally_licensed_instruments:
            return False
        return family.is_commercial is True

    def _is_license_acknowledged(self, family: QuestionnaireParent) -> bool:
        return family.instrument_id in self.settings.acknowledged_licenses

    def _is_institutionally_licensed(self, family: QuestionnaireParent) -> bool:
        return family.instrument_id in self.admin_config.institutionally_licensed_instruments

    def _remote_processing_enabled(self) -> bool:
        """Combine the per-installation preference with the admin's kill switch."""
        return (
            self.settings.remote_processing_enabled and self.admin_config.remote_processing_allowed
        )

    @staticmethod
    def _primary_license_source(version: QuestionnaireVersion) -> Any:
        return version.source_documents[0] if version.source_documents else None

    async def _acknowledge_license(self, family: QuestionnaireParent) -> None:
        """Persist a local, one-time confirmation that license terms were read."""
        self.settings = self.settings.model_copy(
            update={
                "acknowledged_licenses": {
                    **self.settings.acknowledged_licenses,
                    family.instrument_id: datetime.now(timezone.utc).isoformat(),
                }
            }
        )
        try:
            await asyncio.to_thread(self.workspace_store.save_settings, self.settings)
        except WorkspacePersistenceError as error:
            LOGGER.warning("Could not persist license acknowledgment (%s)", type(error).__name__)

    def _show_license_gate_dialog(
        self,
        family: QuestionnaireParent,
        version: QuestionnaireVersion,
        on_confirmed: Callable[[], None],
    ) -> None:
        """Ask for a one-time, per-instrument license acknowledgment before use.

        This does not grant redistribution rights: it records that the local
        user has read and will follow the license terms for a commercially
        restricted instrument they already have institutional/study access to
        (for example through a licensed test library). It is asked once per
        instrument per local installation, not on every view or selection.
        """
        source = self._primary_license_source(version)
        license_name = source.license_name if source else "Lizenz nicht dokumentiert"
        license_url = str(source.license_url) if source and source.license_url else None
        permission_basis = source.permission_basis if source else None

        confirm_button = ft.Button(content="Bestätigen und fortfahren", disabled=True)

        def _on_agree_change(event: Any) -> None:
            confirm_button.disabled = not bool(event.control.value)
            self.page.update()

        agree_checkbox = ft.Checkbox(
            label="Ich habe die Lizenzbestimmungen gelesen und halte mich daran.",
            value=False,
            on_change=_on_agree_change,
        )

        async def _confirm(_event: Any) -> None:
            await self._acknowledge_license(family)
            self.page.pop_dialog()
            on_confirmed()

        confirm_button.on_click = _confirm

        contents: list[ft.Control] = [
            ft.Text(
                f"{family.name_full} ist lizenzpflichtig. Bestätige, dass du Zugriff über eine "
                "gültige Lizenz hast (z. B. eine institutionelle Testbibliothek oder einen für "
                "diese Studie erworbenen Zugang) und dich an deren Bedingungen hältst.",
                size=13,
            ),
            ft.Text(f"Lizenz/Status: {license_name}", size=12, weight=ft.FontWeight.BOLD),
        ]
        if permission_basis:
            contents.append(ft.Text(permission_basis, size=12, color="#55716A", selectable=True))
        if license_url:
            contents.append(ft.Text(license_url, size=12, color="#28685D", selectable=True))
        contents.append(agree_checkbox)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Lizenzbestimmungen bestätigen"),
            content=ft.Column(tight=True, spacing=10, controls=contents),
            actions=[
                ft.Button(content="Abbrechen", on_click=lambda _event: self.page.pop_dialog()),
                confirm_button,
            ],
        )
        self._show_dialog(dialog)

    async def _persist_appearance_preferences(self) -> None:
        self.settings = self.settings.model_copy(
            update={
                "theme_mode": "dark" if self.dark_mode else "light",
                "font_size": self.font_size,
            }
        )
        try:
            await asyncio.to_thread(self.workspace_store.save_settings, self.settings)
            self._set_status("Darstellungseinstellungen lokal gespeichert.")
        except WorkspacePersistenceError as error:
            LOGGER.warning("Could not persist appearance preferences (%s)", type(error).__name__)
            self._set_status(f"Darstellung nicht gespeichert: {error}", error=True)

    async def _toggle_dark_mode(self, _event: Any) -> None:
        self.dark_mode = not self.dark_mode
        self._render()
        await self._persist_appearance_preferences()

    async def _set_dark_mode(self, event: Any) -> None:
        self.dark_mode = bool(event.control.value)
        self._render()
        await self._persist_appearance_preferences()

    async def _set_font_size(self, event: Any) -> None:
        self.font_size = event.control.value
        self._render()
        await self._persist_appearance_preferences()

    def _render(self) -> None:
        LOGGER.debug(
            "Rendering GUI view=%s families=%d selections=%d",
            self.active_view,
            len(self.catalog_records),
            len(self.project.selections),
        )
        titles = {
            "catalog": "Instrumentenbibliothek",
            "research": "Instrumentenrecherche",
            "project": "Projekt und Auswahl",
            "exchange": "Import und Export",
            "intake": "PDF-Posteingang",
            "settings": "Einstellungen",
        }
        self.header_title.value = titles[self.active_view]
        self.header_summary.value = (
            f"{len(self.catalog_records)} Instrumentfamilien · "
            f"{len(self.project.selections)} Versionen im Projekt"
        )
        for view, button in self.nav_buttons.items():
            button.bgcolor = "#28685D" if self.active_view == view else "#1B4941"
        try:
            view_controls = {
                "catalog": self._catalog_view,
                "research": self._research_view,
                "project": self._project_view,
                "exchange": self._exchange_view,
                "intake": self._intake_view,
                "settings": self._settings_view,
            }[self.active_view]()
        except Exception:
            LOGGER.exception("GUI view construction failed: view=%s", self.active_view)
            raise
        self.content_host.controls = view_controls
        self.status_text.value = self.status_message
        self.status_text.color = "#9B3E35" if self.status_is_error else "#36554E"
        self._apply_appearance()
        try:
            self.page.update()
        except Exception:
            LOGGER.exception("Flet page update failed for view=%s", self.active_view)
            raise

    def _navigate(self, view: str) -> None:
        if view in self.admin_config.hidden_views:
            LOGGER.warning("Ignored navigation to admin-hidden view=%s", view)
            return
        self.active_view = view
        self._render()

    def _show_help(self, title: str, explanation: str, example: str = "") -> None:
        contents: list[ft.Control] = [ft.Text(explanation, size=14, selectable=True)]
        if example:
            contents.extend(
                [
                    ft.Text("Beispiel", size=12, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        padding=10,
                        border_radius=6,
                        bgcolor="#EEF3F1",
                        content=ft.Text(example, size=12, selectable=True),
                    ),
                ]
            )
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Column(tight=True, spacing=12, controls=contents),
            actions=[
                ft.Button(
                    content="Schließen",
                    on_click=lambda _event: self.page.pop_dialog(),
                )
            ],
        )
        self._show_dialog(dialog)

    def _help_button(self, title: str, explanation: str, example: str = "") -> ft.Control:
        return ft.IconButton(
            icon=_icon("INFO_OUTLINE"),
            icon_size=18,
            tooltip=f"Hilfe zu {title} öffnen",
            on_click=lambda _event: self._show_help(title, explanation, example),
        )

    def _action_button(
        self,
        label: str,
        icon_name: str,
        on_click: Any,
        explanation: str,
        example: str = "",
        *,
        primary: bool = False,
        disabled: bool = False,
    ) -> ft.Control:
        return ft.Row(
            spacing=2,
            controls=[
                ft.Button(
                    content=label,
                    icon=_icon(icon_name),
                    bgcolor="#146B5A" if primary else "#FFFFFF",
                    color="#FFFFFF" if primary else "#173D36",
                    disabled=disabled,
                    on_click=on_click,
                    tooltip=label,
                ),
                self._help_button(label, explanation, example),
            ],
        )

    def _field(
        self,
        label: str,
        control: ft.Control,
        explanation: str,
        example: str = "",
    ) -> ft.Control:
        is_material_field = isinstance(control, (ft.TextField, ft.Dropdown))
        if is_material_field:
            control.label = label
        return ft.Column(
            spacing=5,
            controls=[
                ft.Row(
                    spacing=2,
                    controls=[
                        *(
                            []
                            if is_material_field
                            else [
                                ft.Text(
                                    label,
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color="#203F39",
                                )
                            ]
                        ),
                        self._help_button(label, explanation, example),
                    ],
                ),
                control,
            ],
        )

    def _panel(self, title: str, content: ft.Control, help_text: str) -> ft.Control:
        return ft.Container(
            bgcolor="#FFFFFF",
            border_radius=8,
            padding=14,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color="#173D36"),
                            self._help_button(title, help_text),
                        ],
                    ),
                    content,
                ],
            ),
        )

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status_message = message
        self.status_is_error = error
        self.status_text.value = message
        self.status_text.color = "#9B3E35" if error else "#36554E"
        self.page.update()

    def _catalog_status(self) -> str:
        if self.catalog_error:
            return self.catalog_error
        return f"Katalog geladen: {len(self.catalog_records)} Instrumentfamilien."

    def _reload_catalog(self, *, silent: bool = False) -> None:
        new_store = QuestionnaireCatalogStore(_resolve_path(self.settings.catalogue_directory))
        try:
            loaded = new_store.load()
        except CatalogStoreError as error:
            self.catalog_error = str(error)
            LOGGER.exception(
                "GUI catalog reload failed (silent=%s, records_retained=%d)",
                silent,
                len(self.catalog_records),
            )
            if not silent:
                self._set_status(self.catalog_error, error=True)
            return
        self.catalog_store = new_store
        self.catalog_records = loaded
        self.catalog_error = None
        LOGGER.info(
            "GUI catalog loaded: families=%d versions=%d directory=%s",
            len(loaded),
            sum(len(family.versions) for family, _path in loaded),
            _relative_path(new_store.directory),
        )
        if self.active_version_key and not self._find_version(*self.active_version_key):
            self.active_version_key = None
        if not silent:
            self._set_status(self._catalog_status())

    def _find_family(self, instrument_id: str) -> QuestionnaireParent | None:
        return next(
            (
                family
                for family, _path in self.catalog_records
                if family.instrument_id == instrument_id
            ),
            None,
        )

    def _find_version(
        self, instrument_id: str, version_id: str
    ) -> tuple[QuestionnaireParent, QuestionnaireVersion] | None:
        family = self._find_family(instrument_id)
        if family is None:
            return None
        version = next((value for value in family.versions if value.version_id == version_id), None)
        return (family, version) if version is not None else None

    @staticmethod
    def _matches_language_filter(version: QuestionnaireVersion, selected: str) -> bool:
        """Match a language subtag broadly, but match a selected regional tag exactly."""
        selected = selected.casefold()
        language = version.language.casefold()
        locale = (version.locale or "").casefold()
        if "-" in selected:
            return selected in {language, locale}
        return any(
            value == selected or value.startswith(f"{selected}-")
            for value in (language, locale)
            if value
        )

    @staticmethod
    def _matches_population_filter(version: QuestionnaireVersion, selected: str) -> bool:
        """Match source-reported age ranges against broad researcher-facing age bands."""
        populations = version.target_populations
        if selected == "unknown":
            return not populations or all(
                population.minimum_age_years is None
                and population.maximum_age_years is None
                and not _population_age_groups(population.group_name)
                for population in populations
            )

        selected_bounds = AGE_GROUP_RANGES.get(selected)
        if selected_bounds is None:
            return False
        selected_minimum, selected_maximum = selected_bounds
        selected_upper = float("inf") if selected_maximum is None else selected_maximum
        for population in populations:
            if population.minimum_age_years is None and population.maximum_age_years is None:
                if selected in _population_age_groups(population.group_name):
                    return True
                continue
            minimum = 0 if population.minimum_age_years is None else population.minimum_age_years
            maximum = (
                float("inf")
                if population.maximum_age_years is None
                else population.maximum_age_years
            )
            if minimum <= selected_upper and maximum >= selected_minimum:
                return True
        return False

    def _selected_population_filters(self) -> set[str]:
        """Return multi-select age filters while accepting the legacy scalar state."""
        selected = getattr(self, "population_filters", set())
        if selected:
            return set(selected)
        legacy = getattr(self, "population_filter", "all")
        return set() if legacy == "all" else {legacy}

    def _set_population_filter(self, group: str, selected: bool) -> None:
        selected_groups = self._selected_population_filters()
        if selected:
            selected_groups.add(group)
        else:
            selected_groups.discard(group)
        self.population_filters = selected_groups
        self.population_filter = "all"
        self._render()

    def _selected_form_type_filters(self) -> set[str]:
        selected = getattr(self, "form_type_filters", set())
        if selected:
            return set(selected)
        legacy = getattr(self, "form_type_filter", "all")
        return set() if legacy == "all" else {legacy}

    def _selected_commercial_filters(self) -> set[str]:
        selected = getattr(self, "commercial_filters", set())
        if selected:
            return set(selected)
        legacy = getattr(self, "commercial_filter", "all")
        return set() if legacy == "all" else {legacy}

    def _set_multi_catalog_filter(self, filter_name: str, value: str, selected: bool) -> None:
        attributes = {
            "form_type": ("form_type_filters", "form_type_filter"),
            "commercial": ("commercial_filters", "commercial_filter"),
        }
        selected_attribute, legacy_attribute = attributes[filter_name]
        selected_values = set(getattr(self, selected_attribute))
        if selected:
            selected_values.add(value)
        else:
            selected_values.discard(value)
        setattr(self, selected_attribute, selected_values)
        setattr(self, legacy_attribute, "all")
        self._render()

    def _reset_catalog_filters(self, _event: Any = None) -> None:
        self.search_query = ""
        self.language_filter = "all"
        self.locale_filter = "all"
        self.form_type_filter = "all"
        self.form_type_filters = set()
        self.population_filter = "all"
        self.population_filters = set()
        self.commercial_filter = "all"
        self.commercial_filters = set()
        self.license_filter = "all"
        self.item_content_filter = "with_items"
        self._render()

    def _active_catalog_filter_summary(self) -> str:
        active: list[str] = []
        if self.search_query.strip():
            active.append(f'Suche: "{self.search_query.strip()}"')
        if self.language_filter != "all":
            active.append(f"Sprache: {self.language_filter}")
        if self.locale_filter != "all":
            active.append(f"Locale: {self.locale_filter}")
        form_type_filters = self._selected_form_type_filters()
        if form_type_filters:
            active.append("Form: " + ", ".join(sorted(form_type_filters)))
        population_filters = self._selected_population_filters()
        if population_filters:
            active.append(
                "Alter: "
                + ", ".join(
                    AGE_GROUP_LABELS[group]
                    for group in AGE_GROUP_LABELS
                    if group in population_filters
                )
            )
        commercial_filters = self._selected_commercial_filters()
        if commercial_filters:
            active.append("Rechte: " + ", ".join(sorted(commercial_filters)))
        if self.license_filter != "all":
            active.append(f"Lizenz: {self.license_filter}")
        if self.item_content_filter != "with_items":
            active.append(f"Inhalt: {self.item_content_filter}")
        return " · ".join(active) if active else "Keine Filter aktiv"

    def _visible_versions(self) -> list[tuple[QuestionnaireParent, QuestionnaireVersion]]:
        query = self.search_query.strip().casefold()
        matches: list[tuple[QuestionnaireParent, QuestionnaireVersion]] = []
        for family, _path in self.catalog_records:
            for version in family.versions:
                if self.item_content_filter == "with_items" and not version.item_text_included:
                    continue
                if self.item_content_filter == "references" and version.item_text_included:
                    continue
                if self.language_filter != "all" and not self._matches_language_filter(
                    version, self.language_filter
                ):
                    continue
                if (
                    self.locale_filter != "all"
                    and (version.locale or "").casefold() != self.locale_filter
                ):
                    continue
                form_type_filters = self._selected_form_type_filters()
                if form_type_filters and version.form_type not in form_type_filters:
                    continue
                population_filters = self._selected_population_filters()
                if population_filters and not any(
                    self._matches_population_filter(version, selected)
                    for selected in population_filters
                ):
                    continue
                commercial_filters = self._selected_commercial_filters()
                if commercial_filters:
                    commercial_status = (
                        "commercial"
                        if family.is_commercial is True
                        else "noncommercial"
                        if family.is_commercial is False
                        else "unknown"
                    )
                    if commercial_status not in commercial_filters:
                        continue
                source_licenses = {
                    source.license_name.casefold() for source in version.source_documents
                }
                if self.license_filter == "undocumented" and source_licenses:
                    continue
                if (
                    self.license_filter not in {"all", "undocumented"}
                    and self.license_filter not in source_licenses
                ):
                    continue
                searchable = " ".join(
                    [
                        family.instrument_id,
                        family.name_full,
                        version.version_id,
                        version.display_name or "",
                        version.language,
                        version.locale or "",
                        version.source_citation or "",
                        version.source_doi or "",
                        family.metadata.description or "",
                        family.metadata.intended_use or "",
                        family.metadata.name_origin or "",
                        family.metadata.development_history or "",
                        family.metadata.measurement_rationale or "",
                        family.metadata.interpretation_notes or "",
                        version.metadata.description or "",
                        version.metadata.intended_use or "",
                        version.metadata.name_origin or "",
                        version.metadata.development_history or "",
                        version.metadata.measurement_rationale or "",
                        version.metadata.interpretation_notes or "",
                        *(family.metadata.keywords),
                        *(family.metadata.search_aliases),
                        *(version.metadata.keywords),
                        *(version.metadata.search_aliases),
                        version.metadata.notes or "",
                        *(population.group_name for population in version.target_populations),
                        *(contributor.name for contributor in family.contributors),
                        *(contributor.name for contributor in version.contributors),
                        *(version.source_reported_dimensions),
                        *(
                            value
                            for source in version.source_documents
                            for value in (
                                source.title,
                                source.license_name,
                                source.permission_basis,
                                str(source.source_url or ""),
                            )
                        ),
                        *(family.construct_ontology),
                        *(item.prompt_text for item in version.items),
                        *(item.dimension for item in version.items),
                        *(
                            option.label
                            for options in version.response_sets.values()
                            for option in options
                        ),
                    ]
                ).casefold()
                if not query or query in searchable:
                    matches.append((family, version))
        return matches

    def _project_selection(self, instrument_id: str, version_id: str) -> VersionSelection | None:
        return next(
            (
                selection
                for selection in self.project.selections
                if selection.instrument_id == instrument_id and selection.version_id == version_id
            ),
            None,
        )

    def _adaptations_for_selection(
        self, instrument_id: str, version_id: str
    ) -> dict[str, tuple[str, str]]:
        selection = self._project_selection(instrument_id, version_id)
        if selection is None:
            return {}
        return {
            adaptation.item_id: (adaptation.adapted_prompt_text, adaptation.reason)
            for adaptation in selection.item_adaptations
        }

    def _selected_item_ids(self, instrument_id: str, version: QuestionnaireVersion) -> set[str]:
        selection = self._project_selection(instrument_id, version.version_id)
        if selection is None or not selection.item_ids:
            return set() if selection is None else {item.item_id for item in version.items}
        return set(selection.item_ids)

    def _set_selection(
        self, selection: VersionSelection | None, instrument_id: str, version_id: str
    ) -> None:
        current = [
            entry
            for entry in self.project.selections
            if (entry.instrument_id, entry.version_id) != (instrument_id, version_id)
        ]
        if selection is not None:
            current.append(selection)
        self.project = self.project.model_copy(update={"selections": current})

    def _toggle_version(
        self, family: QuestionnaireParent, version: QuestionnaireVersion, selected: bool
    ) -> None:
        if (
            selected
            and version.item_text_included
            and self._requires_license_acknowledgment(family)
            and not self._is_license_acknowledged(family)
        ):
            self._show_license_gate_dialog(
                family, version, lambda f=family, v=version: self._toggle_version(f, v, True)
            )
            self._render()
            return
        current = self._project_selection(family.instrument_id, version.version_id)
        if selected:
            self._set_selection(
                VersionSelection(
                    instrument_id=family.instrument_id,
                    version_id=version.version_id,
                    item_adaptations=current.item_adaptations if current else [],
                ),
                family.instrument_id,
                version.version_id,
            )
            if current is None:
                self.project = self.project.record_step(
                    "version_selected",
                    f"Version ausgewählt: {family.instrument_id}/{version.version_id}",
                    f"{family.instrument_id}/{version.version_id}",
                )
        else:
            self._set_selection(None, family.instrument_id, version.version_id)
            self.project = self.project.record_step(
                "version_removed",
                f"Version entfernt: {family.instrument_id}/{version.version_id}",
                f"{family.instrument_id}/{version.version_id}",
            )
        self._render()

    def _toggle_item(
        self,
        family: QuestionnaireParent,
        version: QuestionnaireVersion,
        item_id: str,
        selected: bool,
    ) -> None:
        if (
            selected
            and self._requires_license_acknowledgment(family)
            and not self._is_license_acknowledged(family)
        ):
            self._show_license_gate_dialog(
                family,
                version,
                lambda f=family, v=version, i=item_id: self._toggle_item(f, v, i, True),
            )
            self._render()
            return
        selected_ids = self._selected_item_ids(family.instrument_id, version)
        if selected:
            selected_ids.add(item_id)
        else:
            selected_ids.discard(item_id)
        self._store_item_selection(
            family,
            version,
            selected_ids,
            action="items_updated",
            summary=f"Itemauswahl geändert: {family.instrument_id}/{version.version_id}",
        )

    def _toggle_item_group(
        self,
        family: QuestionnaireParent,
        version: QuestionnaireVersion,
        item_ids: list[str],
        selected: bool,
        *,
        is_scale: bool,
        label: str,
    ) -> None:
        if (
            selected
            and self._requires_license_acknowledgment(family)
            and not self._is_license_acknowledged(family)
        ):
            self._show_license_gate_dialog(
                family,
                version,
                lambda f=family, v=version, ids=item_ids, s=is_scale, lbl=label: (
                    self._toggle_item_group(f, v, ids, True, is_scale=s, label=lbl)
                ),
            )
            self._render()
            return
        selected_ids = self._selected_item_ids(family.instrument_id, version)
        if selected:
            selected_ids.update(item_ids)
        else:
            selected_ids.difference_update(item_ids)
        action = (
            "scale_selected"
            if is_scale and selected
            else ("scale_removed" if is_scale else "items_updated")
        )
        self._store_item_selection(
            family,
            version,
            selected_ids,
            action=action,
            summary=f"{'Skala' if is_scale else 'Itemgruppe'} {label} "
            f"{'hinzugefügt' if selected else 'entfernt'}",
        )

    def _store_item_selection(
        self,
        family: QuestionnaireParent,
        version: QuestionnaireVersion,
        selected_ids: set[str],
        *,
        action: str,
        summary: str,
    ) -> None:
        ordered_ids = [item.item_id for item in version.items if item.item_id in selected_ids]
        current = self._project_selection(family.instrument_id, version.version_id)
        adaptations = [
            adaptation
            for adaptation in (current.item_adaptations if current else [])
            if adaptation.item_id in selected_ids
        ]
        selection = (
            VersionSelection(
                instrument_id=family.instrument_id,
                version_id=version.version_id,
                item_ids=[] if len(ordered_ids) == len(version.items) else ordered_ids,
                item_adaptations=adaptations,
            )
            if ordered_ids
            else None
        )
        self._set_selection(selection, family.instrument_id, version.version_id)
        self.project = self.project.record_step(
            action,
            summary,
            f"{family.instrument_id}/{version.version_id}",
        )
        self._render()

    def _item_adaptation(
        self, family: QuestionnaireParent, version: QuestionnaireVersion, item_id: str
    ) -> ItemAdaptation | None:
        selection = self._project_selection(family.instrument_id, version.version_id)
        if selection is None:
            return None
        return next(
            (
                adaptation
                for adaptation in selection.item_adaptations
                if adaptation.item_id == item_id
            ),
            None,
        )

    def _edit_item_prompt(
        self,
        family: QuestionnaireParent,
        version: QuestionnaireVersion,
        item_id: str,
    ) -> None:
        item = next((value for value in version.items if value.item_id == item_id), None)
        if item is None:
            return
        existing = self._item_adaptation(family, version, item_id)
        prompt_field = ft.TextField(
            label="Studienformulierung",
            value=existing.adapted_prompt_text if existing else item.prompt_text,
            multiline=True,
            min_lines=3,
            max_lines=6,
        )
        reason_field = ft.TextField(
            label="Begründung der Anpassung",
            value=existing.reason if existing else "",
            hint_text="Warum ist diese Änderung für die Studie erforderlich?",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        def save_adaptation(_event: Any) -> None:
            new_prompt = (prompt_field.value or "").strip()
            reason = (reason_field.value or "").strip()
            if not new_prompt or new_prompt == item.prompt_text and not existing:
                self.page.pop_dialog()
                return
            if not reason:
                self._set_status("Bitte begründe die Itemanpassung.", error=True)
                return
            current = self._project_selection(family.instrument_id, version.version_id)
            selected_ids = self._selected_item_ids(family.instrument_id, version)
            selected_ids.add(item_id)
            adaptations = [
                adaptation
                for adaptation in (current.item_adaptations if current else [])
                if adaptation.item_id != item_id
            ]
            if new_prompt != item.prompt_text:
                adaptations.append(
                    ItemAdaptation(
                        item_id=item_id,
                        adapted_prompt_text=new_prompt,
                        reason=reason,
                    )
                )
            ordered_ids = [
                value.item_id for value in version.items if value.item_id in selected_ids
            ]
            selection = VersionSelection(
                instrument_id=family.instrument_id,
                version_id=version.version_id,
                item_ids=[] if len(ordered_ids) == len(version.items) else ordered_ids,
                item_adaptations=adaptations,
            )
            self._set_selection(selection, family.instrument_id, version.version_id)
            self.project = self.project.record_step(
                "items_updated",
                f"Studienanpassung gespeichert für {item_id}; Validierung/Scoring überprüfen",
                f"{family.instrument_id}/{version.version_id}",
            )
            self.page.pop_dialog()
            self._render()

        self._show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Item für diese Studie anpassen"),
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        ft.Text(
                            "Die Katalogfassung bleibt unverändert. Eine geänderte Formulierung kann Lizenzbedingungen und psychometrische Validität beeinflussen; betroffene Scores werden beim Export entfernt.",
                            size=12,
                            color="#8A4A2E",
                        ),
                        prompt_field,
                        reason_field,
                    ],
                ),
                actions=[
                    ft.Button(
                        content="Abbrechen",
                        on_click=lambda _event: self.page.pop_dialog(),
                    ),
                    ft.Button(content="Im Projekt übernehmen", on_click=save_adaptation),
                ],
            )
        )

    def _catalog_overview_panel(self) -> ft.Control:
        return dashboard_view.build_catalog_overview_panel(self.catalog_records)

    def _construct_similarity_panel(self) -> ft.Control:
        rows: list[ft.Control] = [
            ft.Text(self.similarity_status, size=12, color="#55716A", selectable=True),
        ]
        if self.similarity_matches:
            rows.append(
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text(
                            f"{match.name_a} ↔ {match.name_b} "
                            f"({match.instrument_a}/{match.instrument_b}) · "
                            f"Ähnlichkeit {match.similarity:.2f}",
                            size=12,
                            color="#173D36",
                            selectable=True,
                        )
                        for match in self.similarity_matches[:20]
                    ],
                )
            )
        rows.append(
            self._action_button(
                "Konstruktähnlichkeit prüfen",
                "PSYCHOLOGY",
                self._check_construct_similarity,
                "Vergleicht Name, Konstrukte, Beschreibung und Keywords aller Instrumente semantisch (sentence-transformers) und listet Kandidatenpaare mit hoher Ähnlichkeit auf.",
                "Findet mögliche 'Jingle-Jangle'-Fälle: unterschiedlich benannte Instrumente, die vermutlich dasselbe Konstrukt messen. Kein automatischer Befund, sondern ein Hinweis zur manuellen Prüfung.",
                primary=True,
            )
        )
        return ft.ExpansionTile(
            title="Konstrukt-Ähnlichkeitsprüfung (semantisch)",
            subtitle="Findet Kandidaten für überlappende Konstrukte über Instrumentgrenzen hinweg.",
            expanded=False,
            maintain_state=True,
            bgcolor="#F7F9F8",
            collapsed_bgcolor="#EEF3F1",
            controls=[ft.Column(spacing=10, controls=rows)],
        )

    async def _check_construct_similarity(self, _event: Any) -> None:
        self.similarity_status = (
            "Berechne Ähnlichkeiten... (lädt beim ersten Mal ggf. ein Modell "
            "herunter; erfordert dann Internetzugang)"
        )
        self._render()
        try:
            matches = await asyncio.to_thread(find_similar_constructs, self.catalog_records)
        except NLPEngineError as error:
            self.similarity_matches = None
            self.similarity_status = f"Fehlgeschlagen: {error}"
            self._render()
            return
        self.similarity_matches = matches
        self.similarity_status = (
            f"{len(matches)} Kandidatenpaar(e) mit Ähnlichkeit ≥ 0.75 gefunden."
            if matches
            else "Keine auffälligen Konstrukt-Überlappungen über der Schwelle gefunden."
        )
        self._render()

    def _research_view(self) -> list[ft.Control]:
        query_field = ft.TextField(
            value=self.research_query,
            hint_text='Konstrukt oder Fragestellung, z. B. "wahrgenommener Stress bei Studierenden"',
            on_change=lambda event: setattr(self, "research_query", event.control.value),
        )

        catalog_rows: list[ft.Control] = [
            ft.Text(self.research_status, size=12, color="#55716A", selectable=True),
        ]
        for match in self.research_matches or []:
            family = self._find_family(match.instrument_id)
            detail_parts = [f"Ähnlichkeit {match.similarity:.2f}"]
            entry_controls: list[ft.Control] = []
            if family is not None:
                version = family.versions[0]
                if family.is_commercial:
                    detail_parts.append("kommerziell/lizenzpflichtig")
                if not version.item_text_included:
                    detail_parts.append("Metadatenreferenz, kein Itemtext")
                time_estimate = estimate_version_time(family, version)
                if time_estimate.minimum_minutes is not None:
                    detail_parts.append(
                        f"ca. {time_estimate.minimum_minutes:.0f}–"
                        f"{time_estimate.maximum_minutes:.0f} Min."
                    )
                entry_controls.append(
                    self._action_button(
                        "Zur Batterie hinzufügen",
                        "ADD_CIRCLE_OUTLINE",
                        lambda _event, f=family, v=version: self._add_research_match_to_project(
                            f, v
                        ),
                        f"Fügt {version.display_name or version.version_id} direkt zur Projektauswahl hinzu.",
                    )
                )
            catalog_rows.append(
                ft.Container(
                    padding=8,
                    bgcolor="#F7F9F8",
                    border_radius=6,
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(match.name_full, size=13, weight=ft.FontWeight.BOLD),
                            ft.Text(" · ".join(detail_parts), size=11, color="#55716A"),
                            *entry_controls,
                        ],
                    ),
                )
            )
        catalog_rows.append(
            self._action_button(
                "Katalog durchsuchen",
                "TRAVEL_EXPLORE",
                self._search_catalog_instruments,
                "Vergleicht deine Eingabe semantisch (lokales sentence-transformers-Modell) mit "
                "Name, Konstrukten, Beschreibung und Keywords aller Katalog-Instrumente. Itemtext "
                "wird dabei nie verwendet.",
                "Läuft vollständig lokal; beim allerersten Aufruf wird das Modell (~90 MB) einmalig heruntergeladen.",
                primary=True,
            )
        )

        external_rows: list[ft.Control] = [
            ft.Text(self.research_external_status, size=12, color="#55716A", selectable=True),
        ]
        for candidate in self.research_external_candidates or []:
            external_rows.append(
                ft.Container(
                    padding=8,
                    bgcolor="#FDF6EC",
                    border_radius=6,
                    content=ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(candidate.title, size=13, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"Quelle: {candidate.source} · Nicht im Katalog, Rechte ungeklärt",
                                size=11,
                                color="#9B3E35",
                            ),
                            ft.Text(
                                candidate.source_url, size=11, selectable=True, color="#55716A"
                            ),
                        ],
                    ),
                )
            )
        for record in self.research_external_evidence or []:
            external_rows.append(
                ft.Text(
                    f"{record.title} ({record.journal or 'unbekannte Zeitschrift'}, "
                    f"{record.publication_date or 'o. J.'}) – {record.source_url}",
                    size=11,
                    selectable=True,
                    color="#55716A",
                )
            )
        external_rows.append(
            self._action_button(
                "Externe Quellen abfragen (NIH CDE / PubMed)",
                "PUBLIC",
                self._search_external_sources,
                "Fragt öffentliche NIH-CDE- und PubMed-APIs mit deinem Suchtext ab. Ergebnisse "
                "sind unkatalogisierte Vorschläge zur Prüfung, keine freigegebenen "
                "Katalogeinträge und keine automatische Nutzungsberechtigung.",
                "Sendet nur deinen Suchtext an die jeweilige öffentliche API, keine Katalog- oder Projektdaten.",
            )
        )

        return [
            ft.Text(
                "Finde passende Instrumente zu einer Fragestellung oder einem Konstrukt.",
                size=13,
                color="#55716A",
            ),
            self._field(
                "Fragestellung / Konstrukt",
                query_field,
                "Freitext, z. B. eine Forschungsfrage oder ein Konstruktname.",
                "Beispiel: 'wahrgenommener Stress bei Studierenden' oder 'Depression'.",
            ),
            self._panel(
                "Katalog (semantisch, lokal)",
                ft.Column(spacing=8, controls=catalog_rows),
                "Nutzt dasselbe lokale Embedding-Modell wie die Konstrukt-Ähnlichkeitsprüfung; "
                "vergleicht nie Itemtext.",
            ),
            self._panel(
                "Externe Quellen (öffentliche APIs, unkatalogisiert)",
                ft.Column(spacing=8, controls=external_rows),
                "NIH CDE und PubMed sind Vorschläge zur Prüfung, keine geprüften "
                "Katalogeinträge; Sichtbarkeit in einer öffentlichen API ist keine Weitergabeerlaubnis.",
            ),
        ]

    async def _search_catalog_instruments(self, _event: Any) -> None:
        query = self.research_query.strip()
        if not query:
            self.research_status = "Bitte zuerst eine Fragestellung oder ein Konstrukt eingeben."
            self._render()
            return
        self.research_status = (
            "Durchsuche Katalog semantisch... (lädt beim ersten Mal ggf. ein Modell "
            "herunter; erfordert dann Internetzugang)"
        )
        self._render()
        try:
            matches = await asyncio.to_thread(
                find_matching_instruments, query, self.catalog_records
            )
        except NLPEngineError as error:
            self.research_matches = None
            self.research_status = f"Fehlgeschlagen: {error}"
            self._render()
            return
        self.research_matches = matches
        self.research_status = (
            f"{len(matches)} Treffer für „{query}“." if matches else f"Keine Treffer für „{query}“."
        )
        self._render()

    def _add_research_match_to_project(
        self, family: QuestionnaireParent, version: QuestionnaireVersion
    ) -> None:
        self._toggle_version(family, version, True)
        self._set_status(f"{family.name_full} zur Projektauswahl hinzugefügt.")

    async def _search_external_sources(self, _event: Any) -> None:
        query = self.research_query.strip()
        if not query:
            self.research_external_status = (
                "Bitte zuerst eine Fragestellung oder ein Konstrukt eingeben."
            )
            self._render()
            return
        self.research_external_status = "Frage öffentliche APIs ab..."
        self._render()
        try:
            candidates = await NIHCDEClient().search_data_elements(query, limit=8)
            evidence = await PubMedClient().search(query, limit=5)
        except ExternalSourceError as error:
            self.research_external_candidates = None
            self.research_external_evidence = None
            self.research_external_status = f"Fehlgeschlagen: {error}"
            self._render()
            return
        self.research_external_candidates = candidates
        self.research_external_evidence = evidence
        self.research_external_status = (
            f"{len(candidates)} NIH-CDE-Kandidat(en), {len(evidence)} PubMed-Treffer für „{query}“."
        )
        self._render()

    def _catalog_view(self) -> list[ft.Control]:
        LOGGER.debug(
            "Building catalog view: visible_versions=%d query_length=%d",
            len(self._visible_versions()),
            len(self.search_query),
        )
        languages = sorted(
            {
                value
                for family, _path in self.catalog_records
                for version in family.versions
                for value in (version.language, version.locale)
                if value
            }
        )
        locales = sorted(
            {
                version.locale
                for family, _path in self.catalog_records
                for version in family.versions
                if version.locale
            }
        )
        license_names = sorted(
            {
                source.license_name
                for family, _path in self.catalog_records
                for version in family.versions
                for source in version.source_documents
            }
        )
        language_options = [ft.DropdownOption(key="all", text="Alle Sprachen")]
        language_options.extend(
            ft.DropdownOption(key=language.casefold(), text=language) for language in languages
        )
        language_dropdown = ft.Dropdown(
            value=self.language_filter,
            options=language_options,
            on_select=lambda event: self._set_language_filter(event.control.value),
            width=180,
        )
        locale_dropdown = ft.Dropdown(
            value=self.locale_filter,
            options=[ft.DropdownOption(key="all", text="Alle Locales")]
            + [ft.DropdownOption(key=value.casefold(), text=value) for value in locales],
            on_select=lambda event: self._set_catalog_filter("locale", event.control.value),
            width=180,
        )
        form_type_filter_panel = self._panel(
            "Formtyp",
            ft.Column(
                spacing=2,
                controls=[
                    ft.Checkbox(
                        label=value.title(),
                        value=value in self._selected_form_type_filters(),
                        on_change=lambda event, form_type=value: self._set_multi_catalog_filter(
                            "form_type", form_type, bool(event.control.value)
                        ),
                    )
                    for value in ("full", "short", "long", "screening", "custom")
                ],
            ),
            "Mehrere Formtypen können gleichzeitig gewählt werden; die Auswahl verbindet sie mit ODER.",
        )
        rights_filter_panel = self._panel(
            "Nutzungsstatus",
            ft.Column(
                spacing=2,
                controls=[
                    ft.Checkbox(
                        label=label,
                        value=value in self._selected_commercial_filters(),
                        on_change=lambda event, status=value: self._set_multi_catalog_filter(
                            "commercial", status, bool(event.control.value)
                        ),
                    )
                    for value, label in (
                        ("noncommercial", "Nicht-kommerziell"),
                        ("commercial", "Kommerziell eingeschränkt"),
                        ("unknown", "Unbekannt / ungeprüft"),
                    )
                ],
            ),
            "Mehrere Rechte-Status können gleichzeitig gewählt werden; unbekannt ist keine Nutzungserlaubnis.",
        )
        license_dropdown = ft.Dropdown(
            value=self.license_filter,
            options=[
                ft.DropdownOption(key="all", text="Alle Lizenzen"),
                ft.DropdownOption(key="undocumented", text="Lizenz nicht dokumentiert"),
            ]
            + [ft.DropdownOption(key=value.casefold(), text=value) for value in license_names],
            on_select=lambda event: self._set_catalog_filter("license", event.control.value),
            width=280,
        )
        content_dropdown = ft.Dropdown(
            value=self.item_content_filter,
            options=[
                ft.DropdownOption(key="with_items", text="Nur vollständige Fragebogen"),
                ft.DropdownOption(key="all", text="Alle inkl. Referenzen"),
                ft.DropdownOption(key="references", text="Nur Referenzrecords"),
            ],
            on_select=lambda event: self._set_catalog_filter("content", event.control.value),
            width=270,
        )
        self.search_field = ft.TextField(
            value=self.search_query,
            hint_text="Instrument, Sprache, Item oder Konstrukt suchen",
            width=360,
            on_submit=lambda _event: self._submit_search(),
        )
        toolbar = ft.Row(
            wrap=True,
            spacing=8,
            controls=[
                ft.Container(
                    width=380,
                    content=self._field(
                        "Suche",
                        self.search_field,
                        "Durchsucht Namen, Versionen, Konstrukte, Itemtexte und Antwortoptionen im aktuell geladenen Katalog.",
                        "Zum Beispiel: PHQ-9, Sorgen, de-CH oder Never.",
                    ),
                ),
                ft.Container(
                    width=200,
                    content=self._field(
                        "Sprache",
                        language_dropdown,
                        "Filtert nach Sprache oder Locale. Kurze Sprachcodes wie 'de' schließen alle dokumentierten Regionen ein; 'de-AT' wählt genau diese Locale.",
                        "de = alle deutschen Sprachvarianten; de-AT = österreichisches Deutsch.",
                    ),
                ),
                self._action_button(
                    "Suchen",
                    "SEARCH",
                    lambda _event: self._submit_search(),
                    "Wendet den eingegebenen Suchtext und Sprachfilter auf den lokalen Katalog an.",
                    "Suche nach 'Depression' zeigt passende Instrumentfamilien und Items.",
                    primary=True,
                ),
                self._action_button(
                    "Filter zurücksetzen",
                    "CLEAR",
                    self._reset_catalog_filters,
                    "Entfernt Suchtext und alle aktiven Katalogfilter.",
                ),
            ],
        )
        facets = ft.Row(
            wrap=True,
            spacing=8,
            controls=[
                ft.Container(
                    width=230,
                    content=self._field(
                        "Locale",
                        locale_dropdown,
                        "Filtert nach konkretem regionalem Sprachraum. Das ist präziser als der Sprachcode allein.",
                        "de-CH und de-DE sind separate Adaptationen.",
                    ),
                ),
                ft.Container(
                    width=230,
                    content=form_type_filter_panel,
                ),
                ft.Container(
                    width=300,
                    content=self._panel(
                        "Zielgruppe",
                        ft.Column(
                            spacing=2,
                            controls=[
                                ft.Checkbox(
                                    label=label,
                                    value=key in self._selected_population_filters(),
                                    on_change=lambda event, group=key: self._set_population_filter(
                                        group, bool(event.control.value)
                                    ),
                                )
                                for key, label in AGE_GROUP_LABELS.items()
                            ],
                        ),
                        "Mehrere Altersgruppen können gleichzeitig gewählt werden. Die Auswahl verbindet Gruppen mit ODER; ein Instrument für 15-69-Jährige erscheint deshalb in mehreren passenden Gruppen.",
                    ),
                ),
                ft.Container(
                    width=270,
                    content=rights_filter_panel,
                ),
                ft.Container(
                    width=320,
                    content=self._field(
                        "Lizenz / Rechtehinweis",
                        license_dropdown,
                        "Filtert nach dem im Quelldatensatz dokumentierten Lizenznamen. Ein Filter oder eine Erlaubnisangabe ist keine Nutzungssperre und kein Rechtsgutachten.",
                        "Beispiele: Public domain, CC BY 4.0, Registrierung erforderlich.",
                    ),
                ),
                ft.Container(
                    width=300,
                    content=self._field(
                        "Iteminhalt",
                        content_dropdown,
                        "Standardmäßig werden nur vollständige Fragebogen mit lokal vorhandenem Itemtext gezeigt. Referenzrecords enthalten nur Metadaten und Quellenlinks.",
                        "Alle inkl. Referenzen zeigt zusätzlich link-only Instrumente.",
                    ),
                ),
            ],
        )
        versions = self._visible_versions()
        active_filter_summary = ft.Text(
            self._active_catalog_filter_summary(), size=12, color="#55716A", selectable=True
        )
        left = ft.Column(
            expand=5,
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(f"{len(versions)} Versionen", size=13, color="#55716A"),
                        ft.Row(
                            controls=[
                                self._action_button(
                                    "Katalog neu laden",
                                    "REFRESH",
                                    lambda _event: self._reload_and_render(),
                                    "Liest den eingestellten Katalogordner erneut ein. Ungültige Katalogdateien werden gemeldet; die bisherige Ansicht bleibt erhalten.",
                                ),
                                self._action_button(
                                    "Dateien importieren",
                                    "UPLOAD_FILE",
                                    self._choose_import_files,
                                    "Importiert PsyMetriQ JSON, HL7 FHIR Questionnaire JSON, REDCap Data Dictionary CSV, Qualtrics QSF, oder LimeSurvey TSV/Unipark Paste-Text (beide .txt, Best-Effort, automatisch erkannt). Versionskonflikte werden nicht überschrieben.",
                                    "Eine REDCap CSV benötigt ein Sprach-Tag, das unter Einstellungen festgelegt wird.",
                                    primary=True,
                                ),
                            ]
                        ),
                    ],
                ),
                active_filter_summary,
                ft.ListView(
                    height=460,
                    spacing=6,
                    controls=[self._version_card(family, version) for family, version in versions]
                    or [
                        ft.Container(
                            padding=18,
                            content=ft.Text(
                                self.catalog_error
                                or "Keine passenden Versionen. Importiere JSON/FHIR/REDCap oder passe die Suche an.",
                                color="#55716A",
                            ),
                        )
                    ],
                ),
            ],
        )
        right = ft.Container(
            expand=6,
            content=self._version_detail(),
        )
        return [
            ft.Text(
                "Instrumente finden, Versionen vergleichen und passende Items in ein Projekt übernehmen.",
                size=13,
                color="#55716A",
            ),
            self._catalog_overview_panel(),
            self._construct_similarity_panel(),
            toolbar,
            facets,
            ft.Container(height=4),
            ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[left, right],
            ),
        ]

    def _version_card(
        self, family: QuestionnaireParent, version: QuestionnaireVersion
    ) -> ft.Control:
        key = (family.instrument_id, version.version_id)
        selection = self._project_selection(*key)
        selected_ids = self._selected_item_ids(family.instrument_id, version)
        is_selected = selection is not None
        rights_count = len(version.source_documents)
        rights_label = (
            "Rechte nicht dokumentiert"
            if rights_count == 0
            else f"{rights_count} Rechte-/Quelldatensätze"
        )
        license_locked = (
            version.item_text_included
            and self._requires_license_acknowledgment(family)
            and not self._is_license_acknowledged(family)
        )
        subtitle = " · ".join(
            value
            for value in (
                version.language,
                version.locale or "",
                version.form_type,
                (
                    f"{len(selected_ids) if is_selected else 0}/{len(version.items)} Items ausgewählt"
                    if version.item_text_included
                    else (
                        f"Metadatenreferenz · "
                        f"{version.source_reported_item_count or 'Anzahl unbekannt'} Items laut Quelle"
                    )
                ),
                "Lizenzpflichtig · Bestätigung erforderlich" if license_locked else "",
                (
                    "Institutionell lizenziert"
                    if version.item_text_included
                    and family.is_commercial is True
                    and self._is_institutionally_licensed(family)
                    else ""
                ),
            )
            if value
        )
        LOGGER.debug(
            "Building version card: instrument_id=%s version_id=%s item_count=%d link_only=%s",
            family.instrument_id,
            version.version_id,
            len(version.items),
            not version.item_text_included,
        )
        return ft.Container(
            bgcolor="#FFFFFF",
            border_radius=8,
            padding=8,
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Checkbox(
                        value=is_selected,
                        label="Auswahl",
                        tooltip=(
                            f"{family.name_full} ({version.version_id}) zum Projekt hinzufügen"
                            if version.item_text_included
                            else "Nimmt die dokumentierte Version als Referenz ins Projekt auf; Itemtexte werden nicht mitkopiert"
                        ),
                        on_change=lambda event, f=family, v=version: self._toggle_version(
                            f, v, bool(event.control.value)
                        ),
                    ),
                    ft.Button(
                        expand=True,
                        content=ft.Column(
                            spacing=3,
                            horizontal_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Text(
                                    version.display_name or family.name_full,
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color="#173D36",
                                ),
                                ft.Text(family.name_full, size=12, color="#55716A"),
                                ft.Text(subtitle, size=11, color="#55716A"),
                            ],
                        ),
                        on_click=lambda _event, k=key: self._show_version(k),
                        tooltip=(
                            f"Details anzeigen: {family.name_full}, "
                            f"{version.display_name or version.version_id}, {version.language}"
                        ),
                    ),
                    self._help_button(
                        "Katalogversion",
                        "Jede Zeile ist eine konkrete Sprach-/Formversion. Rechteinformationen sind Quellenangaben, keine automatische Freigabe.",
                        f"{family.instrument_id} · {version.version_id} · {rights_label}",
                    ),
                ],
            ),
        )

    @staticmethod
    def _profile_text(label: str, value: str | None) -> ft.Control:
        return ft.Text(
            f"{label}: {value or 'nicht dokumentiert'}",
            size=12,
            color="#55716A" if value else "#8A4A2E",
            selectable=True,
        )

    def _instrument_profile_controls(
        self, family: QuestionnaireParent, version: QuestionnaireVersion
    ) -> list[ft.Control]:
        """Build a source-grounded instrument profile without inventing missing facts."""
        family_metadata = family.metadata
        version_metadata = version.metadata
        populations = [
            population.group_name
            + (
                f" ({population.minimum_age_years:g}-{population.maximum_age_years:g} Jahre)"
                if population.minimum_age_years is not None
                and population.maximum_age_years is not None
                else (
                    f" (ab {population.minimum_age_years:g} Jahre)"
                    if population.minimum_age_years is not None
                    else ""
                )
            )
            + (f"; {population.notes}" if population.notes else "")
            for population in version.target_populations
        ]
        contributors = ", ".join(
            f"{contributor.name} ({contributor.role})" for contributor in family.contributors
        )
        version_contributors = ", ".join(
            f"{contributor.name} ({contributor.role})" for contributor in version.contributors
        )
        characteristics = ", ".join(
            dict.fromkeys(family_metadata.characteristics + version_metadata.characteristics)
        )
        keywords = ", ".join(dict.fromkeys(family_metadata.keywords + version_metadata.keywords))
        aliases = ", ".join(
            dict.fromkeys(family_metadata.search_aliases + version_metadata.search_aliases)
        )
        metrics = ", ".join(f"{key}: {value}" for key, value in version.cosmin_metrics.items())
        dimensions = ", ".join(version.source_reported_dimensions)
        constructs = ", ".join(family.construct_ontology)
        profile_rows: list[ft.Control] = [
            self._profile_text(
                "Worum geht es", version_metadata.description or family_metadata.description
            ),
            self._profile_text(
                "Dokumentierter Zweck",
                version_metadata.intended_use or family_metadata.intended_use,
            ),
            self._profile_text(
                "Was misst das Instrument",
                constructs or dimensions or keywords,
            ),
            self._profile_text(
                "Warum wird dieses Merkmal erfasst",
                version_metadata.measurement_rationale or family_metadata.measurement_rationale,
            ),
            self._profile_text(
                "Namensherkunft",
                version_metadata.name_origin or family_metadata.name_origin,
            ),
            self._profile_text("Namensvarianten / Suchbegriffe", aliases or keywords),
            self._profile_text("Zielgruppe", "; ".join(populations)),
            self._profile_text("Merkmale der Durchführung", characteristics),
            self._profile_text("Bearbeitungszeit", version.administration_time),
            self._profile_text("Recall-/Bezugszeitraum", version.recall_period),
            self._profile_text("Antwortformat", version.response_format),
            self._profile_text("Itemaufbau", version.item_structure),
            self._profile_text("Auswertung", version.scoring_notes),
            self._profile_text("Entwicklung / Autorenschaft", contributors),
            self._profile_text("Versionsbeitrag", version_contributors),
            self._profile_text(
                "Entwicklungsgeschichte",
                version_metadata.development_history or family_metadata.development_history,
            ),
            self._profile_text(
                "Gütekriterien / COSMIN-Metriken",
                version.psychometric_summary
                or metrics
                or "Keine strukturierten Gütekriterien im Katalog hinterlegt",
            ),
            self._profile_text(
                "Interpretation und Grenzen",
                version_metadata.interpretation_notes or family_metadata.interpretation_notes,
            ),
            self._profile_text(
                "Quellen-/Reviewhinweis",
                version_metadata.notes or family_metadata.notes,
            ),
            self._profile_text(
                "Erstellungs-/Publikationsjahr",
                str(version.publication_year) if version.publication_year else None,
            ),
            self._profile_text("Primärquelle", version.source_citation),
            self._profile_text("DOI", version.source_doi),
        ]
        return profile_rows

    def _version_detail(self) -> ft.Control:
        if self.active_version_key is None:
            return self._panel(
                "Versionsdetails",
                ft.Text(
                    "Wähle links eine Version aus, um Metadaten und Items anzusehen.",
                    color="#55716A",
                ),
                "Hier erscheinen Version, Sprache, Rechte-/Quellhinweise und einzelne Items.",
            )
        found = self._find_version(*self.active_version_key)
        if found is None:
            return ft.Text("Die gewählte Version ist nicht mehr im Katalog vorhanden.")
        family, version = found
        license_locked = (
            version.item_text_included
            and self._requires_license_acknowledgment(family)
            and not self._is_license_acknowledged(family)
        )
        source_rows: list[ft.Control] = []
        for source in version.source_documents:
            source_rows.append(
                ft.Text(
                    f"{source.document_type}: {source.title} · Lizenz/Status: {source.license_name} · "
                    f"{'Weitergabe laut Quelle dokumentiert' if source.redistribution_permitted else 'Weitergabe laut Quelle nicht freigegeben oder ungeklärt'} · "
                    f"Basis: {source.permission_basis}"
                    + (f" · {source.source_url}" if source.source_url else ""),
                    size=12,
                    color="#55716A",
                    selectable=True,
                )
            )
        if not source_rows:
            source_rows.append(
                ft.Text(
                    "Für diese Version sind keine Rechte-/Quelldokumente hinterlegt.",
                    size=12,
                    color="#9B3E35",
                )
            )
        scale_controls: list[ft.Control] = []
        selected_ids = self._selected_item_ids(family.instrument_id, version)
        for algorithm in [] if license_locked else version.scoring_algorithms:
            targets = [
                item_id
                for item_id in algorithm.target_items
                if item_id in {item.item_id for item in version.items}
            ]
            if not targets:
                continue
            scale_selected = set(targets).issubset(selected_ids)
            scale_controls.append(
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Checkbox(
                            label=algorithm.output_variable,
                            value=scale_selected,
                            tooltip=f"Gesamte Score-Skala {algorithm.output_variable} auswählen",
                            on_change=lambda event, f=family, v=version, ids=targets, name=algorithm.output_variable: (
                                self._toggle_item_group(
                                    f,
                                    v,
                                    ids,
                                    bool(event.control.value),
                                    is_scale=True,
                                    label=name,
                                )
                            ),
                        ),
                        ft.Text(
                            f"{algorithm.method} · {len(targets)} Items · Faktor {algorithm.multiplier:g}",
                            size=11,
                            color="#55716A",
                        ),
                        self._help_button(
                            f"Skala {algorithm.output_variable}",
                            "Wählt alle Item-Zielwerte dieses Scoring-Algorithmus als Gruppe aus. Wenn ein Item angepasst wird, wird der betroffene Score beim Export nicht mit ausgegeben.",
                            f"{algorithm.method} über {', '.join(targets)}",
                        ),
                    ],
                )
            )
        dimension_groups: dict[str, list[str]] = {}
        for item in [] if license_locked else version.items:
            dimension_groups.setdefault(item.dimension, []).append(item.item_id)
        dimension_controls: list[ft.Control] = []
        if not license_locked and not version.item_text_included:
            dimension_controls = [
                ft.Text(
                    f"{dimension} · Metadaten der Quelle",
                    size=12,
                    color="#55716A",
                    selectable=True,
                )
                for dimension in version.source_reported_dimensions
            ]
        if dimension_groups:
            dimension_controls = [
                ft.Row(
                    controls=[
                        ft.Checkbox(
                            label=dimension,
                            value=set(item_ids).issubset(selected_ids),
                            on_change=lambda event, f=family, v=version, ids=item_ids, name=dimension: (
                                self._toggle_item_group(
                                    f,
                                    v,
                                    ids,
                                    bool(event.control.value),
                                    is_scale=False,
                                    label=name,
                                )
                            ),
                        ),
                        self._help_button(
                            f"Itemdimension {dimension}",
                            "Wählt alle Items aus, die der Katalog dieser Dimension zuordnet. Das ist eine Auswahlhilfe und ändert nicht die fachliche Subskala.",
                            f"{len(item_ids)} Item(s)",
                        ),
                    ]
                )
                for dimension, item_ids in dimension_groups.items()
            ]
        item_controls: list[ft.Control] = []
        items_by_id = {sibling.item_id: sibling for sibling in version.items}
        for item in [] if license_locked else version.items:
            options = (
                version.response_sets[item.response_set_ref]
                if item.response_set_ref is not None
                else []
            )
            option_labels = ", ".join(option.label for option in options) or (
                item.measurement_unit or item.response_mode
            )
            adaptation = self._item_adaptation(family, version, item.item_id)
            displayed_prompt = adaptation.adapted_prompt_text if adaptation else item.prompt_text
            item_controls.append(
                ft.Container(
                    bgcolor="#F7F9F8",
                    border_radius=6,
                    padding=8,
                    content=ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Checkbox(
                                value=item.item_id in selected_ids,
                                on_change=lambda event, f=family, v=version, i=item.item_id: (
                                    self._toggle_item(f, v, i, bool(event.control.value))
                                ),
                            ),
                            ft.Column(
                                expand=True,
                                spacing=3,
                                controls=[
                                    ft.Text(
                                        displayed_prompt,
                                        size=13,
                                        selectable=True,
                                        color="#8A4A2E" if adaptation else "#203F39",
                                    ),
                                    *(
                                        [
                                            ft.Text(
                                                "Studienanpassung · Original im Katalog unverändert",
                                                size=10,
                                                color="#8A4A2E",
                                            )
                                        ]
                                        if adaptation
                                        else []
                                    ),
                                    ft.Text(
                                        f"{item.item_id} · {item.variable_name} · {item.dimension} · {option_labels}",
                                        size=11,
                                        color="#55716A",
                                        selectable=True,
                                    ),
                                    *(
                                        [
                                            ft.Text(
                                                "Nur sichtbar, wenn "
                                                + " und ".join(
                                                    f"{items_by_id[condition.source_item_id].variable_name} "
                                                    f"{'=' if condition.operator == 'equals' else '≠'} "
                                                    f"{condition.value}"
                                                    for condition in item.show_if
                                                    if condition.source_item_id in items_by_id
                                                ),
                                                size=10,
                                                color="#55716A",
                                                italic=True,
                                            )
                                        ]
                                        if item.show_if
                                        else []
                                    ),
                                    *(
                                        [
                                            ft.Text(
                                                f"Matrixgruppe: {item.matrix_group_name}"
                                                + (" (Ranking)" if item.matrix_ranking else ""),
                                                size=10,
                                                color="#55716A",
                                                italic=True,
                                            )
                                        ]
                                        if item.matrix_group_name
                                        else []
                                    ),
                                ],
                            ),
                            self._help_button(
                                "Item und Antwortformat",
                                "Der Itemtext und das angegebene Antwortformat stammen aus der aktiven Version. Eine Auswahl übernimmt das Item in das lokale Arbeitsprojekt, nicht automatisch in einen Export.",
                                f"Antwortmodus: {item.response_mode}; Antwortoptionen: {option_labels}",
                            ),
                            self._action_button(
                                "Anpassen",
                                "EDIT",
                                lambda _event, f=family, v=version, i=item.item_id: (
                                    self._edit_item_prompt(f, v, i)
                                ),
                                "Erstellt eine studienspezifische Formulierung im Projekt. Der Quellkatalog bleibt unverändert; die betroffene Scoring-Skala wird beim Export nicht als gültig übernommen.",
                                "Begründe z.B. eine Änderung der Zielgruppenansprache. Prüfe vor Nutzung Lizenz und Validität.",
                            ),
                        ],
                    ),
                )
            )
        metadata_text = " · ".join(
            value
            for value in (
                f"ID {family.instrument_id}",
                f"Version {version.version_id}",
                f"Sprache {version.language}",
                f"Locale {version.locale}" if version.locale else "",
                f"Jahr {version.publication_year}" if version.publication_year else "",
                (
                    f"{len(version.items)} Items"
                    if version.item_text_included
                    else f"{version.source_reported_item_count or 'Unbekannte Anzahl'} Items laut Quelle; Itemtext nicht enthalten"
                ),
            )
            if value
        )
        license_gate_panel: ft.Control | None = None
        if license_locked and version.item_text_included:
            source = self._primary_license_source(version)
            license_gate_panel = ft.Container(
                bgcolor="#FBF1E8",
                border_radius=6,
                padding=12,
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Text(
                            f"{family.name_full} ist lizenzpflichtig. Bestätige einmalig, dass du "
                            "über eine gültige Lizenz verfügst (z. B. institutionelle "
                            "Testbibliothek oder erworbener Studienzugang) und dich an deren "
                            "Bedingungen hältst, um Itemtext anzuzeigen und auszuwählen.",
                            size=12,
                            color="#8A4A2E",
                        ),
                        ft.Text(
                            f"Lizenz/Status: {source.license_name if source else 'nicht dokumentiert'}",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color="#8A4A2E",
                        ),
                        ft.Button(
                            content="Lizenzbestimmungen bestätigen",
                            on_click=lambda _event, f=family, v=version: (
                                self._show_license_gate_dialog(f, v, lambda f2=f: self._render())
                            ),
                        ),
                    ],
                ),
            )
        item_help: ft.Control = (
            self._help_button(
                "Itemauswahl",
                "Markiere einzelne Items links. Beim Export werden nur markierte Items dieser Version aufgenommen. Rechtebedingungen bleiben pro Quellversion zu prüfen.",
                "PHQ-9: einzelne Items plus Antwortskala 'Not at all' bis 'Nearly every day'.",
            )
            if version.item_text_included and not license_locked
            else ft.Text(
                (
                    "Lizenz noch nicht bestätigt: Itemtext wird erst nach Bestätigung oben angezeigt."
                    if version.item_text_included and license_locked
                    else "Metadatenreferenz: Itemtext ist nicht in dieser Software gespeichert oder exportiert. Nutze den offiziellen Quellenlink, prüfe dortige Nutzungs-/Adaptionsbedingungen und beschaffe eine Nutzungserlaubnis für Feldanwendung, Lehre oder geteilte Materialien, falls erforderlich. Die Auswahl hier dient Literatur-/Meta-Analysen und Projektplanung und ist keine Erlaubnis zur Itemnutzung."
                ),
                size=12,
                color="#8A4A2E",
                selectable=True,
            )
        )
        profile_tile = ft.ExpansionTile(
            title="Instrumentprofil",
            subtitle="Zweck, Zielgruppe, Durchführung, Auswertung und psychometrische Evidenz",
            expanded=False,
            maintain_state=True,
            controls=[
                ft.Column(spacing=4, controls=self._instrument_profile_controls(family, version))
            ],
            bgcolor="#F7F9F8",
            collapsed_bgcolor="#EEF3F1",
        )
        sources_tile = ft.ExpansionTile(
            title="Rechte und Quellen",
            subtitle=f"{len(source_rows)} Quelldatensatz/-sätze",
            expanded=False,
            maintain_state=True,
            controls=[ft.Column(spacing=4, controls=source_rows)],
            bgcolor="#F7F9F8",
            collapsed_bgcolor="#EEF3F1",
        )
        scoring_tiles: list[ft.Control] = []
        if scale_controls:
            scoring_tiles.append(
                ft.ExpansionTile(
                    title="Skalen / Scoring",
                    subtitle=f"{len(scale_controls)} auswählbare Scoregruppe(n)",
                    expanded=False,
                    maintain_state=True,
                    controls=[ft.Column(spacing=4, controls=scale_controls)],
                    bgcolor="#F7F9F8",
                    collapsed_bgcolor="#EEF3F1",
                )
            )
        if dimension_controls:
            scoring_tiles.append(
                ft.ExpansionTile(
                    title="Itemdimensionen",
                    subtitle="Auswahl nach Dimension oder Quellstruktur",
                    expanded=False,
                    maintain_state=True,
                    controls=[ft.Column(spacing=4, controls=dimension_controls)],
                    bgcolor="#F7F9F8",
                    collapsed_bgcolor="#EEF3F1",
                )
            )
        return self._panel(
            "Versionsdetails",
            ft.Column(
                spacing=10,
                controls=[
                    ft.Text(
                        version.display_name or family.name_full,
                        size=17,
                        weight=ft.FontWeight.BOLD,
                        color="#173D36",
                        selectable=True,
                    ),
                    ft.Text(family.name_full, size=13, color="#55716A", selectable=True),
                    ft.Text(metadata_text, size=12, color="#55716A", selectable=True),
                    ft.Text(
                        "Konstrukte: "
                        + (", ".join(family.construct_ontology) or "nicht angegeben"),
                        size=12,
                        selectable=True,
                    ),
                    profile_tile,
                    sources_tile,
                    *scoring_tiles,
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Items"
                                if version.item_text_included
                                else "Itemtext nicht enthalten",
                                weight=ft.FontWeight.BOLD,
                                size=13,
                            ),
                            item_help,
                        ]
                    ),
                    *([license_gate_panel] if license_gate_panel else []),
                    *(
                        [ft.Column(spacing=6, controls=item_controls)]
                        if version.item_text_included and not license_locked
                        else []
                    ),
                ],
            ),
            "Metadaten und Itemvorschau der ausgewählten konkreten Instrumentversion.",
        )

    def _project_view(self) -> list[ft.Control]:
        name_field = ft.TextField(
            value=self.project.name,
            hint_text="Projektname",
            on_change=lambda event: self._update_project_name(event.control.value),
        )
        description_field = ft.TextField(
            value=self.project.description,
            multiline=True,
            min_lines=2,
            max_lines=4,
            hint_text="Fragestellung, Population oder Notizen zum Arbeitsschritt",
            on_change=lambda event: self._update_project_description(event.control.value),
        )
        project_actions = ft.Row(
            wrap=True,
            controls=[
                self._action_button(
                    "Projekt laden",
                    "FOLDER_OPEN",
                    self._choose_project,
                    "Lädt eine versionierte .psymetriq.json-Projektdatei mit Auswahl und Workflow-Schritten.",
                    "Zum Beispiel data/workspaces/mental-health-review.psymetriq.json.",
                ),
                self._action_button(
                    "Projekt speichern",
                    "SAVE",
                    self._save_project,
                    "Speichert Projektname, ausgewählte Instrumentversionen/Items und eine kurze Prozesshistorie als portables JSON. API-Schlüssel und Itemtexte der Historie werden nicht gespeichert.",
                    "Ein gespeichertes Projekt lässt sich später unabhängig vom Rechner wieder laden.",
                    primary=True,
                ),
                self._action_button(
                    "Ethik-Dossier erstellen",
                    "FACT_CHECK",
                    self._export_ethics_dossier,
                    "Fasst Lizenz-, Zitations-, Populations- und Zeitangaben der ausgewählten Batterie als Markdown-Dokument zusammen. Keine Rechts- oder Ethikberatung, sondern eine Planungshilfe aus bereits im Katalog hinterlegten Angaben.",
                    "Jede Angabe muss vor Einreichung bei einer Ethikkommission gegen die aktuelle Quelle geprüft werden.",
                    disabled=not self.project.selections,
                ),
            ],
        )
        selected_rows: list[ft.Control] = []
        total_selections = len(self.project.selections)
        for selection_index, selection in enumerate(self.project.selections):
            found = self._find_version(selection.instrument_id, selection.version_id)
            if found is None:
                label = f"Nicht aufgelöst: {selection.instrument_id}/{selection.version_id}"
                selection_summary = (
                    f"{len(selection.item_ids)} ausgewählte Items · Katalogversion nicht aufgelöst"
                )
                item_rows = [
                    ft.Text(
                        "Diese Katalogversion ist aktuell nicht verfügbar.",
                        size=12,
                        color="#9B3E35",
                    )
                ]
            else:
                family, version = found
                label = f"{family.name_full} · {version.display_name or version.version_id}"
                if version.item_text_included:
                    item_count = len(self._selected_item_ids(selection.instrument_id, version))
                    selection_summary = f"{item_count} ausgewählte Items"
                else:
                    item_count = version.source_reported_item_count or "Unbekannte Anzahl"
                    selection_summary = f"Metadatenreferenz · {item_count} Items laut Quelle · Itemtext nicht enthalten"
                    if version.source_reported_dimensions:
                        selection_summary += " · Dimensionen: " + ", ".join(
                            version.source_reported_dimensions
                        )
                    if version.source_documents:
                        selection_summary += (
                            f" · Lizenz: {version.source_documents[0].license_name}"
                        )
                item_rows = self._project_item_rows(family, version, selection)
            adaptation_count = len(selection.item_adaptations)
            item_tile = ft.ExpansionTile(
                title=label,
                subtitle=(
                    f"Position {selection_index + 1} von {total_selections} · "
                    f"{selection_summary} · {adaptation_count} Studienanpassung(en)"
                ),
                expanded=False,
                maintain_state=True,
                controls=[ft.Column(spacing=6, controls=item_rows)],
                bgcolor="#F7F9F8",
                collapsed_bgcolor="#EEF3F1",
            )
            action_row = ft.Row(
                wrap=True,
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    self._action_button(
                        "Nach oben",
                        "ARROW_UPWARD",
                        lambda _event, s=selection: self._move_selection(s, -1),
                        "Verschiebt dieses Instrument in der Projektzusammenstellung nach oben.",
                        disabled=selection_index == 0,
                    ),
                    self._action_button(
                        "Nach unten",
                        "ARROW_DOWNWARD",
                        lambda _event, s=selection: self._move_selection(s, 1),
                        "Verschiebt dieses Instrument in der Projektzusammenstellung nach unten.",
                        disabled=selection_index == total_selections - 1,
                    ),
                    self._action_button(
                        "Entfernen",
                        "DELETE_OUTLINE",
                        lambda _event, s=selection: self._remove_selection(s),
                        "Entfernt diese Version aus dem aktuellen Projekt, ändert aber nicht den Katalog.",
                    ),
                ],
            )
            selected_rows.append(
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            item_tile,
                            ft.Text(
                                f"Versions-ID: {selection.version_id}",
                                size=10,
                                color="#55716A",
                                selectable=True,
                            ),
                            action_row,
                        ],
                    ),
                )
            )
        if not selected_rows:
            selected_rows.append(
                ft.Text(
                    "Noch keine Items ausgewählt. Wähle Versionen oder einzelne Items in der Bibliothek.",
                    color="#55716A",
                )
            )
        step_rows: list[ft.Control] = [
            ft.Text(
                f"{step.occurred_at.astimezone().strftime('%Y-%m-%d %H:%M')} · {step.summary}",
                size=11,
                color="#55716A",
            )
            for step in reversed(self.project.workflow_steps[-12:])
        ] or [
            ft.Text(
                "Projektschritte erscheinen hier, sobald Versionen ausgewählt, importiert oder exportiert wurden.",
                size=12,
                color="#55716A",
            )
        ]
        return [
            ft.Text(
                "Arbeitsstand speichern, später wieder laden und nachvollziehen.",
                size=13,
                color="#55716A",
            ),
            project_actions,
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Container(
                        expand=6,
                        content=self._panel(
                            "Projektinformationen",
                            ft.Column(
                                controls=[
                                    self._field(
                                        "Projektname",
                                        name_field,
                                        "Kurzer Name für diesen gespeicherten Arbeitsstand.",
                                        "Beispiel: PROMIS-Vergleich für Erwachsene.",
                                    ),
                                    self._field(
                                        "Projektbeschreibung",
                                        description_field,
                                        "Optionale Fragestellung oder methodische Notizen. Keine Teilnehmerdaten oder vertraulichen Angaben eintragen.",
                                        "Beispiel: Sprachvergleich für eine nichtklinische Erwachsenenstichprobe.",
                                    ),
                                ]
                            ),
                            "Projektmetadaten werden zusammen mit den referenzierten Versionen gespeichert.",
                        ),
                    ),
                    ft.Container(
                        expand=7,
                        content=self._panel(
                            "Ausgewählte Versionen und Items",
                            ft.Column(spacing=8, controls=selected_rows),
                            "Die Projektdatei speichert stabile Katalog-IDs und Item-IDs, nicht kopierte Itemtexte.",
                        ),
                    ),
                ],
            ),
            self._battery_time_panel(),
            self._panel(
                "Letzte Arbeitsschritte",
                ft.Column(spacing=5, controls=step_rows),
                "Ein kompakter Verlauf dokumentiert Import, Auswahl und Export. Er enthält keine API-Schlüssel und keine Itemtexte.",
            ),
        ]

    def _exchange_view(self) -> list[ft.Control]:
        selected_versions = self._selected_versions()
        choices = [ft.DropdownOption(key=key, text=label) for label, key in EXPORT_FORMATS.items()]
        format_dropdown = ft.Dropdown(
            value=self.export_format,
            options=choices,
            on_select=lambda event: self._set_export_format(event.control.value),
            width=320,
        )
        self.export_preview = ft.TextField(
            value=self._export_preview_text(),
            read_only=True,
            multiline=True,
            min_lines=10,
            max_lines=18,
            text_size=11,
        )
        return [
            ft.Text(
                "Dateiformate einlesen und ausgewählte Versionen standardisiert ausgeben.",
                size=13,
                color="#55716A",
            ),
            ft.Row(
                wrap=True,
                controls=[
                    self._action_button(
                        "Dateien importieren",
                        "UPLOAD_FILE",
                        self._choose_import_files,
                        "Unterstützt PsyMetriQ-Familien JSON, FHIR R4 Questionnaire JSON, REDCap Data Dictionary CSV, Qualtrics QSF, sowie LimeSurvey TSV und Unipark Paste-Text (die letzten beiden als .txt, automatisch erkannt).",
                        "Ein FHIR-Questionnaire wird in eine rights-unassessed PsyMetriQ-Version umgewandelt.",
                        primary=True,
                    ),
                    self._field(
                        "Exportformat",
                        format_dropdown,
                        "Wähle ein interoperables Zielformat. PsyMetriQ JSON ist verlustarm; FHIR nutzt dokumentierte PsyMetriQ-Extensions für Konstrukte, Scores und Locale.",
                        "REDCap Data Dictionary CSV kann direkt im REDCap-Projekt-Setup importiert werden.",
                    ),
                    self._action_button(
                        f"{len(selected_versions)} Version(en) als ZIP exportieren",
                        "DOWNLOAD",
                        self._export_bundle,
                        "Erstellt ein ZIP mit je einer Datei pro ausgewählter Version sowie einem Manifest der enthaltenen Formate und IDs.",
                        "Das Exportmanifest enthält Katalog-IDs und Versionen, keine API-Schlüssel.",
                        primary=True,
                        disabled=not selected_versions,
                    ),
                ],
            ),
            self._panel(
                "Exportvorschau",
                self._field(
                    "Vorschau der ersten ausgewählten Version",
                    self.export_preview,
                    "Zeigt einen Ausschnitt des gewählten Exports. Beim ZIP-Export sind alle Versionen enthalten; hier siehst du die erste Version zur Kontrolle.",
                    "Wechsle zwischen FHIR/REDCap/CSV/JSON und überprüfe Itemlabels und Antwortoptionen vor dem Export.",
                ),
                "Die Vorschau wird aus der Projektselektion erstellt und übernimmt nur ausgewählte Items.",
            ),
            self._panel(
                "REDCap (Live-API)",
                ft.Column(
                    spacing=10,
                    controls=[
                        ft.Text(
                            self.redcap_status_message, size=12, color="#55716A", selectable=True
                        ),
                        ft.Row(
                            wrap=True,
                            controls=[
                                self._action_button(
                                    "Mit REDCap verbinden",
                                    "LINK",
                                    self._redcap_connect,
                                    "Öffnet eine Verbindung mit dem in Einstellungen konfigurierten REDCap-Projekt (URL + Token aus .env) und bestätigt Projekttitel/-ID.",
                                    "Erfordert REDCAP_API_URL/Token-Variable in Einstellungen und einen gültigen Wert in der lokalen .env-Datei.",
                                ),
                                self._action_button(
                                    "Erste ausgewählte Version pushen",
                                    "UPLOAD",
                                    self._redcap_push,
                                    "Fügt die Felder der ersten im Projekt ausgewählten Version zum verbundenen REDCap-Projekt hinzu. Bricht bei Namenskonflikten ohne Änderung ab.",
                                    "Ein Metadata-Push ersetzt das gesamte Data Dictionary des Projekts; bestehende Felder bleiben nur erhalten, weil sie vorher mit übernommen werden.",
                                    disabled=self.redcap_project is None
                                    or not self._selected_versions(),
                                ),
                                self._action_button(
                                    "Data Dictionary importieren",
                                    "DOWNLOAD",
                                    self._redcap_pull,
                                    "Liest das komplette Data Dictionary des verbundenen REDCap-Projekts und fügt es als neues Instrument zum lokalen Katalog hinzu.",
                                    "Nicht unterstützte Feldtypen (z.B. calc, descriptive) werden nicht als Item importiert, sondern in den Instrument-Notizen aufgelistet.",
                                    disabled=self.redcap_project is None,
                                ),
                            ],
                        ),
                    ],
                ),
                "Ein REDCap-API-Token gewährt vollen Zugriff auf das jeweilige Projekt; Push-Aktionen werden zusätzlich bestätigt.",
            ),
            self._panel(
                "Zotero",
                self._action_button(
                    "Erste ausgewählte Version nach Zotero exportieren",
                    "UPLOAD",
                    self._push_to_zotero,
                    "Legt ein neues Zotero-Element mit Instrument-/Versionsangaben an und hängt die exportierte Datei (aktuelles Exportformat) daran an.",
                    "Erfordert ZOTERO_API_KEY und ZOTERO_USER_ID (oder ZOTERO_LIBRARY_ID) in der lokalen .env; optional ZOTERO_LIBRARY_TYPE/ZOTERO_COLLECTION_KEY.",
                    disabled=not selected_versions,
                ),
                "Legt einen Referenz-/Zitations-Eintrag für den Export an; ändert nichts an Weitergaberechten des Quellinstruments.",
            ),
            self._panel(
                "Importierte Standardformate",
                ft.Column(
                    spacing=5,
                    controls=[
                        ft.Text(
                            "PsyMetriQ JSON: validiert und versionsweise zusammengeführt.", size=12
                        ),
                        ft.Text(
                            "FHIR R4 Questionnaire JSON: Fragen/Antwortoptionen werden übernommen; nicht vorhandene Rechte- oder Validitätsangaben bleiben unbekannt.",
                            size=12,
                        ),
                        ft.Text(
                            "REDCap Data Dictionary CSV: Feldlabels, Antwortoptionen und Zahlenbereiche; CSV-Codes werden nicht als Scores interpretiert.",
                            size=12,
                        ),
                    ],
                ),
                "Beim Import werden Konflikte geprüft; vorhandene Versionen werden nie still ersetzt.",
            ),
        ]

    def _intake_view(self) -> list[ft.Control]:
        remote = self._remote_processing_enabled()
        inbox_directory = _resolve_path(self.settings.pdf_inbox_directory)
        inbox_files = sorted(inbox_directory.glob("*.pdf")) if inbox_directory.exists() else []
        self.intake_output = ft.TextField(
            value="Noch kein Verarbeitungslauf in dieser Sitzung.",
            read_only=True,
            multiline=True,
            min_lines=8,
            max_lines=14,
            text_size=12,
        )
        return [
            ft.Text(
                "Lokaler PDF-Posteingang mit expliziter, kontrollierter Remote-Option.",
                size=13,
                color="#55716A",
            ),
            self._panel(
                "Posteingang",
                ft.Column(
                    spacing=10,
                    controls=[
                        ft.Text(f"Ordner: {_relative_path(inbox_directory)}", selectable=True),
                        ft.Text(f"{len(inbox_files)} PDF-Datei(en) bereit", color="#55716A"),
                        self._action_button(
                            "Lokale PDFs verarbeiten" if not remote else "PDFs an Provider senden",
                            "PLAY_ARROW",
                            self._run_intake,
                            "Prüft PDFs, erzeugt Pydantic-Entwürfe und routet unklare Dokumente in den lokalen Review-Ordner. Keine automatische Rechtefreigabe.",
                            "Remote ist nur aktiv, wenn es in Einstellungen aktiviert und hier nochmals ausdrücklich bestätigt wird.",
                            primary=True,
                            disabled=not inbox_files,
                        ),
                    ],
                ),
                "PDF-Dateien aus dem lokalen Fragebogen-Inbox-Ordner.",
            ),
            self._panel(
                "Verarbeitungsergebnis",
                self._field(
                    "Letzter Lauf",
                    self.intake_output,
                    "Zeigt Status, Dateiname und Review-/Katalogpfade. Keine PDF-Inhalte oder API-Schlüssel werden angezeigt.",
                    "review_required bedeutet: Entwurf prüfen, Rechte/Items bestätigen und erst dann separat freigeben.",
                ),
                "Jede Veröffentlichung bleibt an die bestehende hashgebundene Rechte- und Inhaltsprüfung gekoppelt.",
            ),
        ]

    def _settings_view(self) -> list[ft.Control]:
        self.catalogue_path_field = ft.TextField(value=self.settings.catalogue_directory)
        self.export_path_field = ft.TextField(value=self.settings.export_directory)
        self.inbox_path_field = ft.TextField(value=self.settings.pdf_inbox_directory)
        self.review_path_field = ft.TextField(value=self.settings.pdf_review_directory)
        self.language_field = ft.TextField(value=self.settings.default_language)
        self.ocr_switch = ft.Switch(value=self.settings.enable_ocr)
        self.ocr_languages_field = ft.TextField(value=self.settings.ocr_languages)
        self.maximum_pdf_size_field = ft.TextField(
            value=str(self.settings.maximum_pdf_size_mib), keyboard_type=ft.KeyboardType.NUMBER
        )
        self.maximum_pdf_pages_field = ft.TextField(
            value=str(self.settings.maximum_pdf_pages), keyboard_type=ft.KeyboardType.NUMBER
        )
        self.maximum_text_characters_field = ft.TextField(
            value=str(self.settings.maximum_extracted_characters),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.minimum_text_characters_field = ft.TextField(
            value=str(self.settings.minimum_extracted_characters),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.confidence_threshold_field = ft.TextField(
            value=str(self.settings.extraction_confidence_threshold),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.watcher_poll_field = ft.TextField(
            value=str(self.settings.watcher_poll_seconds),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.provider_dropdown = ft.Dropdown(
            value=self.settings.llm_provider,
            options=[
                ft.DropdownOption(key="openai", text="OpenAI"),
                ft.DropdownOption(key="anthropic", text="Anthropic"),
                ft.DropdownOption(key="alpineai", text="AlpineAI SwissGPT"),
                ft.DropdownOption(key="openai-compatible", text="OpenAI-kompatibler Endpoint"),
            ],
            on_select=self._provider_changed,
        )
        self.model_field = ft.TextField(value=self.settings.llm_model)
        self.base_url_field = ft.TextField(value=self.settings.llm_base_url or "")
        self.key_environment_field = ft.TextField(value=self.settings.llm_api_key_environment)
        self.remote_processing_switch = ft.Switch(
            value=self.settings.remote_processing_enabled,
            label="Remote-PDF-Extraktion erlauben",
            disabled=not self.admin_config.remote_processing_allowed,
        )
        self.redcap_url_field = ft.TextField(value=self.settings.redcap_api_url)
        self.redcap_key_environment_field = ft.TextField(
            value=self.settings.redcap_api_key_environment
        )
        self.dark_mode_switch = ft.Switch(
            value=self.dark_mode,
            label="Dunkles Design",
            on_change=self._set_dark_mode,
        )
        self.font_size_dropdown = ft.Dropdown(
            value=self.font_size,
            options=[
                ft.DropdownOption(key="small", text="Klein"),
                ft.DropdownOption(key="normal", text="Normal"),
                ft.DropdownOption(key="large", text="Groß"),
            ],
            on_select=self._set_font_size,
            width=220,
        )
        self.export_format_dropdown = ft.Dropdown(
            value=self.settings.default_export_format,
            options=[
                ft.DropdownOption(key=value, text=label) for label, value in EXPORT_FORMATS.items()
            ],
        )
        return [
            ft.Text(
                "Pfade, Austauschstandard und optionale LLM-Anbindung konfigurieren.",
                size=13,
                color="#55716A",
            ),
            self._panel(
                "Darstellung",
                ft.Row(
                    wrap=True,
                    controls=[
                        self._field(
                            "Farbschema",
                            self.dark_mode_switch,
                            "Schaltet zwischen hellem und dunklem Farbschema um. Die Wahl wird lokal gespeichert und beim nächsten Start wiederhergestellt.",
                            "Dunkles Design ist unabhängig vom PDF-Remote-Opt-in.",
                        ),
                        self._field(
                            "Schriftgröße",
                            self.font_size_dropdown,
                            "Wählt eine kleinere oder größere Lesestufe für UI-Texte, Eingaben und Schaltflächen.",
                            "Klein, Normal oder Groß.",
                        ),
                    ],
                ),
                "Persönliche Darstellungsoptionen für diese lokale Installation.",
            ),
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Container(
                        expand=True,
                        content=self._panel(
                            "Dateien und Standards",
                            ft.Column(
                                spacing=12,
                                controls=[
                                    self._field(
                                        "Katalogordner",
                                        self.catalogue_path_field,
                                        "Ordner mit den validierten PsyMetriQ-JSON-Familien. Absolute und projekt-relative Pfade sind möglich.",
                                        "data/questionnaires/json",
                                    ),
                                    self._field(
                                        "Exportordner",
                                        self.export_path_field,
                                        "Vorgeschlagener lokaler Zielordner für Exporte. ZIP-Auswahl wird vor dem Speichern nochmals abgefragt.",
                                        "data/03_export_artifacts",
                                    ),
                                    self._field(
                                        "Standardsprache für REDCap-Importe",
                                        self.language_field,
                                        "Wird nur genutzt, wenn eine importierte REDCap CSV kein Sprachfeld besitzt.",
                                        "de oder en-US",
                                    ),
                                    self._field(
                                        "Standard-Exportformat",
                                        self.export_format_dropdown,
                                        "Vorauswahl in Import & Export. Unterstützt PsyMetriQ JSON, FHIR R4, Item-CSV und REDCap Data Dictionary CSV.",
                                    ),
                                ],
                            ),
                            "Diese Einstellungen werden lokal als versioniertes JSON gespeichert.",
                        ),
                    ),
                    ft.Container(
                        expand=True,
                        content=self._panel(
                            "LLM und Datenschutz",
                            ft.Column(
                                spacing=12,
                                controls=[
                                    self._field(
                                        "Provider",
                                        self.provider_dropdown,
                                        "OpenAI und Anthropic verwenden ihre nativen APIs. AlpineAI SwissGPT verwendet die dokumentierte OpenAI-kompatible Chat-Completions-API; andere Endpoints benötigen denselben Vertrag.",
                                        "SwissGPT API: https://api.prod.alpineai.ch/v1",
                                    ),
                                    self._field(
                                        "Modell-ID",
                                        self.model_field,
                                        "Wähle ein Konto-verfügbares Modell aus der API-Liste oder gib eine Modell-ID manuell ein.",
                                        "Die Liste hängt von Account, Berechtigungen und Provider ab.",
                                    ),
                                    self._action_button(
                                        "Modelle laden",
                                        "REFRESH",
                                        self._load_provider_models,
                                        "Fragt die verfügbare Modellliste des gewählten Accounts über dessen Models-API ab. Die freie Modell-ID-Eingabe bleibt für nicht gelistete/alias IDs verfügbar.",
                                        "OpenAI/AlpineAI: GET /v1/models; Anthropic: GET /v1/models.",
                                    ),
                                    self._field(
                                        "OpenAI-kompatible Base-URL",
                                        self.base_url_field,
                                        "Nur für OpenAI-kompatible Endpoints. Die Base-URL ist kein Schlüssel; Zugangsdaten bleiben in der Umgebungsvariable.",
                                        "Zum Beispiel https://<anbieter>/v1",
                                    ),
                                    self._field(
                                        "API-Key-Variablenname",
                                        self.key_environment_field,
                                        "Name einer Umgebungsvariablen, deren Wert den Schlüssel enthält. Das GUI speichert niemals den Schlüssel selbst.",
                                        "OPENAI_API_KEY, ANTHROPIC_API_KEY, ALPINEAI_API_KEY oder SWISSGPT_API_KEY",
                                    ),
                                    self._field(
                                        "Remote-Opt-in",
                                        self.remote_processing_switch,
                                        "Wenn aktiviert, kann der PDF-Posteingang extrahierten Volltext an den gewählten Provider senden. Prüfe vorher Hochschulregeln, Verträge und Quellenrechte."
                                        + (
                                            ""
                                            if self.admin_config.remote_processing_allowed
                                            else " Von der Administration deployment-weit deaktiviert."
                                        ),
                                        "Die Checkbox ist standardmäßig aus; jeder Remote-Lauf wird zusätzlich bestätigt.",
                                    ),
                                ],
                            ),
                            "Kein API-Schlüssel wird in Einstellungen, Projekten oder Exportdateien abgelegt.",
                        ),
                    ),
                ],
            ),
            self._panel(
                "REDCap (Live-API)",
                ft.Column(
                    spacing=12,
                    controls=[
                        self._field(
                            "REDCap API-URL",
                            self.redcap_url_field,
                            "Die API-Adresse deiner REDCap-Instanz, z. B. https://redcap.deine-uni.de/api/.",
                            "Zu finden im REDCap-Projekt unter API > API-Dokumentation.",
                        ),
                        self._field(
                            "API-Token-Variablenname",
                            self.redcap_key_environment_field,
                            "Name einer Umgebungsvariablen (in .env), deren Wert das projektspezifische REDCap-API-Token enthält. Das GUI speichert niemals den Token selbst.",
                            "REDCAP_API_TOKEN",
                        ),
                    ],
                ),
                "Ein REDCap-API-Token gewährt vollen Lese-/Schreibzugriff auf das jeweilige Projekt; behandle es wie ein Passwort.",
            ),
            self._panel(
                "PDF-Import und OCR",
                ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            wrap=True,
                            controls=[
                                self._field(
                                    "PDF-Inboxordner",
                                    self.inbox_path_field,
                                    "Lokaler Ordner, aus dem die GUI PDF-Dateien für einen Verarbeitungslauf einliest.",
                                    "data/questionnaires/inbox",
                                ),
                                self._field(
                                    "Reviewordner",
                                    self.review_path_field,
                                    "Lokaler, von Git ignorierter Ordner für Originale und unvollständige Entwürfe.",
                                    "data/questionnaires/review",
                                ),
                            ],
                        ),
                        ft.Row(
                            wrap=True,
                            controls=[
                                self._field(
                                    "OCR",
                                    self.ocr_switch,
                                    "Erkennt Text auf eingescannten Seiten lokal, sofern Tesseract samt Sprachen installiert ist.",
                                    "Bei OCR-Ausfall bleibt die Datei im Review; es wird kein Text erfunden.",
                                ),
                                self._field(
                                    "OCR-Sprachen",
                                    self.ocr_languages_field,
                                    "Tesseract-Sprachcodes, kombiniert mit '+'. Die Sprachpakete müssen lokal installiert sein.",
                                    "eng+deu",
                                ),
                                self._field(
                                    "Maximale PDF-Größe (MiB)",
                                    self.maximum_pdf_size_field,
                                    "Größere PDFs werden vor dem Lesen abgelehnt, um Arbeitsspeicher und Laufzeit zu begrenzen.",
                                    "40 MiB",
                                ),
                                self._field(
                                    "Maximale Seiten",
                                    self.maximum_pdf_pages_field,
                                    "Obergrenze für Seiten pro Quelldatei.",
                                    "500 Seiten",
                                ),
                                self._field(
                                    "Maximaler extrahierter Text",
                                    self.maximum_text_characters_field,
                                    "Zeichenlimit für den kompletten extrahierten PDF-Text. Trunkierte Inhalte werden nicht katalogisiert.",
                                    "120000 Zeichen",
                                ),
                                self._field(
                                    "Mindesttext für Extraktion",
                                    self.minimum_text_characters_field,
                                    "Unter diesem Textumfang wird keine LLM-Extraktion gestartet; das Dokument geht in die Review.",
                                    "160 Zeichen",
                                ),
                                self._field(
                                    "Konfidenzschwelle",
                                    self.confidence_threshold_field,
                                    "Mindestwert von 0 bis 1 für eine vorgeschlagene Katalogpromotion. Rechte- und Inhaltsprüfung bleiben trotzdem verpflichtend.",
                                    "0.92 bedeutet 92 Prozent",
                                ),
                                self._field(
                                    "Watcher-Intervall (Sekunden)",
                                    self.watcher_poll_field,
                                    "Abstand zwischen lokalen Inbox-Prüfungen, falls später der Watcher-Modus gestartet wird.",
                                    "3 Sekunden",
                                ),
                            ],
                        ),
                    ],
                ),
                "Grenzwerte und OCR-Sprachen werden pro lokaler Installation gespeichert und vor jeder Verarbeitung validiert.",
            ),
            ft.Row(
                wrap=True,
                controls=[
                    ft.Row(
                        wrap=True,
                        controls=[
                            self._action_button(
                                "Einstellungen laden",
                                "FOLDER_OPEN",
                                self._import_settings,
                                "Lädt eine validierte JSON-Einstellungsdatei. Zum dauerhaften Anwenden anschließend lokal speichern.",
                                "Die Datei enthält keine Schlüsselwerte, nur Namen von Umgebungsvariablen.",
                            ),
                            self._action_button(
                                "Einstellungen exportieren",
                                "DOWNLOAD",
                                self._export_settings,
                                "Exportiert die aktuellen Formularwerte als portable JSON-Datei für eine Teamvorlage.",
                                "API-Schlüssel selbst werden niemals exportiert.",
                            ),
                            self._action_button(
                                "Einstellungen speichern",
                                "SAVE",
                                self._save_settings,
                                "Speichert die Formulareinstellungen lokal und lädt den Katalog neu, falls sein Ordner geändert wurde.",
                                "Die Datei data/psymetriq-settings.json ist lokal und Git-ignoriert.",
                                primary=True,
                            ),
                        ],
                    ),
                ],
            ),
        ]

    def _provider_changed(self, event: Any) -> None:
        provider = event.control.value
        previous_provider = self.active_provider
        defaults = {
            "openai": ("gpt-4o-mini", "OPENAI_API_KEY"),
            "anthropic": ("claude-sonnet-4-6", "ANTHROPIC_API_KEY"),
            "alpineai": ("mistral-large-3-675b-nvfp4", "ALPINEAI_API_KEY"),
            "openai-compatible": ("", "LLM_API_KEY"),
        }
        model, key_environment = defaults.get(provider, defaults["openai"])
        if not self.model_field.value or self.model_field.value in {
            value[0] for value in defaults.values()
        }:
            self.model_field.value = model
        self.key_environment_field.value = key_environment
        alpine_default_url = "https://api.prod.alpineai.ch/v1"
        if provider == "alpineai" and previous_provider != "alpineai":
            self.base_url_field.value = os.environ.get("ALPINEAI_BASE_URL", alpine_default_url)
        elif (
            previous_provider == "alpineai"
            and provider == "openai-compatible"
            and self.base_url_field.value == alpine_default_url
        ):
            self.base_url_field.value = ""
        self.active_provider = provider
        self.available_models = []
        self.page.update()

    async def _load_provider_models(self, _event: Any) -> None:
        provider = self.provider_dropdown.value
        key_environment = (self.key_environment_field.value or "").strip()
        api_key = os.environ.get(key_environment, "")
        if provider == "alpineai" and not api_key:
            api_key = os.environ.get("SWISSGPT_API_KEY", "")
        try:
            models = await list_available_models(
                provider=provider,
                api_key=api_key,
                base_url=(self.base_url_field.value or "").strip() or None,
            )
        except ModelDiscoveryError as error:
            self._set_status(str(error), error=True)
            return
        self.available_models = models
        model_dropdown = ft.Dropdown(
            label="Verfügbare Modell-ID",
            value=models[0],
            options=[ft.DropdownOption(key=model, text=model) for model in models],
            expand=True,
        )

        def choose_model(_event: Any) -> None:
            self.model_field.value = model_dropdown.value
            self.page.pop_dialog()
            self._set_status(f"Modell ausgewählt: {model_dropdown.value}")

        self._show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Modelle von {provider}"),
                content=ft.Column(
                    tight=True,
                    controls=[
                        ft.Text(
                            f"{len(models)} Modell-IDs verfügbar. Die Liste stammt vom Anbieter-Account.",
                            size=12,
                        ),
                        model_dropdown,
                    ],
                ),
                actions=[
                    ft.Button(
                        content="Abbrechen",
                        on_click=lambda _event: self.page.pop_dialog(),
                    ),
                    ft.Button(content="Modell verwenden", on_click=choose_model),
                ],
            )
        )

    def _submit_search(self) -> None:
        self.search_query = self.search_field.value or ""
        self._render()

    def _set_language_filter(self, value: str | None) -> None:
        self.language_filter = value or "all"
        self._render()

    def _set_catalog_filter(self, filter_name: str, value: str | None) -> None:
        filter_attributes = {
            "locale": "locale_filter",
            "form_type": "form_type_filter",
            "population": "population_filter",
            "commercial": "commercial_filter",
            "license": "license_filter",
            "content": "item_content_filter",
        }
        attribute = filter_attributes.get(filter_name)
        if attribute is None:
            raise ValueError(f"Unknown catalogue filter: {filter_name}")
        setattr(self, attribute, value or "all")
        self._render()

    def _show_version(self, key: tuple[str, str]) -> None:
        self.active_version_key = key
        self._render()

    def _set_export_format(self, value: str | None) -> None:
        if value:
            self.export_format = value
        self._render()

    def _update_project_name(self, value: str | None) -> None:
        self.project = self.project.model_copy(update={"name": value or "Neues Projekt"})

    def _update_project_description(self, value: str | None) -> None:
        self.project = self.project.model_copy(update={"description": value or ""})

    def _remove_selection(self, selection: VersionSelection) -> None:
        self.project.selections = [
            current for current in self.project.selections if current != selection
        ]
        self.project = self.project.record_step(
            "version_removed",
            f"Version aus Projekt entfernt: {selection.instrument_id}/{selection.version_id}",
            f"{selection.instrument_id}/{selection.version_id}",
        )
        self._render()

    def _move_selection(self, selection: VersionSelection, direction: int) -> None:
        selections = list(self.project.selections)
        try:
            index = selections.index(selection)
        except ValueError:
            return
        target_index = index + direction
        if target_index < 0 or target_index >= len(selections):
            return
        selections[index], selections[target_index] = selections[target_index], selections[index]
        self.project = self.project.model_copy(update={"selections": selections}).record_step(
            "selection_reordered",
            "Reihenfolge der Instrumente geändert",
            f"{selection.instrument_id}/{selection.version_id}",
        )
        self._render()

    def _project_item_rows(
        self,
        family: QuestionnaireParent,
        version: QuestionnaireVersion,
        selection: VersionSelection,
    ) -> list[ft.Control]:
        selected_ids = self._selected_item_ids(family.instrument_id, version)
        if not version.item_text_included:
            return [
                ft.Text(
                    "Metadatenreferenz ohne Itemtexte. Dimensionen: "
                    + (", ".join(version.source_reported_dimensions) or "nicht dokumentiert"),
                    size=12,
                    color="#8A4A2E",
                    selectable=True,
                )
            ]
        item_rows: list[ft.Control] = []
        for item in version.items:
            if item.item_id not in selected_ids:
                continue
            adaptation = self._item_adaptation(family, version, item.item_id)
            item_rows.append(
                ft.Container(
                    bgcolor="#F7F9F8",
                    padding=8,
                    border_radius=6,
                    content=ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(
                                adaptation.adapted_prompt_text if adaptation else item.prompt_text,
                                size=12,
                                selectable=True,
                                color="#8A4A2E" if adaptation else "#203F39",
                            ),
                            ft.Text(
                                f"{item.item_id} · {item.dimension} · "
                                f"{item.response_mode} · {item.variable_name}",
                                size=10,
                                color="#55716A",
                                selectable=True,
                            ),
                        ],
                    ),
                )
            )
        return item_rows or [ft.Text("Keine Items ausgewählt.", size=12, color="#55716A")]

    def _reload_and_render(self) -> None:
        self._reload_catalog()
        self._render()

    async def _choose_import_files(self, _event: Any) -> None:
        files = await self.file_picker.pick_files(
            dialog_title="PsyMetriQ- oder Standarddateien importieren",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json", "csv", "txt", "qsf"],
            allow_multiple=True,
            with_data=True,
        )
        if not files:
            return
        imported: list[QuestionnaireParent] = []
        try:
            for file in files:
                if file.bytes is not None:
                    text = file.bytes.decode("utf-8-sig")
                    records = import_questionnaire_content(
                        text,
                        file_name=file.name,
                        redcap_language=self.settings.default_language,
                    )
                elif file.path:
                    records = await asyncio.to_thread(
                        import_questionnaire_file,
                        file.path,
                        redcap_language=self.settings.default_language,
                    )
                else:
                    raise DataExchangeError(f"Dateiinhalt nicht verfügbar: {file.name}")
                imported.extend(records)
            saved = await asyncio.to_thread(self.catalog_store.import_families, imported)
            self._reload_catalog(silent=True)
            ids = ", ".join(family.instrument_id for family in saved)
            self.project = self.project.record_step(
                "catalog_import",
                f"{len(saved)} Familie(n) importiert oder aktualisiert",
                ids[:250] or None,
            )
            self._set_status(f"Import erfolgreich: {ids}")
            self._render()
        except (DataExchangeError, CatalogStoreError, OSError, UnicodeError) as error:
            LOGGER.warning("Questionnaire import failed (%s)", type(error).__name__)
            self._set_status(str(error), error=True)

    async def _save_project(self, _event: Any) -> None:
        file_name = f"{_safe_filename(self.project.name)}.psymetriq.json"
        saved_project = self.project.model_copy(
            update={"catalogue_directory": self.settings.catalogue_directory}
        ).record_step("project_saved", "Projekt gespeichert", file_name)
        project_bytes = json.dumps(
            saved_project.model_dump(mode="json"), ensure_ascii=False, indent=2
        ).encode("utf-8")
        path = await self.file_picker.save_file(
            dialog_title="Projekt speichern",
            file_name=file_name,
            initial_directory=str(PROJECT_ROOT / "data" / "workspaces"),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"],
            src_bytes=project_bytes,
        )
        self.project = saved_project
        self.project_path = Path(path) if path else None
        self._set_status(
            f"Projektdatei bereit: {path or file_name}. "
            "Im Browser erscheint sie im Downloadbereich."
        )
        self._render()

    async def _export_ethics_dossier(self, _event: Any) -> None:
        selected = self._selected_versions()
        if not selected:
            self._set_status(
                "Es sind keine Versionen ausgewählt; es gibt nichts für ein Dossier.", error=True
            )
            return
        try:
            dossier = build_ethics_dossier(
                selected,
                project_name=self.project.name,
                project_description=self.project.description or None,
            )
        except EthicsDossierError as error:
            self._set_status(str(error), error=True)
            return
        file_name = f"{_safe_filename(self.project.name)}.ethics-dossier.md"
        path = await self.file_picker.save_file(
            dialog_title="Ethik-Dossier speichern",
            file_name=file_name,
            initial_directory=str(PROJECT_ROOT / "data" / "workspaces"),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["md"],
            src_bytes=dossier.encode("utf-8"),
        )
        self.project = self.project.record_step("exported", "Ethik-Dossier erstellt", file_name)
        self._set_status(
            f"Ethik-Dossier bereit: {path or file_name}. "
            "Im Browser erscheint es im Downloadbereich. Vor Einreichung prüfen."
        )
        self._render()

    async def _choose_project(self, _event: Any) -> None:
        files = await self.file_picker.pick_files(
            dialog_title="PsyMetriQ-Projekt laden",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"],
            allow_multiple=False,
            with_data=True,
        )
        if not files:
            return
        try:
            selected_file = files[0]
            if selected_file.bytes is not None:
                loaded = WorkspaceStore.load_project_content(
                    selected_file.bytes.decode("utf-8-sig"), selected_file.name
                )
            elif selected_file.path:
                loaded = await asyncio.to_thread(WorkspaceStore.load_project, selected_file.path)
            else:
                raise WorkspacePersistenceError("Der Projektdateiinhalt ist nicht verfügbar")
            self.project = loaded.record_step("project_loaded", "Projekt geladen", files[0].name)
            self.project_path = Path(selected_file.path) if selected_file.path else None
            self._set_status(f"Projekt geladen: {self.project.name}")
            self._render()
        except (WorkspacePersistenceError, UnicodeError) as error:
            self._set_status(str(error), error=True)

    def _selected_versions(
        self,
    ) -> list[tuple[QuestionnaireParent, QuestionnaireVersion, list[str]]]:
        selected: list[tuple[QuestionnaireParent, QuestionnaireVersion, list[str]]] = []
        for reference in self.project.selections:
            found = self._find_version(reference.instrument_id, reference.version_id)
            if found is None:
                continue
            family, version = found
            item_ids = reference.item_ids or [item.item_id for item in version.items]
            selected.append((family, version, item_ids))
        return selected

    def _battery_time_summary(self) -> tuple[str, list[str]]:
        """Summarize the selected battery's estimated completion time.

        Prefers each version's source-reported ``administration_time``;
        falls back to a labelled item-count heuristic; never silently drops
        a version whose time could not be estimated either way.
        """
        selected = self._selected_versions()
        if not selected:
            return "Noch keine Versionen für eine Zeitschätzung ausgewählt.", []
        battery = estimate_battery_time(selected)
        low, high = battery.minimum_minutes, battery.maximum_minutes
        if low is None:
            headline = "Geschätzte Bearbeitungszeit unbekannt (keine Quellenangabe oder Itemanzahl vorhanden)."
        else:
            headline = f"Geschätzte Bearbeitungszeit der Batterie: ca. {low:.0f}–{high:.0f} Minuten"
            if battery.has_unknown_entries:
                headline += " (ohne die Version(en) mit unbekannter Zeit)"
        lines = []
        for entry in battery.entries:
            if entry.minimum_minutes is None:
                lines.append(f"{entry.label}: unbekannt")
                continue
            basis = "Quellenangabe" if entry.source == "source_reported" else "Schätzung"
            lines.append(
                f"{entry.label}: ca. {entry.minimum_minutes:.0f}–{entry.maximum_minutes:.0f} Min. ({basis})"
            )
        return headline, lines

    def _battery_time_panel(self) -> ft.Control:
        headline, lines = self._battery_time_summary()
        return self._panel(
            "Geschätzte Bearbeitungszeit der Batterie",
            ft.Column(
                spacing=4,
                controls=[
                    ft.Text(headline, size=13, weight=ft.FontWeight.BOLD),
                    *[ft.Text(line, size=12, color="#55716A") for line in lines],
                ],
            ),
            "Schätzwerte ohne Quellenangabe sind eine grobe Näherung aus Itemzahl/-format für Planung "
            "und Ethikanträge, kein validierter Normwert für die tatsächliche Bearbeitungsdauer.",
        )

    @staticmethod
    def _metadata_reference_payload(
        family: QuestionnaireParent, version: QuestionnaireVersion
    ) -> dict[str, Any]:
        """Serialize a reference record without adding or implying questionnaire wording."""
        return {
            "format": "psymetriq-metadata-reference",
            "schema_version": 1,
            "instrument_id": family.instrument_id,
            "name_full": family.name_full,
            "constructs": family.construct_ontology,
            "is_commercial": family.is_commercial,
            "family_metadata": family.metadata.model_dump(mode="json"),
            "version": version.model_dump(mode="json"),
            "item_text_included": False,
            "reference_note": (
                "Reference metadata only. This file does not contain item wording or grant "
                "permission to reproduce, administer, translate, adapt, or redistribute the form."
            ),
        }

    def _export_preview_text(self) -> str:
        selected = self._selected_versions()
        if not selected:
            return "Wähle zuerst Versionen oder Items in Bibliothek und Projekt."
        family, version, item_ids = selected[0]
        note = (
            f"Vorschau: {family.instrument_id}/{version.version_id}; "
            f"{len(selected)} Version(en) im ZIP.\n\n"
        )
        if not version.item_text_included:
            return (
                note
                + json.dumps(
                    self._metadata_reference_payload(family, version),
                    ensure_ascii=False,
                    indent=2,
                )[:12_000]
            )
        try:
            subset = select_questionnaire_items(
                family,
                version.version_id,
                item_ids,
                adaptations=self._adaptations_for_selection(
                    family.instrument_id, version.version_id
                ),
            )
            _, content = export_questionnaire(subset, version.version_id, self.export_format)
            if isinstance(content, bytes):
                preview = (
                    f"XLSX-Arbeitsmappe mit {len(subset.versions[0].items)} Items. "
                    "Blätter: Items, Antwortoptionen, Scoring, Quellen."
                )
            else:
                preview = content
            return note + preview[:12_000]
        except DataExchangeError as error:
            return str(error)

    async def _export_bundle(self, _event: Any) -> None:
        selected = self._selected_versions()
        if not selected:
            self._set_status("Es sind keine exportierbaren Versionen ausgewählt.", error=True)
            return
        buffer = io.BytesIO()
        manifest: dict[str, Any] = {
            "format": "psymetriq-export-bundle",
            "schema_version": 1,
            "project_id": self.project.project_id,
            "project_name": self.project.name,
            "export_format": self.export_format,
            "selections": [],
            "psychometric_warning": (
                "Study-adapted item wording is not equivalent to the validated source version. "
                "Affected scoring algorithms are omitted."
            ),
        }
        try:
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for family, version, item_ids in selected:
                    if not version.item_text_included:
                        file_name = (
                            f"{_safe_filename(family.instrument_id)}_"
                            f"{_safe_filename(version.version_id)}.reference.json"
                        )
                        reference_payload = self._metadata_reference_payload(family, version)
                        archive.writestr(
                            file_name,
                            json.dumps(reference_payload, ensure_ascii=False, indent=2).encode(
                                "utf-8"
                            ),
                        )
                        manifest["selections"].append(
                            {
                                "instrument_id": family.instrument_id,
                                "version_id": version.version_id,
                                "selection_type": "metadata_reference",
                                "item_text_included": False,
                                "item_ids": [],
                                "license_names": [
                                    source.license_name for source in version.source_documents
                                ],
                                "file": file_name,
                            }
                        )
                        continue
                    adaptations = self._adaptations_for_selection(
                        family.instrument_id, version.version_id
                    )
                    subset = select_questionnaire_items(
                        family,
                        version.version_id,
                        item_ids,
                        adaptations=adaptations,
                    )
                    extension, content = export_questionnaire(
                        subset, version.version_id, self.export_format
                    )
                    file_name = (
                        f"{_safe_filename(family.instrument_id)}_"
                        f"{_safe_filename(version.version_id)}{extension}"
                    )
                    archive.writestr(
                        file_name,
                        content if isinstance(content, bytes) else content.encode("utf-8"),
                    )
                    manifest["selections"].append(
                        {
                            "instrument_id": family.instrument_id,
                            "version_id": version.version_id,
                            "selection_type": "item_selection",
                            "item_text_included": True,
                            "item_ids": item_ids,
                            "adapted_item_ids": sorted(adaptations),
                            "adaptation_reasons": {
                                item_id: reason
                                for item_id, (_prompt, reason) in adaptations.items()
                            },
                            "file": file_name,
                        }
                    )
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                )
        except DataExchangeError as error:
            self._set_status(str(error), error=True)
            return

        suggested_name = f"{_safe_filename(self.project.name)}-export.zip"
        path = await self.file_picker.save_file(
            dialog_title="Exportpaket speichern",
            file_name=suggested_name,
            initial_directory=str(_resolve_path(self.settings.export_directory)),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["zip"],
            src_bytes=buffer.getvalue(),
        )
        if not path:
            return
        self.project = self.project.record_step(
            "exported",
            f"{len(selected)} Version(en) als {self.export_format} exportiert",
            Path(path).name,
        )
        self._set_status(f"Exportpaket erstellt: {path}")
        self._render()

    async def _save_settings(self, _event: Any) -> None:
        try:
            new_settings = self._settings_from_controls()
            await asyncio.to_thread(self.workspace_store.save_settings, new_settings)
            catalog_changed = new_settings.catalogue_directory != self.settings.catalogue_directory
            self.settings = new_settings
            self.export_format = new_settings.default_export_format
            self.project.catalogue_directory = new_settings.catalogue_directory
            self.project = self.project.record_step(
                "settings_saved", "Einstellungen lokal gespeichert"
            )
            if catalog_changed:
                self._reload_catalog(silent=True)
            self._set_status(f"Einstellungen gespeichert: {_relative_path(SETTINGS_PATH)}")
            self._render()
        except Exception as error:
            LOGGER.warning("GUI settings could not be saved (%s)", type(error).__name__)
            self._set_status(f"Einstellungen nicht gespeichert: {error}", error=True)

    def _settings_from_controls(self) -> WorkspaceSettings:
        """Validate the currently edited preferences before save or export."""
        return WorkspaceSettings(
            catalogue_directory=(self.catalogue_path_field.value or "").strip(),
            export_directory=(self.export_path_field.value or "").strip(),
            pdf_inbox_directory=(self.inbox_path_field.value or "").strip(),
            pdf_review_directory=(self.review_path_field.value or "").strip(),
            default_language=(self.language_field.value or "").strip(),
            default_export_format=self.export_format_dropdown.value,
            theme_mode="dark" if self.dark_mode else "light",
            font_size=self.font_size,
            enable_ocr=bool(self.ocr_switch.value),
            ocr_languages=(self.ocr_languages_field.value or "").strip(),
            maximum_pdf_size_mib=int(self.maximum_pdf_size_field.value or "40"),
            maximum_pdf_pages=int(self.maximum_pdf_pages_field.value or "500"),
            maximum_extracted_characters=int(self.maximum_text_characters_field.value or "120000"),
            minimum_extracted_characters=int(self.minimum_text_characters_field.value or "160"),
            extraction_confidence_threshold=float(self.confidence_threshold_field.value or "0.92"),
            watcher_poll_seconds=float(self.watcher_poll_field.value or "3"),
            llm_provider=self.provider_dropdown.value,
            llm_model=(self.model_field.value or "").strip(),
            llm_base_url=(self.base_url_field.value or "").strip() or None,
            llm_api_key_environment=(self.key_environment_field.value or "").strip(),
            remote_processing_enabled=bool(self.remote_processing_switch.value),
            redcap_api_url=(self.redcap_url_field.value or "").strip(),
            redcap_api_key_environment=(self.redcap_key_environment_field.value or "").strip(),
        )

    def _apply_settings(self, settings: WorkspaceSettings) -> None:
        """Apply imported preferences to this session without persisting implicitly."""
        catalog_changed = settings.catalogue_directory != self.settings.catalogue_directory
        self.settings = settings
        self.dark_mode = settings.theme_mode == "dark"
        self.font_size = settings.font_size
        self.export_format = settings.default_export_format
        self.project.catalogue_directory = settings.catalogue_directory
        if catalog_changed:
            self._reload_catalog(silent=True)

    async def _import_settings(self, _event: Any) -> None:
        files = await self.file_picker.pick_files(
            dialog_title="PsyMetriQ-Einstellungen laden",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"],
            allow_multiple=False,
            with_data=True,
        )
        if not files:
            return
        try:
            selected_file = files[0]
            if selected_file.bytes is not None:
                settings = WorkspaceSettings.model_validate_json(
                    selected_file.bytes.decode("utf-8-sig")
                )
            elif selected_file.path:
                settings = await asyncio.to_thread(WorkspaceStore(selected_file.path).load_settings)
            else:
                raise WorkspacePersistenceError("Der Einstellungsdateiinhalt ist nicht verfügbar")
            self._apply_settings(settings)
            self._set_status(
                f"Einstellungen geladen: {selected_file.name}. "
                "Zum dauerhaften Übernehmen lokal speichern."
            )
            self._render()
        except (WorkspacePersistenceError, ValidationError, UnicodeError) as error:
            self._set_status(f"Einstellungen nicht geladen: {error}", error=True)

    async def _export_settings(self, _event: Any) -> None:
        try:
            content = json.dumps(
                self._settings_from_controls().model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
        except ValidationError as error:
            self._set_status(f"Einstellungen ungültig: {error}", error=True)
            return
        path = await self.file_picker.save_file(
            dialog_title="PsyMetriQ-Einstellungen exportieren",
            file_name="psymetriq-settings.json",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["json"],
            src_bytes=content,
        )
        if path:
            self._set_status(f"Einstellungen exportiert: {path}")

    async def _run_intake(self, _event: Any) -> None:
        remote_enabled = self._remote_processing_enabled()
        if remote_enabled:
            confirmed = await self._confirm_remote_intake()
            if not confirmed:
                return
        from src.ingestion.document_pipeline import PipelineConfig, process_inbox

        config = PipelineConfig(
            inbox_directory=_resolve_path(self.settings.pdf_inbox_directory),
            review_directory=_resolve_path(self.settings.pdf_review_directory),
            catalogue_directory=_resolve_path(self.settings.catalogue_directory),
            maximum_file_size_bytes=self.settings.maximum_pdf_size_mib * 1024 * 1024,
            maximum_page_count=self.settings.maximum_pdf_pages,
            maximum_text_characters=self.settings.maximum_extracted_characters,
            minimum_text_characters=self.settings.minimum_extracted_characters,
            confidence_threshold=self.settings.extraction_confidence_threshold,
            ocr_languages=self.settings.ocr_languages,
            enable_ocr=self.settings.enable_ocr,
            poll_interval_seconds=self.settings.watcher_poll_seconds,
        )
        try:
            results = await process_inbox(
                config=config,
                allow_remote_processing=remote_enabled,
                provider=self.settings.llm_provider,
                model=self.settings.llm_model or None,
                base_url=self.settings.llm_base_url,
                api_key_env=self.settings.llm_api_key_environment,
            )
            lines = [
                f"{result.status}: {result.source_filename} · "
                f"Entwurf: {result.draft_path or '—'} · Katalog: {result.catalogue_path or '—'}"
                for result in results
            ]
            self.intake_output.value = "\n".join(lines) or "Keine PDFs im Posteingang gefunden."
            self._reload_catalog(silent=True)
            self.project = self.project.record_step(
                "catalog_reload", f"PDF-Posteingang verarbeitet: {len(results)} Datei(en)"
            )
            self._set_status(f"PDF-Lauf abgeschlossen: {len(results)} Datei(en)")
            self._render()
        except Exception as error:
            LOGGER.warning("PDF intake failed in GUI (%s)", type(error).__name__)
            self.intake_output.value = f"Verarbeitung fehlgeschlagen: {error}"
            self._set_status(f"PDF-Import fehlgeschlagen: {error}", error=True)
            self._render()

    def _redcap_token(self) -> str:
        return os.environ.get(self.settings.redcap_api_key_environment, "")

    async def _redcap_connect(self, _event: Any) -> None:
        token = self._redcap_token()
        if not self.settings.redcap_api_url or not token:
            self._set_status(
                "REDCap-URL und Token-Umgebungsvariable (.env) sind erforderlich.", error=True
            )
            return
        try:
            project = await asyncio.to_thread(redcap_connect, self.settings.redcap_api_url, token)
            summary = await asyncio.to_thread(redcap_describe_project, project)
        except RedcapApiError as error:
            self.redcap_project = None
            self.redcap_project_summary = None
            self.redcap_status_message = f"Verbindung fehlgeschlagen: {error}"
            self._render()
            return
        self.redcap_project = project
        self.redcap_project_summary = summary
        self.redcap_status_message = (
            f"Verbunden: {summary.project_title} (Projekt-ID {summary.project_id})"
        )
        self._render()

    async def _confirm_redcap_push(self, form_name: str, field_count: int) -> tuple[bool, bool]:
        """Ask for push confirmation; return (confirmed, allow_update)."""
        result: asyncio.Future[tuple[bool, bool]] = asyncio.get_running_loop().create_future()
        allow_update_checkbox = ft.Checkbox(
            label=(
                "Bestehende Felder mit gleichem Namen bewusst aktualisieren (z.B. nach einer "
                "Korrektur), statt bei jedem Namenskonflikt komplett abzubrechen."
            ),
            value=False,
        )

        def finish(value: bool) -> None:
            if not result.done():
                result.set_result((value, bool(allow_update_checkbox.value)))
            self.page.pop_dialog()

        self._show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Data Dictionary nach REDCap pushen?"),
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(
                            f"{field_count} Feld(er) für Formular '{form_name}' werden zu den "
                            f"bestehenden Feldern von {self.redcap_project_summary.project_title if self.redcap_project_summary else 'diesem Projekt'} "
                            "hinzugefügt. REDCaps Metadata-Import ersetzt das gesamte Data "
                            "Dictionary des Projekts; ohne die Option unten wird bei einem "
                            "Namenskonflikt nichts geschrieben. Fortfahren?"
                        ),
                        allow_update_checkbox,
                    ],
                ),
                actions=[
                    ft.Button(content="Abbrechen", on_click=lambda _event: finish(False)),
                    ft.Button(
                        content="Bestätigen und pushen",
                        bgcolor="#9B3E35",
                        color="#FFFFFF",
                        on_click=lambda _event: finish(True),
                    ),
                ],
            )
        )
        return await result

    async def _redcap_push(self, _event: Any) -> None:
        if self.redcap_project is None:
            self._set_status("Zuerst mit einem REDCap-Projekt verbinden.", error=True)
            return
        selected = self._selected_versions()
        if not selected:
            self._set_status("Es ist keine Version im Projekt ausgewählt.", error=True)
            return
        family, version, item_ids = selected[0]
        if not version.item_text_included:
            self._set_status(
                "Diese Version enthält keinen Itemtext und kann nicht nach REDCap gepusht werden.",
                error=True,
            )
            return
        try:
            subset = select_questionnaire_items(
                family,
                version.version_id,
                item_ids,
                adaptations=self._adaptations_for_selection(
                    family.instrument_id, version.version_id
                ),
            )
            preview_records = await asyncio.to_thread(
                build_redcap_metadata_records, subset, subset.versions[0]
            )
        except DataExchangeError as error:
            self._set_status(f"Export für REDCap fehlgeschlagen: {error}", error=True)
            return
        form_name = preview_records[0]["form_name"] if preview_records else family.instrument_id
        confirmed, allow_update = await self._confirm_redcap_push(form_name, len(preview_records))
        if not confirmed:
            return
        try:
            push_result = await asyncio.to_thread(
                push_questionnaire_to_project,
                self.redcap_project,
                subset,
                subset.versions[0],
                allow_update=allow_update,
            )
        except RedcapApiError as error:
            self.redcap_status_message = f"Push fehlgeschlagen: {error}"
            self._render()
            return
        updated_note = (
            f", davon {push_result.updated_field_count} aktualisiert"
            if push_result.updated_field_count
            else ""
        )
        self.redcap_status_message = (
            f"Gepusht: {push_result.pushed_field_count} Feld(er) in Formular "
            f"'{push_result.form_name}'{updated_note} "
            f"({push_result.total_field_count} Felder insgesamt im Projekt)."
        )
        self._render()

    async def _redcap_pull(self, _event: Any) -> None:
        if self.redcap_project is None:
            self._set_status("Zuerst mit einem REDCap-Projekt verbinden.", error=True)
            return
        try:
            imported = await asyncio.to_thread(
                pull_questionnaire_from_project,
                self.redcap_project,
                language=self.settings.default_language,
            )
            saved = await asyncio.to_thread(self.catalog_store.import_families, [imported])
        except RedcapApiError as error:
            self.redcap_status_message = f"Import fehlgeschlagen: {error}"
            self._render()
            return
        except CatalogStoreError as error:
            self.redcap_status_message = f"Import fehlgeschlagen: {error}"
            self._render()
            return
        self._reload_catalog(silent=True)
        self.project = self.project.record_step(
            "catalog_import",
            f"REDCap-Import: {imported.instrument_id} ({len(saved)} Datei(en) aktualisiert)",
            imported.instrument_id,
        )
        self.redcap_status_message = (
            f"Aus REDCap importiert: {imported.instrument_id} "
            f"({len(imported.versions[0].items)} Item(s)). Details siehe Instrumentprofil/Notizen."
        )
        self._render()

    def _zotero_config_from_environment(self) -> ZoteroSyncConfig | None:
        library_id = os.environ.get("ZOTERO_LIBRARY_ID") or os.environ.get("ZOTERO_USER_ID")
        api_key = os.environ.get("ZOTERO_API_KEY")
        if not library_id or not api_key:
            return None
        return ZoteroSyncConfig(
            library_id=library_id,
            library_type=os.environ.get("ZOTERO_LIBRARY_TYPE", "user"),
            api_key=api_key,
            collection_key=os.environ.get("ZOTERO_COLLECTION_KEY"),
        )

    async def _push_to_zotero(self, _event: Any) -> None:
        zotero_config = self._zotero_config_from_environment()
        if zotero_config is None:
            self._set_status(
                "ZOTERO_API_KEY und ZOTERO_USER_ID/ZOTERO_LIBRARY_ID müssen in der lokalen "
                ".env gesetzt sein.",
                error=True,
            )
            return
        selected = self._selected_versions()
        if not selected:
            self._set_status("Es ist keine Version im Projekt ausgewählt.", error=True)
            return
        family, version, item_ids = selected[0]
        temporary_path: Path | None = None
        try:
            if version.item_text_included:
                subset = select_questionnaire_items(
                    family,
                    version.version_id,
                    item_ids,
                    adaptations=self._adaptations_for_selection(
                        family.instrument_id, version.version_id
                    ),
                )
                extension, content = export_questionnaire(
                    subset, version.version_id, self.export_format
                )
            else:
                subset = family
                extension, content = (
                    ".json",
                    json.dumps(
                        self._metadata_reference_payload(family, version),
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            with tempfile.NamedTemporaryFile(
                mode="wb" if isinstance(content, bytes) else "w",
                suffix=extension,
                delete=False,
                **({} if isinstance(content, bytes) else {"encoding": "utf-8"}),
            ) as temporary_file:
                temporary_file.write(content)
                temporary_path = Path(temporary_file.name)
            push_result = await asyncio.to_thread(
                push_questionnaire_to_zotero,
                zotero_config,
                questionnaire=subset,
                version=subset.versions[0],
                export_file_path=temporary_path,
            )
        except (DataExchangeError, ZoteroSourceError) as error:
            self._set_status(f"Export nach Zotero fehlgeschlagen: {error}", error=True)
            return
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        attachment_note = (
            f"; Datei {push_result.attached_file} angehängt"
            if push_result.attached_file
            else "; Datei-Anhang fehlgeschlagen (Item wurde trotzdem angelegt)"
        )
        self._set_status(f"Nach Zotero exportiert: Item {push_result.item_key}{attachment_note}.")

    async def _confirm_remote_intake(self) -> bool:
        result: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

        def finish(value: bool) -> None:
            if not result.done():
                result.set_result(value)
            self.page.pop_dialog()

        self._show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("PDF-Text extern verarbeiten?"),
                content=ft.Text(
                    f"Der extrahierte PDF-Text wird an {self.settings.llm_provider} "
                    f"(Modell {self.settings.llm_model}) gesendet. Prüfe vorher die "
                    "Hochschulvorgaben, Anbieterbedingungen und Rechte der Quelle. "
                    "Fortfahren?"
                ),
                actions=[
                    ft.Button(content="Abbrechen", on_click=lambda _event: finish(False)),
                    ft.Button(
                        content="Bestätigen",
                        bgcolor="#9B3E35",
                        color="#FFFFFF",
                        on_click=lambda _event: finish(True),
                    ),
                ],
            )
        )
        return await result


def main(page: ft.Page) -> None:
    """Run the local Flet application."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    LOGGER.info("Flet page connected: platform=%s", getattr(page, "platform", "unknown"))
    PsyMetriQApplication(page)
