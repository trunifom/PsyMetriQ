# ruff: noqa: E402, E501
"""Enrich every catalog version with structured administration metadata.

This step is intentionally separate from the source builders: it can be rerun
against the complete generated catalog and never copies questionnaire wording.
Unknown values remain explicit instead of being guessed.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.questionnaire_schema import QuestionnaireParent, QuestionnaireVersion

LOGGER = logging.getLogger(__name__)
CATALOG_DIRECTORY = PROJECT_ROOT / "data" / "questionnaires" / "json"

PROFILE_FIELDS: dict[str, dict[str, str]] = {
    "phq9": {"administration_time": "ca. 2-5 Minuten", "recall_period": "letzte 2 Wochen", "response_format": "4-stufige Häufigkeitsskala", "scoring_notes": "Itemwerte werden zum PHQ-9-Gesamtscore summiert; offizielle Cutoffs und klinische Abklärung gelten versions- und populationsspezifisch.", "psychometric_summary": "Der PHQ-9 ist umfangreich validiert; konkrete Sensitivität, Spezifität und Cutoffs sind für die jeweilige deutsche Version und Population zu prüfen."},
    "gad7": {"administration_time": "ca. 2-5 Minuten", "recall_period": "letzte 2 Wochen", "response_format": "4-stufige Häufigkeitsskala", "scoring_notes": "Sieben Items werden zum GAD-7-Gesamtscore summiert; Schwellenwerte sind Screeninghilfen und keine Diagnose.", "psychometric_summary": "Der GAD-7 ist für Angstscreening gut untersucht; die Evidenz ist für Sprache, Setting und Population zu prüfen."},
    "dass21": {"administration_time": "ca. 5-10 Minuten", "recall_period": "letzte 7 Tage", "response_format": "4-stufige Häufigkeitsskala", "scoring_notes": "Drei Subskalen mit je sieben Items werden getrennt ausgewertet; DASS-Scores sind dimensional und nicht diagnostisch.", "psychometric_summary": "Die Erwachsenenform ist in vielen Populationen untersucht; deutsche Übersetzung und Normen sind separat zu bewerten."},
    "dass_y": {"administration_time": "ca. 5-10 Minuten", "recall_period": "letzte 7 Tage", "response_format": "4-stufige Häufigkeitsskala", "scoring_notes": "Depressions-, Angst- und Stressdimensionen werden getrennt ausgewertet; keine Übertragung von Erwachsenen-Cutoffs.", "psychometric_summary": "DASS-Y ist eine eigenständige Jugendform; Scores sind nicht direkt mit DASS-21 vergleichbar."},
    "ipaq": {"administration_time": "ca. 5-10 Minuten", "recall_period": "letzte 7 Tage", "response_format": "Tage- und Dauerangaben für körperliche Aktivität", "scoring_notes": "Auswertung folgt der offiziellen IPAQ-Syntax; MET-Werte werden von PsyMetriQ nicht automatisch berechnet.", "psychometric_summary": "Die Standardform verfügt über internationale Reliabilitäts- und Validierungsevidenz; Übersetzungen und IPAQ-E sind getrennt zu prüfen."},
    "rosenberg_self_esteem": {"administration_time": "ca. 3-5 Minuten", "recall_period": "kein einheitlicher Recall-Zeitraum", "response_format": "4-stufige Zustimmungsskala", "scoring_notes": "Reverse-keyed Items müssen vor der Summierung umgepolt werden; die konkrete Auswertung folgt der Quelle.", "psychometric_summary": "Die Skala ist international sehr häufig eingesetzt; Sprach- und populationsspezifische Evidenz bleibt relevant."},
    "who5": {"administration_time": "ca. 1-2 Minuten", "recall_period": "letzte 2 Wochen", "response_format": "6-stufige Häufigkeitsskala", "scoring_notes": "Quelle konsultieren; genaue Transformation und mögliche Schwellenwerte sind editionsspezifisch.", "psychometric_summary": "Der WHO-5 ist breit untersucht, die konkrete Publikation und Übersetzung müssen für die Anwendung geprüft werden."},
    "wemwbs": {"administration_time": "ca. 3-5 Minuten", "recall_period": "letzte 2 Wochen", "response_format": "5-stufige Häufigkeitsskala", "scoring_notes": "WEMWBS und SWEMWBS werden mit ihren jeweiligen offiziellen Scoringregeln ausgewertet.", "psychometric_summary": "WEMWBS verfügt über umfangreiche UK- und internationale Evidenz; Form, Lizenz und Population sind getrennt zu beachten."},
    "general_self_efficacy": {"administration_time": "ca. 3-5 Minuten", "recall_period": "kein einheitlicher Recall-Zeitraum", "response_format": "4-stufige Zustimmungsskala", "scoring_notes": "Die zehn Antwortwerte werden zum Gesamtscore addiert; offizielle Bereichs- und Sprachhinweise gelten.", "psychometric_summary": "Die GSE ist international breit untersucht; deutsche Norm- und Übersetzungsevidenz ist versionsspezifisch."},
    "perceived_stress_scale": {"administration_time": "ca. 5-10 Minuten", "recall_period": "üblicherweise letzter Monat", "response_format": "5-stufige Häufigkeitsskala", "scoring_notes": "Positiv formulierte Items werden gemäß offizieller Syntax umgepolt und anschließend summiert; es gibt keine diagnostischen Cutoffs.", "psychometric_summary": "PSS ist häufig eingesetzt, aber Normen und Validität hängen von Form, Recall-Zeitraum und Population ab."},
    "kidscreen": {"administration_time": "ca. 5-20 Minuten je nach Form", "recall_period": "üblicherweise letzte Woche", "response_format": "5-stufige Häufigkeits- oder Intensitätsskala", "scoring_notes": "Die KIDSCREEN-Formen werden dimensionsbezogen nach offizieller Syntax ausgewertet; Normwerte sind landes- und altersbezogen.", "psychometric_summary": "Offizielle KIDSCREEN-Informationen berichten versionsabhängige interne Konsistenzen und Normen."},
    "mspss": {"administration_time": "ca. 3-5 Minuten", "recall_period": "kein einheitlicher Recall-Zeitraum", "response_format": "7-stufige Zustimmungsskala", "scoring_notes": "Familien-, Freunde- und wichtige-Bezugspersonen-Subskalen sowie ein Gesamtscore werden gemäß Form ausgewertet.", "psychometric_summary": "Die MSPSS ist international gut untersucht; deutsche Evidenz muss nach Zielgruppe und Form geprüft werden."},
    "cius": {"administration_time": "ca. 5 Minuten", "recall_period": "kein einheitlicher Recall-Zeitraum", "response_format": "5-stufige Häufigkeitsskala", "scoring_notes": "Itemwerte werden gemäß offizieller Form zum CIUS-Score zusammengeführt; Screening ist keine Diagnose.", "psychometric_summary": "Deutsche Jugend- und erwachsene Sprachinvarianzstudien sind vorhanden, aber nicht automatisch auf jede Population übertragbar."},
    "gadis_a": {"administration_time": "ca. 5 Minuten", "recall_period": "kein einheitlicher Recall-Zeitraum", "response_format": "ordinales Selbstberichtformat", "scoring_notes": "Auswertung und Schwellenwerte folgen der ICD-11-orientierten Originalstudie; keine Übertragung auf DSM-5-Kriterien.", "psychometric_summary": "Die deutsche Validierung bezieht sich auf häufig spielende Jugendliche und ist populationsspezifisch."},
    "isap": {"administration_time": "formabhängig; Quelle konsultieren", "recall_period": "schulbezogener aktueller Zeitraum", "response_format": "formabhängige Rating-Skala", "scoring_notes": "Subskalen und Auswertung müssen aus der jeweiligen ISAP-/ISAP-P-Version übernommen werden; Anwesenheitsdaten ergänzen.", "psychometric_summary": "Deutsche klinische Jugendstichproben liegen vor; Elternform und Selbst-/Fremdbericht sind nicht austauschbar."},
    "psq": {"administration_time": "ca. 5-10 Minuten", "recall_period": "aktuelles subjektives Belastungserleben", "response_format": "4-stufige Zustimmungsskala", "scoring_notes": "Worries, Tension, Demands und Joy werden nach der offiziellen PSQ-Syntax ausgewertet.", "psychometric_summary": "Deutsche Referenzwerte und psychometrische Untersuchungen liegen für verschiedene klinische und gesunde Populationen vor."},
    "f_sozu": {"administration_time": "ca. 5 Minuten", "recall_period": "kein einheitlicher Recall-Zeitraum", "response_format": "mehrstufige Zustimmungsskala", "scoring_notes": "Subskalen und Gesamtscore richten sich nach der konkreten F-SozU-Kurzform und dem Manual.", "psychometric_summary": "Deutschsprachige psychometrische Evidenz ist vorhanden; Form und Zielgruppe müssen vor Vergleich ausgewiesen werden."},
    "ucla_loneliness": {"administration_time": "unter 2 Minuten", "recall_period": "kein einheitlicher Recall-Zeitraum", "response_format": "kurze ordinale Häufigkeitsskala", "scoring_notes": "Die Kurzform wird nach der Originalsyntax summiert; es gibt keinen universellen diagnostischen Cutoff.", "psychometric_summary": "Die Drei-Item-Form ist für große Surveys entwickelt; deutsche Übersetzungsevidenz ist separat zu prüfen."},
    "sdq": {"administration_time": "ca. 5-10 Minuten", "recall_period": "üblicherweise letzte 6 Monate", "response_format": "3-stufige Rating-Skala", "scoring_notes": "Fünf Subskalen und gegebenenfalls Impact-Supplement werden getrennt ausgewertet; Informanten nicht unmarkiert zusammenlegen.", "psychometric_summary": "Der SDQ verfügt über umfangreiche internationale und deutschsprachige Evidenz; Alter und Informant bestimmen die Interpretation."},
    "whoqol_bref": {"administration_time": "ca. 5-10 Minuten", "recall_period": "üblicherweise letzte 2 Wochen", "response_format": "5-stufige Intensitäts- oder Häufigkeitsskala", "scoring_notes": "Vier Domänen und zwei globale Items werden nach WHO-Syntax ausgewertet; Domänenwerte sind nicht automatisch EQ-5D-Werte.", "psychometric_summary": "WHOQOL-BREF ist international breit validiert; Übersetzungen wurden laut WHO nicht zwingend von WHO erstellt."},
    "eq5d5l": {"administration_time": "ca. 3-5 Minuten", "recall_period": "aktueller Gesundheitszustand", "response_format": "5 Dimensionen mit je 5 Stufen plus EQ-VAS", "scoring_notes": "Deskriptives Profil, VAS und präferenzbasierter Index sind getrennte Auswertungselemente; deutscher Value Set erforderlich.", "psychometric_summary": "EuroQol stellt versions-, sprach- und Value-Set-spezifische Evidenz und Nutzungsbedingungen bereit."},
    "hads": {"administration_time": "ca. 2-5 Minuten", "recall_period": "aktuelle letzte Woche", "response_format": "4-stufige Antwortskala", "scoring_notes": "Je sieben Items werden zu Angst- und Depressivitätssubskalen summiert; Schwellenwerte sind Screeninginstrumente.", "psychometric_summary": "HADS ist für medizinische und psychosomatische Settings breit untersucht; somatische Erkrankung und Setting beeinflussen die Interpretation."},
    "audit": {"administration_time": "ca. 2-5 Minuten", "recall_period": "üblicherweise letzter Jahreszeitraum", "response_format": "mehrstufige Häufigkeits- und Mengenangaben", "scoring_notes": "Konsum-, Abhängigkeits- und Schadensbereiche werden zum AUDIT-Score zusammengeführt; Cutoffs folgen WHO- und Kontextleitlinien.", "psychometric_summary": "AUDIT ist international und in der Primärversorgung umfangreich validiert; deutsche Version und Setting bleiben maßgeblich."},
    "tics": {"administration_time": "ca. 10-15 Minuten", "recall_period": "chronisches aktuelles Belastungserleben", "response_format": "mehrstufige Zustimmungsskala", "scoring_notes": "TICS-Subskalen werden getrennt ausgewertet; Form, Normen und Kurzformen müssen angegeben werden.", "psychometric_summary": "TICS ist ein deutschsprachiges, multidimensionales Verfahren mit Skalen zu chronischem Stress und Arbeitsbelastung."},
    "k6_k10": {"administration_time": "ca. 2-5 Minuten", "recall_period": "letzte 30 Tage", "response_format": "5-stufige Häufigkeitsskala", "scoring_notes": "Antwortwerte werden zum K6- bzw. K10-Distressscore summiert; Schwellenwerte sind populations- und kontextabhängig.", "psychometric_summary": "K6/K10 wurden zur Bevölkerungsüberwachung psychischer Belastung entwickelt und sind keine störungsspezifische Diagnostik."},
    "swls": {"administration_time": "ca. 2 Minuten", "recall_period": "globales aktuelles Urteil", "response_format": "7-stufige Zustimmungsskala", "scoring_notes": "Fünf Items werden zum globalen Lebenszufriedenheitsscore summiert; keine klinische Diagnose.", "psychometric_summary": "SWLS ist international sehr häufig eingesetzt; deutsche Norm- und Übersetzungsevidenz ist versionsabhängig."},
    "phq15": {"administration_time": "ca. 3-5 Minuten", "recall_period": "letzte 4 Wochen", "response_format": "3-stufige Belastungsskala", "scoring_notes": "Somatische Symptome werden gemäß PHQ-15-Syntax summiert; medizinische Abklärung bleibt erforderlich.", "psychometric_summary": "PHQ-15 ist für somatische Symptomlast gut untersucht, aber nicht als Erklärung ungeklärter Symptome allein ausreichend."},
    "feess": {"administration_time": "formabhängig; ca. 10-20 Minuten", "recall_period": "aktuelle Schulerfahrung", "response_format": "mehrstufige Schüler-Zustimmungsskala", "scoring_notes": "Subskalen zu Schulerfahrung und Klassenklima werden mit der jeweiligen FEESS-Version ausgewertet.", "psychometric_summary": "Deutschsprachige schulbezogene Norm- und Validierungsevidenz ist versions- und Klassenstufenabhängig."},
    "sessko": {"administration_time": "ca. 5-10 Minuten", "recall_period": "aktuelles schulisches Selbstbild", "response_format": "mehrstufige Schüler-Zustimmungsskala", "scoring_notes": "Dimensionen des schulischen Selbstkonzepts werden getrennt nach SESSKO-Form ausgewertet.", "psychometric_summary": "SESSKO ist für deutsche Schulstufen entwickelt; Normen und Bezugsgruppen sind für die Interpretation wesentlich."},
    "fas3": {"administration_time": "ca. 3 Minuten", "recall_period": "aktuelle materielle Lebensbedingungen", "response_format": "konkrete Haushalts- und Besitzangaben", "scoring_notes": "Antworten werden zum FAS-Score zusammengeführt; der Score ist kein vollständiger SES-Index.", "psychometric_summary": "FAS III ist für internationale Schulgesundheitsstudien entwickelt; Länder- und Zeitvergleiche erfordern Vorsicht."},
    "asrs": {"administration_time": "ca. 3-5 Minuten", "recall_period": "letzte 6 Monate", "response_format": "5-stufige Häufigkeitsskala", "scoring_notes": "Kurz- oder Vollform werden nach offizieller ASRS-Syntax ausgewertet; positives Screening verlangt Diagnostik.", "psychometric_summary": "ASRS ist international als Erwachsenenscreening gut untersucht; es ersetzt keine Entwicklungs- und Funktionsanamnese."},
    "disyps_fbb_adhs": {"administration_time": "formabhängig; ca. 10-20 Minuten", "recall_period": "aktuelles und typisches Verhalten", "response_format": "mehrstufige Fremdbeurteilungsskala", "scoring_notes": "FBB-ADHS-Subskalen werden nach DISYPS-III-Normen und Informantenform ausgewertet.", "psychometric_summary": "DISYPS-III bietet deutschsprachige entwicklungs- und störungsspezifische Normierung; Edition und Informant sind entscheidend."},
    "conners3": {"administration_time": "formabhängig; ca. 10-20 Minuten", "recall_period": "aktuelles und typisches Verhalten", "response_format": "mehrstufige Rating-Skala", "scoring_notes": "Conners-Subskalen und Indexwerte werden mit den kommerziellen Normen der jeweiligen Form ausgewertet.", "psychometric_summary": "Multi-Informanten-Evidenz ist ein Kern der Conners-Familie; kommerzielle deutsche Normen und Versionen gelten."},
    "aq": {"administration_time": "ca. 5-10 Minuten", "recall_period": "typisches aktuelles Verhalten", "response_format": "4-stufige Zustimmungsskala", "scoring_notes": "Domänen- und Gesamtscore folgen der AQ-Syntax; Cutoffs sind Screeninghilfen und nicht diagnostisch.", "psychometric_summary": "AQ ist ein verbreitetes Trait-Screening; Sensitivität und Spezifität variieren nach Population und klinischem Kontext."},
    "srs2": {"administration_time": "ca. 15-20 Minuten", "recall_period": "typisches aktuelles Verhalten", "response_format": "4-stufige Rating-Skala", "scoring_notes": "SRS-2-Subskalen und Gesamtwert werden anhand der informanten- und altersbezogenen Normen ausgewertet.", "psychometric_summary": "SRS-2 ist multi-informant und dimensional, aber nicht spezifisch für ASS; ADHS, Angst und Sprache können Scores beeinflussen."},
    "mchat_rf": {"administration_time": "ca. 5 Minuten plus Follow-up", "recall_period": "typisches Verhalten des Kindes", "response_format": "Ja/Nein-Elternbericht mit strukturiertem Follow-up", "scoring_notes": "Risikobereiche werden mit dem offiziellen Follow-up abgeklärt; ein positives Ergebnis ist keine ASS-Diagnose.", "psychometric_summary": "M-CHAT-R/F ist für frühes Kleinkind-Screening validiert; Alter, Follow-up und Entwicklungsabklärung sind wesentlich."},
    "copsoq": {"administration_time": "formabhängig; ca. 10-20 Minuten", "recall_period": "aktuelle Arbeitsbedingungen", "response_format": "mehrstufige Arbeits- und Zustimmungsskalen", "scoring_notes": "Skalenwerte werden dimensionsweise berichtet und mit geeigneten Referenzwerten verglichen.", "psychometric_summary": "COPSOQ ist ein etabliertes multidimensionales Instrument für psychosoziale Arbeitsbedingungen; Version und Benchmark sind auszuweisen."},
    "eri": {"administration_time": "ca. 5-10 Minuten", "recall_period": "aktuelle Arbeitssituation", "response_format": "mehrstufige Zustimmungsskala", "scoring_notes": "Effort-Reward-Ratio und Overcommitment werden nach der offiziellen ERI-Syntax berechnet.", "psychometric_summary": "Das ERI-Modell ist in der Arbeitsstressforschung umfangreich untersucht; deutsche Form und Ratio-Variante müssen dokumentiert werden."},
    "olbi": {"administration_time": "ca. 5 Minuten", "recall_period": "aktuelle Arbeitssituation", "response_format": "4-stufige Zustimmungsskala", "scoring_notes": "Exhaustion und Disengagement werden getrennt ausgewertet; positiv formulierte Items werden entsprechend umgepolt.", "psychometric_summary": "OLBI ist eine etablierte Burnout-Referenz mit zwei Dimensionen; Kontext und deutsche Validierung sind zu berücksichtigen."},
    "bdi_ii": {"administration_time": "ca. 5-10 Minuten", "recall_period": "letzte 2 Wochen", "response_format": "4-stufige Schweregradskala", "scoring_notes": "21 Items werden zum Gesamtscore summiert; Auswertung und Cutoffs folgen der lizenzierten deutschen Anleitung.", "psychometric_summary": "BDI-II ist international umfangreich validiert; deutsche Normen und klinische Anwendung sind versionsabhängig."},
    "scl90r": {"administration_time": "ca. 15-20 Minuten", "recall_period": "letzte 7 Tage", "response_format": "5-stufige Belastungsskala", "scoring_notes": "Neun Symptomdimensionen und globale Kennwerte werden gemäß deutscher Normierung ausgewertet.", "psychometric_summary": "SCL-90-R ist breit eingesetzt, aber Profilwerte sind kontext- und response-stilabhängig; keine eigenständige Diagnose."},
    "sswq": {"administration_time": "ca. 5-10 Minuten", "recall_period": "aktuelle Schulerfahrung", "response_format": "mehrstufige Schüler-Zustimmungsskala", "scoring_notes": "SSWQ-Dimensionen werden nach der Original- und versionsspezifischen Syntax ausgewertet.", "psychometric_summary": "Die publizierte Evidenz stammt zunächst aus Schulstufen 6-8; deutsche Übertragung und Normen sind separat zu prüfen."},
    "adhd_rs_iv": {"administration_time": "ca. 5 Minuten", "recall_period": "aktuelles und typisches Verhalten", "response_format": "4-stufige Eltern-/Lehrkraft-Rating-Skala", "scoring_notes": "Inattention und Hyperaktivität/Impulsivität werden getrennt und als Gesamtwert nach Normen ausgewertet.", "psychometric_summary": "ADHD-RS-IV ist ein etabliertes Fremdbeurteilungsinstrument; es ersetzt keine umfassende ADHS-Diagnostik."},
    "snap_iv": {"administration_time": "ca. 5-10 Minuten", "recall_period": "aktuelles und typisches Verhalten", "response_format": "4-stufige Eltern-/Lehrkraft-Rating-Skala", "scoring_notes": "ADHS- und oppositionelle Symptomcluster werden nach der gewählten SNAP-IV-Syntax ausgewertet.", "psychometric_summary": "SNAP-IV ist häufig in Forschung und Screening eingesetzt; deutsche Form, Normen und Cutoffs müssen belegt werden."},
    "scq": {"administration_time": "ca. 10 Minuten", "recall_period": "Entwicklungsgeschichte und aktuelles Verhalten", "response_format": "Ja/Nein-Elternbericht", "scoring_notes": "Social-Communication- und Restricted-Behavior-Bereiche werden zum Screeningscore zusammengeführt.", "psychometric_summary": "SCQ ist ein verbreitetes Elternscreening, dessen Genauigkeit von Alter, Entwicklung und klinischer Vergleichsgruppe abhängt."},
    "assq": {"administration_time": "ca. 10 Minuten", "recall_period": "typisches Verhalten im Schulalter", "response_format": "3-stufige Eltern-/Lehrkraft-Rating-Skala", "scoring_notes": "Items werden zum ASSQ-Screeningscore summiert; Schwellenwerte sind populationsspezifisch.", "psychometric_summary": "ASSQ wurde für schulaltrige Autismusmerkmale entwickelt; deutsche Evidenz und Informantenversion sind zu beachten."},
    "mbi": {"administration_time": "ca. 10 Minuten", "recall_period": "aktuelle Arbeitserfahrung", "response_format": "mehrstufige Häufigkeits- oder Intensitätsskala", "scoring_notes": "Exhaustion, Depersonalisation/Cynicism und Professional Efficacy werden getrennt nach MBI-Form ausgewertet.", "psychometric_summary": "MBI ist die am häufigsten zitierte Burnout-Instrumentfamilie, aber kommerzielle Form und Subskalen müssen exakt angegeben werden."},
    "jcq": {"administration_time": "ca. 10-15 Minuten", "recall_period": "aktuelle Arbeitsbedingungen", "response_format": "mehrstufige Arbeits- und Zustimmungsskalen", "scoring_notes": "Demand-, Control- und Support-Skalen werden getrennt nach JCQ-Syntax ausgewertet.", "psychometric_summary": "JCQ ist international etabliert; deutsche Übersetzung, Kurzform und Benchmark müssen dokumentiert werden."},
    "eortc_qlq_c30": {"administration_time": "ca. 10 Minuten", "recall_period": "letzte Woche bzw. aktueller Gesundheitszustand je Item", "response_format": "4-stufige Antwortskalen plus globale 7-stufige Gesundheits-/Lebensqualitätsskala", "scoring_notes": "Funktions- und Symptomskalen werden nach EORTC-Scoring Manual linear transformiert; höhere Werte haben je Skala unterschiedliche Bedeutung.", "psychometric_summary": "QLQ-C30 ist international in Onkologie und klinischen Studien umfangreich validiert; Sprachversion und Module sind getrennt zu prüfen."},
}


def _default_fields(version: QuestionnaireVersion) -> dict[str, str]:
    count = len(version.items) if version.item_text_included else version.source_reported_item_count
    dimensions = ", ".join(version.source_reported_dimensions) or "keine Dimensionen im Katalog dokumentiert"
    if count is None:
        structure = f"Itemanzahl nicht dokumentiert; Dimensionen: {dimensions}."
    else:
        structure = f"{count} Items; Dimensionen: {dimensions}."
    if version.response_sets:
        response = "Kategoriale Antwortsets: " + ", ".join(version.response_sets)
    elif version.items:
        response_modes = sorted({item.response_mode for item in version.items})
        response = "Antwortmodi: " + ", ".join(response_modes)
    else:
        response = "Antwortformat der Originalquelle prüfen; Itemtexte sind in diesem Referenzrecord nicht enthalten."
    if version.scoring_algorithms:
        scoring = "; ".join(
            f"{algorithm.output_variable}: {algorithm.method} über {len(algorithm.target_items)} Items"
            for algorithm in version.scoring_algorithms
        )
    else:
        scoring = "Auswertungsdetails sind in diesem Katalogrecord nicht vollständig strukturiert; offizielle Anleitung konsultieren."
    return {
        "item_structure": structure,
        "response_format": response,
        "scoring_notes": scoring,
        "psychometric_summary": "Keine strukturierten psychometrischen Kennwerte in diesem Katalogrecord; zitierte Originalquelle prüfen.",
        "administration_time": "Nicht dokumentiert; Originalquelle konsultieren.",
        "recall_period": "Nicht dokumentiert; Originalquelle konsultieren.",
    }


def enrich_catalog(catalog_directory: Path = CATALOG_DIRECTORY) -> int:
    updated = 0
    for path in sorted(catalog_directory.glob("*.json")):
        family = QuestionnaireParent.model_validate_json(path.read_text(encoding="utf-8"))
        profile = PROFILE_FIELDS.get(family.instrument_id, {})
        versions: list[QuestionnaireVersion] = []
        for version in family.versions:
            fields = _default_fields(version)
            fields.update(profile)
            fields["item_structure"] = fields.get("item_structure") or _default_fields(version)["item_structure"]
            versions.append(version.model_copy(update=fields))
        enriched = family.model_copy(update={"versions": versions})
        path.write_text(enriched.model_dump_json(indent=2), encoding="utf-8")
        updated += 1
    LOGGER.info("Enriched %d questionnaire families", updated)
    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    enrich_catalog()
