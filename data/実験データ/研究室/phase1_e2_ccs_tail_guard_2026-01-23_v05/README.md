# Phase1 E2 CCS+TailGuard データセット（2026-01-23 v05）

## 目的/範囲
- E2（高干渉）環境で CCS + Tail Guard（WDT/NO_TICK 対策込み）の実測ログを取得する。
- TX外部電源運用、RX/TXSD USBログ取得。
- 本データは Phase1 の「tailガード効果」検証用。

## 入力データ（出所/版/行数/SHA256）
- 出所: SDカード（TXSD/RX の /logs 配下）
- 版: phase1_e2_ccs_tail_guard_2026-01-23_v05

### TXSD（電力ログ）
| ファイル | 行数(データ行) | SHA256 | 備考 |
|---|---:|---|---|
| TXSD/pwr_00558198_d9087cde_sweep.csv | 54539 | 59a6a1c73510d982f9a1e6a8c4c29c8ba2b53ca98a975c63ecbf555dab9b71aa | 有効 |
| TXSD/pwr_01106208_2d7f9d22_sweep.csv | 54514 | 8a9a6b097098a70a670fd3ef0d696de9d801354741695561b9d4ba39614e0bff | 有効 |
| TXSD/pwr_01654212_47d22a11_sweep.csv | 54501 | 5575e1b1d4463ad4d7acc78b8d131a0e8ccd9b5a92bbd71261029563ae6f57a0 | 有効 |
| TXSD/pwr_02202239_af48d534_sweep.csv | 54514 | 43eb1524b4ea91bdde6dd729787c337a7ede45fe5bfd1fbd7b0b9e687bad4e59 | 有効 |
| TXSD/pwr_02750259_ff5bac6a_sweep.csv | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | ABORT（空ファイル） |

### RX（受信ログ）
| ファイル | 行数(データ行) | SHA256 | 備考 |
|---|---:|---|---|
| RX/rx_03297389_2bacad48.csv | 2668 | c58e06d6040a5e0c8d1ceb90f58425589af3e45634d2b91ab5bff97a9970e94b | 有効 |
| RX/rx_04393423_097252ba.csv | 2832 | ae71ce6f78e090a4413c0b5c81793e0f59598e0e6df59d69acb374188ced3bc8 | 有効 |
| RX/rx_00010549_47f070c3.csv | 2664 | 58c615577e280848a81d80f7ff7f0ad7d1e219fe5cd916a0858d2c2c38836666 | 有効 |
| RX/rx_01106578_506cb3c1.csv | 2636 | d6c31bddaea51134205337555715d51910c3b6b6a8712a7535dbf14b73eb4924 | 有効 |
| RX/rx_02202605_cb97cf0a.csv | 2630 | de43cd241bfd8c774b297bdfd080a28c47eb659e8cfd6188e505444c9366fdd2 | ABORT対象（TXSD空ファイルと対応） |

## 出力物（生成日/生成スクリプト）
- `results/phase1_e2_ccs_tail_guard_2026-01-23_v05.md`
  - 生成日: 2026-01-23
  - 生成スクリプト: `python scripts/analyze_ccs_experiment.py`
  - 注記: 有効4試行のみで集計（ABORTは除外）

## 再現手順（コマンド）
1) 解析入力を作成（本ディレクトリからコピー/ペアリング）
   - 例: `results/phase1_e2_ccs_tail_guard_2026-01-23_v05_input/E2/CCS/` に
     `pwr_*.csv` と `rx_*.csv` を同一 trial_id で配置
2) 解析実行
```bash
python scripts/analyze_ccs_experiment.py \
  --data-dir results/phase1_e2_ccs_tail_guard_2026-01-23_v05_input \
  --session-manifest data/esp32_sessions/session_manifest.json \
  --baseline-p-off 22.1 \
  --out results/phase1_e2_ccs_tail_guard_2026-01-23_v05.md
```

## 状態
- draft

## 関連リンク
- `data/実験データ/研究室/phase1_e2_ccs_tail_guard_2026-01-23_v05/manifest.csv`
- `logs/serial_capture/serial_COM8_20260123_082614_phase1_e2_ccs_tail_guard_v05.log`
- `logs/serial_capture/serial_COM9_20260123_082614_phase1_e2_ccs_tail_guard_v05.log`
- `logs/worklog_2026-01-23_ccs.txt`

## 更新履歴
- 2026-01-23: RX/TXSDログ回収、manifest更新、解析レポート生成
