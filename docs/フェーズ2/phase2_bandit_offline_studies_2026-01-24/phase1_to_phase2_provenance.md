# Phase1→Phase2 データ系譜（Evidence Matrix）

- 作成日: 2026-01-28
- 状態: draft
- 目的: Phase2 の報酬/制約が Phase1 実測に基づくことを、**データの系譜**として固定する。
- 前提: 追加の実機実験なし。既存ログと既存シミュレーション結果のみを参照する。

---

## 1) Evidence Matrix（Phase2モデルに直接使用）

| Phase2パラメータ | 定義（式/単位） | 元データ（Phase1由来） | 実測根拠（ログ列） | 集約方法 | 再現性（行数/SHA256） |
| --- | --- | --- | --- | --- | --- |
| 報酬 cost（per_60s） | ΔE_total = E_on − E_off [mJ/60s] | `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv` | `metric=e_total_mj`, `mode=OFF/100/500/1000/2000`, `mean/std/n` | ON/OFF の mean を差分、std は独立仮定で合成 | rows=17, sha256=6dd0e80acaba7b452b02f3e096a613cbf8167deab36396f31d6d777cc835126d |
| 報酬 cost（per_adv） | μC = (E_on − E_off)/N_adv [uJ/adv] | `results/deltae_v3rig_sweep_2026-01-21_v02_stats_ci.csv`, `results/deltae_v3rig_sweep_2026-01-21_v02_trials.csv` | `metric=e_total_mj`, `mode` + `mode_ms`, `adv_count` | trials の `adv_count` 平均で正規化（E_on std のみ使用） | stats: rows=17, sha256=6dd0e80acaba7b452b02f3e096a613cbf8167deab36396f31d6d777cc835126d / trials: rows=50, sha256=89521ce5289a0050fb583004423132aab3efaa75a8ddcb87a97c987ef8fc65b9 |
| 制約 Pout（E1_scan90_stress_v5） | Pout(τ)=Pr[TL>τ]（τ=1,2,3） | `results/stress_fixed/scan90/stress_causal_real_summary_1211_stress_full_scan90_v5.csv` | `interval_ms`, `pout_1s/2s/3s`, `tl_time_offset_ms` | interval ごとに `pout_*` を平均/分散集約 | rows=8, sha256=009cbbb719ab9199b7f56c86f378c8d42022fe7171d498be23001f85e4e151e6 |
| 制約 Pout（scan90/scan70 per-trial） | Pout(τ)=Pr[TL>τ]（τ=1,2,3） | `uccs_d4b_scan90/metrics/01/per_trial.csv`, `uccs_d4b_scan70/metrics/01_fixed/per_trial.csv` | `mode`, `pout_1s/2s/3s`, `tl_time_offset_ms` | FIXED_* を抽出し interval ごとに平均/分散集約 | scan90: rows=12, sha256=98e60a62e3d4be48c051d05843d33608258d9d91a49bd639d7fdbc2df8cdc598 / scan70: rows=12, sha256=9809fbe0d36130d34a80bc50682ec48fa07396f106402ed0cfc358e64e204832 |
| 制約 Pout（E2_fixed_v01, RXログ） | Pout(τ)=Pr[TL>τ]（τ=1,2,3） | `data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/` | `RX/*.csv` の `ms`, `mfd`（seq） | seq×interval の傾きから interval 推定 → 60s周期イベントで TL を生成 → Pout 集計 | manifest rows=34, sha256=fd5ca19a268c93aa52f6218d520b84680638e8787823d7d5e9a4ccc078230f88 |

---

## 2) 補助エビデンス（本文での根拠に使用）

| 根拠 | 目的 | 元データ | 参照指標 | 再現性 |
| --- | --- | --- | --- | --- |
| 固定 interval の電力テーブル | 「長間隔ほど平均電力が下がる」の根拠 | `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-14_interval_sweep_sleep_on_n9_10.csv` | `avg_power_mW` | rows=4, sha256=c3d0f9ad8150fa8054de3f26e7f0ef8e5f3967392e35c36fdf5bdaf39c2df2fd |
| UCCS D2b（n=6）まとめ | 動的制御が意味を持つ実測根拠 | `uccs_d2_scan90/metrics/B_n6/summary.md` | power/QoS 指標の比較 | sha256=eafbeb6e14db6b5f1cb0697c28f514d53fa6bac5544a5c368454ee839bde344a |
| UCCS D4b まとめ | 役割分離（U/CCS）の実測根拠 | `uccs_d4b_scan90/metrics/01/summary.md` | power/QoS 指標の比較 | sha256=8bdfd79f4bc8731fd63645a0b4e5ab093082b9ea54a48d43f7f01a9a0042cba0 |
| D4b 効果量（CI） | 省電力 vs QoS の差分根拠 | `uccs_d4b_scan90/metrics/01/effects_ci.md` | 差分 CI | sha256=6c9cf0e4e743cf0f9a45b9c9d0d563cfba33ed98e6a9ac8b931a18d9f82a90ef |

---

## 3) 仕様・計算の参照点（実装）

- 報酬モデル: `scripts/phase2_offline_eval/models/reward_model.py`
- 制約モデル: `scripts/phase2_offline_eval/models/constraint_model.py`
  - 1 pull = 60s 相当（DEFAULT_EVENT_PERIOD_MS=60_000）
- 実験ランナー: `scripts/phase2_offline_eval/run_offline_studies.py`

---

## 4) SHA256 算出（再現性）

```powershell
Get-FileHash -Algorithm SHA256 <path>
```

---

## 5) 注意（主張の通し方）

- 数値を本文で引用する際は、**必ず上表のパスと SHA256** を併記する。
- 「妥当性の担保」ではなく、「Phase1 実測に基づくデータ駆動シミュレーションとして比較に妥当」と記述する。

