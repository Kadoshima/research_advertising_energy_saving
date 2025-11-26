#!/bin/bash
# Phase 0-1 根拠ファイル込みrepomix生成スクリプト
# 作成日: 2025-11-25
# 用途: Phase 0-1の全根拠ファイルを含めたrepomix出力

set -e

REPO_ROOT="/Users/kadoshima/Documents/research_advertising-energy_saving"
OUTPUT_DIR="${REPO_ROOT}/har/001/docs"
OUTPUT_FILE="${OUTPUT_DIR}/phase0-1_evidence_repomix.xml"

cd "$REPO_ROOT"

echo "=== Phase 0-1 Evidence Repomix Generator ==="
echo "Output: $OUTPUT_FILE"
echo ""

# repomix実行
repomix \
  --output "$OUTPUT_FILE" \
  --include \
    "har/001/src/preprocess_mhealth.py" \
    "har/001/src/train_phase0-1.py" \
    "har/001/src/calibration.py" \
    "har/001/src/compute_usc.py" \
    "har/001/src/analyze_subject_outliers.py" \
    "har/001/src/analyze_confusion_detail.py" \
    "har/001/configs/phase0-1.local.yaml" \
    "docs/フェーズ0-1/splits.yaml" \
    "har/001/runs/phase0-1/summary.json" \
    "har/001/runs/phase0-1/fold5/metrics.json" \
    "har/001/analysis/subject_statistics.json" \
    "har/001/analysis/subject_comparison.csv" \
    "har/001/analysis/confusion_detail_12class.json" \
    "har/001/analysis/confusion_4class.json" \
    "har/001/analysis/ble_interval_errors.json" \
    "har/001/analysis/ble_impact_summary.csv" \
    "har/001/docs/Phase0-1_作業ログ_2025-11-25.md" \
    "har/001/docs/実験完了報告書_phase0-1_2025-11-25.md" \
    "har/001/docs/外れ値分析_Sub02_Sub08.md" \
    "har/001/docs/Phase0-1再評価報告書_2025-11-25.md" \
    "CLAUDE.md" \
    "README.md"

echo ""
echo "=== Generation Complete ==="
echo "Output file: $OUTPUT_FILE"
echo ""
echo "Included files:"
echo "  - 6 Python scripts (src/)"
echo "  - 2 Config files (configs/, splits.yaml)"
echo "  - 2 Result JSONs (summary.json, fold5/metrics.json)"
echo "  - 6 Analysis files (analysis/)"
echo "  - 4 Documentation files (docs/)"
echo "  - 2 Repository docs (CLAUDE.md, README.md)"
echo ""
echo "Total: 22 files with full evidence chain"
