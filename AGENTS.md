# Repository Guidelines

## Project Structure & Module Organization
The repository currently focuses on written research assets. Core deliverables live under `docs/フェーズ1/`, where each Markdown file captures requirements, specifications, or design details for phase one of the project. Add new phases in their own subdirectories (for example, `docs/フェーズ2/`) and keep filenames descriptive, using underscores to separate concepts when romanized filenames are preferable. Store shared assets (figures, datasets, spreadsheets) alongside the document that references them, prefixed with the document slug to avoid collisions.

## Documentation Workflow
Before drafting new material, review existing phase documents to maintain conceptual continuity and terminology. When introducing updates, call out the affected document and section in your pull request to help reviewers trace changes quickly. Large additions should start with an outline PR or issue comment so other contributors can align on scope before prose is written.

## Build, Test, and Development Commands
This project does not include an automated build. For consistency, run Markdown checks locally when available:
- `markdownlint docs` — flags formatting issues such as heading order, list spacing, and code fence consistency.
- `glow docs/フェーズ1/要件定義.md` — preview Markdown in the terminal; substitute any Markdown viewer you prefer.
Always inspect `git diff` before submitting to confirm tables, lists, and headings render as intended.

## Coding Style & Naming Conventions
Write concise, declarative prose. Use sentence case headings unless the subject uses a proper noun. Keep bullet lists parallel and limit paragraphs to three sentences. When incorporating bilingual terminology, present the primary term in Japanese followed by the English equivalent in parentheses on first mention. Use YYYY-MM-DD dates and prefer metric units for quantitative references.

## Testing Guidelines
There is no automated test suite. Instead, verify cross-references manually: confirm internal links resolve, external citations remain accessible, and numerical claims cite a source within the same document. When adding tables or diagrams, preview the Markdown to ensure alignment and legibility.

## Commit & Pull Request Guidelines
Commits in this project follow short imperative summaries (for example, “Update README.md”). Scope each commit to a single topic so reviewers can cherry-pick if needed. Pull requests should include: a concise summary of changes, links to supporting research or issues, and screenshots or rendered snippets when visual formatting changes. Request at least one peer review before merging and wait for all automated checks (if introduced later) to pass.
