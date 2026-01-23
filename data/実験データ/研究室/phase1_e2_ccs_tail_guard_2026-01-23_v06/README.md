# Phase1 E2 CCS+TailGuard データセット（2026-01-23 v06）

## 目的/範囲
- E2（高干渉）環境で CCS + Tail Guard（WDT/NO_TICK 対策込み）の実測ログを取得する。
- 追加1本取得のための補完データ。

## 入力データ（出所/版/行数/SHA256）
- 出所: SDカード（TXSD/RX の /logs 配下）
- 版: phase1_e2_ccs_tail_guard_2026-01-23_v06

### TXSD（電力ログ）
| ファイル | 行数(データ行) | SHA256 | 備考 |
|---|---:|---|---|
| TXSD/pwr_00007166_5bc8d461_sweep.csv | 976 | 2d4950ffdd5b045ccde8f01db5dbacf047d12f16ed37ac6664ec3002c26b4c1c | ABORT短時間 |
| TXSD/pwr_00562703_a45ded90_sweep.csv | 54578 | 558cab9b1b9ec4b6cdf73fc6da992af86566f444f2bd195e6b02693f591906c5 | 有効 |
| TXSD/pwr_01110739_2a681e37_sweep.csv | 54578 | 07fa898ed40759160be3d343154c72bd9636a33cc5b331bb25230fd12a0d3e84 | 有効 |
| TXSD/pwr_01658785_cb8c7b1f_sweep.csv | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | ABORT空ファイル |

### RX（受信ログ）
| ファイル | 行数(データ行) | SHA256 | 備考 |
|---|---:|---|---|
| RX/rx_00007794_4a5f30ac.csv | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 | ABORT空ファイル |
| RX/rx_00014111_0c8a1dee.csv | 2680 | 5ac40f10979ee808723fbb0d40343eefd88ddfad1735b540ebaff099447b077f | 有効 |
| RX/rx_01110175_195ee40f.csv | 2635 | 08850a2863ca571665e3c14813594aea32b1d0f92bdd4e71cf6b20c7245d953e | 有効 |

## 出力物（生成日/生成スクリプト）
- `results/phase1_e2_ccs_tail_guard_2026-01-23_v06.md`
  - 生成日: 2026-01-23
  - 生成スクリプト: `python scripts/analyze_ccs_experiment.py`
  - 注記: 有効2試行のみで集計（ABORTは除外）

## 再現手順（コマンド）
```bash
python scripts/analyze_ccs_experiment.py \
  --data-dir results/phase1_e2_ccs_tail_guard_2026-01-23_v06_input \
  --session-manifest data/esp32_sessions/session_manifest.json \
  --baseline-p-off 22.1 \
  --out results/phase1_e2_ccs_tail_guard_2026-01-23_v06.md
```

## 状態
- draft

## 関連リンク
- `data/実験データ/研究室/phase1_e2_ccs_tail_guard_2026-01-23_v06/manifest.csv`
- `logs/serial_capture/serial_COM8_20260123_110413_phase1_e2_ccs_tail_guard_v06.log`
- `logs/serial_capture/serial_COM9_20260123_110413_phase1_e2_ccs_tail_guard_v06.log`
- `logs/worklog_2026-01-23_ccs.txt`

## 更新履歴
- 2026-01-23: RX/TXSDログ回収、manifest更新、解析レポート生成
