# ruff: noqa: E501
"""Enrich catalog versions with COSMIN-style psychometric metrics and provenance.

Companion to enrich_catalog_metadata.py: this step never adds or changes
item wording. It only adds:

1. ``cosmin_metrics`` (currently empty for every catalog entry): a small,
   deliberately hedged summary of the internal-consistency/reliability
   evidence reported in each instrument's original or a well-established
   validation publication, always phrased as "ca." and "may vary by
   sample/translation" -- consistent with how every other enrichment
   field in this catalog is written -- and always naming the source study
   so a user can verify it rather than trust a number in isolation.
2. ``publication_year``/``source_citation``/``source_doi`` where a version
   is currently missing them but is the same underlying instrument as
   another version that already documents them (e.g. a regional/language
   edition of the same scale) -- it never overwrites a value already
   present, and never invents a translation-specific citation/DOI that
   is not confidently known.

Only a curated, high-confidence subset of the catalog is covered here
(well-known instruments with widely cited, stable psychometric figures).
Every other instrument is left untouched rather than guessed at -- exactly
the same "explicit gap over invented precision" rule enrich_catalog_metadata.py
already follows.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import QuestionnaireParent  # noqa: E402

LOGGER = logging.getLogger(__name__)
CATALOG_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "json"

# instrument_id -> cosmin_metrics dict applied to every version of that family.
COSMIN_METRICS: dict[str, dict[str, str]] = {
    "phq9": {
        "internal_consistency": "Cronbach's alpha ca. .86-.89 in der US-Primärversorgungs-Originalstudie; Werte variieren je nach Population, Sprache und Setting.",
        "source": "Kroenke K, Spitzer RL, Williams JBW (2001). The PHQ-9: validity of a brief depression severity measure. J Gen Intern Med, 16(9), 606-613.",
    },
    "gad7": {
        "internal_consistency": "Cronbach's alpha ca. .92 in der Originalstudie an Primärversorgungspatient*innen; internationale Replikationen berichten meist Werte über .80.",
        "source": "Spitzer RL, Kroenke K, Williams JBW, Löwe B (2006). A brief measure for assessing generalized anxiety disorder: the GAD-7. Arch Intern Med, 166(10), 1092-1097.",
    },
    "dass21": {
        "internal_consistency": "Cronbach's alpha ca. .88 (Depression), .82 (Angst), .90 (Stress) in Normstichproben; deutsche und klinische Stichproben können abweichen.",
        "source": "Lovibond SH, Lovibond PF (1995). Manual for the Depression Anxiety Stress Scales (2nd ed.). Psychology Foundation of Australia; Henry JD, Crawford JR (2005). Br J Clin Psychol, 44(2), 227-239.",
    },
    "rosenberg_self_esteem": {
        "internal_consistency": "Cronbach's alpha meist ca. .77-.88 über zahlreiche Studien und Sprachen; Test-Retest-Reliabilität in Originalstudien ca. .82-.85.",
        "source": "Rosenberg M (1965). Society and the Adolescent Self-Image. Princeton University Press.",
    },
    "ipaq": {
        "internal_consistency": "Test-Retest-Reliabilität (Spearman) meist ca. .8 über 12 Länder; Kriteriumsvalidität gegen Akzelerometer moderat (ca. .30).",
        "source": "Craig CL, Marshall AL, Sjöström M, et al. (2003). International physical activity questionnaire: 12-country reliability and validity. Med Sci Sports Exerc, 35(8), 1381-1395.",
    },
    "who5": {
        "internal_consistency": "Cronbach's alpha ca. .82-.95 über eine systematische Übersichtsarbeit von >200 Studien; Werte variieren stark nach Population und Sprache.",
        "source": "Topp CW, Østergaard SD, Søndergaard S, Bech P (2015). The WHO-5 Well-Being Index: a systematic review of the literature. Psychother Psychosom, 84(3), 167-176.",
    },
    "perceived_stress_scale": {
        "internal_consistency": "Cronbach's alpha ca. .78 (14-Item-Originalform) bzw. ca. .89 (PSS-10) in Normstichproben.",
        "source": "Cohen S, Kamarck T, Mermelstein R (1983). A global measure of perceived stress. J Health Soc Behav, 24(4), 385-396.",
    },
    "audit": {
        "internal_consistency": "Cronbach's alpha ca. .80-.94 über die internationale WHO-Validierungsstudie an sechs Ländern; Sensitivität/Spezifität sind settingabhängig.",
        "source": "Saunders JB, Aasland OG, Babor TF, de la Fuente JR, Grant M (1993). Development of the AUDIT. Addiction, 88(6), 791-804.",
    },
    "swls": {
        "internal_consistency": "Cronbach's alpha ca. .87, Test-Retest-Reliabilität (2 Monate) ca. .82 in der Originalstudie.",
        "source": "Diener E, Emmons RA, Larsen RJ, Griffin S (1985). The Satisfaction with Life Scale. J Pers Assess, 49(1), 71-75.",
    },
    "hads": {
        "internal_consistency": "Cronbach's alpha meist ca. .80-.93 (Angst-Subskala) bzw. .81-.90 (Depressions-Subskala) über eine Übersichtsarbeit von >70 Studien.",
        "source": "Zigmond AS, Snaith RP (1983). The Hospital Anxiety and Depression Scale. Acta Psychiatr Scand, 67(6), 361-370; Bjelland I et al. (2002). J Psychosom Res, 52(2), 69-77.",
    },
    "bdi_ii": {
        "internal_consistency": "Cronbach's alpha ca. .92 in nichtklinischen und ca. .92-.93 in klinischen Stichproben der Originalvalidierung.",
        "source": "Beck AT, Steer RA, Brown GK (1996). Manual for the Beck Depression Inventory-II. Psychological Corporation.",
    },
    "scl90r": {
        "internal_consistency": "Cronbach's alpha je Symptomdimension meist ca. .77-.90 über verschiedene Normierungsstudien.",
        "source": "Derogatis LR (1994). SCL-90-R: Administration, Scoring, and Procedures Manual (3rd ed.). National Computer Systems.",
    },
    "mbi": {
        "internal_consistency": "Cronbach's alpha ca. .90 (Emotional Exhaustion), .79 (Depersonalization/Cynicism), .71 (Personal/Professional Accomplishment) in der Originalnormierung.",
        "source": "Maslach C, Jackson SE (1981). The measurement of experienced burnout. J Organ Behav, 2(2), 99-113.",
    },
    "ucla_loneliness": {
        "internal_consistency": "Cronbach's alpha ca. .72-.82 für die 3-Item-Kurzform über mehrere bevölkerungsbasierte Surveys (u.a. Health and Retirement Study).",
        "source": "Hughes ME, Waite LJ, Hawkley LC, Cacioppo JT (2004). A short scale for measuring loneliness. Res Aging, 26(6), 655-672.",
    },
    "k6_k10": {
        "internal_consistency": "Cronbach's alpha ca. .89 (K6) in der US-Normierungsstichprobe (National Health Interview Survey); K10-Werte liegen meist ähnlich hoch.",
        "source": "Kessler RC, Andrews G, Colpe LJ, et al. (2002). Short screening scales to monitor population prevalences and trends in non-specific psychological distress. Psychol Med, 32(6), 959-976.",
    },
    "whoqol_bref": {
        "internal_consistency": "Cronbach's alpha je Domäne meist ca. .66-.84 in der internationalen Feldstudie; Werte variieren nach Domäne, Sprache und Population.",
        "source": "WHOQOL Group (1998). Development of the World Health Organization WHOQOL-BREF quality of life assessment. Psychol Med, 28(3), 551-558.",
    },
    "olbi": {
        "internal_consistency": "Cronbach's alpha ca. .74-.85 (Exhaustion) und ca. .75-.84 (Disengagement) über mehrere Stichproben und Sprachversionen.",
        "source": "Demerouti E, Bakker AB, Vardakou I, Kantas A (2003). The convergent validity of two burnout instruments. Eur J Psychol Assess, 19(1), 12-23.",
    },
    "eortc_qlq_c30": {
        "internal_consistency": "Cronbach's alpha für die meisten Funktions-/Symptomskalen ca. >.70 in der internationalen Validierungsstudie; einzelne Skalen (z.B. Kognition) liegen teils niedriger.",
        "source": "Aaronson NK, Ahmedzai S, Bergman B, et al. (1993). The European Organization for Research and Treatment of Cancer QLQ-C30. J Natl Cancer Inst, 85(5), 365-376.",
    },
}


def _needs_provenance(field_values: dict[str, object]) -> bool:
    return not (field_values.get("publication_year") and field_values.get("source_citation"))


def enrich() -> list[str]:
    """Apply cosmin_metrics and fill blank provenance fields; return changed instrument ids."""
    changed: list[str] = []
    for instrument_id, metrics in COSMIN_METRICS.items():
        path = CATALOG_DIRECTORY / f"{instrument_id}.json"
        if not path.is_file():
            LOGGER.warning("Skipping %s: catalog file not found", instrument_id)
            continue
        family = QuestionnaireParent.model_validate_json(path.read_text(encoding="utf-8"))

        # Find a sibling version that already documents provenance, to fill blanks elsewhere.
        reference_year = next((v.publication_year for v in family.versions if v.publication_year), None)
        reference_citation = next((v.source_citation for v in family.versions if v.source_citation), None)
        reference_doi = next((v.source_doi for v in family.versions if v.source_doi), None)

        updated_versions = []
        any_change = False
        for version in family.versions:
            updates: dict[str, object] = {"cosmin_metrics": dict(metrics)}
            if version.publication_year is None and reference_year:
                updates["publication_year"] = reference_year
            if not version.source_citation and reference_citation:
                updates["source_citation"] = reference_citation
            if not version.source_doi and reference_doi:
                updates["source_doi"] = reference_doi
            if version.cosmin_metrics != metrics or any(
                key != "cosmin_metrics" for key in updates
            ):
                any_change = True
            updated_versions.append(version.model_copy(update=updates))

        if not any_change:
            continue
        updated_family = family.model_copy(update={"versions": updated_versions})
        # Round-trip through validation to catch any inconsistency before writing.
        updated_family = QuestionnaireParent.model_validate(updated_family.model_dump(mode="json"))
        path.write_text(
            updated_family.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        changed.append(instrument_id)
        LOGGER.info("Enriched %s with cosmin_metrics/provenance", instrument_id)
    return changed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    changed = enrich()
    LOGGER.info("Done. %d instrument(s) updated: %s", len(changed), ", ".join(changed))


if __name__ == "__main__":
    main()
