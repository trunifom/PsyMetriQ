# Licensing Workflow, Zotero Sync, and Admin Configuration

This page documents, in full detail, everything involved in getting licensed
(commercial) questionnaire item text into PsyMetriQ safely, keeping it visible
to users only after they acknowledge its license, and operating a shared
deployment as its administrator. It complements [security.md](security.md)
(general secret/data handling) and [pdf_intake.md](pdf_intake.md) (the PDF
ingestion pipeline itself).

The design principle throughout: **only a human, reviewing one exact file,
can establish that item text may be stored and redistributed inside
PsyMetriQ.** Nothing described on this page — not the Zotero sync, not a
license profile, not an admin toggle — is allowed to skip or weaken that
human, per-file rights review. Everything here either (a) feeds candidate
PDFs into that review faster, (b) speeds up writing the resulting rights
record for institutions with a known, standing license, or (c) controls a
*local, per-installation* usage confirmation that is layered on top of an
already-published item, never a substitute for the rights review itself.

## 1. End-to-end workflow overview

For an instrument your institution already licenses (for example through a
physical or negotiated test library with its own librarians), the full path
from "PDF sitting in Zotero" to "usable in a project, with a click-through
acknowledgment for every user" looks like this:

1. **Sync** — `python -m src.ingestion.zotero_source` pulls new/changed PDF
   attachments from your Zotero library (optionally one collection) into
   `data/questionnaires/inbox/`, with a metadata note beside each file.
2. **Extract** — `python -m src.ingestion.document_pipeline` (optionally with
   `--allow-remote-processing`) reads each inbox PDF, attempts structured
   extraction, and writes an unapproved review draft under
   `data/questionnaires/review/drafts/`. Nothing is published yet.
3. **Authorize** — a reviewer (for example your test library's staff)
   confirms the license terms for this exact PDF and writes a rights sidecar.
   If your institution has a standing agreement with the publisher, use a
   **license profile** (Section 3) to generate that sidecar in one command
   instead of typing every field by hand.
4. **Promote** — `python -m src.ingestion.document_pipeline --approve-draft <path>`
   re-validates the draft against the sidecar and, only if every check
   passes, writes the item text into the shared catalogue JSON under
   `data/questionnaires/json/` and copies the PDF into `data/questionnaires/forms/`.
5. **Use, gated by acknowledgment** — because the instrument's
   `is_commercial` flag is `true`, the GUI now shows a one-time
   confirmation dialog (Section 4) to each user before it displays or lets
   them select that instrument's item wording, reminding them of the
   license terms recorded in step 3.
6. **Administer the deployment** — as the sole administrator of a shared
   (for example cloud-hosted) deployment, you can adjust or disable parts of
   step 5, and hide entire features, through `data/admin_config.json`
   (Section 5) — without touching the rights review in steps 3–4.

Steps 1–2 are described in full in the [user manual](user_manual.md#sync-pdfs-from-zotero)
and [PDF intake guide](pdf_intake.md). This page focuses on steps 3, 5, and 6.

## 2. Zotero sync: what it does and does not do

`src/ingestion/zotero_source.py` (`python -m src.ingestion.zotero_source`)
uses `pyzotero` to list `application/pdf` attachments in your Zotero library
(or one collection, via `ZOTERO_COLLECTION_KEY`) and downloads any that are
new or whose Zotero item `version` has increased since the last sync. Sync
progress — which attachment version was last downloaded, its checksum — is
kept in `data/questionnaires/review/zotero_sync_state.json` (git-ignored), so
re-running the command only fetches what actually changed.

Alongside every downloaded PDF it writes `<filename>.pdf.zotero-metadata.json`
containing the parent item's title, authors, publication year, DOI, tags, and
a `https://www.zotero.org/<library>/items/<key>` link — purely so the human
who writes the rights sidecar in step 3 does not have to re-look this up.

**It never writes a rights sidecar itself.** A PDF that arrives via Zotero
sits in the exact same unapproved state as one dropped in manually: the
intake pipeline in step 4 still refuses to publish it without a matching,
explicitly human-authored `<filename>.pdf.source.json` (or one generated from
a license profile, which still requires an explicit `--content-reviewed`
flag — see Section 3).

Configuration (`.env`, see `.env.example`): `ZOTERO_API_KEY`,
`ZOTERO_USER_ID` (or `ZOTERO_LIBRARY_ID` for a group library),
`ZOTERO_LIBRARY_TYPE` (`user` or `group`, default `user`),
`ZOTERO_COLLECTION_KEY` (optional).

### 2.1 The other direction: pushing an export back to Zotero

The GUI's **Import & Export** screen has a "Zotero" panel with one button:
"Erste ausgewählte Version nach Zotero exportieren". It takes the first
version selected in your current project (the same one the export preview
shows), exports it in your currently chosen export format, and:

1. Creates a new Zotero item (`document` type) titled
   `<instrument name> (<version_id>) -- PsyMetriQ export`, with an `extra`
   field recording the PsyMetriQ `instrument_id`/`version_id`/language and,
   when documented, the version's `source_citation`/`source_doi`, and the
   tag `psymetriq-export`.
2. Attaches the exported file to that new item, so the export travels with
   your Zotero library.

This is a **citation/reference record of what you exported**, not a
substitute for the original instrument's own publication record, and it
never changes or infers anything about redistribution rights: creating the
item and attaching the file both happen entirely independently of the
version's own rights sidecar/license metadata. If the attachment step fails
(for example a transient network error), the Zotero item is still created;
the status message says so, and you can attach the file to it manually in
Zotero afterward. Uses the same `ZOTERO_*` environment variables as the sync
above; `python -m src.ingestion.zotero_source` (the sync direction) and this
push are independent operations against the same configured library.

## 3. License profiles: fast, still human-confirmed rights sidecars

`src/ingestion/license_profiles.py` lets you save an institution's recurring
license boilerplate once — license name, license URL, a permission-basis
template naming your test library or study agreement, a default reviewer —
as a named **profile**, instead of retyping it for every PDF from that
publisher.

### 3.1 Setting up profiles

Copy the template and edit it with your institution's real agreements:

```powershell
Copy-Item data/questionnaires/license_profiles.example.json data/questionnaires/review/license_profiles.json
```

The file (git-ignored, since it may name real institutional agreements) is a
JSON list of profiles:

```json
[
  {
    "profile_id": "acme_test_library",
    "license_name": "Acme Publishing Institutional Test Library Agreement",
    "license_url": "https://library.example.org/acme-agreement",
    "permission_basis_template": "Licensed through the institutional test library for this study; see agreement #2026-014.",
    "default_reviewed_by": "Test library staff",
    "document_type": "questionnaire_form"
  }
]
```

Each `profile_id` must be unique and match `^[a-z0-9_-]+$`.
`permission_basis_template` must be at least 20 characters and, like every
field the underlying `RedistributionApproval` model checks, is rejected if it
still contains obvious placeholder text (`"placeholder"`, `"todo"`,
`"example.org"`, `"researcher name"`, `"describe "`).

### 3.2 Generating a sidecar from a profile

For one exact, already-extracted review PDF:

```powershell
python -m src.ingestion.license_profiles `
  --profile acme_test_library `
  --pdf data/questionnaires/review/forms/mental_health/acme_scale/<hash>_form.pdf `
  --reviewed-by "Dr. Meier, Testbibliothek" `
  --content-reviewed
```

This:

1. Reads the exact PDF's bytes and computes its SHA-256 — never trusting a
   previously recorded hash.
2. Fills `license_name`, `license_url`, and `permission_basis` from the
   profile.
3. Sets `redistribution_permitted: true` and `document_type` from the
   profile (default `questionnaire_form`).
4. Writes `<pdf>.source.json` next to the PDF, atomically.

Two flags are deliberately **not** taken from the profile and must be passed
explicitly, per file:

- `--content-reviewed` → `questionnaire_content_reviewed: true`. Only pass
  this after you (or your librarian) have actually checked the extracted
  item wording against the source PDF.
- `--study-metadata-reviewed` → for a validation-study document instead of a
  questionnaire form.

Omitting both is allowed (the CLI warns you) and produces a sidecar the
intake pipeline will still refuse to promote — useful if you want to record
the license now and confirm the content later.

`--source-url` overrides the profile's `license_url` as the sidecar's
`source_url`, which is required when a profile has no `license_url` at all
(each institution's agreement may not have a public URL; you then supply the
document's own source URL per file).

### 3.3 Promotion

Once the sidecar exists, promotion is identical to the manual workflow:

```powershell
python -m src.ingestion.document_pipeline --approve-draft data/questionnaires/review/drafts/<sha256>.json
```

The pipeline re-checks the sidecar's hash against the exact PDF bytes and
every other promotion gate (extraction confidence, completeness, one version
per PDF, etc.) exactly as it would for a hand-written sidecar. A profile
changes nothing about that gate.

## 4. The GUI license acknowledgment gate

### 4.1 When it appears

The gate applies **only** when both are true:

- The instrument's `QuestionnaireParent.is_commercial` is `true` (an
  instrument the catalogue does not know the commercial status of, or
  explicitly knows is free/public-domain, is never gated), **and**
- The version actually stores item text (`item_text_included: true`).
  Metadata-only reference records (for example a WHO-5 profile with no item
  wording stored) are never gated, because there is no item wording to
  protect; gating them would only add friction with no protective purpose.

Under those conditions, the first time a user, in a given local installation:

- opens a version's detail panel and would see its item list,
- checks the "Auswahl" checkbox to add the whole version to their project, or
- checks an individual item, scale, or dimension checkbox,

PsyMetriQ shows a modal dialog instead of the item text/selection change:

- The instrument's full name and a short explanation of why the dialog
  appeared.
- `Lizenz/Status: <license_name>` from the version's first source document.
- The `permission_basis` text recorded during rights review (so the user sees
  *why* this was approved, for example "licensed via the institutional test
  library"), if present.
- The license URL, if present.
- A checkbox: "Ich habe die Lizenzbestimmungen gelesen und halte mich daran."
  ("I have read the license terms and will follow them.")
- "Bestätigen und fortfahren" (enabled only once the checkbox is ticked) and
  "Abbrechen".

Cancelling leaves everything exactly as it was (no selection change, item
text still hidden). Confirming performs two things atomically from the
user's point of view: it persists the acknowledgment (Section 4.2) and then
completes the action that triggered the dialog (the checkbox toggle, or
revealing the item list).

### 4.2 What "acknowledged" means and where it lives

An acknowledgment is recorded as
`WorkspaceSettings.acknowledged_licenses[instrument_id] = <ISO 8601 UTC timestamp>`
in `data/psymetriq-settings.json` (the same file that stores theme/font-size
preferences). It is:

- **Per instrument**, not per version: acknowledging one commercial
  instrument's license does not carry over to a different instrument.
- **Per local installation/settings file**, not per browser tab or per Flet
  session: once acknowledged, the dialog never reappears for that instrument
  on that installation, even after restarting the app.
- **A local usage confirmation, not a redistribution approval.** It has no
  bearing on what the intake pipeline in Section 3 will publish; it only
  gates what the local GUI displays/lets a user select *after* something was
  already published through that separate, still-mandatory review.

Because it lives in the same settings file as every other local preference,
see Section 6 for an important caveat about what "per installation" means on
a shared multi-user deployment.

### 4.3 Where license information stays visible regardless

Even before acknowledgment, the catalogue list already shows
"Lizenzpflichtig · Bestätigung erforderlich" in a version's subtitle, so
browsing/searching still surfaces which instruments are commercially
restricted. After acknowledgment (or for any non-gated instrument), the full
"Rechte und Quellen" panel in the version detail view continues to show every
recorded source document's license name, redistribution status, permission
basis, and source URL — the acknowledgment gate only ever hides the item
*wording*, never the rights metadata about it.

## 5. Admin configuration (`data/admin_config.json`)

`src/gui/admin_config.py` defines a small, deployment-wide configuration that
is deliberately **separate** from `WorkspaceSettings`:

| Aspect | `WorkspaceSettings` (`data/psymetriq-settings.json`) | `AdminConfig` (`data/admin_config.json`) |
| --- | --- | --- |
| Who changes it | Any user, from the **Einstellungen** screen | Only whoever has file/server access to the deployment |
| Exposed in the GUI? | Yes | Never |
| Included in settings export/import? | Yes | No |
| Read | Every render that needs it | Once, at process startup |

Copy `data/admin_config.example.json` to `data/admin_config.json`
(git-ignored) and edit it directly on the server/host running PsyMetriQ:

```json
{
  "admin_config_schema_version": 1,
  "license_acknowledgment_enabled": true,
  "remote_processing_allowed": true,
  "hidden_views": [],
  "feature_flags": {}
}
```

### 5.1 Field reference

- **`license_acknowledgment_enabled`** (`bool`, default `true`). Set to
  `false` to skip the Section 4 dialog entirely, for every user, for every
  instrument. Intended for test/debug sessions or a small, trusted team where
  you have decided the per-click acknowledgment adds no value. This flag
  never touches the intake pipeline: a PDF still cannot be published without
  its rights sidecar regardless of this setting. Internally, when this is
  `false`, `PsyMetriQApplication._requires_license_acknowledgment()` always
  returns `False`.
- **`remote_processing_allowed`** (`bool`, default `true`). A deployment-wide
  kill switch for remote LLM PDF extraction (OpenAI/Anthropic/AlpineAI
  SwissGPT/OpenAI-compatible). When `false`: the **Einstellungen** remote-opt-in
  switch is shown disabled with an explanatory note, and
  `PsyMetriQApplication._remote_processing_enabled()` (which ANDs this with
  each user's own `remote_processing_enabled` preference) returns `False`
  even if a user's saved preference is `true` — both the PDF-intake screen's
  button label/behavior and the actual `process_inbox(...)` call respect
  this.
- **`hidden_views`** (list of `"catalog" | "project" | "exchange" | "intake" | "settings"`,
  default `[]`). Any view listed here disappears from the sidebar for every
  user and cannot be reached: `_build_sidebar()` skips it entirely, and
  `_navigate()` silently refuses to switch to it (logging a warning) even if
  something else tries to. If the default view (`catalog`) is hidden, the
  application falls back to the first still-visible view in
  `catalog, project, exchange, intake, settings` order; if all are hidden it
  falls back to `catalog` regardless (so the app never fails to render a
  view; hiding every entry is not a supported "kiosk lock" and would leave a
  visible-but-unreachable state).
- **`feature_flags`** (`dict[str, bool]`, default `{}`). Reserved namespace
  for future ad-hoc toggles that do not yet warrant their own named field.
  Nothing in the current codebase reads it yet; it exists so a future flag
  can be introduced without an `AdminConfig` schema migration.

### 5.2 Failure behavior

If `data/admin_config.json` does not exist, `AdminConfig()` defaults (every
feature enabled, nothing hidden) are used silently. If the file exists but is
invalid JSON, fails schema validation (for example an unknown entry in
`hidden_views`), the application still starts, falls back to the same
all-enabled defaults, and appends a warning to the startup status message
(visible in the header status bar and in `DEBUG` logs) so you notice the
misconfiguration without the deployment going down.

## 6. Operating a shared/cloud deployment: what "per installation" really means

Everything in Sections 4–5 is described as "per installation" or
"deployment-wide" because that is what the underlying files
(`data/psymetriq-settings.json`, `data/admin_config.json`) actually are:
**one file on the server's filesystem, shared by every Flet session that
connects to that running process.** This matters once several research
colleagues use the same cloud-hosted instance concurrently, which the current
single-process design does not fully account for:

- **License acknowledgments are effectively shared, not personal.** If
  colleague A acknowledges a commercial instrument's license, colleague B
  using the same deployment will not see the dialog for that instrument
  either, because both read/write the same `acknowledged_licenses` map in
  the same settings file. There is currently no per-user identity to key
  acknowledgments (or any other preference) by.
- **Concurrent settings writes can race.** `WorkspaceStore.save_settings()`
  writes the whole file atomically (temp file + `os.replace`), so a single
  write is never corrupted, but two users saving different preference
  changes at nearly the same time will have one silently overwrite the
  other's most recent settings write (last write wins, no merge).
- **The catalogue/project directories are also shared paths** on the same
  filesystem unless each user is pointed at their own; saved project
  `.psymetriq.json` files are independent artifacts a user downloads/loads
  explicitly, so those are naturally isolated as long as colleagues do not
  all save to the exact same path.

None of this is a security hole in the sense of exposing item text to
unauthorized people — everyone on the same deployment already has the same
access by construction — but it does mean the acknowledgment gate currently
functions as "someone on this deployment has confirmed the license," not
"this specific person has." If per-user acknowledgment, settings, and
project isolation matters for your team's workflow, the deployment topology
that already gives you that today is **one PsyMetriQ process per researcher**
(for example one container/session per person, each with its own `data/`
directory), rather than one shared process for the whole team; introducing
real multi-user accounts inside the application itself is tracked as a
possible future enhancement, not something currently implemented.
