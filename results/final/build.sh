#!/usr/bin/env bash
set -euo pipefail

# results/final/build.sh
# 目的: 実験全体の「提出/貼り付け用の最終成果物」を results/final/ に固定する。
#
# 依存:
# - python3（標準ライブラリのみで動くスクリプトのみを呼ぶ想定）
#
# 入力runの差し替え:
# - 環境変数で per_trial / summary_by_condition のパスを上書きできる。

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

OUT_FIG="results/final/fig"
OUT_TAB="results/final/tab"
OUT_META="results/final/meta"
OUT_SCRIPTS="results/final/scripts"

mkdir -p "${OUT_FIG}" "${OUT_TAB}" "${OUT_META}" "${OUT_SCRIPTS}"

# ---- Inputs (defaults) ----
SCAN90_PER_TRIAL="${SCAN90_PER_TRIAL:-uccs_d4b_scan90/metrics/01/per_trial.csv}"
SCAN70_PER_TRIAL="${SCAN70_PER_TRIAL:-uccs_d4b_scan70/metrics/01_fixed/per_trial.csv}"

# summary_by_condition inputs used by some plots/tables
D3_SUMMARY="${D3_SUMMARY:-uccs_d3_scan70/metrics/01/summary_by_condition.csv}"
D4_SUMMARY="${D4_SUMMARY:-uccs_d4_scan90/metrics/01/summary_by_condition.csv}"
D4B90_SUMMARY="${D4B90_SUMMARY:-uccs_d4b_scan90/metrics/01/summary_by_condition.csv}"
D4B70_SUMMARY="${D4B70_SUMMARY:-uccs_d4b_scan70/metrics/01_fixed/summary_by_condition.csv}"

echo "[build] fig_main_scan70_scan90.svg"
python3 uccs_d4b_scan90/analysis/plot_mainfig_scan70_scan90.py \
  --scan90 "${SCAN90_PER_TRIAL}" \
  --scan70 "${SCAN70_PER_TRIAL}" \
  --out "${OUT_FIG}/fig_main_scan70_scan90.svg"

echo "[build] fig_role_separation_d3_d4_d4b.svg"
python3 uccs_d4b_scan90/analysis/plot_role_separation_overview.py \
  --d3-csv "${D3_SUMMARY}" \
  --d4-csv "${D4_SUMMARY}" \
  --d4b-csv "${D4B90_SUMMARY}" \
  --out "${OUT_FIG}/fig_role_separation_d3_d4_d4b.svg"

echo "[build] fig_alpha_vs_pout_overview.svg"
python3 uccs_d4b_scan90/analysis/plot_alpha_vs_pout.py \
  --d3 "${D3_SUMMARY}" \
  --d4 "${D4_SUMMARY}" \
  --d4b "${D4B90_SUMMARY}" \
  --out "${OUT_FIG}/fig_alpha_vs_pout_overview.svg"

echo "[build] copy supplemental outage story (already generated)"
if [[ -f "uccs_d4b_scan90/plots/outage_story_01/fig_outage_timeline.svg" ]]; then
  cp -f "uccs_d4b_scan90/plots/outage_story_01/fig_outage_timeline.svg" "${OUT_FIG}/fig_outage_story_01.svg"
fi

echo "[build] tab_summary_by_condition.csv"
python3 results/final/scripts/build_tables.py \
  --d3 "${D3_SUMMARY}" \
  --d4 "${D4_SUMMARY}" \
  --d4b90 "${D4B90_SUMMARY}" \
  --d4b70 "${D4B70_SUMMARY}" \
  --out "${OUT_TAB}/tab_summary_by_condition.csv"

echo "[build] done"
echo " - ${OUT_FIG}"
echo " - ${OUT_TAB}"

