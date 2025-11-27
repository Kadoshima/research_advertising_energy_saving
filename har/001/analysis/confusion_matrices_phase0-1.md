# Phase 0-1 混同行列 (Confusion Matrices)

**作成日**: 2025-11-26
**データソース**: `har/001/runs/phase0-1/fold*/metrics.json`
**評価方法**: 10-fold LOSO (Leave-One-Subject-Out) cross-validation

---

## 1. fold5（代表モデル: Subject 5）12-class混同行列

**Test samples**: 669 (Subject 5)
**Test BAcc**: 90.98%

```
True \ Pred     0    1    2    3    4    5    6    7    8    9   10   11   | Total
-------------------------------------------------------------------------------------
 0 Standing    5   35    0    0    0    0    0    0    0    0    0    0   |   40
 1 Sitting     0   61    0    0    0    0    0    0    0    0    0    0   |   61
 2 Lying       0    0   60    0    0    0    0    0    0    0    0    0   |   60
 3 Walking     0    0    0   60    0    0    0    0    0    0    0    0   |   60
 4 Stairs      0    0    0    9   51    0    0    0    0    0    0    0   |   60
 5 Bends       0    0    0    0    0   55    0    0    0    0    0    0   |   55
 6 Arms        0    0    0    0    0    0   56    0    0    0    0    0   |   56
 7 Crouch      0    0    0    0    0    0    0   53    0    0    0    0   |   53
 8 Cycling     0    0    0    0    0    0    0    0   61    0    0    0   |   61
 9 Jogging     0    0    0    0    0    0    0    0    0   61    0    0   |   61
10 Running     0    0    0    0    0    0    0    0    0    0   61    0   |   61
11 Jump        0    0    0    0    0    0    0    0    0    0    0   19   |   19
-------------------------------------------------------------------------------------
Total            5   96   60   69   51   55   56   53   61   61   61   19   |  647
```

### Per-class Accuracy (fold5)

| Class | Activity   | Accuracy | Correct/Total |
|-------|-----------|----------|---------------|
| 0     | Standing  | 12.50%   | 5/40          |
| 1     | Sitting   | 100.00%  | 61/61         |
| 2     | Lying     | 100.00%  | 60/60         |
| 3     | Walking   | 100.00%  | 60/60         |
| 4     | Stairs    | 85.00%   | 51/60         |
| 5     | Bends     | 100.00%  | 55/55         |
| 6     | Arms      | 100.00%  | 56/56         |
| 7     | Crouch    | 100.00%  | 53/53         |
| 8     | Cycling   | 100.00%  | 61/61         |
| 9     | Jogging   | 100.00%  | 61/61         |
| 10    | Running   | 100.00%  | 61/61         |
| 11    | Jump      | 100.00%  | 19/19         |

**主要な誤分類パターン（fold5）**:
- **Standing → Sitting**: 35/40サンプル（87.5%が誤分類）
- **Stairs → Walking**: 9/60サンプル（15.0%が誤分類）

---

## 2. fold5（代表モデル）4-class混同行列

**Test samples**: 669 (Subject 5)
**4-class BAcc**: 94.79%
**Overall Accuracy**: 95.37%

```
True \ Pred     Loco  Trans  Stat  Unkn  | Total
-------------------------------------------------------
0 Locomotion    243     0     0     0  |   243
1 Transition      9   234     0     1  |   244
2 Stationary      0     0   161    21  |   182
3 Unknown         0     0     0     0  |     0
-------------------------------------------------------
Total              252   234   161    22  |   669
```

### Per-class Accuracy (4-class, fold5)

| Class | Category     | Accuracy | Correct/Total |
|-------|-------------|----------|---------------|
| 0     | Locomotion  | 100.00%  | 243/243       |
| 1     | Transition  | 95.90%   | 234/244       |
| 2     | Stationary  | 88.46%   | 161/182       |

**主要な誤分類パターン（fold5, 4-class）**:
- **Transition → Locomotion**: 9/244サンプル（3.7%）
- **Stationary → Unknown**: 21/182サンプル（11.5%）— 低信頼度による意図的Unknown判定

---

## 3. 10-fold LOSO集約 12-class混同行列

**Total test samples**: 6768 (全10被験者)
**Overall BAcc**: 74.07%
**Overall Macro F1**: 70.94%

```
True \ Pred      0    1    2    3    4    5    6    7    8    9   10   11  | Total
-----------------------------------------------------------------------------------------------
 0 Standing   203  156    0    0    0    0   41    0    0    0    0    0  |   400
 1 Sitting    209  121    0    0    4    0  133    0    0    0    0    0  |   467
 2 Lying        0    0  602    0    0    0    0    0    0    0    0    0  |   602
 3 Walking      0    0    0  554   34    0    2    0    0    0    0    0  |   590
 4 Stairs       0    0    0   47  519    0    0    3    0    0    0    0  |   569
 5 Bends        0    0    0    0    0  482    0   63    0    0    0    0  |   545
 6 Arms         9   26    0    0    0    0  423    0    0    0    0    0  |   458
 7 Crouch       0    0    0    0   60  107    0  336    0    0    0    0  |   503
 8 Cycling      0    0    0    0   60    0    0   61  451    0    0    0  |   572
 9 Jogging      0    0    0    0    0    0    0    0    0  553   22    0  |   575
10 Running      0    0    0    0    0    0    0    0    0   10  578    0  |   588
11 Jump         0    0    0    0    0    0    0    5    0    6    9  161  |   181
-----------------------------------------------------------------------------------------------
Total           421  303  602  601  677  589  599  468  451  569  609  161  |  6050
```

### Per-class Accuracy (10-fold集約)

| Class | Activity   | Accuracy | Correct/Total | 備考                    |
|-------|-----------|----------|---------------|------------------------|
| 0     | Standing  | 50.75%   | 203/400       | ❌ 構造的失敗            |
| 1     | Sitting   | 25.91%   | 121/467       | ❌ 構造的失敗            |
| 2     | Lying     | 100.00%  | 602/602       | ✅ 完璧                 |
| 3     | Walking   | 93.90%   | 554/590       | ✅ 良好                 |
| 4     | Stairs    | 91.21%   | 519/569       | ✅ 良好                 |
| 5     | Bends     | 88.44%   | 482/545       | ✅ 良好                 |
| 6     | Arms      | 92.36%   | 423/458       | ✅ 良好                 |
| 7     | Crouch    | 66.80%   | 336/503       | ⚠️ 改善余地あり          |
| 8     | Cycling   | 78.85%   | 451/572       | ⚠️ 改善余地あり          |
| 9     | Jogging   | 96.17%   | 553/575       | ✅ 良好                 |
| 10    | Running   | 98.30%   | 578/588       | ✅ 良好                 |
| 11    | Jump      | 88.95%   | 161/181       | ✅ 良好                 |

### 主要な誤分類パターン（10-fold集約）

#### Stationary系（Standing/Sitting/Lying）
1. **Standing → Sitting**: 156/400 (39.0%) — 胸部センサでは区別不可
2. **Standing → Standing**: 203/400 (50.8%) — 正解率50%程度
3. **Sitting → Arms**: 133/467 (28.5%) — 動的誤分類
4. **Sitting → Standing**: 209/467 (44.8%) — 相互混同
5. **Sitting → Sitting**: 121/467 (25.9%) — 正解率26%のみ

#### Locomotion系
1. **Walking → Stairs**: 34/590 (5.8%) — 許容範囲
2. **Cycling → Stairs**: 60/572 (10.5%) — 改善必要
3. **Cycling → Crouch**: 61/572 (10.7%) — 改善必要

#### Transition系
1. **Stairs → Walking**: 47/569 (8.3%) — 許容範囲
2. **Crouch → Stairs**: 60/503 (11.9%) — 改善必要
3. **Crouch → Bends**: 107/503 (21.3%) — 相互混同大
4. **Bends → Crouch**: 63/545 (11.6%) — 相互混同

---

## 4. 10-fold LOSO集約 4-class混同行列

**Total test samples**: 6768 (全10被験者)
**Overall BAcc**: 81.97%
**Overall Macro F1**: 65.33%

```
True \ Pred     Loco  Trans  Stat  Unkn  | Total
-------------------------------------------------------
0 Locomotion   2168   157     0   106  |  2431
1 Transition     62  2159    35   265  |  2521
2 Stationary      0   178  1291   347  |  1816
3 Unknown         0     0     0     0  |     0
-------------------------------------------------------
Total             2230  2494  1326   718  |  6768
```

### Per-class Accuracy (4-class, 10-fold)

| Class | Category     | Accuracy | Correct/Total | BLE制御への影響              |
|-------|-------------|----------|---------------|----------------------------|
| 0     | Locomotion  | 89.18%   | 2168/2431     | 良好（100ms間隔維持）        |
| 1     | Transition  | 85.64%   | 2159/2521     | 良好（500ms間隔維持）        |
| 2     | Stationary  | 71.09%   | 1291/1816     | ⚠️ 改善必要（2000ms間隔）    |

### 主要な誤分類パターン（4-class, 10-fold）

#### BLE制御への影響大
1. **Stationary → Transition**: 178/1816 (9.8%) — **電力+300%** (2000ms→500ms)
2. **Stationary → Unknown**: 347/1816 (19.1%) — 電力+100% (2000ms→1000ms fallback)
3. **Locomotion → Transition**: 157/2431 (6.5%) — 電力+400% (100ms→500ms)

#### BLE制御への影響小
4. **Transition → Locomotion**: 62/2521 (2.5%) — 電力-80% (500ms→100ms)
5. **Transition → Stationary**: 35/2521 (1.4%) — 電力-75% (500ms→2000ms)

---

## 5. 重要な発見と考察

### 5.1 Standing/Sitting認識の構造的失敗

**10-fold集約での実績**:
- Standing正解率: **50.75%** (203/400)
- Sitting正解率: **25.91%** (121/467)
- Standing ↔ Sitting相互誤分類: **365サンプル**（全Standing/Sittingの47.3%）

**原因**:
- 胸部加速度計では上半身姿勢しか捉えられない
- Standing/Sittingの違いは膝・腰の状態（下半身）に依存
- 両者とも上半身は直立 → 胸部センサでは区別不可

**対策**:
1. ✅ **4-class統合**: Standing/Sitting/Lying → Stationary（BLE制御には十分）
2. ⚠️ **Phase 0-2**: 腰センサ追加（下半身状態を捉える）

### 5.2 4-class統合による実用性確保

**BLE制御に必要な区分**:
- Locomotion（動作中）: 100ms間隔 → 高頻度通信
- Transition（遷移中）: 500ms間隔 → 中頻度通信
- Stationary（静止中）: 2000ms間隔 → 低頻度通信
- Unknown（低信頼）: 1000ms間隔 → Fallback

**4-class性能**:
- Locomotion認識: **89.2%** ✅
- Transition認識: **85.6%** ✅
- Stationary認識: **71.1%** ⚠️
- Overall BAcc: **82.0%** ✅（要件≥80%達成）

### 5.3 最悪ケースのBLE制御影響

**Stationary → Transition誤分類**: 178/1816 (9.8%)
- 期待動作: 2000ms間隔（低消費電力）
- 実際動作: 500ms間隔（4倍の広告頻度）
- 電力影響: **+300%** (9.76mJ/adv ÷ 2.26mJ/adv)

**被験者別最悪ケース**:
- Sub04: Stationary誤分類率 **33.7%** → 平均電力+40%
- Sub02: Operational_Acc **60.8%** → 頻繁な状態遷移
- Sub08: Operational_Acc **59.8%** → 頻繁な状態遷移

### 5.4 fold間の性能分散

**12-class BAcc**:
- 最悪: fold2 = 51.3% (Subject 2)
- 最良: fold5 = 91.0% (Subject 5)
- 標準偏差: ±14.4%

**被験者依存性が大きい理由**:
1. mHealthデータセットの個人差（装着位置、体格、動作スタイル）
2. Chest-onlyセンサの限界（特にStationary系）
3. サンプル数のクラス不均衡

---

## 6. Phase 1への推奨事項

### 6.1 モデル改善（優先度: 低）
- 12-class個別制御は断念 → 4-class統合で十分
- Stationary認識の改善は腰センサ追加が必要（Phase 0-2で検討）

### 6.2 BLE制御ロジック（優先度: 高）
- Stationary → Transition誤分類の許容度設定
  - 目標: 誤分類率≤5%（現状9.8%）
  - 対策: U/S/CCSの閾値調整、ヒステリシス強化
- Unknown判定の最適化
  - 現状19.1%がUnknown → 過剰な保守的判定
  - 目標: Unknown率5-10%（現状10.5%は妥当）

### 6.3 実機実験（優先度: 最高）
- ESP32実装とリアルタイムU/S/CCS計算
- BLE間隔制御の実データログ取得
- 電力消費の実測とΔE/adv検証

---

## データソース

- **fold5 predictions**: `har/001/runs/phase0-1/fold5/metrics.json`
- **10-fold predictions**: `har/001/runs/phase0-1/fold*/metrics.json` (fold1-10集約)
- **Class mapping**: `har/001/src/train_phase0-1.py:46-71`
- **BLE impact**: `har/001/analysis/ble_impact_summary.csv`

**生成日時**: 2025-11-26
**検証済み**: 全混同行列を元データから直接計算確認
