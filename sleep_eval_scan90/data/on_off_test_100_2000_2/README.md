# on_off_test_100_2000_2

sleep_eval_scan90 の4条件（100/2000 × sleep OFF/ON）取得のテスト保存先。

## 構造
- `TX/` : TXSD（INA219）ログ（`trial_*.csv`）
  - ファイル名例: `trial_001_c2_i100_on.csv`
  - `# meta` に `cond_id/adv_interval_ms/sleep` を埋め込み
- `RX/` : RXログ（`rx_trial_*.csv`）
  - `# condition_label=I100_ON` のように条件ラベルを追記

## 集計
- 解析: `sleep_eval_scan90/analysis/summarize_txsd_power.py --run on_off_test_100_2000_2`
- 出力:
  - `sleep_eval_scan90/metrics/on_off_test_100_2000_2/txsd_power_summary.csv`
  - `sleep_eval_scan90/metrics/on_off_test_100_2000_2/txsd_power_diff.md`
  - `sleep_eval_scan90/plots/on_off_test_100_2000_2/txsd_power_summary.png`

## 補正（cond_id=0 / ラベルずれ）
- 本runでは preamble（TICK）が「先頭1パルス欠落」した可能性があり、TXSDの `cond_id/interval/sleep` がずれることがある。
  - RX側の `# condition_label=...` とシリアル時刻（start/end）を根拠に、`condition_overrides.csv` で補正する。
- `sleep_eval_scan90/analysis/summarize_txsd_power.py` は `data/<run>/condition_overrides.csv` があれば自動で反映する。

## 1回目データ混在の整理
- `TX/` に 1回目と2回目の `trial_*.csv` が混在していたため、2回目（ユーザ提示ログ: 17:49-17:58 JST）のみ `TX/` に残した。
- 1回目相当は `TX/_excluded_first_run/` に退避（削除はしていない）。

## 注意
- `cond_id=0` / `sleep=unk` の試行は preamble（TICK）取得に失敗した可能性がある。
  - 配線: TX GPIO27 → TXSD GPIO33 を再確認
  - TX/TXSD の preamble待ち時間（SYNC→TICK）設定も確認
