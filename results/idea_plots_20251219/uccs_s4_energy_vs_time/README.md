# uccs_s4_energy_vs_time

UCCS 系（S4, scan90）の複数条件（Fixed100/Fixed500/Policy/U-only/U-shuffle）について、TXSD ログから累積エネルギーと時間の関係を折れ線で可視化。D4B と D4 の run01 を混在しているため、比較は参考値。

## 生成物
- `plot.svg`

## 生成スクリプト
- `plot.py`
- 実行: `python results/idea_plots_20251219/uccs_s4_energy_vs_time/plot.py`

## 入力データ
- `uccs_d4b_scan90/metrics/01/per_trial.csv`
- `uccs_d4_scan90/metrics/01/per_trial.csv`
- `uccs_d4b_scan90/data/01/TX/*.csv`
- `uccs_d4_scan90/data/01/TX/*.csv`

注: 条件とログの対応は `per_trial.csv` の `txsd_path` を基準にしている（ファイル名に `unk` を含むログあり）。

## SHA256
- `98e60a62e3d4be48c051d05843d33608258d9d91a49bd639d7fdbc2df8cdc598`  `uccs_d4b_scan90/metrics/01/per_trial.csv`
- `f0b39210e284ccaf93143e8e06538369ecf57fd0e9e80a884e114bf3ec6b4e1a`  `uccs_d4_scan90/metrics/01/per_trial.csv`
- `6eeff81a3b7b87ae84bbb53c16c6710bead036d14363afd4f5bec7842f7f5d2d`  `uccs_d4b_scan90/data/01/TX/trial_003_c2_s4_fixed500.csv`
- `498b626fca142a63d4422ffe360eafbf64cf89316e2af3718af3c8a8160426f3`  `uccs_d4b_scan90/data/01/TX/trial_001_c3_s4_policy.csv`
- `9c5ac9eede08c61589cbc5a7520d58de51a88772678674063adc4ddf99d76911`  `uccs_d4b_scan90/data/01/TX/trial_001_c5_unk.csv`
- `d673145dce93f02ed2e24155c10b87f27375f3adba0d17ed5f5f986d7db2c5bd`  `uccs_d4b_scan90/data/01/TX/trial_001_c4_s4_ablation_ccs_off.csv`
- `63a30e5cfa7ce4128804889d3e857f10b4086c7388b4a9e88c33b0d0e23f9254`  `uccs_d4b_scan90/data/01/TX/trial_004_c2_s4_fixed500.csv`
- `850f6fecd669361ca02f0cfde6716bc84a8fee9a2b905a94f95c3f901a590a23`  `uccs_d4b_scan90/data/01/TX/trial_002_c3_s4_policy.csv`
- `2416e6c284ba16031b8b2df5b4e5b9a2b89cf484be9549f0dfd5bb24ba23b9d5`  `uccs_d4b_scan90/data/01/TX/trial_002_c5_unk.csv`
- `307c1490d61ffb3dc8f9290f0aaf51d94a695d433a0c8e6de8def316a9316043`  `uccs_d4b_scan90/data/01/TX/trial_002_c4_s4_ablation_ccs_off.csv`
- `9cb2be0dcc0092723d97cf3a750ac37439486c9a8454475b80cf2a031929aeb6`  `uccs_d4b_scan90/data/01/TX/trial_005_c2_s4_fixed500.csv`
- `baaa8885e4aae7d51638b7835a261c9b5f6f16d3ad26731e86155344d07daaf0`  `uccs_d4b_scan90/data/01/TX/trial_003_c3_s4_policy.csv`
- `4fb6cdaea39e8f842289a706836f3dd6864670811e385e18f3d574316c4e53db`  `uccs_d4b_scan90/data/01/TX/trial_003_c5_unk.csv`
- `30864274c2ba159ecfd63ab81ae93db3309bd29d12d3ce4cc29f14bb0d424202`  `uccs_d4b_scan90/data/01/TX/trial_003_c4_s4_ablation_ccs_off.csv`
- `7d3c30f27c1c6d5ed4931788efe349ea4aa00d2f6f89caf347c5b9a53e3ef490`  `uccs_d4_scan90/data/01/TX/trial_001_c5_unk.csv`
- `86bff2ce8302036e49df73f501099be748e3e0b9373c6c67b8e81c48496a46a3`  `uccs_d4_scan90/data/01/TX/trial_002_c5_unk.csv`
- `15b5b4f9787c9fc4a1799e05295759574a4dc3c9375bb8b222efccad68c20da6`  `uccs_d4_scan90/data/01/TX/trial_003_c5_unk.csv`

## 生成日
- 2025-12-19
