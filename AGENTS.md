# Repository Guidelines

## Project Structure & Module Organization
- Core deliverables live in `docs/フェーズ1/` (e.g., `要件定義.md`, `設計方針.md`).
- Add new phases as `docs/フェーズN/` when scope expands.
- Store assets next to the referencing document and prefix with the doc slug (e.g., `要件定義_図1.png`, `設計方針_調査.xlsx`).
- Prefer Japanese filenames; when romanizing, use underscores (e.g., `yoken_teigi.md`). Keep files small and focused.

## Build, Test, and Development Commands
- `markdownlint docs` — Lints headings, list spacing, and code fences.
- `glow docs/フェーズ1/要件定義.md` — Previews Markdown in the terminal (use any viewer).
- `git diff` — Verifies tables, lists, and headings render as intended before committing.
- No build system or code compilation is required for this repository.

## Coding Style & Naming Conventions
- Prose: concise and declarative. Use sentence case for headings unless proper nouns.
- Keep bullet lists parallel; paragraphs should be three sentences or fewer.
- Bilingual terms: write Japanese first, add English in parentheses on first mention.
- Dates use `YYYY-MM-DD`; metric units throughout.

## Testing Guidelines
- No automated tests. Manually verify:
  - Internal anchors and relative links resolve.
  - External citations are reachable.
  - Numbers/claims cite a source within the same document.
  - Tables/diagrams align in a Markdown preview (`glow` or GUI viewer).

## Commit & Pull Request Guidelines
- Commits: short imperative summaries (e.g., "Update 要件定義.md"); one topic per commit.
- For large additions, open an outline PR or issue first.
- In PRs, call out the affected document and section (e.g., "Updates `docs/フェーズ1/要件定義.md` — 性能要件").
- Provide a brief summary, link any issues/sources, and include screenshots/rendered snippets for visual changes. Request at least one peer review and wait for checks to pass.

## Agent-Specific Instructions
- This AGENTS.md applies repo-wide. Place new material in the correct phase directory and co-locate assets with clear slugs.
- Keep changes minimal and focused; avoid introducing build systems or unrelated tooling.

