# HAR-BLE Safe Contextual Bandit 実験計画書

**文書ID**: RHT-EXP-PLAN-v1.2
**作成日**: 2025-11-27
**最終更新**: 2025-12-10
**ステータス**: ドラフト（Baseline再計測中、実地検証で発見した問題を反映）

**進捗メモ (2025-12-12)**  
- ストレス固定 S1/S4 × {100,500,1000,2000} を E1 で取得し manifest 整備済み（`data/1211_modeC2prime_stress_fixed/full`）。  
  集計: `results/stress_causal_real_summary_1211_stress_modes.csv`（pdr_raw/pdr_unique/TL/Pout/E_per_adv）。  
- PDRは TXSD adv_count でクランプ、QoSは `pdr_unique` を参照。2000ms で Pout/TL が顕著に悪化、S4 は PDR も低下。  
- 次ブロック: CCS/self-UCB 実機（S1/S4）に進む前に、図表化とシミュ比較を完了させる。
- 指標定義: `docs/metrics_definition.md` 追加（pdr_raw/unique, TL/Pout, 2000msでPout1s≥0.5, EFFECTIVE_LEN など）。  

---

## 設計レビュー指摘（2025-12-08 追記）

- 計測方式の一本化: 実験設計書のPPK-II記述をINA219+TXSD(I²C)前提に揃える。ΔE/advはper_adv、活動遷移用は別指標名（例: μC_transition）で式を明記。
- CCSパラメータ: World Modelデフォルト閾値(0.4/0.7)と今回実験値(0.80/0.90)を区別し、ログに `theta_low/high`, `model_id`, `calib_T` を必須出力。
- HARモデル前提: Phase1デフォルトはA0、A_tiny準備でき次第差し替えOKと明記。
- セッション長の整合: 10分 vs 15分の差異を解消（どちらかに統一。必要なら10分×2で15分扱い等ルール決め）。
- E1/E2の具体化: 低/高干渉を場所・Wi-Fi条件で仕様書に明記。
- スクリプト/ログ仕様: `sync_logs.py`のSYNC条件（短パルス無視など）を仕様書に記載。`compute_event_charge.py`のevent単位をper_advかper_transitionか明記。ログにモデル/閾値情報を必ず残す。
- フェイルセーフ: Phase1は観測のみ、Phase2で制約付きBandit実装と明記（Pout超過時の戻し方はPhase2で実装）。
- 実験A〜Eの章立てと整合: A/B=物理レンジ（Mode A/B）、C=HARラベル固定間隔基準線、D=不確実性閾値方策（Phase1ゴール）、E=self-UCB/Safe Bandit（Phase2）。どれを実機/シミュレーションでやるかを実験計画に明示。

---

### 追加実験プラン (2025-12-09)

- 理想ベースライン凍結: Mode_C_2_06（低遷移・良好チャネル）を基準データとして固定し、解析パイプライン健全性のリファレンスにする。
- 高遷移セッション作成: mHealth 10分ウィンドウをスライドし、遷移回数が多い区間（例: transitions≧30）を上位抽出。`labels_all_dyn.h` / `SESSIONS_DYN[]` を生成し dyn 用TXをビルド。
- 高遷移×E1計測: dyn セッションを E1 環境で 100/500/1000/2000ms 計測。理論シミュレーション（PDR=100→90%）と TL/Pout/acc_timeline を突き合わせ。
- 悪化チャネル E2 設計: 目標 PDR(100ms)=0.6〜0.7 を達成できる距離/障害物/Wi-Fi干渉/scan duty の条件を決め、調整ログを残す。
- E2 での再計測: Mode_C_2_06（低遷移）と dyn（高遷移）をE2で取得し、エネルギー・QoSの2×2比較を作成。必要ならE3（より悪化）も検討。
- 解析スクリプト更新: dyn マニフェストと `labels_all_dyn` 読み込みに対応し、PDR劣化時の理論曲線と実測を同じスクリプトで出力できるようにする。

---

### 因果CCSアップデート (2025-12-10)

- 生成: `scripts/generate_modec2_stress_causal.py` で S を「最後の遷移からの経過時間」に変更し U/CCS/T_adv/manifest を再生成。PDR=1 ストレス6セッション平均で CCS_causal: acc≈0.916, TL≈6.8s (`Mode_C_2_シミュレート_causal/sim_timeline_metrics_causal_agg.csv`)。
- 設計ゴール（メタ）:
  - [ ] CCS_causal は PDR≒1 前提で QoS(Pout/TL) は FIXED_2000 より良く、エネルギーは FIXED_500 より小さい領域を狙うと明文化する。

#### A. 因果CCSシミュレーションの読み解き＆設計判断
- [x] A-1: `Mode_C_2_シミュレート_causal/sim_timeline_metrics_causal_agg.csv` で確認。CCS_causal: acc=0.9160, TL_mean=6.81s, Pout(1s/2s/3s)=0.323/0.091/0.088。位置づけ: FIXED_1000(0.935,5.26s,Pout1s=0.064) と FIXED_2000(0.870,9.40s,Pout1s=0.492) の中間〜やや2000寄り。FIXED_500: acc=0.972, TL=2.92s, Pout1s=0.036。
- [x] A-2: `Mode_C_2_シミュレート_causal/manifest_stress_causal.json` より interval_frac 平均 {100ms:0.2086, 500ms:0.2033, 2000ms:0.5881}。E[T_adv]≈1298.7ms。Mode_C_2_03 E_per_adv_uJ を用いた加重 E/adv≈256,025 μJ → 相対 (per-adv): vs100ms=12.88x, vs500ms=2.65x, vs2000ms=0.65x。加重平均電力（E/adv÷T_adv）≈196.9 mW で FIXED_500比 ≈1.02x, FIXED_100比 ≈0.99x（パワーはほぼ横並びで、per-adv指標は区間長依存で大きくなる点に注意）。
- [x] A-3: しきい値/重みの決定（ストレスケースは凍結）。採用値:
  - CCS形: CCS=0.7*(1−U)+0.3*S（正史に合わせる）
  - S_causal: clip(time_since_last_transition/5.0, 0, 1)
  - U_causal: clip(1−S_causal+N(0,0.05^2), 0, 1)
  - T_adv写像: CCS<0.30→100ms, 0.30≤CCS<0.70→500ms, CCS≥0.70→2000ms
  - ヒステリシス/最小滞在: ストレスケースのオフライン評価・実機再生では無し（本番Phase1は θ_low=0.40/θ_high=0.70＋ヒステリシスを別途適用）
  - 見直しトリガ（参考メモ）: 実機で CCS が FIXED-2000 より QoS悪化、またはエネルギーが FIXED-500 と同等・優位性なし、または実データで Pout が FIXED-100 より悪化する場合に再検討。
- [x] A-4: PDR=0.95/0.9 の簡易シミュで順位確認（sim_timeline_metrics_causal_pdr_sweep.csv）。結果: 順位は概ね維持。例: PDR=0.95 → FIXED_500 acc≈0.968 TL≈0.33s Pout1s=0, CCS_causal acc≈0.915 TL≈0.69s Pout1s≈0.30; FIXED_2000 acc≈0.860 TL≈1.21s Pout1s≈0.55. PDR=0.9 でも同様の傾向で CCS は FIXED_1000〜2000 中間寄り。

#### B. Mode_C_2_stress_causal 実機最小セット
- [ ] B-1: TX 実装方式を決定（オンラインS計算 vs `T_adv`列再生）。工数次第でオフライン再生→オンライン化の二段階でも可。使用データ: `Mode_C_2_シミュレート/labels_stress.h` + `Mode_C_2_シミュレート_causal/ccs/stress_causal_S*.csv`。
- [ ] B-2: 実験プロトコル確定（E1想定）。セッション: S2（中遷移）/S5（高遷移）。条件: C1=FIXED_100, C2=FIXED_2000, C3=CCS_causal。繰返し: 各1〜3 trial。指標: PDR, Pout(1s)+TL_mean, ΔE/adv(μC) from TXSD summary。
- [ ] B-3: 実機 vs シミュの比較フォーマットを先に決め、集計スクリプト出力を合わせる（例: x軸モード、左軸Pout(1s)棒＋右軸相対エネ線; 青=シミュ、橙=実機）。

#### C. 実データ (mHealth/ccs_sequences) への因果CCS適用（余裕タスク）
- [ ] C-1: `data/ccs_sequences/subjectXX_ccs.csv` に S_causal/U/CCS/T_adv を付与し、ratio_100/500/2000 を確認。
- [ ] C-2: PDR=1 の簡易シミュで FIXED_100/500/2000 vs CCS_causal の Pout/TL/エネルギー位置を把握（低遷移での効果の有無を確認）。

#### D. 記述整理
- [ ] D-1: Oracle CCS vs Causal CCS の違い（S定義、U/CCS式、T_advしきい値、振る舞い: oracle=上界/因果=FIXED100-2000中間）を docs に明文化。
- [ ] D-2: Phase1レター用の図・表候補を箇条書き（Fig: Mode A/B/Cエネ、ストレス FIXED vs CCS_causal シミュ/実機、Tab: Pout/TL/エネ）。

---

## 0. 前提条件の確認

### 0.1 既存資産の棚卸し

- [x] **フェーズ0-0データの確認** (2025-12-07 更新)
  - [x] ΔE/adv実測値（100/500/1000/2000ms） → Mode A/B (1202配線変更後, 1203) 再計測済み。旧参考: `docs/フェーズ1/results/delta_energy_row1120_row1123_off.md` / `docs/フェーズ0-0/decision_log_2025-11-29.md`
  - [x] P_off_mean → OFF計測11本完了（配線修正後）。旧値 22.106 mW は参考のみ。
  - [x] PDR実測値（p_d ≈ 0.85）の根拠データ → OK (`docs/フェーズ1/results/pdr_row1120_txsd_rx.md`)

- [x] **HARモデル（A0）の確認** (2025-11-27 完了)
  - [x] TFLite int8モデル（90.6KB）がエクスポート済みか → OK (`har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite`)
  - [x] 校正パラメータ（T=0.7443, τ=0.66）が確定しているか → OK (`har/001/docs/A0_acc_v1_baseline_summary.md`)
  - [x] θ_low=0.80, θ_high=0.90 の閾値が設定済みか → **調整済み** (`logs/threshold_adjustment_2025-11-27.md`)
    - 旧デフォルト: θ_low=0.40, θ_high=0.70
    - mHealthのCCS分布が高め(0.84-0.93)のため閾値を上げて調整

- [x] **mHealthデータセットの確認** (2025-11-27 完了)
  - [x] 生データへのアクセスがあるか → OK (`data/MHEALTHDATASET/`)
  - [x] 被験者数・セッション数・活動ラベルの把握 → 10名、12活動、6,768窓
  - [x] データ前処理パイプラインが動作するか → OK (`har/001/data_processed/subject*.npz`)

**棚卸しログ**: `logs/inventory_0.1_2025-11-27.md`

### 0.2 ハードウェア準備状況

- [x] **ESP32ボード** (2025-11-27 確認)
  - [x] 型番: ESP32 Dev Module (3台: TX/TXSD/RX)
  - [x] 動作確認済み

- [x] **電力計測** (2025-11-29 配線修正済み)
  - [x] **INA219構成を継続**（PPK-IIは使用しない）
  - [x] INA219 Vcc配線修正済み（外部3.3V直結）
  - **注意**: Phase 0-0とは構成が異なる（配線修正後）

- [x] **Android端末** (2025-11-28 確認完了)
  - [x] 機種名: Galaxy S9 (SCV38)
  - [x] OSバージョン: **Android 10** (One UI 2.1)
  - [x] BLE受信アプリ: nRF Connect for Mobile

- [ ] **実験環境** (一部未確認)
  - [ ] E1（干渉弱）環境: 未確認
  - [x] E2（干渉強）環境: 確保済み（簡易に実施可能）
  - [ ] 距離1mの固定方法: 要確認

- [x] **配線修正** (2025-11-29 完了)
  - [x] INA219 Vcc配線を外部3.3V直結に修正
  - [x] UARTボーレート 230400→115200 に変更（ノイズ対策）
  - [x] 詳細: `docs/フェーズ0-0/decision_log_2025-11-29.md`
  - **注意**: 修正前のP_off/ΔE/advは参考値、再計測が必要

**ハードウェアログ**: `logs/inventory_0.2_2025-11-27.md`, `docs/フェーズ0-0/decision_log_2025-11-29.md`

---

## 1. 準備フェーズ（Week 1）

### 1.1 mHealth CCS時系列生成 ✅ (2025-11-27 完了)

**目的**: mHealthデータからU, S, CCS時系列を生成し、ESP32で再生可能な形式にする

#### 1.1.1 HAR推論パイプライン構築 ✅

- [x] **統合スクリプト作成**: `scripts/generate_ccs_sequences.py`
  - 既存の前処理済みデータ `har/001/data_processed/subject*.npz` を使用
  - TFLite int8モデルで推論 → U, S, CCS計算 → CSV出力
  - 全10被験者分のCCS時系列を生成

#### 1.1.2 CCS→T_adv変換 ✅

- [x] **ヒステリシス付き写像関数**: `scripts/generate_ccs_sequences.py` 内に実装
  - **閾値調整済み (2025-11-27)**: θ_high=0.90, θ_low=0.80, hysteresis=0.05, min_stay=2.0s
  - 理由: mHealthのCCS分布が高め(0.84-0.93)のため、閾値を上げて間隔多様性を確保
  - 変更ログ: `logs/threshold_adjustment_2025-11-27.md`
- [x] **CCS時系列出力**: `data/ccs_sequences/subject{01-10}_ccs.csv`

#### 1.1.3 代表セッションの選定 ✅

- [x] **セッション選定スクリプト**: `scripts/create_esp32_sessions.py`
  - mHealthデータ制約（各被験者約11分）により15分→**10分セッション**に変更
  - 遷移回数、間隔多様性、CCS範囲をスコアリングして選定

**成果物**:
- [x] `data/ccs_sequences/subject{01-10}_ccs.csv` - 被験者別CCS時系列
- [x] `data/esp32_sessions/session_{01-10}.csv` - ESP32再生用10分セッション
- [x] `data/esp32_sessions/session_selection_report.md` - 選定レポート
- [x] `data/esp32_sessions/session_manifest.json` - セッションメタデータ

**セッション概要** (10分 = 600秒, θ_high=0.90, θ_low=0.80):
| Session | Subject | CCS Mean | Transitions | 100ms% | 500ms% | 2000ms% |
|---------|---------|----------|-------------|--------|--------|---------|
| 01 | 06 | 0.90 | 13 | 26.2% | 2.3% | 71.5% |
| 02 | 08 | 0.86 | 32 | 27.3% | 4.7% | 68.0% |
| 10 | 10 | 0.85 | 66 | 36.7% | 13.2% | 50.2% |

---

### 1.2 ESP32ファームウェア開発 🔧 (実地検証で問題発見・修正中)

**目的**: CCS時系列に基づき、T_advを動的に変更するファームウェア

**既存資産** (Phase 0-0から継承、2025-11-29 ディレクトリ再編済み):
- `esp32_firmware/baseline_on/TX_BLE_Adv/` - TX送信+電流測定（マルチinterval自動実行対応）
- `esp32_firmware/baseline_on/TXSD_PowerLogger/` - 電力ロガー
- `esp32_firmware/baseline_on/RX_BLE_to_SD/` - BLE受信ロガー
- `esp32_firmware/baseline_off/` - OFF計測用（BLE無効ベースライン）
- `esp32_firmware/ccs_mode/` - CCS動的インターバル制御用
- `docs/フェーズ0-0/decision_log_2025-11-29.md` - 最新の設計決定ログ

#### 1.2.1 基本機能実装 ✅ (既存コードで対応)

- [x] **BLE Advertising制御** - `esp32_firmware/baseline_on/TX_BLE_Adv/TX_BLE_Adv.ino`
  - マルチinterval自動実行（100→500→1000→2000ms）
  - N_ADV_PER_TRIAL=300固定、interval別トライアル長
  - INA219による電流測定、UART出力実装済み
- [x] **ログ出力機能** - TX→TXSD→SD構成で実装済み
  - フォーマット: `mv,uA` (10ms周期)

#### 1.2.2 実験モード実装 ✅ (全モード完了)

- [x] **Baseline ON計測** - `esp32_firmware/baseline_on/` (マルチinterval自動実行)
- [x] **Baseline OFF計測** - `esp32_firmware/baseline_off/` (60秒固定窓)
- [x] **CCSモード** - `esp32_firmware/ccs_mode/TX_BLE_Adv_CCS_Mode.ino`
  - `RUN_MODE` で `MODE_FIXED_100` / `MODE_FIXED_2000` / `MODE_CCS` を選択
  - CCS時系列は `ccs_session_data.h` として定数配列に埋め込み
  - 1秒解像度でT_adv動的変更（100/500/2000ms）
  - BLE interval動的再設定: `adv->stop()` → `setMinInterval/setMaxInterval` → `adv->start()`

#### 1.2.3 同期機能実装 ✅ (既存コードで実装済み)

- [x] **SYNC_OUT_PIN (GPIO25)** - トライアル開始/終了マーカー
- [x] **TICK_OUT_PIN (GPIO27)** - 各広告イベントのパルス
- [x] **LED_PIN (GPIO2)** - 状態インジケータ

#### 1.2.4 ビルド手順（CCSモード）

```bash
# 1. セッションヘッダー生成
python3 scripts/convert_session_to_header.py --session 01

# 2. TX_BLE_Adv_CCS_Mode.ino で RUN_MODE を設定
#    MODE_FIXED_100, MODE_FIXED_2000, MODE_CCS から選択

# 3. Arduino IDEでビルド・書き込み
#    Board: ESP32 Dev Module
```

**成果物チェックリスト** (2025-11-29 ディレクトリ再編後):
- [x] `esp32_firmware/baseline_on/TX_BLE_Adv/TX_BLE_Adv.ino` - マルチinterval自動実行TX
- [x] `esp32_firmware/baseline_on/TXSD_PowerLogger/TXSD_PowerLogger.ino` - ON用電力ロガー
- [x] `esp32_firmware/baseline_on/RX_BLE_to_SD/RX_BLE_to_SD.ino` - BLE受信ロガー
  - **修正済み (2025-11-30)**: USE_SYNC_END=true に変更（トライアル数不一致問題を解消）
- [x] `esp32_firmware/baseline_off/TX_BLE_OFF/TX_BLE_OFF.ino` - OFF計測TX
- [x] `esp32_firmware/baseline_off/TXSD_PowerLogger/TXSD_PowerLogger.ino` - OFF用電力ロガー
- [x] `esp32_firmware/ccs_mode/TX_BLE_Adv_CCS_Mode.ino` - CCSモード対応TX
- [x] `esp32_firmware/ccs_mode/TXSD_PowerLogger_CCS_Mode.ino` - CCSモード対応TXSD
- [x] `esp32_firmware/ccs_mode/ccs_session_data.h` - セッションデータ（自動生成）
- [x] `scripts/convert_session_to_header.py` - CSV→ヘッダー変換スクリプト
- [x] `docs/フェーズ0-0/decision_log_2025-11-29.md`（最新の設計決定ログ）

#### 1.2.5 実地検証で発見した問題 (2025-11-30)

| 問題 | 状態 | 対応 |
|------|------|------|
| UARTデータ化け (230400bps) | ✅ 解決 | 115200bpsに変更 |
| SYNC信号パルス問題 | ✅ 解決 | TX側でSYNC=HIGH維持に変更 |
| RXトライアル数不一致 | ✅ 修正済み | USE_SYNC_END=true (要再書き込み) |
| TXSD SD open FAIL | ✅ 解決 | SDカード接触/ファイル数確認で解消 |
| TXSD SD init FAIL | ✅ 解決 | 電源再投入で解消 |

**詳細**: `docs/フェーズ0-0/decision_log_2025-11-29.md`

---

### 1.3 Android受信アプリ準備 ✅ (nRF Connect使用)

**目的**: BLE広告を受信し、タイムスタンプ付きでログを記録

**使用アプリ**: **nRF Connect for Mobile** (Nordic Semiconductor)
- Google Play: https://play.google.com/store/apps/details?id=no.nordicsemi.android.mcp

#### 1.3.1 nRF Connect設定

- [x] **スキャン設定**
  - Scanner → Settings → Scan mode: Low Latency
  - フィルタ: "TXM_ESP32" (デバイス名)

- [x] **ログ記録項目** (nRF Connectで自動取得)
  - タイムスタンプ
  - RSSI
  - Advertising Data (Manufacturer Specific Data含む)

- [x] **ログ出力**
  - Scanner → Export → CSV形式

#### 1.3.2 運用手順

1. nRF Connectを起動
2. Scanner画面でフィルタ設定（"TXM_ESP32"）
3. スキャン開始
4. 実験終了後、Export → CSVで保存

**成果物チェックリスト**:
- [x] 使用アプリ: nRF Connect for Mobile
- [ ] ログフォーマットのサンプル取得（実験時に確認）

---

### 1.4 電力計測セットアップ 🔧 (配線修正済み、再校正中)

**目的**: INA219でESP32の電力を正確に計測する（PPK-IIは使用しない）

**既存資産**: `docs/フェーズ0-0/decision_log_2025-11-29.md` に最新構成を記載

#### 1.4.1 配線 ✅ (2025-11-29 修正済み)

- [x] ESP32 3V3ピンへの外部電源供給（INA219経由）
- [x] INA219 VIN+/VIN-で電流測定
- [x] GND共通化（TX/TXSD/RX/外部電源）
- [x] **INA219 Vcc配線修正**: 外部3.3V直結（旧: Vin-分岐でブラウンアウト発生）

#### 1.4.2 計測設定 ✅ (既存コードで実装済み)

- [x] サンプリングレート: 100Hz (10ms周期)
- [x] UART出力: `mv,uA` 形式
- [x] TXSDでSDカードに記録

#### 1.4.3 動作確認 (再計測中 2025-11-30)

- [x] Phase 0-0で実施済み（**配線修正前のため参考値**）
  - 旧ΔE/adv: `docs/フェーズ1/results/delta_energy_row1120_row1123_off.md`
  - 旧P_off = 22.106 mW
- [ ] **配線修正後の再計測** (進行中)
  - [x] OFF計測完了 (11 trials) → P_off再算出待ち
  - [ ] ON計測 (100/500/1000/2000ms 自動実行中)
  - [ ] 解析スクリプト: `scripts/analyze_baseline_v2.py`
- [ ] Phase 1実験前の最終校正
  - 旧基準値 (100ms): ΔE/adv = 2256.82 µJ（参考）
  - 新基準値: 再計測後に確定

**成果物チェックリスト**:
- [x] 配線図: `docs/フェーズ0-0/decision_log_2025-11-29.md` セクション2
- [ ] 再計測レポート（Baseline ON/OFF）
- [ ] Phase 1校正確認レポート

---

## 2. 実験実施フェーズ（Week 2-3）

### 2.1 実験プロトコル

#### 2.1.1 セッション手順

**注意: 計測タイプによりセッション長が異なる**

| 計測タイプ | セッション長 | 説明 |
|------------|-------------|------|
| **Baseline ON計測** | interval依存 | N_ADV=300固定、100ms→30s, 500ms→150s, 1000ms→5min, 2000ms→10min |
| **Baseline OFF計測** | 60秒固定 | P_off算出用 |
| **CCSモード** | 10分固定 | mHealthセッション再生（mHealthデータ制約により15分→10分）|

```
[開始前]
1. ESP32にCCS時系列をビルド（CCSモードの場合）
2. ESP32のモード選択（FIXED-100 / FIXED-2000 / CCS）
3. Android受信アプリ起動、ログ記録開始
4. INA219計測準備（TX→TXSD構成）
5. ESP32電源ON

[セッション中]
6. 同期マーカー（SYNC_OUT HIGH→LOW）を記録
7. 10分間待機（介入なし）
8. 終了マーカーを記録

[終了後]
9. ESP32電源OFF
10. TXSD SDカードから電力ログ回収
11. Androidログ保存
12. RX SDカードからBLE受信ログ回収
13. ファイル名をセッションIDでリネーム
```

#### 2.1.2 命名規則

```
セッションID: {env}_{condition}_{rep}
例: E1_FIXED100_01, E2_CCS_05

ファイル名:
- 送信ログ: tx_{session_id}.csv
- 受信ログ: rx_{session_id}.csv
- 電力ログ: pwr_{session_id}.csv
```

### 2.2 実験スケジュール

#### Week 2: E1環境（30セッション）

| 日 | 条件 | セッション数 | 累計 |
|----|------|-------------|------|
| Day 1 | FIXED-100 | 10 | 10 |
| Day 2 | FIXED-2000 | 10 | 20 |
| Day 3 | CCS | 10 | 30 |

- [ ] Day 1 完了
- [ ] Day 2 完了
- [ ] Day 3 完了
- [ ] E1データバックアップ完了

#### Week 3前半: E2環境（30セッション）

| 日 | 条件 | セッション数 | 累計 |
|----|------|-------------|------|
| Day 4 | FIXED-100 | 10 | 40 |
| Day 5 | FIXED-2000 | 10 | 50 |
| Day 6 | CCS | 10 | 60 |

- [ ] Day 4 完了
- [ ] Day 5 完了
- [ ] Day 6 完了
- [ ] E2データバックアップ完了

### 2.3 品質管理チェックリスト

各セッション終了後に確認:

- [ ] 送信ログのadv_countが期待値±5%以内
- [ ] 受信ログのrx_countがadv_countの70%以上
- [ ] 電力ログに異常スパイク（>100mA）がないか
- [ ] 同期マーカーが送信・受信・電力ログで一致
- [ ] CCSモードの場合、T_adv遷移が発生しているか

**異常時の対応**:
- ログ欠損 → セッション再実施
- 電力異常 → 配線確認後、再実施
- 同期ずれ → 手動補正 or 再実施

---

## 3. データ処理フェーズ（Week 3後半）

### 3.1 データ統合

- [ ] **ログ同期**
  - 送信・受信・電力ログのタイムスタンプを統一
  - 同期マーカーを基準にオフセット補正
  - ファイル: `scripts/sync_logs.py`

- [ ] **マニフェスト作成**
  - 全60セッションのメタデータ一覧
  - 除外セッションがあればフラグ付与
  - ファイル: `data/experiments_manifest.yaml`

### 3.2 KPI算出

#### 3.2.1 エネルギー指標の分離

- [ ] **μC_adv (mJ/adv)** : ΔE/adv = (E_on − P_off×T) / N_adv（物理層の基準。FIXED/CCS共通）
- [ ] **μC_transition (mJ/transition)** : 活動遷移区間のΔEを遷移回数で割る（CCS/FIXEDで比較）
- [ ] スクリプト/ドキュメントで per_adv と per_transition を明記し、名前を揃える（旧「μC/event」は per_adv に一本化するか上記2分割で）

- [ ] **電荷計算**
  ```python
  def compute_event_charge(power_log, events, P_off=22.106):
      results = []
      for event in events:
          t_start, t_end = event['start'], event['end']
          segment = power_log[(power_log.t >= t_start) & (power_log.t < t_end)]
          E_on = integrate(segment.current_mA) * segment.duration_s  # mJ
          E_idle = P_off * segment.duration_s / 1000  # mJ
          mu_c = (E_on - E_idle) / event['adv_count']  # mJ/adv
          results.append(mu_c)
      return results
  ```
  - ファイル: `scripts/compute_event_charge.py`

#### 3.2.2 Pout(τ)算出

- [ ] **TL（検知遅延）計算**
  ```python
  def compute_tl(tx_log, rx_log, events):
      results = []
      for event in events:
          t_event = event['start']
          # イベント後の最初の受信を探す
          rx_after = rx_log[rx_log.t > t_event]
          if len(rx_after) > 0:
              t_first_rx = rx_after.iloc[0].t
              tl = t_first_rx - t_event
          else:
              tl = float('inf')  # 未受信
          results.append(tl)
      return results
  ```

- [ ] **Pout計算**
  ```python
  def compute_pout(tl_list, tau=2.0):
      violations = sum(1 for tl in tl_list if tl > tau)
      return violations / len(tl_list)
  ```
  - ファイル: `scripts/compute_pout.py`

#### 3.2.3 集計

- [ ] **条件別集計**
  ```
  | 条件 | 環境 | μC/event (mean±std) | Pout(2s) | N |
  |------|------|---------------------|----------|---|
  | FIXED-100 | E1 | x.xx ± x.xx | x.xx% | 10 |
  | FIXED-100 | E2 | x.xx ± x.xx | x.xx% | 10 |
  | FIXED-2000 | E1 | x.xx ± x.xx | x.xx% | 10 |
  | FIXED-2000 | E2 | x.xx ± x.xx | x.xx% | 10 |
  | CCS | E1 | x.xx ± x.xx | x.xx% | 10 |
  | CCS | E2 | x.xx ± x.xx | x.xx% | 10 |
  ```
  - ファイル: `results/kpi_summary.csv`

### 3.3 図表作成

- [ ] **Figure 1: Pout-μCトレードオフ曲線**
  - X軸: μC/event [mJ]
  - Y軸: Pout(τ=2s) [%]
  - プロット: 6点（3条件×2環境）+ 誤差バー
  - 理論曲線: Pout = (1-p_d)^⌊τ/T_adv⌋ を重ねる

- [ ] **Figure 2: CCS制御の時系列例**
  - 上段: CCS(t)とT_adv(t)
  - 下段: 電流波形
  - 1セッション分の代表例

- [ ] **Figure 3: 省エネ率の比較**
  - 棒グラフ: FIXED-100基準の省エネ率
  - E1/E2を並べて表示

- [ ] **Table 1: 実験条件**
- [ ] **Table 2: KPI集計結果**

**成果物チェックリスト**:
- [ ] `figures/fig1_tradeoff.pdf`
- [ ] `figures/fig2_timeseries.pdf`
- [ ] `figures/fig3_energy_saving.pdf`
- [ ] `results/kpi_summary.csv`
- [ ] `results/statistical_tests.md`（t検定等）

---

## 4. 執筆フェーズ（Week 4）

### 4.1 論文構成（IEICE ComEX想定、4ページ）

```
1. Introduction (0.5p)
   - 背景: ウェアラブルHAR + BLE通信の課題
   - 問題: 固定広告間隔の非効率性
   - 提案: HAR不確実度に基づく適応制御
   - 貢献: 3点

2. System Model (0.75p)
   - 2.1 Problem Formulation（Safe Bandit定式化）
   - 2.2 CCS-based Policy（決め打ちルール）
   - 2.3 Pout(τ) Model（理論式）

3. Experimental Setup (0.5p)
   - 3.1 Hardware Configuration
   - 3.2 mHealth Dataset
   - 3.3 Evaluation Metrics

4. Results (1.0p)
   - 4.1 Energy Reduction
   - 4.2 Pout-μC Tradeoff
   - 4.3 Model Validation

5. Conclusion (0.25p)
   - まとめ
   - Future Work: Safe Contextual Banditへの拡張

References (~15件)
```

### 4.2 執筆チェックリスト

- [ ] **Introduction**
  - [ ] 背景の記述（先行研究3-5件引用）
  - [ ] 問題設定の明確化
  - [ ] 貢献の3点リスト

- [ ] **System Model**
  - [ ] 数式の整合性確認
  - [ ] 記号表の作成
  - [ ] 図1（システム構成図）の作成

- [ ] **Experimental Setup**
  - [ ] ハードウェア仕様の記載
  - [ ] データセット情報の記載
  - [ ] 再現可能な実験条件の記述

- [ ] **Results**
  - [ ] 図表の挿入
  - [ ] 統計的有意性の記載（あれば）
  - [ ] 考察の記述

- [ ] **Conclusion**
  - [ ] 主要結果の要約
  - [ ] Future Workの明記

- [ ] **その他**
  - [ ] 英文校正
  - [ ] フォーマット確認（IEICE ComEX template）
  - [ ] 参考文献フォーマット確認

---

## 5. リスク管理

### 5.1 技術リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| ESP32のT_adv動的変更が不安定 | 実験不可 | 事前に100セッション分の安定性テスト |
| Android受信漏れ | Pout過大評価 | LOW_LATENCYモード固定、バックグラウンド処理停止 |
| TXSD/INA219ログの同期ずれ | μC算出誤差 | GPIOマーカーで±10ms以内に補正 |
| mHealthのCCS分布が偏る | 効果が見えない | 事前にCCS分布を確認、必要なら複数被験者使用 |

### 5.2 スケジュールリスク

| リスク | 影響 | 対策 |
|--------|------|------|
| 準備が遅延 | 実験期間圧縮 | Week1で最低限動く状態を優先 |
| 実験環境が使えない | 実験不可 | 代替環境を事前に確保 |
| データ処理で問題発覚 | 再実験 | 毎日の品質チェックで早期発見 |

### 5.3 Goサイン判定基準

**Week 1終了時点で以下が揃っていればGo**:
- [ ] CCS時系列10セッション分が生成済み
- [ ] ESP32ファームウェアが3モードで動作
- [ ] Android受信ログが正常に取れる
- [ ] INA219での電力計測がフェーズ0-0(再計測)と整合

**揃っていない場合**:
- 不足分の優先対応
- 実験スケジュールの後ろ倒し
- 最悪、セッション数を30に削減（5反復）

---

## 6. 成果物一覧

### コード

**CCS生成（完了）**:
- [x] `scripts/generate_ccs_sequences.py` - TFLite推論+U/S/CCS計算+時系列出力
- [x] `scripts/create_esp32_sessions.py` - ESP32用セッション選定

**ESP32ファームウェア（完了、2025-11-29 ディレクトリ再編済み）**:
- [x] `esp32_firmware/baseline_on/` - マルチinterval自動実行（TX/TXSD/RX）
- [x] `esp32_firmware/baseline_off/` - OFF計測（TX/TXSD）
- [x] `esp32_firmware/ccs_mode/` - CCSモード（TX/TXSD/RX + ccs_session_data.h）
- [x] ハッシュ記録: `docs/フェーズ0-0/decision_log_2025-11-29.md` Section 7

**データ処理（未実装）**:
- [ ] `scripts/sync_logs.py` - TX/RX/電力ログのタイムスタンプ統一
- [ ] `scripts/compute_event_charge.py` - μC/event算出
- [ ] `scripts/compute_pout.py` - Pout(τ)算出

**暫定代替**: `scripts/analyze_baseline_v2.py` でbaseline ON/OFF計測のΔE/adv算出は可能

### データ

**CCS時系列（完了）**:
- [x] `data/ccs_sequences/subject{01-10}_ccs.csv`
- [x] `data/ccs_sequences/generation_summary.json`
- [x] `data/esp32_sessions/session_{01-10}.csv`
- [x] `data/esp32_sessions/session_manifest.json`
- [x] `data/esp32_sessions/session_selection_report.md`

**実験データ（未取得）**:
- [ ] `data/raw/E1/`, `data/raw/E2/`
- [ ] `data/experiments_manifest.yaml`

### 結果
- [ ] `results/kpi_summary.csv`
- [ ] `results/statistical_tests.md`
- [ ] `figures/fig1_tradeoff.pdf`
- [ ] `figures/fig2_timeseries.pdf`
- [ ] `figures/fig3_energy_saving.pdf`

### 文書
- [x] `data/esp32_sessions/session_selection_report.md`
- [ ] `docs/experiment_log.md`
- [ ] `paper/main.tex`

---

## 次のアクション

**完了済み（2025-11-27）**:
- [x] 0.1 既存資産の棚卸し
- [x] 0.2 ハードウェア準備状況の確認
- [x] 1.1 mHealth CCS時系列生成
- [x] 閾値調整（θ_high=0.90, θ_low=0.80）

**残タスク**:
1. [x] ~~1.2 CCSモード拡張~~ (2025-11-28 完了)
2. [x] ~~1.3 Android受信アプリ~~ → nRF Connect使用 (2025-11-28 決定)
3. [x] ~~0.2 Android OSバージョン確認~~ → Android 10 (2025-11-28 確認)
4. [x] ~~配線修正~~ → INA219 Vcc直結、UART 115200bps (2025-11-29 完了)
5. [ ] **Baseline再計測** (進行中 2025-11-30)
   - [x] OFF計測完了 (11 trials)
   - [ ] ON計測 (100/500/1000/2000ms 自動実行中)
6. [ ] 1.4.3 P_off/ΔE/adv再校正（Baseline再計測データで算出）
7. [ ] 0.2 E1環境確認、距離1mマーキング確認

### 緊急対応（Mode C2′再計測・SYNC安定化）※2025-12-07追記
- [ ] labels_all.h を100ms版で再生成（subject01≒6946など、各6.3k〜7.0k）
- [ ] TX: trial終了後にSYNC LOWを数百ms保持 → 次trial開始を遅延させ、RX/TXSDが境界を確実に検出
- [ ] TXSD/RX: SYNC=26で開始/終了を確認（ログに sync=1→0 が出ること）
- [ ] REPEAT=3時の所要時間 ≒ 2.1h/被験者（4区間×3回×約10.6分）→ 長時間放置でも12本に分割されているか確認
- [ ] 期待adv_count目安: 100ms≒6352, 500ms≒1271, 1000ms≒636, 2000ms≒318（REPEAT=3で総計≒25.7k）
- [ ] シリアルで “all trials completed” を確認。リセット・SYNC抜けをチェック

---

*Last updated: 2025-12-10*
