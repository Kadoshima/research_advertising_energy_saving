# Phase 2 データ棚卸し（Data Inventory）

- 作成日: 2026-01-21
- 目的: Phase 2（Safe-UCB）で使用するデータを明確化し、train/test分割を固定する
- 状態: **DRAFT**（実験完了後に更新）

---

## 1. データ在庫一覧

### 1.1 Phase 0-0（ΔE基準データ）

| データセットID | パス | 環境 | 条件 | n | 用途 |
|---------------|------|------|------|---|------|
| deltae_v02 | `data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/` | E1 | OFF+ON(100/500/1000/2000ms) | 50 | 報酬モデル（μC推定） |

### 1.2 Phase 1 E1（CCS制御実験）

| データセットID | パス | 環境 | 条件 | n | 用途 |
|---------------|------|------|------|---|------|
| D1 | `data/実験データ/研究室/d1_*/` | E1 | 基本動作（100↔500ms） | TBD | 制約モデル |
| D2b | `data/実験データ/研究室/d2b_*/` | E1 | S1/S4シナリオ | 6 | 制約モデル |
| D3 | `data/実験データ/研究室/d3_*/` | E1(scan70) | 劣化環境 | 3 | 制約モデル |
| D4 | `data/実験データ/研究室/d4_*/` | E1 | U-shuffle ablation | 3 | 制約モデル |
| D4B | `data/実験データ/研究室/d4b_*/` | E1 | CCS-off ablation | 3+3 | 制約モデル |

### 1.3 Phase 1 E2（高干渉環境）

| データセットID | パス | 環境 | 条件 | n | 用途 |
|---------------|------|------|------|---|------|
| e2_ccs_v01 | `data/実験データ/研究室/phase1_e2_ccs_2026-01-21_v01/` | E2 | CCS-Control | TBD | 制約モデル（E2） |
| e2_fixed_v02 | `data/実験データ/研究室/phase1_e2_fixed_2026-01-21_v02/` | E2 | FIXED(500/1000/2000ms) | 15 | 制約モデル（E2） |

---

## 2. データ属性詳細

### 2.1 deltae_v02（報酬モデル用）

```yaml
dataset_id: deltae_v02
path: data/実験データ/研究室/deltae_v3rig_sweep_2026-01-21_v02/
environment: E1
date: 2026-01-21
conditions:
  - mode: OFF
    n_trials: 10
    duration_s: 60
  - mode: ON_100ms
    n_trials: 10
    duration_s: 60
  - mode: ON_500ms
    n_trials: 10
    duration_s: 60
  - mode: ON_1000ms
    n_trials: 10
    duration_s: 60
  - mode: ON_2000ms
    n_trials: 10
    duration_s: 60
total_trials: 50
firmware:
  TX: TX_DELTAE_SWEEP_20260115
  TXSD: TXSD_DELTAE_SWEEP_20260115
  RX: RX_DELTAE_SWEEP_20260115
metrics_available:
  - E_total_mJ
  - ΔE_mJ
  - PDR
  - RSSI
use_in_phase2: reward_model (μC estimation)
```

### 2.2 e2_fixed_v02（制約モデル用）

```yaml
dataset_id: e2_fixed_v02
path: data/実験データ/研究室/phase1_e2_fixed_2026-01-21_v02/
environment: E2
env_details:
  strongest_ap_rssi_dbm: -20
  wifi_channel: 1 (2412 MHz)
  measurement_app: Analiti
date: 2026-01-21
conditions:
  - mode: FIXED_500ms
    n_trials: 5
    duration_s: 600
  - mode: FIXED_1000ms
    n_trials: 5
    duration_s: 600
  - mode: FIXED_2000ms
    n_trials: 5
    duration_s: 600
total_trials: 15
firmware:
  TX: TX_PHASE1_FIXED_SWEEP_20260121
  TXSD: TXSD_PHASE1_FIXED_SWEEP_20260121
  RX: RX_PHASE1_FIXED_SWEEP_20260121
metrics_available:
  - TL (Time-to-first-Receive)
  - Pout(τ)
  - PDR
  - RSSI
  - P_avg_mW
use_in_phase2: constraint_model (Pout estimation, E2)
```

---

## 3. Train/Test 分割ルール

### 3.1 分割方針

| 項目 | 値 | 理由 |
|------|-----|------|
| 分割単位 | **run（実験セット）単位** | セッション単位だとリークリスク |
| 分割比率 | train 70% / test 30% | 標準的な比率 |
| seed | 42 | 再現性 |
| リーク防止 | 同一runは分けない | 時間相関を考慮 |

### 3.2 具体的な分割

#### 報酬モデル（μC推定）

| データ | train | test |
|--------|-------|------|
| deltae_v02 | trial 1-7（各モード） | trial 8-10（各モード） |

#### 制約モデル（Pout推定）

| データ | train | test |
|--------|-------|------|
| E1系（D1-D4B） | 70%のrun | 30%のrun |
| E2系（e2_*） | 全量（補足評価用） | - |

### 3.3 環境シフト評価用（段階2）

| 用途 | train | test |
|------|-------|------|
| E1→E2一般化 | E1系全量 | E2系全量 |

---

## 4. Phase 2で使用するデータの決定

### 4.1 報酬モデル（μC(a)推定）

**使用データ**: deltae_v02

**抽出する値**:
| 行動a | μC(a) [μJ/event] | σ(a) | n |
|-------|-----------------|------|---|
| 100ms | TBD | TBD | 10 |
| 500ms | TBD | TBD | 10 |
| 1000ms | TBD | TBD | 10 |
| 2000ms | TBD | TBD | 10 |

**算出方法**:
```
μC(a) = (E_ON(a) - E_OFF) / N_adv(a)
```

### 4.2 制約モデル（Pout(τ|a)推定）

**使用データ**: E1系（D1-D4B）+ E2系（e2_ccs, e2_fixed）

**抽出する値**:
| 行動a | 環境 | Pout(1s) | Pout(2s) | n |
|-------|------|----------|----------|---|
| 100ms | E1 | TBD | TBD | TBD |
| 500ms | E1 | TBD | TBD | TBD |
| 1000ms | E1 | TBD | TBD | TBD |
| 2000ms | E1 | TBD | TBD | TBD |
| 500ms | E2 | TBD | TBD | 5 |
| 1000ms | E2 | TBD | TBD | 5 |
| 2000ms | E2 | TBD | TBD | 5 |

### 4.3 評価用（hold-out）

**使用データ**: 各データセットのtest split

**評価指標**:
- 累積Regret
- 制約違反率
- 平均エネルギー

---

## 5. データ品質チェックリスト

### 各データセットで確認すべき項目

- [ ] ファイル数がmanifest.csvと一致
- [ ] 各ファイルのrows > 0（空ファイルなし）
- [ ] SHA256がmanifest.csvと一致
- [ ] duration_sが期待値の±10%以内
- [ ] 欠損率（parse_drop等）< 1%

### 確認結果

| データセットID | ファイル数 | 空ファイル | SHA256 | duration | 欠損率 | 判定 |
|---------------|----------|----------|--------|----------|--------|------|
| deltae_v02 | 100 | 0 | ✅ | ✅ | <1% | ✅ |
| e2_ccs_v01 | TBD | TBD | TBD | TBD | TBD | TBD |
| e2_fixed_v02 | TBD | TBD | TBD | TBD | TBD | TBD |

---

## 6. 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-01-21 | 初版作成。テンプレートとして構造を定義。実験完了後に数値を埋める |
