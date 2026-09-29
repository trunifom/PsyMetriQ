# Datenbanken, APIs und Datenformate für eine Software zur Suche und Zusammenstellung von Fragebogen

**Stand: 27. September 2026**

## Management Summary

Für eine Software, die gesundheitliche, psychosoziale, psychometrische, pädagogische und sozialwissenschaftliche Fragebogen suchen und zu Erhebungsinstrumenten zusammenstellen soll, existiert **keine einzelne Datenbank**, die gleichzeitig vollständig, offen, maschinenlesbar, mehrsprachig, psychometrisch kuratiert und rechtlich frei nachnutzbar ist. Die fachlich und technisch tragfähigste Lösung ist deshalb eine **föderierte Metasuchmaschine**: Sie indexiert Metadaten aus mehreren offenen und lizenzierten Quellen, speichert vollständige Items nur bei eindeutigem Nutzungsrecht und verweist bei geschützten Instrumenten auf den Rechteinhaber beziehungsweise die Originalquelle.

Als technische Primärquellen sind besonders geeignet:

- **NIH Common Data Elements Repository (CDE-R)** für strukturierte Fragen und Formulare mit öffentlicher API sowie Exporten in JSON, XML, CSV, CDISC ODM, REDCap CSV und HL7 FHIR Questionnaire.[^1][^2][^3]
- **PhenX Toolkit** für kuratierte gesundheits-, epidemiologie- und biomedizinbezogene Messprotokolle, Datenwörterbücher, Word/RTF-, CSV- und REDCap-Exporte sowie einen Gesamtdatenbank-Export.[^4][^5][^6]
- **Open Test Archive/PsychArchives**, **GESIS ZIS** und **FDZ Bildung** für offene oder nichtkommerziell nachnutzbare deutschsprachige Instrumente, Skalen, Items, Dokumentationen und persistente Identifikatoren.[^7][^8][^9][^10]
- **PSYNDEX Tests**, **HaPI** und **APA PsycTests** für die umfassende fachliche Discovery-Schicht. Diese Quellen sind besonders wertvoll für Auffindbarkeit und psychometrische Metadaten, aber teilweise abonnementpflichtig und nicht als frei kopierbare Instrumentensammlung zu behandeln.[^11][^12][^13]
- **HealthMeasures/PROMIS** und **ePROVIDE/PROQOLID** für Patient-Reported Outcomes und Clinical Outcome Assessments; der maschinelle Zugriff und die elektronische Bereitstellung sind dort jedoch lizenz- beziehungsweise vertragsabhängig.[^14][^15][^16]

Die zentrale Produktentscheidung lautet daher: **Metadaten umfassend indexieren, Instrumentinhalte rechteabhängig freischalten.** „Im Internet sichtbar“, „kostenfrei zugänglich“, „Open Access“, „für Forschung kostenlos“ und „für Einbau in eine Software frei nutzbar“ sind rechtlich und technisch nicht dasselbe.

## Zielbild der Software

Die geplante Software sollte drei klar getrennte Funktionen anbieten:

1. **Discover:** Instrumente anhand von Konstrukt, Zielgruppe, Setting, Sprache, Anzahl Items, Bearbeitungszeit, Messmodus, psychometrischer Evidenz und Lizenzstatus auffinden.
2. **Evaluate:** Versionen, Übersetzungen, Reliabilität, Validität, Responsivität, Normierung, Anwendungsvoraussetzungen und Quellen vergleichen.
3. **Compose:** Nur rechtlich zulässige Instrumente oder vom Nutzer lizenzierte Inhalte zu einem Fragebogenpaket zusammenstellen und in technische Zielformate exportieren.

Diese Trennung ist wesentlich. Bibliografische Datensätze können häufig recherchiert und angezeigt werden, ohne dass daraus das Recht folgt, die vollständigen Items, Antwortoptionen, Auswertungsalgorithmen oder Übersetzungen in einer eigenen Software zu speichern oder weiterzugeben. Bei Patient-Reported Outcome Measures kontrolliert der Rechteinhaber typischerweise Reproduktion, Distribution, elektronische Adaption und Übersetzungen; das Fehlen eines Copyright-Hinweises bedeutet nicht, dass ein Instrument frei ist.[^17]

## Begriffe und Inhaltsebenen

Eine Instrumentendatenbank kann sehr unterschiedliche Dokument- und Objekttypen enthalten. Für die Software sollten diese nicht in einem einzigen Feld „Fragebogen“ vermischt werden.

| Ebene | Inhalt | Typische Nutzung |
|---|---|---|
| Instrument-Metadaten | Titel, Akronym, Autor, Konstrukt, Population, Sprache, Quelle, Identifikator | Discovery und Filterung |
| Instrumentversion | Lang-/Kurzform, Übersetzung, Altersversion, Fremd-/Selbstbericht, Papier/ePRO | Versionenkontrolle |
| Itemdefinition | Wortlaut, Instruktion, Fragetyp, Antwortoptionen, Pflichtfeld, Reihenfolge | Fragebogen-Builder |
| Formular/Protokoll | Gruppierung von Items, Abschnitte, Reihenfolge, Sprunglogik | Erhebungsdesign |
| Scoring | Reverse Coding, Subskalen, Summenbildung, Transformationen, Normtabellen | Auswertung |
| Psychometrische Evidenz | Reliabilität, Validität, Messfehler, Responsivität, DIF, Faktorstruktur | Instrumentenauswahl |
| Implementierungsdokumente | Manual, Datenwörterbuch, Codebook, REDCap-Projekt, Syntax | Technische Umsetzung |
| Rechteinformation | Copyright, Lizenz, erlaubter Zweck, Gebühren, Übersetzungs- und ePRO-Rechte | Zugriffs- und Exportsteuerung |
| Review/Empfehlung | Testrezension, systematischer Review, regulatorische Empfehlung | Qualitätsbewertung |

HL7 FHIR trennt beispielsweise die Definition eines Fragebogens als `Questionnaire` von den ausgefüllten Antworten als `QuestionnaireResponse`. Das Questionnaire-Modell bildet Gruppen, Items, Datentypen, Pflichtangaben, Wiederholungen, erlaubte Antworten und bedingte Anzeige ab. CDISC ODM ist dagegen ein herstellerneutrales Austausch- und Archivformat für klinische Studiendaten und zugehörige Metadaten; es wird von vielen Electronic-Data-Capture-Systemen für Case Report Forms verwendet.[^18][^19][^20][^21]

## Datenbanklandschaft

### Offene technische Kernquellen

| Quelle | Fachlicher Schwerpunkt | Zugang | API | Exporte und Dateien | Eignung für Software |
|---|---|---|---|---|---|
| NIH CDE Repository | NIH-empfohlene Common Data Elements und Forms | Öffentlich; Konto für viele Speicher-/Exportfunktionen | Öffentliche Swagger-dokumentierte API für CDEs und Forms | CDE: JSON, XML, CSV/Excel; Forms: JSON, XML, ODM; zusätzlich REDCap CSV, CDE Dictionary CSV und FHIR Questionnaire JSON | **Sehr hoch** für strukturierten Import und Interoperabilität |
| PhenX Toolkit | Standardisierte Phänotyp-, Expositions-, Gesundheits- und Forschungsprotokolle | Suche ohne Registrierung; überwiegend kostenlos, einzelne Protokolle eingeschränkt | Keine belastbar dokumentierte öffentliche REST-API in den geprüften offiziellen Informationen | Word-Data-Collection-Worksheet, RTF-Datenwörterbuch, CSV, REDCap ZIP, Datenbank-Gesamtexport | **Sehr hoch** für Batch-Import und Gesundheitsforschung |
| NLM Clinical Tables/LOINC Forms | Kodierte klinische Fragen, Antwortlisten und Formulare | Öffentlich | Öffentliche HTTP-Such-API | JSON-Antworten; Formdefinitionen und kodierte Antwortlisten | **Hoch** für Terminologie, Autocomplete und klinische Formulare |
| PubMed/PMC | Validierungs-, Entwicklungs- und Anwendungsstudien | Öffentlich | NCBI E-utilities | XML und bibliografische Metadaten; Volltext nur, wenn rechtlich verfügbar | **Sehr hoch** als Evidenz- und Referenzschicht |
| DataCite | DOI-Metadaten, unter anderem für PsychArchives | Öffentlich | REST-API | JSON-Metadaten | **Hoch** für DOI-Auflösung, Provenienz und Aktualisierung |

Das NIH CDE Repository bietet strukturierte, menschen- und maschinenlesbare Definitionen. Die API dokumentiert Such- und Einzelabrufe für CDEs und Forms; die Benutzeroberfläche kann CDEs und Forms in mehreren Formaten exportieren. Für einzelne Formulare nennt die NLM ausdrücklich NIH-CDE-JSON, CDISC-ODM-XML, NIH-CDE-XML, REDCap-CSV, CDE-Dictionary-CSV und FHIR-Questionnaire-JSON.[^2][^22][^3]

PhenX erlaubt Suche, Browsing, Auswahl und Berichterstellung ohne Benutzerkonto; die meisten Protokolle sind frei verfügbar, bei einem kleinen Anteil wird auf die eingeschränkte Originalquelle verwiesen. Ein PhenX-Datenwörterbuch enthält Variablennamen, Identifikatoren und Attribute; als Dateien stehen unter anderem RTF, CSV und REDCap ZIP bereit.[^6][^23][^4]

Die NLM Clinical Tables API bietet Suchendpunkte für LOINC-Fragen, Forms und Formabschnitte sowie separate Abrufe für Antwortlisten und Formdefinitionen. Sie liefert unter anderem LOINC-Code, Fragetext, Datentyp, Synonyme und – soweit vorhanden – kodierte Antworten. PubMed-Daten sind über FTP und die E-utilities verfügbar; diese eignen sich für das automatische Nachladen bibliografischer Evidenz, nicht als primäre Quelle vollständiger Fragebogen.[^24][^25][^26]

### Deutschsprachige Repositorien

| Quelle | Inhalt | Offenheit | Formate | API-Status | Wichtige Einschränkung |
|---|---|---|---|---|---|
| Open Test Archive / PsychArchives | Psychologische Tests, Fragebogen, Dokumentationen, Auswertungsbogen, Normtabellen | Öffentlich; objektbezogene Creative-Commons-Lizenzen | Vor allem PDF, teilweise DOCX und weitere Repositoriumsformate | Keine stabile, öffentlich dokumentierte, instrumentenspezifische Such-API verifiziert; DOI-Metadaten über DataCite nutzbar | Lizenz jedes einzelnen Objekts beachten |
| GESIS ZIS | Sozial- und verhaltenswissenschaftliche Items, Skalen, Tests, Indizes und Fragebogen | Frei zugänglich; Instrumente grundsätzlich kostenlos für nichtkommerzielle Forschung | Webansicht, DOI, häufig PDF-Dokumentation | Keine öffentliche ZIS-API in den geprüften offiziellen Informationen verifiziert | Kommerzielle Plattformnutzung wegen NC-Bedingung vorher genehmigen lassen |
| FDZ Bildung | Skalen, Items, Originalfragebogen, Kompetenz- und Leistungstests | Metadaten frei; Skalen/Items oft offen; Testaufgaben teilweise registrierungs- und antragspflichtig | Webansicht, Skalendokumentation und Originaldokumente je Bestand | Keine öffentliche API verifiziert | Zugang und Rechte unterscheiden sich auf Instrument-/Aufgabenebene |
| PSYNDEX Tests | Diagnostische Tests und Forschungsinstrumente aus dem deutschsprachigen Raum | Basissuche frei; erweiterte Zugänge via Ovid, EBSCO und wiso | Webdatensätze; herunterladbare Testverzeichnisse; Host-Exporte | API gegebenenfalls über lizenzierten Host, nicht als offene PSYNDEX-Content-API | Viele Einträge sind Beschreibungen, nicht frei übernehmbare Vollinstrumente |

Das Open Test Archive stellt frei zugängliche und lizenzierte Testverfahren bereit. Einzelne Datensätze können Verfahrensdokumentation, Fragebogen, Auswertungsbogen oder Normtabellen enthalten und besitzen DOI sowie eine explizite Creative-Commons-Lizenz; Beispiele zeigen sowohl CC BY-SA als auch restriktivere CC BY-NC-ND-Lizenzen. Für die Software muss deshalb die Lizenz **pro Datei und pro Version** erfasst werden, statt das gesamte Repositorium pauschal als „frei“ zu klassifizieren.[^27][^9][^28]

PsychArchives empfiehlt PDF/A für Textdokumente und CSV für tabellarische Daten; es archiviert daneben Quellcode und weitere digitale Forschungsobjekte. Die DataCite-API kann für DOI-Metadaten genutzt werden, ersetzt aber keine native API für Instrumentinhalte oder Dateirechte.[^29][^30][^31]

ZIS beschreibt sich als kostenfreies Open-Access-Repositorium für deutsch-, englisch- und mehrsprachige Items, Skalen, Fragebogen, Tests und Indizes. Die Instrumente sind qualitätsgesichert und für nichtkommerzielle Forschungszwecke kostenfrei einsetzbar. Da eine Softwarebereitstellung – insbesondere bei Gebühren, institutioneller Lizenz oder SaaS-Betrieb – als kommerzielle beziehungsweise weitergehende Nutzung gelten kann, sollte vor einer Volltextintegration eine schriftliche Daten- und Content-Lizenz mit GESIS vereinbart werden.[^10][^32]

Das FDZ Bildung stellt Skalen und Items aus Fragebogenerhebungen frei bereit, während die Einsicht und Nachnutzung von Testaufgaben oder ganzen Testinstrumenten eine Registrierung erfordern kann. Alle Metadaten sind frei einsehbar, aber die konkrete Verwendung bleibt urheberrechtlich und durch die jeweiligen Nutzungsbedingungen begrenzt.[^33][^34][^7]

PSYNDEX Tests enthielt beim Update vom 16. Juni 2025 insgesamt 8.879 Nachweise, davon 4.006 ausführliche Verfahrensbeschreibungen; außerdem stehen herunterladbare Listen der verzeichneten Instrumente zur Verfügung. Der kostenfreie Zugang erfolgt über PubPsych, während erweiterte Suchfunktionen über Ovid, EBSCO und wiso angeboten werden. Die Ovid-Datenstruktur umfasst unter anderem Felder für Items, Itembeispiele, Anwendungsvoraussetzungen, Zielgruppe, Bearbeitungszeit, Reliabilität, Testkonstruktion, Verfügbarkeit und Quelle.[^12][^35][^36]

### Lizenzierte Discovery-Datenbanken

| Quelle | Inhalt | Zugriff | API/Integration | Vollinstrumente | Empfohlene Rolle |
|---|---|---|---|---|---|
| HaPI | Gesundheitsbezogene und psychosoziale Messinstrumente, Quellen und Psychometrie | Institutionelles Abonnement über EBSCO oder Ovid | EBSCOhost API über EIT-Profil und Vertrag; REST/SOAP, XML; Datenbank-Kompatibilität bestätigen | Grundsätzlich bibliografisch; kein genereller Direktzugriff auf den vollständigen Fragebogen | Discovery und psychometrische Metadaten |
| APA PsycTests | Psychologische Tests, Maße, Skalen, Surveys und Assessments | Institutionelles Abonnement, u. a. über EBSCO/ProQuest | Host-APIs und Host-Exporte nach Vertrag | Bei vielen Datensätzen Testdatei oder Items; Scoringmaterial häufig nicht enthalten | Discovery plus rechteabhängiger Dokumentzugriff |
| ePROVIDE / PROQOLID | Clinical Outcome Assessments, Entwickler, Copyright, Übersetzungen und Nutzungsbedingungen | Teilweise öffentliche Ansicht; erweiterte Inhalte/Services per Konto oder Abonnement | API-Dokumentation technisch sichtbar; produktiver Zugriff, Umfang und Wiederverwendung vertraglich klären | Instrumentzugriff abhängig vom jeweiligen COA und Lizenzprozess | COA-Rechte- und Beschaffungsschicht |
| COSMIN Database | Systematische Reviews von Outcome-Messinstrumenten | Kostenlos | Keine öffentliche API verifiziert | Keine Instrumenten-Volltextdatenbank | Evidenz- und Qualitätsbewertung |
| REDCap Shared Library | Fertige REDCap-Erhebungsinstrumente und Forms | Nur für Nutzer teilnehmender REDCap-Institutionen | Import innerhalb REDCap; kein öffentlicher Katalogzugriff | Ja, abhängig von Bibliothek und Rechten | Deployment in REDCap, nicht offene Harvesting-Quelle |

HaPI ist eine abonnementbasierte bibliografische Datenbank. Die Datensätze enthalten Titel, Autoren, Originalquelle, Sprache und Schlagwörter; häufig zusätzlich Zweck, Antwortformat, Itemzahl, Beispielitems, Subskalen, Reliabilitäts- und Validitätsangaben. HaPI stellt aber nicht generell den wörtlichen Fragebogen bereit, sondern verweist auf die Publikationsquelle; wenn alle Items in der Quelle enthalten sind, wird dies im Datensatz kenntlich gemacht.[^37][^38][^11]

Die EBSCOhost API kann Inhalte abonnierter Datenbanken in andere Anwendungen einbetten. Sie benötigt ein EIT-Profil, unterstützt REST und SOAP und liefert XML; ob HaPI, PSYNDEX oder APA PsycTests im konkreten Lizenzprofil API-fähig ist, muss EBSCO für den Kundenvertrag bestätigen. Die Benutzeroberfläche von EBSCOhost unterstützt je nach Konfiguration PDF, Word, CSV, BibTeX, MARC21, XML und RIS; größere Exporte können bis zu 25.000 Datensätze umfassen, wenn die Institution dies freigeschaltet hat.[^39][^40][^41][^42]

APA PsycTests enthält strukturierte Beschreibungen sowie bei vielen Einträgen tatsächliche Instrumentdateien oder Items; die Datenbank ist auf Forschungsinstrumente ausgerichtet, während Scoringmaterial häufig fehlt. Ein vorhandener Download in PsycTests ist deshalb nicht automatisch eine Lizenz zur Aufnahme in einen eigenen öffentlichen Katalog oder Fragebogen-Builder. Die Permissions-Angabe des Datensatzes – etwa Research/Teaching, Contact Author oder Contact Publisher – muss als maschinenlesbare Rechteentscheidung übernommen werden.[^43][^44][^45][^13]

ePROVIDE bündelt PROQOLID, PROLABELS, PROINSIGHT, Anfragemanagement und Instrumentdistribution. PROQOLID beschreibt unter anderem Autor, Copyright-Inhaber, Zweck und Merkmale von Clinical Outcome Assessments. Eine API-Dokumentationsoberfläche ist erreichbar, doch für einen produktiven Connector müssen Authentifizierung, erlaubte Endpunkte, Rate Limits, Anzeigeumfang, Caching und Weitergabe ausdrücklich vertraglich geklärt werden. Für nicht finanzierte akademische Forschung können bestimmte von Mapi verteilte COAs nach Anmeldung kostenfrei zugänglich sein; dies ist keine pauschale Erlaubnis zur Plattformdistribution.[^46][^47][^48][^14]

COSMIN sammelt systematische Reviews von Outcome-Messinstrumenten und dient primär dazu, verfügbare Messinstrumente und deren Messeigenschaften zu beurteilen. Ergebnisse lassen sich seitenweise beziehungsweise als Lesezeichen in DOCX exportieren, typischerweise bis 100 Treffer pro Export. Die Nutzungsbedingungen beschränken Inhalte auf nichtkommerzielle beziehungsweise private Zwecke und untersagen Weitergabe oder kommerzielle Bereitstellung ohne ausdrückliche Genehmigung.[^49][^50][^51][^52][^53]

Die REDCap Shared Library ist nicht öffentlich zugänglich; Nutzer müssen in einer REDCap-Instanz angemeldet sein. Kuratierte Instrumente werden vor Aufnahme auf Forschungsrelevanz, funktionale Kodierung und Copyright-Fragen geprüft. Die normale REDCap-Projekt-API ermöglicht Daten- und Metadatenoperationen innerhalb eines autorisierten Projekts, ist aber nicht mit einer offenen Katalog-API für die Shared Library gleichzusetzen.[^54]

### Spezialisierte Gesundheitsquellen

| Quelle | Inhalt | Zugriff/Format | Softwarehinweis |
|---|---|---|---|
| HealthMeasures / PROMIS | PROMIS, Neuro-QoL, ASCQ-Me, NIH Toolbox | Viele respondent-ready PDFs; API und Plattformintegrationen lizenzpflichtig | Für CAT, automatische Administration und Scoring Assessment Center API lizenzieren |
| RAND Health Surveys | Gesundheit, Lebensqualität, Versorgungsqualität, mentale Gesundheit | Öffentliche Dokumente, meist PDF; teils Excel und SAS-Scoringdateien | Gute Quelle für direkt nutzbare Instrumente, aber Bedingungen des konkreten Tools speichern |
| WHO Tools | WHOQOL, WHS+, STEPS, SAGE und thematische Fragebanken | Meist Webseiten und PDF/Office-Dokumente; je Instrument unterschiedliche Bedingungen | Nicht als einheitlich offene Instrumentenbibliothek behandeln |
| ICHOM | Standard Sets, Referenzleitfäden und Datenwörterbücher | Öffentlich und kostenlos | Enthaltene PROMs können eigene Lizenzen benötigen |

HealthMeasures erlaubt für viele englische und spanische PROMIS- und Neuro-QoL-Instrumente eine öffentlich verfügbare Nutzung in individueller Forschung oder klinischer Anwendung ohne Lizenzgebühr. Für CATs, integrierte digitale Administration und Scoring wird jedoch eine Assessment-Center-API oder eine entsprechend lizenzierte Plattform benötigt; Gebühren und Rechte richten sich nach Plattform, Sprache und Nutzungsart.[^15][^55][^16][^56]

RAND stellt zahlreiche Health-Care-Surveys als öffentliche Dokumente ohne Gebühr zur Verfügung und verlangt eine angemessene Quellenangabe. Einzelne Sammlungen bieten PDF-Fragebogen, Scoringmanuals, Excel-Vorlagen und SAS-Code. Dennoch sollte die Software die Bedingungen des jeweiligen Instruments archivieren, da verlinkte Fremdinstrumente nicht zwangsläufig den RAND-Bedingungen unterliegen.[^57][^58][^59]

WHO bietet verschiedene Datenerhebungsinstrumente und Fragebanken, unter anderem WHS+, STEPS und eine COVID-19 Question Bank. WHOQOL zeigt, warum ein einheitliches Label „WHO = offen“ falsch wäre: Für die Verwendung ist eine Genehmigung vorgesehen, die Rechte können sprach- und studienspezifisch sein und Änderungen oder Weitergabe können untersagt sein.[^60][^61][^62][^63][^64]

ICHOM stellt Standard Sets, Referenzleitfäden und Datenwörterbücher kostenlos online bereit. Die in einem Set empfohlenen PROMs können jedoch weiterhin eine eigene Lizenz erfordern; ICHOM weist ausdrücklich darauf hin, dies pro Instrument zu prüfen.[^65]

## API-Klassifikation

Für die Implementierung empfiehlt sich eine Einteilung in vier Connector-Klassen.

### Klasse A: Offene APIs

Diese Quellen können nach technischer und rechtlicher Prüfung automatisiert abgefragt werden:

- **NIH CDE API:** `GET /api/de/{tinyId}`, versionierter CDE-Abruf, `POST /api/de/search`, entsprechende Form-Endpunkte und Formsuche.[^3]
- **NLM Clinical Tables:** offene Suchendpunkte für LOINC-Fragen und Forms, plus Abruf von Antwortlisten und Formdefinitionen.[^24]
- **NCBI E-utilities:** Suche, ID-Auflösung, Abstract-/Metadatenabruf und Verlinkung für PubMed/PMC.[^66][^67]
- **DataCite REST API:** DOI-Metadaten, beispielsweise für PsychArchives-Objekte.[^30]

Für jeden Connector sind Rate Limits, `User-Agent`, Caching, Änderungsdatum, Retry-Logik, Backoff und Provenienz zu dokumentieren. Eine öffentliche API bedeutet nicht automatisch, dass alle gelieferten Texte oder Instrumentinhalte ohne Einschränkung weiterveröffentlicht werden dürfen.

### Klasse B: Vertragliche APIs

- **EBSCOhost API:** geeignet für HaPI, PSYNDEX und APA PsycTests, sofern die jeweilige Datenbank und der Kundenvertrag API-Zugriff zulassen. Technisch stehen REST/SOAP und XML zur Verfügung; organisatorisch sind EIT-Profil, institutionelle Authentifizierung und Nutzungsvertrag erforderlich.[^39]
- **Assessment Center API:** integrierte Administration und Auswertung von HealthMeasures; kommerzielle oder institutionelle Lizenzierung erforderlich.[^16][^15]
- **ePROVIDE API:** technischer API-Einstieg ist sichtbar, aber produktive Rechte und Datennutzung müssen mit Mapi Research Trust vereinbart werden.[^47][^48]
- **ProQuest Dialog API:** bietet Search- und Alert-Endpunkte mit Konto und Bearer-Authentifizierung; ob und in welchem Umfang PsycTests-Inhalte darüber verfügbar und weiterverwendbar sind, muss vertraglich bestätigt werden.[^68]

### Klasse C: Batch- und Dateiimporte

- **PhenX:** Datenbankexport, Data Dictionary CSV/RTF, Data Collection Worksheet in Word sowie REDCap ZIP.[^5][^4]
- **NIH CDE:** zusätzlich zur API Bulk- und Board-Exporte in CSV, JSON, XML und formularspezifischen Formaten.[^1][^2]
- **PSYNDEX:** herunterladbare Instrumentenlisten als Einstieg für Identifikatoren und Titel; Detaildaten über PubPsych oder lizenzierte Hosts.[^69][^12]
- **PsychArchives/Open Test Archive:** DOI- und Datei-basierter Import unter Beachtung der objektbezogenen CC-Lizenz.[^9][^28]
- **COSMIN:** DOCX-Export für kleinere Literaturbestände; wegen Nutzungsbedingungen nicht als ungeprüfter Vollimport für ein kommerzielles Produkt verwenden.[^51][^53]

### Klasse D: Manuelle oder verlinkte Quellen

WHO-Instrumente, viele Verlagsfragebogen, einzelne ePROVIDE-Instrumente und geschützte Testverfahren sollten zunächst als kuratierte Metadatensätze mit externer Bestell-, Registrierungs- oder Genehmigungs-URL aufgenommen werden. Der Volltext wird erst nach dokumentierter Lizenz in den geschützten Mandantenbereich importiert.

## Daten- und Exportformate

### Empfohlene Zielformate

| Format | Zweck | Empfehlung |
|---|---|---|
| JSON | Interne API, Web-Client, flexible Metadaten | Primäres internes Austauschformat |
| JSON-LD | Verknüpfte Daten und semantische Provenienz | Optional für FAIR-/Knowledge-Graph-Schicht |
| HL7 FHIR Questionnaire JSON | Klinische Systeme, EHR und interoperable Fragebogen | Strategisches Exportformat für Gesundheit |
| HL7 FHIR QuestionnaireResponse | Erhebungsantworten | Nur im getrennten Datenerhebungsmodul |
| CDISC ODM XML | Klinische Studien und EDC-Systeme | Wichtiges Import-/Exportformat |
| REDCap Data Dictionary CSV | REDCap-Projektaufbau | Sehr praxisrelevant für Hochschulen und Forschung |
| REDCap XML/ZIP | Komplettere Projekt-/Instrumentübertragung | Optional nach Kompatibilitätstest |
| DDI-Lifecycle XML | Sozialwissenschaftliche Fragebogen, Variablen und Routing | Empfehlenswert für langfristige Metadatentiefe |
| CSV/XLSX | Redaktion, Rechteprüfung, einfache Übergabe | Unterstützen, aber nicht als kanonisches Modell verwenden |
| RIS/BibTeX | Literatur- und Quellenexport | Für Zotero, Citavi, EndNote und Reviews |
| PDF/PDF-A | Lesefassung, unveränderliche Dokumentation | Nur als Präsentations-/Archivformat |
| DOCX/RTF | Editierbare Arbeitsunterlage | Import mit Qualitätskontrolle; nicht als strukturierte Quelle behandeln |

FHIR Questionnaire modelliert unter anderem erlaubte Antworten über `answerOption` oder referenzierte `ValueSet`s, Pflichtfelder und wiederholbare Items. DDI-Lifecycle kann Fragebogenentwicklung, Fragen, Routing, Variablenzuordnung, mehrsprachige und multimodale Instrumente sowie Question Banks abbilden. CDISC ODM ist für den Austausch und die Archivierung klinischer Daten, Metadaten, administrativer Informationen und Auditinformationen konzipiert.[^70][^19][^71][^21][^18]

### Kanonisches internes Modell

Das interne Schema sollte mindestens folgende Entitäten enthalten:

- `Instrument`: konzeptuelle Familie, Titel, Akronyme, Beschreibung, Konstrukte.
- `InstrumentVersion`: Versionsnummer, Sprache, Land/Variante, Zielgruppe, Reporter, Formlänge, Status.
- `Section`: Überschrift, Instruktion und Reihenfolge.
- `Item`: stabiler interner Identifier, Originalidentifier, Wortlaut, Fragetyp, Pflichtstatus, Wiederholung.
- `ResponseScale`: Antwortoptionen, Codes, Labels, Wertebereich und Missing-Codes.
- `Logic`: Sichtbarkeits-, Sprung-, Berechnungs- und Validierungsregeln.
- `Score`: Subskalen, Reverse Coding, Gewichtung, Missing-Regeln, Transformation, Normbezug.
- `EvidenceRecord`: Stichprobe, Sprache, Population, Kennwert, Schätzer, Konfidenzintervall, Quelle.
- `SourceRecord`: Quelldatenbank, Quell-ID, URL, DOI, Abrufdatum, Hash und Rohmetadaten.
- `RightsStatement`: Rechteinhaber, Lizenz, zulässige Zwecke, elektronische Nutzung, Veränderung, Übersetzung, Distribution, Ablaufdatum.
- `FileAsset`: Format, Prüfsumme, Version, Zugriffsklasse, Lizenzbezug.

Entscheidend ist die Trennung zwischen **Instrumentenfamilie**, **konkreter Version** und **konkreter Sprachfassung**. Eine validierte deutsche Kurzform darf nicht automatisch mit der englischen Langform oder einer kommerziellen ePRO-Version gleichgesetzt werden.

## Rechte- und Zugriffsmodell

### Fünf Zugriffsstatus

Jeder Datensatz und jede Datei sollte einen expliziten Status besitzen:

1. **Open–redistributable:** Speicherung, Anzeige und Weitergabe erlaubt, beispielsweise passende CC BY-/CC BY-SA-Inhalte.
2. **Open–restricted:** kostenlos, aber nur nichtkommerziell, unverändert oder für bestimmte Zwecke; etwa CC BY-NC-ND.
3. **Registration required:** Zugriff nach kostenfreier Registrierung oder studienspezifischer Genehmigung.
4. **Licensed:** institutioneller oder projektspezifischer Vertrag, möglicherweise mit Gebühren.
5. **Metadata only:** nur Titel, Beschreibung, bibliografische Daten und Bezugsweg; keine Items oder Scoringlogik.

Eine Creative-Commons-Lizenz muss vollständig gespeichert werden: `BY`, `SA`, `NC` und `ND` haben unterschiedliche Folgen. `ND` kann insbesondere die Anpassung, Übersetzung, Kürzung oder technische Veränderung problematisch machen; `NC` kann einem kostenpflichtigen SaaS-Produkt oder einem kommerziellen Auftrag entgegenstehen.

### Rechtefelder

Empfohlene Pflichtfelder:

- Copyright-Inhaber und Kontaktstelle
- Lizenzname, Lizenz-URL und Version
- Nutzungszwecke: Forschung, Lehre, klinische Routine, kommerziell
- Reproduktion vollständiger Items erlaubt: ja/nein/unklar
- Elektronische Administration erlaubt: ja/nein/Genehmigung erforderlich
- Änderung des Layouts erlaubt
- Veränderung des Wortlauts erlaubt
- Übersetzung erlaubt
- Einbettung in mobile App/SaaS erlaubt
- Scoringalgorithmus weitergebbar
- Weitergabe an Dritte erlaubt
- Attributionstext
- Gebührenmodell
- Genehmigungsnachweis, Laufzeit und Geltungsbereich
- Prüfstatus: automatisch erkannt, redaktionell geprüft, juristisch freigegeben

Fragebogen können in der Schweiz urheberrechtlich geschützt sein, wenn Fragen und Antwortoptionen eine individuelle geistige Schöpfung darstellen; Schutz entsteht grundsätzlich mit der Schaffung des Werks. Zusätzlich kann bei EU-Quellen das Datenbankrecht die Entnahme oder Wiederverwendung eines wesentlichen Teils sowie die wiederholte systematische Entnahme kleiner Teile beschränken. Deshalb ist Scraping einer öffentlich erreichbaren Website weder technisch noch rechtlich gleichbedeutend mit einer zulässigen Datenübernahme.[^72][^73][^74]

### Technische Durchsetzung

Die Rechte sollten nicht nur als Freitext angezeigt, sondern in der Anwendung durchgesetzt werden:

- Volltextsuche nur für Inhalte, deren Indexierung erlaubt ist.
- Itemanzeige abhängig von Nutzerrolle, Institution und Lizenz.
- „Zum Fragebogen hinzufügen“ nur bei passender Compose-Berechtigung.
- Exportblockade bei fehlenden elektronischen oder Weitergaberechten.
- Wasserzeichen oder Lizenzhinweis in PDF/DOCX, sofern vorgeschrieben.
- Lizenz- und Zitationsblock automatisch in jedes Exportpaket aufnehmen.
- Audit-Log für Import, Anzeige, Zusammenstellung und Export.
- Kein KI-gestütztes Umschreiben oder Übersetzen geschützter Items ohne Erlaubnis.

## Such- und Bewertungsfunktionen

### Suchfelder

Die Suchmaschine sollte mindestens unterstützen:

- Konstrukt und Synonyme
- Fachgebiet und Anwendungszweck
- Zielpopulation, Alter und klinischer Status
- Reporter: Selbst-, Fremd-, Eltern-, Lehrpersonen- oder Klinikerbericht
- Sprache, Land und kulturelle Version
- Messmodus: Papier, Web, App, Interview, CAT
- Itemanzahl und Bearbeitungszeit
- Antwortformat
- Subskalen
- Reliabilitäts- und Validitätsevidenz
- Normierung und Cut-offs
- Kosten und Lizenzstatus
- verfügbare Dateien und Exportformate
- DOI, PMID, HaPI-, PSYNDEX-, LOINC-, CDE- oder interne ID

HaPI und PSYNDEX zeigen, welche fachspezifischen Felder nützlich sind: Itemanzahl, Antwortformat, Subskalen, Zielgruppe, Anwendungsvoraussetzungen, Testdauer, Reliabilität, Validität und Verfügbarkeit. Solche Felder sollten normalisiert, aber immer mit der Originalquelle verknüpft werden.[^38][^35]

### Ranking

Ein transparentes Ranking kann folgende Komponenten getrennt anzeigen:

- **Inhaltliche Passung:** Konstrukt, Population, Setting.
- **Evidenzpassung:** psychometrische Qualität für genau diese Sprach- und Zielgruppenversion.
- **Praktikabilität:** Länge, Aufwand, Kosten und Administration.
- **Interoperabilität:** strukturierte Items, Codes, FHIR/ODM/REDCap-Verfügbarkeit.
- **Rechtenutzbarkeit:** sofort nutzbar, registrierungspflichtig, lizenzpflichtig oder nur Metadaten.
- **Aktualität:** letzte Revision und letzte Evidenzaktualisierung.

Die Software sollte keinen undurchsichtigen Gesamtscore als wissenschaftliche Wahrheit darstellen. Besser sind getrennte Dimensionen mit Quellenbeleg und Warnhinweisen, beispielsweise „gute Evidenz, aber keine validierte deutsche Fassung“ oder „Items verfügbar, elektronische Nutzung ungeklärt“.

## Fragebogen-Builder

Der Builder sollte nur **konkrete Instrumentversionen** aufnehmen. Beim Hinzufügen sind automatisch zu übernehmen:

- exakter Wortlaut und Reihenfolge
- Instruktionen
- Antwortoptionen und Codes
- Pflicht-/Optional-Status
- Sprunglogik
- Scoring und Reverse-Coding
- Quelle, Zitation und Lizenzhinweis
- Version, Sprache und Gültigkeitsdatum

Änderungen müssen als Abweichung von der validierten Version markiert werden. Wird ein Item gekürzt, umformuliert, neu übersetzt, in eine andere Reihenfolge gesetzt oder mit anderen Antwortoptionen versehen, kann dies sowohl urheberrechtliche als auch psychometrische Folgen haben.[^75][^17]

Ein Exportpaket sollte deshalb zwei Ebenen enthalten:

- **Respondent Form:** der tatsächlich zu beantwortende Fragebogen.
- **Research Package:** Codebook, Variablennamen, Werte, Missing-Codes, Scoring, Zitationen, Lizenznachweise, Versionsmanifest und Provenienz.

## Empfohlene Architektur

### Komponenten

1. **Source Registry:** Datenquellen, Verträge, Authentifizierung, Harvesting-Regeln und Ansprechpartner.
2. **Connector Layer:** REST/SOAP, Dateiimport, OAI/DOI-Auflösung, manuelle Redaktion.
3. **Raw Store:** unveränderte Quelldatensätze mit Zeitstempel und Prüfsumme.
4. **Normalization Pipeline:** Mapping in das kanonische Modell, Sprach- und Identifier-Normalisierung.
5. **Entity Resolution:** Dubletten und Beziehungen zwischen Instrumentenfamilien, Versionen und Übersetzungen.
6. **Rights Engine:** Zugriffs-, Anzeige-, Zusammenstellungs- und Exportentscheidungen.
7. **Evidence Graph:** Beziehungen zwischen Instrument, Version, Validierungsstudie, Review und Population.
8. **Search Index:** Volltext, strukturierte Facetten und mehrsprachige Synonyme.
9. **Composer:** Auswahl, Reihenfolge, Abschnittsbildung und Export.
10. **Audit und Redaktion:** Freigaben, Änderungsverlauf, Quellenvergleich und Konfliktbearbeitung.

### Föderiert statt Vollspiegel

Bei offenen, klar lizenzierten Quellen können strukturierte Inhalte lokal gespiegelt werden. Bei kommerziellen oder unklaren Quellen sollte die Software nur lizenzierte Metadaten zwischenspeichern oder Suchergebnisse zur Laufzeit abrufen. Vollinstrumente sollten in einem separaten, rechtegeschützten Content Store liegen.

Empfohlenes Speichermodell:

- PostgreSQL für normalisierte Kernmetadaten
- OpenSearch/Elasticsearch für Facettensuche und Volltext
- Objektspeicher für PDF, DOCX, CSV, XML und JSON
- optional RDF/Knowledge Graph für Konstrukte, Versionen und Evidenzbeziehungen
- unveränderliches Audit-Log für Rechte- und Versionsereignisse

## Importstrategie nach Quelle

### NIH CDE

- API-Suche inkrementell nach geänderten Datensätzen.
- Vollständige Rohantwort als JSON speichern.
- Forms und CDEs getrennt importieren und verknüpfen.
- Originalidentifikatoren und Version beibehalten.
- FHIR-, ODM- und REDCap-Exporte als Konformitätstests verwenden.
- UTS-Konto nur dort einsetzen, wo interaktive Export-/Board-Funktionen es erfordern.[^2][^1]

### PhenX

- Offiziellen Datenbankexport als Baseline importieren.
- Data Dictionaries als strukturierte Variablenquelle nutzen.
- Word/RTF-Dokumente nur ergänzend für Instruktionen und Layout parsen.
- REDCap ZIP gegen das interne Schema testen.
- „Limited availability“ pro Protokoll als Rechteflag übernehmen.[^4][^6]

### Open Test Archive

- DOI als stabilen Primärschlüssel nutzen.
- Metadaten über PsychArchives/DataCite übernehmen.
- Dateien nur herunterladen und indexieren, wenn die konkrete Lizenz dies erlaubt.
- Fragebogen, Dokumentation, Normtabelle und Auswertungsbogen als getrennte Assets speichern.
- Keine automatische Bearbeitung von ND-lizenzierten Dateien.[^28][^9]

### ZIS und FDZ Bildung

- Zunächst Metadaten, DOI/URL und Lizenzbedingungen kuratieren.
- Vor systematischem Harvesting oder kommerzieller Nutzung eine schriftliche Vereinbarung einholen.
- Items und Skalen nur mit dokumentierter Rechtsgrundlage importieren.
- Geschützte Testaufgaben ausschließlich in einem autorisierten Bereich bereitstellen.[^7][^33][^10]

### HaPI, PSYNDEX und PsycTests

- Institutionelle Lizenzen und Host-Vertrag prüfen.
- API- beziehungsweise Exportrechte separat von Endnutzerzugriff und Volltextrechten verhandeln.
- Metadatenfeld-Mapping mit stabilen Source IDs aufbauen.
- Keine Instrumentdatei aus dem Host in die eigene Plattform übernehmen, wenn der Vertrag lediglich Anzeige oder persönlichen Download erlaubt.
- Bei HaPI primär bibliografische Discovery und Psychometrie nutzen; Originalinstrument über die angegebene Quelle oder den Rechteinhaber beschaffen.[^11][^37]

### HealthMeasures und ePROVIDE

- Für reine Suche öffentliche Metadaten und Links verwenden.
- Vor elektronischer Administration, Scoring oder CAT-Nutzung eine passende HealthMeasures-Lizenz beziehungsweise Assessment-Center-API-Lizenz abschließen.[^15][^16]
- Bei ePROVIDE für jedes COA Distribution, Übersetzung, kommerzielle Nutzung und eCOA-Rechte über den vorgesehenen Request-Prozess klären.[^46][^14]
- Lizenznachweise und genehmigte Bildschirmdarstellungen versioniert im Rights Store archivieren.

## Qualitätskontrolle

Ein automatischer Import darf nicht unmittelbar zu einem freigegebenen Instrument führen. Empfohlen wird ein dreistufiger Workflow:

1. **Technische Validierung:** Schema, Kodierung, Pflichtfelder, Identifier, Dateihashes, Zeichensätze und Importfehler.
2. **Wissenschaftliche Redaktion:** Konstrukt, Zielgruppe, Version, Übersetzung, psychometrische Evidenz, Scoring und Quellenkonsistenz.
3. **Rechteprüfung:** Copyright-Inhaber, Lizenz, elektronische Nutzung, Veränderungs- und Weitergaberechte.

Jeder publizierte Datensatz sollte ein Provenienzprotokoll enthalten: Quelldatenbank, Quell-ID, Abrufzeit, Quellversion, Transformationsschritte, redaktionelle Person, Prüfstatus und nächstes Überprüfungsdatum. Konflikte zwischen Quellen dürfen nicht still überschrieben werden; beispielsweise sind abweichende Itemzahlen oder Autorenschaften als separate Behauptungen mit Quelle zu speichern.

## Datenschutz und Sicherheit

Die reine Instrumentensuche verarbeitet normalerweise keine Gesundheitsdaten. Sobald die Software aber Antworten erhebt, auswertet oder Profile bildet, entsteht ein eigenständiges Datenschutz- und Informationssicherheitsprojekt. Daher sollte der **Katalog/Builder technisch und organisatorisch vom Datenerhebungs- und Auswertungsmodul getrennt** werden.

Für die Erhebungsseite sind mindestens vorzusehen:

- Mandantentrennung und rollenbasierter Zugriff
- Datenminimierung und Zweckbindung
- Verschlüsselung bei Transport und Speicherung
- Pseudonymisierung und getrennte Schlüsselspeicherung
- Lösch- und Aufbewahrungskonzepte
- Audit-Logs
- Export- und Zugriffskontrolle
- dokumentierte Auftragsbearbeitung und Hostingregion
- keine Übermittlung von Antworten an externe Sprachmodelle ohne explizite Rechtsgrundlage

FHIR `QuestionnaireResponse` oder REDCap-Exporte mit Antworten dürfen nicht im öffentlichen Instrumentenkatalog gespeichert werden. Der Katalog sollte ausschließlich Definitionen und Evidenz enthalten.

## Umsetzungsetappen

### Phase 1: Offener MVP

Dauer und Aufwand hängen vom Team ab; fachlich sollte der MVP enthalten:

- NIH CDE Connector
- PhenX-Batchimport
- NLM LOINC Questions/Forms Connector
- PubMed-Evidence-Connector
- Open Test Archive und ZIS als kuratierte Quellen
- kanonisches Instrument-/Versions-/Itemmodell
- Rechte- und Provenienzfelder
- Facettensuche
- Zusammenstellung ausschließlich klar freigegebener Inhalte
- Exporte in CSV, XLSX, JSON und respondent-ready PDF

### Phase 2: Forschungsintegration

- REDCap Data Dictionary und Projektimport
- FHIR Questionnaire und CDISC ODM
- psychometrische Evidenztabellen
- DOI-, PMID- und ORCID-Auflösung
- Versionen- und Übersetzungsvergleich
- Screening- und Freigabeworkflow für Redakteure

### Phase 3: Lizenzierte Inhalte

- Verträge und Connectoren für HaPI, PSYNDEX und APA PsycTests
- ePROVIDE-/HealthMeasures-Integration
- institutionelles Single Sign-on und Entitlement-Prüfung
- Rechteabhängiges Rendering und Export
- Lizenzabrechnung, falls vom Anbieter verlangt

### Phase 4: Erweiterte Intelligenz

- semantische Konstruktsuche und kontrollierte Vokabulare
- automatische Dublettenvorschläge
- Empfehlung passender Instrumente mit erklärbaren Kriterien
- Erkennung von Evidenzlücken
- KI-gestützte Metadatenextraktion ausschließlich mit menschlicher Freigabe

KI sollte keine geschützten Instrumente rekonstruieren, keine Items ohne Rechte übersetzen und keine psychometrische Gleichwertigkeit behaupten. Automatische Vorschläge sind als Vorschläge zu markieren und von wissenschaftlich qualifizierten Personen zu prüfen.

## Beschaffungs- und Verhandlungsfragen

Vor einer Integration kommerzieller oder institutioneller Datenbanken sollten folgende Punkte schriftlich beantwortet werden:

- Darf die Software Datensätze über API abrufen?
- Welche Datenbanken und Felder sind im API-Profil enthalten?
- Dürfen Metadaten dauerhaft gespeichert und indexiert werden?
- Wie lange dürfen Daten nach Vertragsende behalten werden?
- Dürfen Suchergebnisse externen Nutzern angezeigt werden?
- Ist ein Multi-Tenant-SaaS-Betrieb zulässig?
- Dürfen Volltexte oder Instrumentdateien lokal gespeichert werden?
- Dürfen Items in einen Fragebogen-Builder übernommen werden?
- Sind PDF-, CSV-, FHIR-, ODM- oder REDCap-Exporte erlaubt?
- Darf die Plattform Nutzern Kopien zur Verfügung stellen?
- Welche Attribution ist erforderlich?
- Gibt es API-Limits, Mehrkosten, SLA oder Sandbox?
- Müssen Endnutzer über Shibboleth/OpenAthens authentifiziert sein?
- Sind kommerzielle Nutzung, klinische Routine und akademische Forschung unterschiedlich geregelt?
- Wer haftet für Rechte- und Inhaltsfehler?

## Quellenpriorität für das Produkt

| Priorität | Quelle | Begründung |
|---|---|---|
| 1 | NIH CDE Repository | Beste Kombination aus API, strukturierten Forms, offenen Standards und Exporten |
| 1 | PhenX | Kuratierte Gesundheitsprotokolle und sehr gute Forschungs-/REDCap-Exporte |
| 1 | PubMed/PMC | Offene Evidenz- und Validierungsrecherche über stabile API |
| 1 | Open Test Archive | Deutschsprachige offene Instrumente mit DOI und objektbezogenen Lizenzen |
| 2 | GESIS ZIS | Hochwertige deutschsprachige Skalen und Items; Lizenz für Plattformbetrieb klären |
| 2 | PSYNDEX Tests | Wichtigste deutschsprachige Discovery-Quelle; API-/Host-Vertrag erforderlich |
| 2 | HealthMeasures | Hochwertige PROs und digitale Administration; Lizenzmodell beachten |
| 2 | NLM LOINC Forms | Kodierung und klinische Interoperabilität |
| 3 | HaPI | Breite fachliche Discovery; überwiegend Nachweis statt Vollinstrument |
| 3 | APA PsycTests | Umfangreich und teilweise Volltext; Host- und Instrumentrechte komplex |
| 3 | ePROVIDE/PROQOLID | Zentral für COA-Rechte, Übersetzungen und Beschaffung; kommerziell geprägt |
| 3 | COSMIN | Sehr wertvoll für Reviews und Auswahlqualität, weniger als Itemquelle |
| 3 | FDZ Bildung | Relevant für Bildung und Pädagogik; differenzierte Zugangsmodelle |
| 4 | WHO, RAND, ICHOM | Wichtige kuratierte Ergänzungen, aber heterogene Rechte und Formate |

## Konkrete Produktempfehlung

Die Software sollte nicht als „Datenbank aller Fragebogen“ vermarktet werden, sondern als **evidenz- und rechtebewusste Instrumenten-Such- und Kompositionsplattform**. Der wissenschaftliche Mehrwert entsteht aus der Verbindung von Discovery, versionsgenauer Evidenz, transparenter Rechteinformation und interoperablen Exporten.

Die robusteste Startkonfiguration lautet:

- Metadaten und offene Forms aus NIH CDE, PhenX, NLM und offenen deutschsprachigen Repositorien lokal indexieren.
- PubMed/PMC automatisiert als Evidenzschicht anbinden.
- HaPI, PSYNDEX, PsycTests und ePROVIDE zunächst über Deep Links beziehungsweise institutionellen Zugriff integrieren.
- Vollitems nur bei expliziter Lizenz oder eindeutiger Open-Content-Lizenz speichern.
- FHIR Questionnaire, CDISC ODM und REDCap CSV als primäre interoperable Exporte anbieten.
- PDF, DOCX und XLSX als benutzerfreundliche, aber sekundäre Ausgabeformate bereitstellen.
- Jede Suchanzeige und jeder Export muss Version, Sprache, Quelle, Rechte und Prüfstatus sichtbar machen.

## Entscheidende Risiken

- **Urheberrechtsrisiko:** Übernahme vollständiger Items ohne entsprechende Erlaubnis.
- **Datenbankrechtsrisiko:** systematisches Scraping oder Spiegeln fremder Kataloge.[^72]
- **Lizenzrisiko:** Verwechslung von kostenfreiem Forschungsgebrauch mit kommerzieller Softwaredistribution.
- **Versionsrisiko:** Vermischung von Lang-/Kurzform, Übersetzung und Altersversion.
- **Evidenzrisiko:** Übertragung psychometrischer Kennwerte auf eine andere Population oder Sprache.
- **Scoringrisiko:** fehlende Reverse-Codierung, Normtabellen oder proprietäre Algorithmen.
- **Interoperabilitätsrisiko:** Verlust von Sprunglogik oder Antwortcodes bei PDF-/DOCX-Parsing.
- **Aktualitätsrisiko:** veraltete URLs, zurückgezogene Versionen und geänderte Nutzungsbedingungen.
- **Haftungsrisiko:** Darstellung eines Forschungsfragebogens als diagnostisch oder klinisch entscheidungsfähig.

## Abnahmekriterien für den MVP

Der MVP sollte erst freigegeben werden, wenn:

- jedes Instrument eine Quelle und stabile interne ID besitzt;
- Version, Sprache und Zielgruppe getrennt modelliert sind;
- Rechte auf Datensatz- und Dateiebene gespeichert werden;
- Instrumente mit unklarem Recht nicht zusammengestellt oder exportiert werden können;
- Importe idempotent und nachvollziehbar sind;
- Dubletten nicht automatisch zusammengeführt werden;
- Scoringregeln maschinell getestet werden;
- CSV-, JSON- und mindestens ein standardisiertes Format verlustarm exportiert werden;
- Zitations- und Lizenzhinweise automatisch ausgegeben werden;
- wissenschaftliche und rechtliche Freigaben im Audit-Log nachvollziehbar sind.

## Fazit

Technisch ist eine leistungsfähige Suche und Zusammenstellung von Fragebogen realisierbar, wenn das System nicht von PDFs, sondern von einem versions-, evidenz- und rechteorientierten Datenmodell ausgeht. Offene strukturierte Quellen wie NIH CDE, PhenX, NLM, PubMed und offene Repositorien bilden den Kern; abonnementbasierte Datenbanken erweitern die Discovery, sollten aber nur auf Basis ausdrücklicher API- und Weiterverwendungsrechte integriert werden.

Der wichtigste Grundsatz lautet: **Metadaten finden, Evidenz bewerten, Rechte prüfen, erst dann Inhalte zusammenstellen.** So kann die Software fachlich belastbar, interoperabel und rechtssicher wachsen, ohne fälschlich jeden online auffindbaren Fragebogen als frei verwendbares Softwaremodul zu behandeln.

---

## References

1. [Guides - NIH CDE Repository](https://cde.nlm.nih.gov/guides) - Repository of Common Data Elements (CDE) and Protocol Forms. Search CDEs. Search Protocol Forms.

2. [Exporting and Saving Your CDE-R Results](https://www.nlm.nih.gov/oet/ed/navigator/cder3/index.html)

3. [Swagger UI - NIH CDE Repository](https://cde.nlm.nih.gov/api-docs/)

4. [PhenX Downloads](https://www.phenxtoolkit.org/resources/download) - The PhenX Toolkit is a catalog of high-priority measures for consideration and inclusion in genome-w...

5. [PhenX Toolkit: Toolkit](https://www.phenxtoolkit.org/toolkit/) - The PhenX Toolkit is a catalog of high-priority measures for consideration and inclusion in genome-w...

6. [PhenX Toolkit: Help](https://www.phenxtoolkit.org/help/faq) - The PhenX Toolkit is a catalog of high-priority measures for consideration and inclusion in genome-w...

7. [Forschungsinstrumente // FDZ Bildung](https://www.fdz-bildung.de/zugang-instrumente) - Forschungsinstrumente der Bildungsforschung - Finden Sie hier Skalen und Items aus Fragebögen sowie ...

8. [Repositorium mit Zugang zu mehr Open-Access-Tests](https://www.psycharchives.org/handle/20.500.12034/9948) - von G Karadere · 2024 — Das Open Test Archive ist ein Produkt des Leibniz-Instituts für Psychologie ...

9. [FKS - Flow-Kurzskala - PsychArchives](https://www.psycharchives.org/en/item/87af4b18-6170-4b39-8627-8ef2513da25c) - PsychArchives is a disciplinary repository for psychological science and neighboring disciplines.

10. [ZIS: Erweiterte Suche - GESIS](https://zis.gesis.org/s/) - ZIS ist ein Open Access Repositorium für sozial- und verhaltenswissenschaftliche Erhebungsinstrument...

11. [FAQs - HaPI database](https://bmdshapi.com/faq/)

12. [Über PSYNDEX Tests](https://psyndex.de/tests/info/) - **PSYNDEX Tests** ist ein Teilbereich von [PSYNDEX](/ueber/) und verzeichnet Test­verfahren, die in ...

13. [Health Care Resources from the American Psychological ...](https://about.ebsco.com/products/research-databases/health-care-resources-apa) - Produced by The American Psychological Association (APA), this suite of databases provides researche...

14. [ePROVIDE™ – online support for Clinical Outcome Assessments](https://www.mapi-trust.org/news-events/news/eprovide-online-support-f) - Integrating knowledge, expertise and insight with a simple to access user interface

15. [Steps to License | HealthMeasures](https://healthmeasures.net/implement/steps-to-license/) - Learn how to implement measures based on your administration platform and the steps to license on He...

16. [Administration Platforms - HealthMeasures](https://healthmeasures.net/implement/administration-platforms/)

17. [Reflection paper on copyright, patient-reported outcome ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC6282242/) - With the growth of patient-reported outcome (PRO) measurement, questions arise regarding how copyrig...

18. [2.5 Resource Questionnaire - Content](https://www.hl7.org/fhir/questionnaire.html)

19. [Data Exchange](https://www.cdisc.org/standards/data-exchange) - Data Exchange Standards facilitate the sharing of structured data across different information syste...

20. [2.6 Resource QuestionnaireResponse - Content](https://hl7.org/fhir/questionnaireresponse.html)

21. [ODM v2.0 - CDISC](https://www.cdisc.org/standards/data-exchange/odm-xml/odm-v2-0)

22. [NIH Common Data Element Repository](https://www.nlm.nih.gov/oet/ed/cde/tutorial/04-200.html)

23. [PhenX Toolkit: About](https://www.phenxtoolkit.org/about) - The PhenX Toolkit is a catalog of high-priority measures for consideration and inclusion in genome-w...

24. [API for LOINC Questions and Forms - Clinical Table Search Service](https://clinicaltables.nlm.nih.gov/apidoc/loinc/v3/doc.html)

25. [Download PubMed Data - NIH](https://pubmed.ncbi.nlm.nih.gov/download/) - PubMed data download page.

26. [What is E-utilities? - The Insider's Guide to Accessing NLM Data](https://www.nlm.nih.gov/dataguide/eutilities/what_is_eutilities.html)

27. [Open Test Archive. Repositorium mit Zugang zu mehr Open-Access ...](https://psycharchives.org/en/item/72273030-168e-4504-82e0-e78c2b06f257) - PsychArchives is a disciplinary repository for psychological science and neighboring disciplines.

28. [SWE - Skala zur Allgemeinen Selbstwirksamkeitserwartung](https://www.psycharchives.org/en/item/ad76b28d-ff47-4657-b35b-c6cb6a582563) - PsychArchives is a disciplinary repository for psychological science and neighboring disciplines.

29. [Info](https://www.psycharchives.org/en/about) - PsychArchives is a disciplinary repository for psychological science and neighboring disciplines.

30. [Dataset for: Wie Kultur und Traumakategorie den Zusammenhang von Sozialer Unterstützung und Posttraumatischer Reifung verändern: Eine Meta-Analyse - B2FIND](https://b2find.eudat.eu/dataset/3ce126e7-85cd-5b04-8fde-4b1b45bb3f56) - Diese Meta-Analyse behandelt die moderierende Rolle von Kultur und Art des Traumas für die Zusammenh...

31. [PsychArchives: Home](https://psycharchives.prod.zpid.org/) - PsychArchives is a disciplinary repository for psychological science and neighboring disciplines.

32. [Fragebogenentwicklung: Unsere Angebote - GESIS](https://www.gesis.org/angebot/studien-planen-und-daten-erheben/fragebogenentwicklung) - Wir stellen Ihnen empirisch erprobte Erhebungsinstrumente zur Verfügung und unterstützen Sie bei der...

33. [Über uns // FDZ Bildung](https://www.fdz-bildung.de/ueber-fdz) - Das Forschungsdatenzentrum Bildung stellt sich vor: Das FDZ Bildung ist eine zentrale Anlaufstelle f...

34. [Erhebung: Fragebogenerhebung (Skalenkollektion)](https://www.fdz-bildung.de/erhebung.php?id=416&la=de) - Die Fragebogeninstrumente dieser Skalenkollektion zielen auf die Erfassung digitaler Kompetenzen von...

35. [Ovid Database Guide](https://ospguides.ovid.com/OSPguides/pskmdb.htm) - Each record in the PSYNDEXplus Tests Database is assigned a unique 7-digit identifier contained in t...

36. [Easy search for finding records in the PSYNDEX database](https://psyndex.de/en/) - **PSYNDEX** - [ZPID](https://leibniz-psychology.org/)'s database for psychology-related publications...

37. [Accessing HaPI through EBSCOhost - HaPI](https://bmdshapi.com/hapi-through-ebscohost/)

38. [Field Definitions - HaPI - BMDSHAPI.COM](https://bmdshapi.com/field-definitions/)

39. [EBSCOhost API - EBSCO Information Services](https://connect.ebsco.com/s/article/EBSCOhost-API?language=en_US)

40. [Exporting search results - EBSCOhost databases - Library guides ...](https://library-guides.ucl.ac.uk/ebscohost/exporting-results) - Guide to using EBSCOhost databases (new interface launched August 2025) How to export and download s...

41. [Exporting up to 25000 Results on EBSCO User Interfaces](https://connect.ebsco.com/s/article/Exporting-up-to-25-000-Results) - Click the drop-down arrow at the top of the result list and click the Export results (Up to 25,000) ...

42. [What databases are supported by the EBSCOhost API?](https://connect.ebsco.com/s/article/What-databases-are-supported-by-the-EBSCOhost-API) - See this spreadsheet to view a list of databases supported by the EBSCOhost API. (Updated 6/23/26). ...

43. [PsycTests (via ProQuest)](https://www.lib.polyu.edu.hk/databases/psyctests)

44. [Psychological tests and measurements | SFU Library](https://www.lib.sfu.ca/help/research-assistance/subject/psychology/psychological-tests)

45. [Identify & Find Tests - PSYC 465 (Swift): Experimental Psychology](https://guides.umd.umich.edu/c.php?g=904683&p=6512201) - Research Guide for Dr. Swift's section of the PSYC 465 course Find Psychology tests and measures

46. [Contact - Online Support for Clinical Outcome Assessments](https://eprovide.mapi-trust.org/page/contact) - Contact - The industry’s most referenced Clinical Outcome Assessment (COA) resources and services in...

47. [Mapi-NG API - API Platform - ePROVIDE](https://eprovide.mapi-trust.org/api/docs?ui=re_doc)

48. [Terms and Conditions of use - ePROVIDE - Mapi Research Trust](https://eprovide.mapi-trust.org/page/terms-and-conditions-of-use) - Terms and Conditions of use - The industry’s most referenced Clinical Outcome Assessment (COA) resou...

49. [Cosmin Tools](https://www.cosmin.nl/cosmin-tools/) - COSMIN Tools These tools help you improve the selection of the most appropriate outcome measurement ...

50. [Export results page](https://database.cosmin.nl/catalog.docx?page=1&q=searching&sort=pub_date_sort+desc,+title_sort+asc)

51. [COSMIN](https://refhunter.org/en/database_sheets/cosmin/) - Hier auf “Export to word (max.100)” klicken. Alle weiteren Schritte sind abhängig vom verwendeten In...

52. [pmc.ncbi.nlm.nih.gov › articles › PMC5891568COSMIN guideline for systematic reviews of patient-reported ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC5891568/) - Systematic reviews of patient-reported outcome measures (PROMs) differ from reviews of interventions...

53. [Disclaimer & Privacy](https://www.cosmin.nl/disclaimer-privacy/) - ... restrictions. Access to and use of the COSMIN websites means that the user has agreed to the fol...

54. [Library](https://projectredcap.org/resources/library/)

55. [Version 1.6, Oct 16, 2018](http://www.healthmeasures.net/images/LearnMore/Pricing_Info/HealthMeasures__Overview_of_Free_and_Fee-Based_Services__v1.6__Final__101618.pdf)

56. [HealthMeasures Terms of Use](https://healthmeasures.net/wp-content/uploads/2026/06/Terms-of-Use_HM_approved_1-12-17-Updated-Copyright-Notices.pdf) - • Publicly Available: HealthMeasures Instruments which are available for download at healthmeasures....

57. [Health Surveys](https://www.rand.org/health-care/surveys_tools.html) - Available for free in the public domain, RAND's health-related surveys are designed for a wide range...

58. [Questionnaires](https://www.rand.org/health-care/projects/hcsus/questionnaires.html) - Questionnaires from the HIV Cost and Services Utilization Study (HCSUS), the first major research ef...

59. [Kidney Disease Quality of Life Instrument (KDQOL)](https://www.rand.org/health-care/surveys_tools/kdqol.html) - Kidney Disease Quality of Life Instrument (KDQOL) survey instruments and scoring programs.

60. [Data collection tools - WHO](https://www.who.int/data/data-collection-tools) - WHO tools that support countries to strengthen their capacity to collect, compile, manage, analyze a...

61. [The World Health Organization Quality of Life (WHOQOL)](https://www.who.int/publications/i/item/WHO-HIS-HSI-Rev.2012.03) - Publicaciones de la Organización Mundial de la Salud

62. [Information for WHOQOL users](http://research.bmh.manchester.ac.uk/ihqolr/questionnaires/research/Userinformation.pdf)

63. [Questionnaires for research ( - University of Manchester)](http://research.bmh.manchester.ac.uk/ihqolr/questionnaires/research/)

64. [SCORE Tools S - World Health Organization (WHO)](https://www.who.int/data/data-collection-tools/score/tools/survey-populations-and-health-risks) - A technical package with five essential interventions and key elements for strengthening country hea...

65. [Healthcare Standardization & Implementation FAQ's](https://www.ichom.org/faqs/) - Get answers to FAQ's about value-based healthcare, patient outcome standardization and implementatio...

66. [welcome_to_e-utilities_for_pubmed_accessible.pptx](https://www.nlm.nih.gov/dataguide/welcome_to_e-utilities_for_pubmed_accessible.pptx)

67. [APIs - Develop - NCBI - NIH](https://www.ncbi.nlm.nih.gov/home/develop/api/)

68. [API Console - ProQuest](https://apidocs-dialog.proquest.com/) - Dialog search and alert APIs give service providers direct, public-facing access to the Dialog platf...

69. [[PDF] Verzeichnis Testverfahren - Einführung - Psyndex](https://psyndex.de/pub/tests/verz_einf.pdf)

70. [Choosing a DDI Product](https://ddialliance.org/product_overview)

71. [DDI-Lifecycle (DDI-L)](https://ddialliance.org/ddi-lifecycle) - DDI-Lifecycle expands on the idea of DDI-Codebook in terms of content coverage, depth, metadata mana...

72. [Directive - 96/9 - EN - EUR-Lex - European Union](https://eur-lex.europa.eu/eli/dir/1996/9/oj/eng)

73. [Database protection in the EU - Your Europe - European Union](https://europa.eu/youreurope/business/growing/protecting-intellectual-property/database-protection/index_en.htm) - The sui generis database right protects the content of your database. You or the maker of the databa...

74. [Intellectual property rights - Research Data Management](https://researchdata.unibas.ch/en/legal-issues/intellectual-property-rights/)

75. [Commentary: Copyright Restrictions versus Open Access to ...](https://pmc.ncbi.nlm.nih.gov/articles/PMC5766425/)

