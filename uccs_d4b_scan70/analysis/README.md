# uccs_d4b_scan70/analysis

## 方針

解析ロジックは `uccs_d4b_scan90/analysis/` を流用する（scan70はRXのscan dutyが違うだけで、payload/tag仕様は同一）。

## 注意（TXSDのcond_idが10..13になる症状）

TXSDのpreamble window中にTX側の「通常TICK」が混入すると、`cond_id`（本来1..4）が `10..13` に潰れて条件分解できず、解析が失敗する。

- 症状: TXSDログが `cond_id=10..13`、`adv_count` が全条件で 178x 付近に偏る（fixed500/policy/u-onlyのクラスタが消える）
- 対策: TX側は **preamble完了まで advertising と TICK（adv_count用）を開始しない**。TXSD側はpreamble windowを短めにする。

## 最小コマンド（run_id=01の例）

- 集計（pout/TL/power/adv_count など）:

`python3 uccs_d4b_scan90/analysis/summarize_d4b_run_v2.py --rx-dir uccs_d4b_scan70/data/01/RX --txsd-dir uccs_d4b_scan70/data/01/TX --out-dir uccs_d4b_scan70/metrics/01`

- 図（power vs pout）:

`python3 uccs_d4b_scan90/analysis/plot_power_vs_pout.py --summary-csv uccs_d4b_scan70/metrics/01/summary_by_condition.csv --out-svg uccs_d4b_scan70/plots/d4b_scan70_01_power_vs_pout.svg`

## 出力先

- 集計: `uccs_d4b_scan70/metrics/<run_id>/`
- 図: `uccs_d4b_scan70/plots/`
