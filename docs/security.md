# Security and Data Protection

## Secrets

- Keep credentials in a local `.env` file or a dedicated secret manager. The repository ignores `.env` and `.env.*`, while explicitly allowing the placeholder-only `.env.example`.
- Never paste real secrets into source code, tests, documentation, issue reports, logs, screenshots, or example commands.
- Give each API key the minimum permissions and lifetime needed. Rotate credentials if exposure is suspected.
- Read secret values only at the integration boundary. Do not put them in Pydantic questionnaire models or view state.
- Before every commit, inspect the staged file list and staged diff. A Git ignore rule is a safeguard, not proof that a secret was never staged or committed.

Useful local checks from the repository root:

```powershell
git status --short
git diff --cached --name-only
git check-ignore -v .env .env.local
```

Do not run commands that print actual secret values into shared logs or chat.

## Research and questionnaire data

Questionnaire text may be copyrighted or licensed, and extracted research material may contain sensitive information. Keep raw PDFs, real extracted JSON, participant-level responses, and production exports out of the public repository unless their distribution has been reviewed and explicitly approved. The Git ignore rules exclude incoming/review PDFs, non-demo extracted JSON, and export artifacts by default. The checked-in corpus is limited to the two synthetic fixtures and the separately documented PHQ-9/GAD-7, DASS/DASS-Y, and IPAQ forms whose source terms permit redistribution with their stated restrictions.

The `QuestionnaireMetadata.notes` fields are searchable and travel with shared JSON. Use them only for source-based notes that the intended audience is allowed to see. Do not put participant responses, confidential reviewer identities, credentials, or private clinical observations into notes, keywords, aliases, or characteristics.

The PDF intake pipeline keeps new uploads and extraction drafts under Git-ignored `data/questionnaires/inbox/` and `data/questionnaires/review/`. Ignore rules prevent accidental commits, but are not access control or encryption. The OpenAI extractor is disabled by default and requires a separate opt-in flag because PDF text may be private, copyrighted, or restricted from third-party processing. Form promotion and validation-study reference promotion use separate human review flags tied to the exact PDF checksum; an LLM's license statement is never trusted. Only explicitly approved validation-study PDFs can reach `data/questionnaires/references/`.

Synthetic fixture text must remain fabricated and must not be described as validated clinical content. Never use participant data in examples, test snapshots, or bug reports.

## API and logging controls

- Use HTTPS for remote services and validate configuration before sending requests.
- Apply timeouts, least privilege, and explicit handling for authentication failures, rate limits, and remote errors.
- Logs must be useful for diagnosis but must not include keys, tokens, authorization headers, sensitive prompt/document contents, or participant responses.
- Avoid returning raw provider exceptions to end users when they could disclose request details or secrets. Preserve safe diagnostic context in restricted logs.

## If a secret is exposed

1. Revoke or rotate it immediately; deleting the text from the current working tree does not invalidate a leaked credential.
2. Determine whether it was committed or pushed. Treat pushed secrets as compromised even if the repository is private.
3. Notify the service owner and follow the provider's incident process.
4. Remove the secret from future files and, if required, coordinate history rewriting with repository maintainers. Do not rewrite shared Git history without explicit authorization.
