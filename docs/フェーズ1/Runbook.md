# フェーズ1 実験運用 Runbook（再現性重視）

## 0. ESP32系スケッチの命名ルール
- 役割別に接頭辞を固定する：受信ロガは `RX_*`, DUT/送信側は `TX_*`, 送信側電力ロガ（PowerLogger/SD書き込み側）は `TXSD_*`。
- 新しいスケッチや派生版を追加する場合は必ずこの接頭辞ルールを守り、既存資料（README, 実験ログ, Runbook）の参照名も同時に更新する。

## 1. 実験前チェック
- NTP同期（ゲートウェイ）／バッテリ残量>80%／電力計校正ログ記録
- 端末・OS・ビルド・スキャン設定（LOW_LATENCY）固定、Doze無効化
- 距離・姿勢を写真で記録（再現用）。E1/E2の時間帯メタを記録

## 2. 条件割付（順序効果の抑制）
- 各セッションの条件順序は Latin 方格で割付
- 固定4条件＋不確実度1条件（計5）を、環境E1/E2で各≥2反復

## 3. 同期・重複除去・評価窓
- 同期: セッション開始時に Sync ADV（seq=0）を1回送信し、LEDを500 ms点灯
- 重複除去: {seq, ts_tx} をキー、判定窓=3×adv_interval。最初の到達を採用
- 評価窓: A/B比較は開始・終了端の0.5 sを除外

## 4. 早期出口（任意、既定OFF）
- 有効化条件（例）: max_softmax≥0.90 かつ 温度スケーリング後≥0.85（Exit‑0）
- 合格基準: 平均t_infがOFF比≥20%短縮、F1低下≤1.0pt、Pout(1 s)/TL p95の劣化が受入基準内
- 速度不足時の縮退: B枝ch数↓ or dilation段削減（C3で顕著な場合）

## 5. P0 校正（推奨）
- 静的/動的3分×2。Arena実測、t_inf（1000反復）、推論のみ/アドバタイズのみ/同時のμC分離
- 取得: Arena_kB, t_inf_ms分布, ベース電流, 校正ログ

## 6. 記録・可視化・受入
- KPI: avg_current, event_charge_uC, PDR, TL（p50/p95）, Pout(τ)
- CI/手元チェック: markdownリンク検査、CSVスキーマ検査（ts単調・値域）
- 併記: 環境ごとに95% CIを併記。P1で{θ_low, θ_high}を確定し、旧{0.40,0.70}を置換

### 6.1 エネルギーKPIとΔE/adv
- 定義: ΔE/adv = (E_ON − P_off × T_ON) / N_adv [mJ/adv]。P_off は OFF 試行の平均電力（E_off/T_off、外れ値除外後）で、T_ON に時間スケールを合わせて引く。
- ねらい: 測定系の定常負荷（CPU/I2C/UART/LED等）を相殺し、無線1回あたりの純粋コストを比較可能にする。T_on≠T_off でも整合。
- レポート: 平均電流[mA]は補助指標として併記し、ΔE/advとセットで解釈する。

### 6.2 PDR の扱い（v1）
- 正式指標: `PDR_ms = rx_unique / (ms_rx / interval_ms)`（RXログを seq 去重、時間から期待 ADV 数を推定）。0〜1に収まる想定。
- 参考指標: `PDR_raw = rx_count_raw / adv_count`、`PDR_unique = rx_count_unique / adv_count`（TXSD adv_count依存）。`--clip-pdr` で max=1.0 を適用。
- 運用ルール:
  - レポート・図表は `PDR_ms`（clip済み）を用いる。
  - `PDR_ms > 1.1` または `<0` が出た trial は manifest で `cluster_id="<interval>ms_pdr_inconsistent"`、`exclude_reason=["pdr_inconsistent"]` として再測定対象。
  - RX単体 est_pdr は QC用。`0<=est_pdr<=1.1` を許容、それ以外は `rx_pdr_out_of_range` として除外候補。

### 6.2 スキャン環境の実務上の注意
- Android: 実験時は `SCAN_MODE_LOW_LATENCY` を原則とし、Doze/App Standby やベンダ独自の省電力機能は無効化する。
- iOS: バックグラウンドでは Duplicate Filtering が強制されるため、連続観測は不可前提とし、前景スキャンまたは接続モードでの観測に限定する。
- Opportunistic Scan: 他アプリのスキャンに合流するため実効スキャンウィンドウは非定常となる。必ず同一端末・同一条件内で A/B 比較を完結させる。

### 6.3 受入基準（品質）
- PowerLogger: parse_drop=0、rate_hz は設計値±10%以内、E_total_mJ 再現性は10分×2反復で±1%以内。
- 受信系: 重複除去窓=3×adv_interval とし、Pout(1 s)・TL p95 の差分が受入基準内かを確認する（95% CIを併記）。
- ログ健全性: ts単調、負値なし、欠損<1%、前処理・設定ハッシュを必須メタとして記録する。

### 6.4 端末別トレースとBlender検証（任意）
- 端末ごとに scan_interval/window の推定トレースを取得し、非理想スキャン条件（Opportunistic Scan含む）を明示する。
- trace-driven の Blender 検証で TL分布・Pout(τ)・Valley Area を事前確認し、ポリシが特定位相で「穴」に落ちないことを確認する。


### 6.x 計測ログ運用アップデート（2025-11-20）
- **LED/SYNC 統一**: `esp32_sweep/TX_BLE_Adv_Meter_ON_sweep.ino` の trial 中常時HIGHを廃止し、開始時100 msパルスのみ（ベースライン差を解消）。固定桁出力（mv=4桁, uA=6桁）で PowerLogger のパーサ互換。
- **PowerLogger推奨**: pass-through 版 `esp32_sweep/TXSD_PowerLogger_PASS_THRU_ON_v2.ino` を使用し、p_mW=mv*uA/1e6 をロガ側でも計算（欠落ゼロ前提）。
- **Manifest運用**: `experiments_manifest.yaml` を必ず渡し、include=false をスキップする。500ms 系はクラスタリング（`scripts/cluster_500ms.py`）で高電流クラスタを自動除外。
- **ヘッダ方言吸収**: ローダ（`scripts/check_units.py`, `scripts/compute_delta_energy.py`）は mv/mV, ua/µA, p_mW の alias を吸収。旧ログ混在でも再積分で整合を取る。
- **計測前提（固定値）**: ON は 1 trial あたり ADV 300 回送出を設計値とし、TXSD の `adv_count` を真値とする。OFF は 60 s 固定窓（必要なら 120 s まで延長可）で P_off を推定し、P_off_trial の median±3MAD で high_baseline_outlier を除外（manifest の include=false で管理）。
- **外れ値ルール（manifest）**: ON は interval ごとに `E_total_mJ`（または mean_p）を median±3MAD で判定し、超過を `high_current_outlier` として include=false。OFF は `P_off_trial` に median±3MAD を適用し、`high_baseline_outlier` として include=false。
- **ΔE/adv集計手順（時間スケール吸収版）**:
  1) `python3 scripts/check_units.py --data-dir <on_tx_dir> --manifest experiments_manifest.yaml`
  2) OFF 側: `python3 scripts/check_units_off.py --data-dir <off_dir> --manifest experiments_manifest.yaml --mad-multiplier 3`
  3) 必要に応じて 500ms 系クラスタ除外: `python3 scripts/cluster_500ms.py --set-dir <dir> --manifest experiments_manifest.yaml --out-manifest experiments_manifest.yaml`
  4) ΔE/adv 計算: `python3 scripts/compute_delta_energy_off.py --on-dir <on_tx_dir> --off-dir <off_dir> --manifest experiments_manifest.yaml --mad-multiplier 3 --expected-adv-per-trial 300`
- **PDR 集計**: TXSD と RX を join し、PDR = rx_count/adv_count を interval ごとに算出する（`scripts/compute_pdr_join.py` を使用）。RX 単体の est_pdr はデバッグ参照値。
