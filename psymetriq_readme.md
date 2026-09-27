# 🧠 PsyMetriQ - Master Architecture Document

> **An interdisciplinary, AI-driven toolkit for Data Science, Psychology, and Health Sciences to automatically extract, manage, and assemble psychometric questionnaires.**

**GitHub About Description:** AI-powered psychometric assembler. Extract questionnaires from PDFs via LLMs, prevent item redundancy using NLP, and export seamlessly to REDCap.

---

## 📖 1. Projektvision & Domänen-Kontext
Die Entwicklung psychometrischer Fragebögen und deren Überführung in EDC-Systeme (Electronic Data Capture wie REDCap) ist in der Praxis fehleranfällig und repetitiv. 
**PsyMetriQ** löst dieses Problem durch:
1. **Automatisierte PDF-Extraktion:** Überführt unstrukturierte Validierungsstudien via LLM in strikt validierte Pydantic-JSON-Objekte.
2. **Semantische Deduplizierung:** Verhindert durch lokale SentenceTransformers-Modelle, dass Forschende methodisch überlappende Items aus verschiedenen Skalen kombinieren.
3. **API-first Export:** Mappt das hierarchische JSON-Modell flach auf REDCap Data Dictionaries oder generiert direkt syntax-fertige R-Skripte.

---

## 🛠 2. Tech-Stack (Versionierung & Bibliotheken)
- **Core:** Python 3.11+
- **GUI:** `flet` (v0.22+ - asynchrones UI-Framework basierend auf Flutter)
- **Data Validation:** `pydantic` (v2.0+ - Source of Truth für alle Datenstrukturen)
- **Search storage:** Portable questionnaire JSON files; the application validates and searches them in memory without requiring a database.
- **NLP / ML:** `sentence-transformers` (lokal via ONNX oder PyTorch)
- **LLM Integration:** `openai` (GPT-4o via *Structured Outputs* API)
- **PDF-Parsing:** `pymupdf` (fitz)
- **APIs:** `pyzotero` (Ingestion), `PyCap` (REDCap Export)

---

## 💾 3. Core Data Model (Die Pydantic Source of Truth)

*KI-Agent Instruktion: Dieses Pydantic-Modell ist das Herzstück. Alle Module (file-backed search, Flet, REDCap) müssen gegen dieses Modell operieren.*

```python
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Optional, Literal

class ResponseOption(BaseModel):
    code: str | int = Field(..., description="Numerischer Wert (z.B. 0, 1, 2)")
    label: str = Field(..., description="Text der Antwort (z.B. 'Trifft völlig zu')")
    score: float = Field(..., description="Tatsächlicher Berechnungswert (oft gleich dem Code)")

class ItemSchema(BaseModel):
    item_id: str = Field(..., description="Eindeutige ID (z.B. bdi2_de_01)")
    variable_name: str = Field(..., description="Maschinenlesbarer Name für REDCap (max 26 Zeichen, keine Sonderzeichen)")
    dimension: str = Field(..., description="Subskala (z.B. 'affektiv', 'kognitiv')")
    prompt_text: str = Field(..., description="Die eigentliche Frage/Aussage")
    response_set_ref: str = Field(..., description="Referenz-ID auf das genutzte ResponseSet")
    is_reverse_scored: bool = Field(default=False)
    redcap_field_type: Literal['radio', 'checkbox', 'slider', 'text'] = Field(default='radio')

class ScoringAlgorithm(BaseModel):
    output_variable: str = Field(..., description="Name des finalen Scores (z.B. bdi_total)")
    method: Literal['sum', 'mean', 'weighted']
    target_items: List[str] = Field(..., description="Liste der item_ids")
    missing_data_rules: Optional[str] = Field(None, description="Regel, falls Items fehlen")

class QuestionnaireVersion(BaseModel):
    version_id: str
    language: str = Field(..., min_length=2, max_length=5) # e.g., 'de', 'en-US'
    cosmin_metrics: Dict[str, any] = Field(default_factory=dict, description="Cronbachs Alpha, etc.")
    response_sets: Dict[str, List[ResponseOption]] = Field(..., description="Dictionary der Antwortskalen")
    items: List[ItemSchema]
    scoring_algorithms: List[ScoringAlgorithm]

class QuestionnaireParent(BaseModel):
    instrument_id: str = Field(..., description="Parent ID (z.B. bdi_2)")
    name_full: str
    construct_ontology: List[str] = Field(default_factory=list, description="ICD-11 / SNOMED CT Codes")
    is_commercial: bool
    versions: List[QuestionnaireVersion]
```

---

## ⚙️ 4. Modul-Spezifikationen & Architektur-Details

### Modul 1: Ingestion Engine (`/src/ingestion/`)
**Aufgabe:** Verbindet Zotero, PyMuPDF und das LLM zu einer automatisierten Pipeline.
*   **Trigger:** Ein Skript pullt alle 5 Minuten via `pyzotero` Einträge mit dem Tag `extract_questionnaire`.
*   **PDF Extraction:** `PyMuPDF` liest den Text. WICHTIG: Tabellen im PDF (wo Fragebögen oft stehen) müssen als Text-Grids geparst werden, da sonst Zuordnungen von Item zu Antwortskala verloren gehen.
*   **LLM API Call:** Nutzung des `client.beta.chat.completions.parse` Endpoints (OpenAI API ab v1.40). 
    *   Übergabe der Pydantic-Klasse `QuestionnaireParent` an den Parameter `response_format`. Das zwingt das LLM deterministisch, exakt das obige Schema zu befüllen.
*   **Post-Processing:** Das Skript ändert den Zotero-Tag auf `questionnaire_extracted` und speichert die JSON-Datei in `/data/02_extracted_jsons/`.

### Modul 2: File-backed Search Engine (`/src/core/search_engine.py`)
**Aufgabe:** Fragebogen-JSON-Dateien ohne Datenbank lokal oder aus einem synchronisierten Teamordner durchsuchen.
*   **Quelle:** Pydantic-validierte JSON-Dateien unter `/data/02_extracted_jsons/`. Die Quelldateien bleiben portable und werden vom Suchdienst nicht verändert.
*   **Laufzeit:** `QuestionnaireSearchEngine` lädt die validierten Modelle in den Arbeitsspeicher. `reload()` aktualisiert den Suchbestand nach Dateiänderungen; bei ungültigen oder doppelten Instrumenten bleibt der vorherige gültige Bestand erhalten.
*   **Treffer:** Instrumente, Versionen, Dimensionen, Itemtexte, REDCap-Feldnamen und Antwortoptionen werden case-insensitiv durchsucht. Ergebnisse sind typisierte Pydantic-Modelle.
*   **Team-Sharing:** Für private/lizenzierte Daten einen zugriffskontrollierten gemeinsamen Ordner verwenden. Nur für öffentliche Verteilung freigegebene oder synthetische Dateien gehören in ein öffentliches Repository.

### Modul 3: NLP Live-Warnsystem (`/src/core/nlp_engine.py`)
**Aufgabe:** Verhindert semantische Duplikate beim Zusammenstellen (Assemblieren).
*   **Modell:** `all-MiniLM-L6-v2` geladen via `sentence-transformers`.
*   **Caching:** Um Ladezeiten beim Starten der GUI zu vermeiden, können die Vektoren (Embeddings) aller Items beim Einlesen der JSON-Dateien vorkalkuliert und lokal zwischengespeichert werden.
*   **Laufzeit-Check:** Zieht der User "Item A" auf das Canvas, vergleicht das System den Vektor von A per *Cosine Similarity* mit den Vektoren aller bereits im Canvas befindlichen Items.
*   **Thresholds:**
    *   Similarity > 0.85 🔴 (Kritische Überlappung, Warn-Modal im UI)
    *   Similarity > 0.70 🟡 (Mögliche Redundanz)

### Modul 4: Frontend GUI (`/src/gui/main.py`)
**Aufgabe:** Interaktive, asynchrone Nutzeroberfläche in Flet.
*   **State Management:** Es MUSS eine `AppState`-Klasse geben, die den aktuellen "Warenkorb" (das Canvas) verwaltet und via Observer-Pattern (Callbacks) die UI aktualisiert, wenn neue Items per Drag & Drop hinzugefügt werden.
*   **Asynchronität:** Das Berechnen der Sentence-Embeddings und API-Calls darf den UI-Thread (Mainloop) nicht blockieren. Nutze `asyncio` in Flet (`async def on_drop(e):`).
*   **UI-Komponenten:**
    *   *SearchPane (Links):* `ft.ListView` mit Facetten-Filtern. Drag-Source.
    *   *CanvasPane (Mitte):* `ft.DragTarget`. Zeigt Items als listbare, verschiebbare Kacheln (`ft.Card`). Zeigt oben eine Warn-Leiste (Rot/Gelb), falls der `nlp_engine` Alarm schlägt.
    *   *InspectorPane (Rechts):* Zeigt Metadaten (Cronbachs Alpha, Lizenzen) des aktiv angewählten Elements aus dem Canvas an.

### Modul 5: Export Engine (`/src/exporters/redcap_api.py`)
**Aufgabe:** Mappt das Pydantic-Canvas-Objekt auf ein valides REDCap Data Dictionary.
*   **Mapping-Logik (Die Übersetzungsebene):**
    *   `ItemSchema.variable_name` -> REDCap `field_name`
    *   `ItemSchema.prompt_text` -> REDCap `field_label`
    *   `ItemSchema.redcap_field_type` -> REDCap `field_type`
    *   `ResponseOption` Array -> String-Formatierung für REDCap: `0, Überhaupt nicht | 1, Leicht | 2, Mittel` -> REDCap `select_choices_or_calculations`
*   **Reverse-Scoring-Injection:** Wenn `ItemSchema.is_reverse_scored == True`, darf das R-Skript (oder das REDCap Calc-Field) nicht simpel aufaddieren. Der Exporter muss die Inversions-Logik mathematisch generieren: `(Max_Scale_Value - [field_name])`.
*   **API-Push:** Nutzt die `pycap` Library: `project.import_metadata(data, format='json')`.

---

## 🤖 5. Prompt-Kaskade für KI-Agenten (Cursor / Claude 3.5)

*Kopiere diese Prompts nacheinander in deinen KI-Agenten, um das Projekt strukturiert aufzubauen.*

**Prompt 1: Data Foundation**
> "Lies das `README.md`. Erstelle die Datei `/schemas/questionnaire_schema.py` und implementiere das Pydantic-Modell exakt wie dokumentiert. Ergänze sinnvolle Validatoren (z.B. `@field_validator`, um sicherzustellen, dass `variable_name` keine Leerzeichen enthält, da REDCap das nicht erlaubt)."

**Prompt 2: Mock Data & File-backed Search**
> "Erstelle ein Skript `/data/generate_mock_data.py`, das zwei valide, synthetische JSON-Dateien basierend auf unserem Pydantic-Schema generiert. Implementiere danach `/src/core/search_engine.py` ohne Datenbankabhängigkeit. Die Klasse `QuestionnaireSearchEngine` soll JSON-Dateien aus einem konfigurierbaren lokalen oder synchronisierten Ordner validieren, in-memory durchsuchbar machen und typisierte Suchtreffer für Instrumente, Dimensionen und Items zurückgeben."

**Prompt 3: Flet GUI Skeleton & State**
> "Erstelle in `/src/gui` die Flet-App. Baue das 3-Spalten-Layout (Search, Canvas, Inspector). Implementiere eine `AppState`-Klasse. Verbinde die linke Spalte mit der file-backed `QuestionnaireSearchEngine` aus Prompt 2. Sorge dafür, dass ich Elemente in der linken Spalte suchen und anklicken kann, und sich der State aktualisiert."

**Prompt 4: The Drag-and-Drop Canvas**
> "Erweitere das Flet-GUI. Mache die Suchergebnisse links zu `ft.Draggable` und die mittlere Spalte (Canvas) zu einem `ft.DragTarget`. Wenn ein Item gedroppt wird, muss es im `AppState` des Canvas gespeichert werden und visuell in der mittleren Liste als Karte auftauchen."

**Prompt 5: NLP Engine & Redundancy Check**
> "Implementiere `/src/core/nlp_engine.py` mit `sentence-transformers`. Integriere dies asynchron in das `on_drop`-Event der Flet-GUI. Wenn ein neues Item auf das Canvas gedroppt wird, berechne sofort die Cosine-Similarity zu den bereits vorhandenen Items. Färbe die Karte im Canvas rot, wenn die Ähnlichkeit > 0.85 ist."

**Prompt 6: REDCap Exporter**
> "Implementiere `/src/exporters/redcap_api.py`. Schreibe eine Funktion, die den aktuellen `AppState` des Canvas ausliest und das Mapping in das REDCap Dictionary-Format durchführt (inkl. Pipe-Separation für Antwortskalen). Baue den API-Call mit `PyCap` ein und verknüpfe es mit dem Export-Button in der rechten Flet-Spalte."