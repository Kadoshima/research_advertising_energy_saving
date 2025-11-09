# Repository Guidelines

## Project structure & module organization
- `docs/フェーズ1/` contains phase-one deliverables such as `要件定義.md` and `Runbook.md`. Add new phases as `docs/フェーズN/` and mirror folder names inside references.
- `data/` stores curated datasets; log source, version, and SHA256 in the consuming document. Do not commit raw exports without documentation.
- `configs/` tracks reusable parameter sets; align filenames with the related doc slug (e.g., `要件定義_simulation.yaml`).
- `results/` captures derived tables, charts, or summaries. Note generation date and script in the adjacent Markdown file.
- `scripts/` keeps ad-hoc automation; run from the repository root (`python scripts/generate_summary.py`) and document dependencies.
- External experiments or firmware belong in sibling repositories such as `labs/`; leave references here that link outward.

## Build, test, and development commands
- `markdownlint docs` lint headings, lists, and fenced blocks before committing.
- `glow docs/フェーズ1/要件定義.md` preview the rendered Markdown; use any equivalent viewer if Glow is unavailable.
- `git diff` confirm table layout and diagram embeds before pushing.
- Optional: `npx markdown-link-check docs/フェーズ1/要件定義.md` verify external URLs when refreshing references.

## Coding style & naming conventions
- Write concise, declarative Japanese-first prose; introduce English terms in parentheses on first mention.
- Prefer Japanese filenames; when romanizing, use lowercase snake case (`yoken_teigi.md`). Keep new content ASCII unless quoting external text.
- Maintain parallel bullet structures, limit paragraphs to three sentences, and date entries as `YYYY-MM-DD`.
- Document dataset metrics with metric units and cite sources alongside quantitative claims.

## Testing guidelines
- No automated suite exists; manually confirm internal anchors, relative links, and cross-phase references.
- Preview diagrams and tables with a Markdown viewer; reconcile CCS thresholds with `docs/フェーズ1/Runbook.md`.
- When adjusting datasets, validate row counts against expectations and update recorded checksums.

## Commit & pull request guidelines
- Write imperative commit subjects such as `Update 要件定義.md`; keep each commit scoped to a single topic.
- PR descriptions should list affected documents, summarize impact, reference issues, and attach render diffs or screenshots for visual changes.
- Request at least one peer review and wait for required checks before merging.

## Agent-specific instructions
- Add new material to the appropriate phase directory and store supporting assets beside the referencing document with slugged filenames (e.g., `要件定義_図1.png`).
- Avoid introducing new tooling or build systems unless coordinated with maintainers.
