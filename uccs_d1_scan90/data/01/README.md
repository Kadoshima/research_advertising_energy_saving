# uccs_d1_scan90/data/01

Step D1 実機ログ（Fixed100 / Fixed500 / Policy(100↔500)）。

## 構成

* `RX/`: RX側SD `/logs/rx_trial_*.csv` をコピー
* `TX/`: TXSD側SD `/logs/trial_*.csv` をコピー（INA219ログ）

## このrunで採用したログ（集計対象）

本runは SDに古いログが残っていたため、集計では **`ms_total >= 50000`（約50秒以上）**のtrialのみを採用。

* RX（9本 = 3条件×3回）
  * `RX/rx_trial_005.csv` … `RX/rx_trial_013.csv`
* TXSD（9本 = 3条件×3回）
  * fixed100: `TX/trial_005_c1_fixed100.csv`, `TX/trial_006_c1_fixed100.csv`, `TX/trial_007_c1_fixed100.csv`
  * fixed500: `TX/trial_001_c2_fixed500.csv`, `TX/trial_002_c2_fixed500.csv`, `TX/trial_003_c2_fixed500.csv`
  * policy: `TX/trial_001_c3_policy.csv`, `TX/trial_002_c3_policy.csv`, `TX/trial_003_c3_policy.csv`

## 参考（速報）

* 集計結果: `uccs_d1_scan90/metrics/01/summary.md`

## 再集計

```bash
python3 uccs_d1_scan90/analysis/summarize_d1_run.py --run 01
```

