# HAR-BLE Safe Contextual Bandit 実験計画書

**文書ID**: RHT-EXP-PLAN-v1.0
**作成日**: 2025-11-27
**ステータス**: ドラフト

---

## 0. 前提条件の確認

### 0.1 既存資産の棚卸し

- [x] **フェーズ0-0データの確認** (2025-11-27 完了)
  - [x] ΔE/adv実測値（100/500/1000/2000ms）が使える状態か → OK (`docs/フェーズ1/results/delta_energy_row1120_row1123_off.md`)
  - [x] P_off_mean = 22.106 mW の値を再利用できるか → OK
  - [x] PDR実測値（p_d ≈ 0.85）の根拠データがあるか → OK (`docs/フェーズ1/results/pdr_row1120_txsd_rx.md`)

- [x] **HARモデル（A0）の確認** (2025-11-27 完了)
  - [x] TFLite int8モデル（90.6KB）がエクスポート済みか → OK (`har/004/export/acc_v1_keras/phase0-1-acc.v1.int8.tflite`)
  - [x] 校正パラメータ（T=0.7443, τ=0.66）が確定しているか → OK (`har/001/docs/A0_acc_v1_baseline_summary.md`)
  - [x] θ_low=0.40, θ_high=0.70 の閾値が設定済みか → デフォルト値設定済み（TFLite出力ベースで再キャリブ推奨）

- [x] **mHealthデータセットの確認** (2025-11-27 完了)
  - [x] 生データへのアクセスがあるか → OK (`data/MHEALTHDATASET/`)
  - [x] 被験者数・セッション数・活動ラベルの把握 → 10名、12活動、6,768窓
  - [x] データ前処理パイプラインが動作するか → OK (`har/001/data_processed/subject*.npz`)

**棚卸しログ**: `logs/inventory_0.1_2025-11-27.md`

### 0.2 ハードウェア準備状況

- [x] **ESP32ボード** (2025-11-27 確認)
  - [x] 型番: ESP32 Dev Module (3台: TX/TXSD/RX)
  - [x] 動作確認済み

- [x] **電力計測** (2025-11-27 確認)
  - [x] **INA219構成を継続**（PPK-IIは使用しない）
  - [x] Phase 0-0と同じ構成

- [ ] **Android端末** (一部未確認)
  - [x] 機種名: Galaxy S9
  - [ ] OSバージョン: 後日確認
  - [ ] BLE受信アプリの準備状況: 要確認

- [ ] **実験環境** (一部未確認)
  - [ ] E1（干渉弱）環境: 未確認
  - [x] E2（干渉強）環境: 確保済み（簡易に実施可能）
  - [ ] 距離1mの固定方法: 要確認

**ハードウェアログ**: `logs/inventory_0.2_2025-11-27.md`

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

### 1.2 ESP32ファームウェア開発

**目的**: CCS時系列を読み込み、T_advを動的に変更するファームウェア

#### 1.2.1 基本機能実装

- [ ] **SDカード読み込み機能**
  - CSVファイルからCCS時系列を読み込み
  - タイムスタンプに従って次のT_adv値を取得

- [ ] **BLE Advertising制御**
  - `esp_ble_gap_config_adv_data()` でペイロード設定
  - `esp_ble_gap_start_advertising()` でinterval動的変更
  - 対応interval: 100, 500, 1000, 2000 ms

- [ ] **ログ出力機能**
  - SDカードに送信ログを記録
  - フォーマット: `t_local_ms, interval_ms, ccs, u, s, adv_seq`

#### 1.2.2 実験モード実装

- [ ] **FIXED-100モード**
  - T_adv = 100ms 固定
  - CCS計算はスキップ

- [ ] **FIXED-2000モード**
  - T_adv = 2000ms 固定
  - CCS計算はスキップ

- [ ] **CCSモード**
  - CCS時系列に従ってT_advを動的変更
  - ヒステリシス・最小滞在時間を適用

#### 1.2.3 同期機能実装

- [ ] **セッション開始マーカー**
  - LED点滅パターン（3秒）
  - シリアル出力（タイムスタンプ）
  - GPIOパルス（PPK-II同期用）

- [ ] **セッション終了マーカー**
  - 同上

**成果物チェックリスト**:
- [ ] `firmware/har_ble_adv/main.c`
- [ ] `firmware/har_ble_adv/README.md`（ビルド・書き込み手順）
- [ ] 動作確認済みバイナリ

---

### 1.3 Android受信アプリ準備

**目的**: BLE広告を受信し、タイムスタンプ付きでログを記録

#### 1.3.1 アプリ要件

- [ ] **スキャン設定**
  - モード: `SCAN_MODE_LOW_LATENCY`
  - フィルタ: ESP32のMACアドレスまたはサービスUUID

- [ ] **ログ記録項目**
  - t_rx_ms: 受信タイムスタンプ（Unix epoch ms）
  - rssi: 受信信号強度
  - adv_seq: 広告シーケンス番号（ペイロードから抽出）
  - raw_payload: 生データ（デバッグ用）

- [ ] **ログ出力**
  - CSV形式でストレージに保存
  - ファイル名: `rx_log_YYYYMMDD_HHMMSS.csv`

#### 1.3.2 既存アプリの確認 or 新規開発

- [ ] 既存のBLEスキャンアプリが使えるか確認
  - nRF Connect app?
  - 自作アプリ?
- [ ] 必要に応じて修正・新規開発

**成果物チェックリスト**:
- [ ] Android APK または使用するアプリの特定
- [ ] ログフォーマットのサンプル

---

### 1.4 電力計測セットアップ

**目的**: PPK-IIでESP32の電力を正確に計測する

#### 1.4.1 配線

- [ ] ESP32のVBAT端子を特定
- [ ] PPK-IIのAmpere Meter端子に直列接続
- [ ] GND共通化

#### 1.4.2 計測設定

- [ ] サンプリングレート: 100kS/s
- [ ] トリガ設定: 外部GPIOまたはマニュアル
- [ ] ログファイル形式: CSV（t_us, current_uA）

#### 1.4.3 動作確認

- [ ] FIXED-100で5分間計測、ΔE/advがフェーズ0-0と±10%以内か確認
- [ ] FIXED-2000で5分間計測、同上

**成果物チェックリスト**:
- [ ] 配線図（写真 or 図）
- [ ] 校正確認レポート

---

## 2. 実験実施フェーズ（Week 2-3）

### 2.1 実験プロトコル

#### 2.1.1 セッション手順（1セッション15分）

```
[開始前]
1. ESP32にCCS時系列ファイルをセット（CCSモードの場合）
2. ESP32のモード選択（FIXED-100 / FIXED-2000 / CCS）
3. Android受信アプリ起動、ログ記録開始
4. PPK-II計測開始
5. ESP32電源ON

[セッション中]
6. 同期マーカー（LED点滅3秒）を記録
7. 15分間待機（介入なし）
8. 終了マーカーを記録

[終了後]
9. ESP32電源OFF
10. PPK-IIログ保存
11. Androidログ保存
12. ESP32 SDカードログ回収
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

#### 3.2.1 μC/event算出

- [ ] **イベント定義**
  - CCSモード: T_adv遷移が発生した時点
  - FIXEDモード: 活動遷移時点（CCS時系列から推定）

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
| PPK-II同期ずれ | μC算出誤差 | GPIOマーカーで±10ms以内に補正 |
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
- [ ] PPK-IIでの電力計測がフェーズ0-0と整合

**揃っていない場合**:
- 不足分の優先対応
- 実験スケジュールの後ろ倒し
- 最悪、セッション数を30に削減（5反復）

---

## 6. 成果物一覧

### コード
- [ ] `scripts/load_mhealth.py`
- [ ] `scripts/run_har_inference.py`
- [ ] `scripts/compute_uncertainty.py`
- [ ] `scripts/ccs_policy.py`
- [ ] `scripts/sync_logs.py`
- [ ] `scripts/compute_event_charge.py`
- [ ] `scripts/compute_pout.py`
- [ ] `firmware/har_ble_adv/`

### データ
- [ ] `data/ccs_sequences/session_*.csv`
- [ ] `data/raw/E1/`, `data/raw/E2/`
- [ ] `data/experiments_manifest.yaml`

### 結果
- [ ] `results/kpi_summary.csv`
- [ ] `results/statistical_tests.md`
- [ ] `figures/fig1_tradeoff.pdf`
- [ ] `figures/fig2_timeseries.pdf`
- [ ] `figures/fig3_energy_saving.pdf`

### 文書
- [ ] `docs/session_selection_report.md`
- [ ] `docs/experiment_log.md`
- [ ] `paper/main.tex`

---

## 次のアクション

**今日やること**:
1. [ ] 0.1 既存資産の棚卸し（30分）
2. [ ] 0.2 ハードウェア準備状況の確認（30分）
3. [ ] 1.1.1 データ読み込みスクリプトの着手

**明日やること**:
1. [ ] 1.1 mHealth CCS時系列生成の完了
2. [ ] 1.2 ESP32ファームウェア開発の着手

---

*Last updated: 2025-11-27*
