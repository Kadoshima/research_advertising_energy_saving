# ΔE再検証 2026-01-14

- 更新日: 2026-01-14
- 目的: Phase0-0のΔE符号問題を解消し、基線の信頼性を確保する
- 対象: v3 rig基準のON/OFF再測定と整合チェック

## 作業方針

- v3 rig（Mode A/B/C2）を基準に再検証する
- 旧v2 rig由来の値は参照のみとし、正式な比較に使わない
- 記録はこのディレクトリ配下に集約する

## 成果物（予定）

- `Phase0-0_deltaE_plan_2026-01-14.md`
- `Phase0-0_deltaE_results_2026-01-14.md`
- `Phase0-0_deltaE_checksums_2026-01-14.md`

## 関連ドキュメント

- `Phase0-0_deltaE_plan_2026-01-14.md`: 計画と配置決定
- 解析: `scripts/compute_delta_energy_v3rig.py`
