#!/usr/bin/env python3
"""
make_repomix.py - Create repomix-like output for thesis files
Proper UTF-8 handling with Python
"""
import os
from pathlib import Path
from datetime import datetime

def main():
    base_path = Path(r"C:\Users\tp240\Documents\Research\research_advertising_energy_saving")
    output_file = base_path / "repomix-thesis.txt"

    all_files = []

    # Find thesis directory (contains main.tex)
    thesis_dir = None
    for d in base_path.iterdir():
        if d.is_dir() and (d / "main.tex").exists():
            thesis_dir = d
            break

    if thesis_dir:
        print(f"Found thesis dir: {thesis_dir.name}")
        for ext in ["*.tex", "*.sty"]:
            all_files.extend(thesis_dir.rglob(ext))

    # Phase 2 scripts
    scripts_path = base_path / "scripts" / "phase2_offline_eval"
    if scripts_path.exists():
        for ext in ["*.py", "*.yaml"]:
            all_files.extend(scripts_path.rglob(ext))

    # Results summary
    results_path = base_path / "results" / "phase2_offline_eval"
    if results_path.exists():
        all_files.extend(results_path.glob("*.csv"))

    print(f"Found {len(all_files)} files total")

    # Create output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# Repository Summary for LLM\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Scope: Thesis (.tex/.sty) + Phase2 scripts (.py/.yaml) + Phase2 results (.csv)\n")
        f.write(f"# Files: {len(all_files)}\n\n")

        for file_path in sorted(all_files):
            rel_path = file_path.relative_to(base_path)
            f.write(f"\n{'='*80}\n")
            f.write(f"File: {rel_path}\n")
            f.write(f"{'='*80}\n")

            try:
                content = file_path.read_text(encoding="utf-8")
                f.write(content)
                f.write("\n")
            except UnicodeDecodeError:
                try:
                    content = file_path.read_text(encoding="cp932")
                    f.write(content)
                    f.write("\n")
                except Exception as e:
                    f.write(f"[Error reading file: {e}]\n")

    size_kb = output_file.stat().st_size / 1024
    print(f"Output: {output_file.name} ({size_kb:.1f} KB)")
    print("Done!")

if __name__ == "__main__":
    main()
