# Repository Guidelines

This repository hosts written research assets. Core deliverables live under `docs/フェーズ1/`, with future phases added as `docs/フェーズ2/`, etc. Keep files small, focused, and co-locate any figures/datasets with the document that references them.

## Project Structure & Module Organization
- Phase docs: `docs/フェーズ1/` (e.g., `要件定義.md`, `設計方針.md`).
- New phases: add `docs/フェーズN/` as needed.
- Assets: store next to the source doc; prefix with the doc slug (e.g., `要件定義_図1.png`, `設計方針_調査.xlsx`).
- Filenames: prefer Japanese; when romanizing, use underscores (e.g., `yoken_teigi.md`).

## Documentation Workflow
- Review existing phase docs to align terminology and scope.
- For large additions, open an outline PR or issue first.
- In PRs, call out the affected document and section (e.g., “Updates `docs/フェーズ1/要件定義.md` — 性能要件”).

## Build, Test, and Development Commands
- `markdownlint docs` — check heading order, list spacing, code fences.
- `glow docs/フェーズ1/要件定義.md` — preview in terminal (or use any viewer).
- `git diff` — verify tables, lists, and headings render as intended.

## Coding Style & Naming Conventions
- Prose: concise, declarative; sentence case headings unless proper nouns.
- Bullets: keep parallel; paragraphs ≤ three sentences.
- Bilingual terms: Japanese first, English in parentheses on first mention.
- Dates: `YYYY-MM-DD`; use metric units.

## Testing Guidelines
- No automated tests. Manually verify:
  - Internal anchors and relative links resolve.
  - External citations are reachable.
  - Numbers/claims cite a source within the same document.
  - Tables/diagrams align in a Markdown preview.

## Commit & Pull Request Guidelines
- Commits: short imperative summaries (e.g., “Update 要件定義.md”); one topic per commit.
- PRs: brief summary, linked issues or sources, and screenshots/rendered snippets for visual changes. Request at least one peer review and wait for checks (if any) to pass.

## Agent-Specific Instructions
- This AGENTS.md applies repo-wide. Obey structure and naming above.
- When adding material, place it in the correct phase directory and co-locate assets with clear slugs.
- Keep changes minimal and focused; avoid introducing build systems or unrelated tooling.
