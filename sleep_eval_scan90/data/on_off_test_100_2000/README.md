# on_off_test_100_2000

sleep_eval_scan90 の4条件（100/2000 × sleep OFF/ON）取得のテスト保存先。

## 構造
- `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
  - ファイル名例: `trial_001_c2_i100_on.csv`
  - `# meta` に `cond_id/adv_interval_ms/sleep` を埋め込み
- `RX/` : RXログ（`rx_trial_*.csv`）
  - `# condition_label=I100_ON` のように条件ラベルを追記

## 集計
- 解析: `sleep_eval_scan90/analysis/summarize_txsd_power.py --run on_off_test_100_2000`
- 出力:
  - `sleep_eval_scan90/metrics/on_off_test_100_2000/txsd_power_summary.csv`
  - `sleep_eval_scan90/metrics/on_off_test_100_2000/txsd_power_diff.md`
  - `sleep_eval_scan90/plots/on_off_test_100_2000/txsd_power_summary.png`

## 注意
- `cond_id=0` / `sleep=unk` の試行は preamble（TICK）取得に失敗した可能性がある。
  - 配線: TX GPIO27 → TXSD GPIO33 を再確認
  - TX/TXSD の preamble待ち時間（SYNC→TICK）設定も確認

