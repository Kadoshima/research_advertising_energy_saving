# mHealthDataset メタ情報

- 取得日: 2025-11-08
- 由来: University of Granada (UGR) mHealth dataset（同梱の `README.txt` を参照）
- 対応センサ: 胸・右前腕・左足首、50 Hz、12アクティビティ

## ファイル構成
- `mHealth_subject{1..10}.log`: 被験者別のログ
- `README.txt`: 原著の説明（出典・活動一覧・列定義）
- `SHA256.txt`: 本配下ファイル（`.log`）のチェックサム一覧（再現用）

## チェックサム（再計算手順）
```bash
cd data/MHEALTHDATASET
shasum -a 256 mHealth_*.log | sort > SHA256.txt
```

## 利用上の注意
- 本リポジトリでは、消費電力評価の再現性確保のため、データ出所・版・チェックサムを明記します。
- 解析時は被験者分割（subject-wise）を基本とし、前処理・分割情報のハッシュを併記してください（詳細は `docs/フェーズ0-1/要件定義.md`）。

