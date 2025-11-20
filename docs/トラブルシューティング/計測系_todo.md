# 計測系・解析パイプライン TODO（ΔE/adv・受信品質・ログ健全性）

ポイントは **「いま手元のデータで自信をもってKPIを出す」ための止血** と、**次回以降で同じ不具合を起こさない根治** の二層構え。  
評価で出てきた課題（uA列の文字化け・単位ズレ・500 ms 内クラスター・旧ログ互換など）を踏まえ、すべて **Why / What / DoD（受け入れ条件）** 付きで整理する。

---

## 0) 全体方針（原則）

- **主KPI** = ΔE/adv（mJ/adv または µJ/adv）を最優先で安定に出す。  
  根拠: TX→TXSD で `ms,mV,µA,p_mW` を記録し、`p_mW=(mV×µA)/1e6`、`E_mJ += p_mW×(dt_ms/1000)` で積分できる仕様。
- 受信品質（PDR / TL / Pout(τ)）は **同じ行に並べて意思決定**（トレードオフを可視化する）。
- Android/iOS の **非理想スキャン（Opportunistic / BG制約）** を前提にし、評価は**端末内A/B比較**で完結させる。
- まずは **止血（A/B）** → 次に **根治（C）** → 最後に **運用/研究（D/E）**。

---

## A) 止血：信頼できる解析対象の確定（優先度: 最上）

進捗メモ（2025-11-20）  
- Manifest: `experiments_manifest.yaml` 新設。1m_on_05/outlier除外、1m_off_05、1m_on/off_04を登録。既知外れ（1m_on_100_01/trial_065_on, 1m_on_1000_01/trial_044_on, 1m_on_500_03/trial_095/096_on）を exclude 済み。  
- パイプライン: `scripts/compute_power_and_pdr.py` が manifest を第一級入力として include=false を自動スキップ。  
- 単位監査: `scripts/check_units.py` 追加。diag mean_p を µWスケール想定で補正し、TXSD互換パーサ（先頭数字採用＋p_mW列優先）で I1/I2 を ±1% 内に収束。  
- TX出力: esp32 TX系を固定桁ASCII化（mv=4桁, uA=6桁）済み。
- ΔE/adv: `scripts/compute_delta_energy.py` を追加（manifest適用で ON/OFF を集計し ΔE/adv を出力）。
- 次の着手: 500 ms 系クラスタリング→manifest反映（高電流クラスタ自動判定）、旧ログヘッダ方言吸収レイヤの実装。

### A‑1. トライアル選別マニフェスト（Manifest）

- **Why**  
  外れトライアル（例: `1m_on_500_03` の 095/096, `1m_on_1000_01` の 044, `1m_on_100_01` の 065）を “毎回手作業で除外” しないため。解析の再現性・透明性を担保する。

- **What**  
  `experiments_manifest.yaml` を新設し、trial 単位のメタを明示する。

  - 例: `trial_id, path, interval_ms, set_id, include: true|false, exclude_reason:[…], notes`
  - 自動除外ルール（案）:
    1. **短すぎ**:  
       `ms_total < 0.8 × (N_ADV_PER_TRIAL × ADV_INTERVAL_MS)`
    2. **adv_count 異常**:  
       TICK ありで `|adv_count − N_ADV_PER_TRIAL| > 5`
    3. **高電流外れ**:  
       `mean_i` の **中央値±3×MAD** を超過
    4. **クラスタ逸脱**:  
       同一条件内で 2 クラスターに分かれる場合（B‑0 で判定）から外れた点

  - 例（テンプレ）:

    ```yaml
    - trial_id: 1m_on_500_03/trial_095_on
      path: data/実験データ/研究室/1m_on_500_03/trial_095_on.csv
      interval_ms: 500
      set_id: 500_03
      include: false
      exclude_reason: [high_current_outlier]
      notes: "mean_i ≈ 220 mA class"
    ```

- **DoD（Done の条件）**
  - 解析スクリプトが Manifest を読み、**include=false の trial を自動除外**する。
  - 含有/除外と理由をまとめた CSV（もしくは同等の表）が出力され、後から人が追える。
  - 進捗: `experiments_manifest.yaml` 起票済み（1m_on/off_05, on/off_04, 100/500/1000 ms の既知外れを exclude）。`compute_power_and_pdr.py --manifest` で自動除外が効く状態。

---

### A‑2. uA 列文字化けの救済（軽→重の二段階）

- **Why**  
  UART 経路で `uA` に `! " # % &` などが混入し、現行パーサが「先頭の連続数字のみ」を採用しているため、末尾桁が落ちるケースが多数ある。trial 内では自己一貫しているが、絶対値にはバイアスが乗っている可能性が高い。

- **What（A‑2a: 軽量の止血策）**  
  ASCII プロトコルのまま、**固定桁＋復元**で救済する。

  - TX 側: `mv,uA` を **ゼロ埋め固定幅**（例: `mv=4 桁, uA=6 桁`）で UART 出力する。
  - 解析側: 正規表現で **非数字を除去＋桁長チェック** した上で整数化する。
    - 桁長不足の行は末尾ゼロ補完などのヒューリスティック復元＋フラグ付け。
  - 備考: `p_mW` と `E_mJ` は TXSD 側のロジックで、すでに「文字化け後の整数値」で一貫して計算されている。復元は**表示や絶対値補正**のためであり、**エネルギー整合は A‑3 の単位監査で別途確認**する。

- **What（A‑2b: 重い根治策）**  
  A‑2a を実施しても問題が残る場合のみ、**バイナリ＋CRC（STX/length/payload/CRC/ETX）** に段階的に移行する。

- **DoD**
  - 100 Hz × 10 分程度の連続ログで、復元不能行（エラー行）が **0** である。
  - 復元後の `E_total_mJ` を再積分した結果が、従来ログの `E_total_mJ` と **±1% 以内** に収まる。

---

### A‑3. 単位の整合（p_mW vs E_total_mJ のスケール監査）

- **Why**  
  diag の `mean_p_mW` と summary の `E_total_mJ` の桁を突き合わせると、ラベル上 mW と書いてあっても実質 µW スケールを扱っている可能性がある。**表示ラベル／計算式／保存単位**を一度きちんと揃えておきたい。

- **What**  
  単位監査用のスクリプト（Invariants チェッカー）を作る。

  - I1: `E_total_mJ ≈ ∑ p_mW × (dt_ms / 1000)` が **±1%** 以内。
  - I2: `mean_p_mW × (ms_total / 1000) ≈ E_total_mJ` が **±1%** 以内。
  - I3: `mean_p_mW` の値域が物理的に妥当（数百 mW レンジ）になっているか。明らかな桁ズレがあれば「単位ラベル不一致」として警告。
  - いずれかが NG の場合:
    - diag のラベル修正（例: 実値が µW なら `mean_p_µW` に改名）、または
    - 計算式側の修正（/1e3 ↔ /1e6 等）を Issue 化して切り分ける。

- **DoD**
  - I1〜I3 がすべて OK になるか、そうでない場合も「どのスケールで一貫しているか」が明示される。
  - `docs/フェーズ0-0/実験装置最終仕様書.md` とスクリプトの単位記述が整合している。
  - 進捗: `scripts/check_units.py` 実装済み。diag mean_p を µW→mW へ 1/1000 補正で I2 整合、TXSD互換パーサで I1=±0.01% 程度に収束（1m_on_05）。今後は他セットへ適用。

---

### A‑4. 旧ログ互換レイヤ（ヘッダ差分・メタ不足の吸収）

- **Why**  
  旧ログは `ms,mv,uA,p_mW` 表記や `adv_interval_ms` メタ欠損が残っている。新ログは `ms,mV,µA,p_mW`＋`adv_interval_ms` 付き。**同じ前処理で扱えるようにする吸収レイヤが必要**。

- **What**  
  ローダ側で方言を吸収する。

  - ヘッダ alias: `mv → mV`, `uA → µA`、`p_mW` はそのまま。
  - メタ欠損時: TICK や `t_ms/ADV_INTERVAL_MS` から `adv_interval_ms` を推定し、正規化メタとして付与。
  - ローディング時に「正規化済み trial オブジェクト」を返すインタフェースに揃える。

- **DoD**
  - 旧ログと新ログが混在するディレクトリを渡しても、ローダが自動で正規化して落ちない。
  - 下流の集計コードは「正規化済み」表だけを見ればよくなる。

---

### A‑5. 500 ms 内のクラスター分割とルール化

- **Why**  
  `1m_on_500_02` のように、同一 500 ms 条件でも `mean_i` と `E_total_mJ` が「低電流クラスタ」と「高電流クラスタ」に分かれている。これを 1 本の 500 ms 条件として平均すると代表性が崩れる。

- **What**  
  条件内クラスタリングを行い、セット分割または後半除外をルール化する。

  - 指標: `mean_i`, `E_total_mJ`（必要なら `E_per_adv_µJ` を追加）で K=2 のクラスタリング。
  - 低電流群 / 高電流群のどちらを「正」とみなすか（ex: 低電流群を標準とし、高電流群は `exclude_reason: [high_baseline_current_cluster]`）。
  - Manifest に `cluster_id` を持たせる。

- **DoD**
  - 同一 set_id 内で「include=true の trial だけを見ると、`mean_i` と `E_total_mJ` が ±15% 程度の帯域に収まる」状態になっている。
  - 500 ms 系の ΔE/adv 集計がクラスタに依存しない形で解釈できる。

---

## B) KPIパイプライン：ΔE/adv と受信品質（優先度: 高）

### B‑0. サマリテーブル（一次集約の土台）

- **Why**  
  A 系の選別と単位監査の結果をひとつの表に集約し、B‑1/B‑2 の入力を安定化させる。

- **What**  
  `trials_summary.parquet`（またはCSV）を生成するスクリプトを作る。

  - 1 行 = 1 trial。
  - カラム例:
    - `set_id, interval_ms, ms_total, samples, rate_hz, adv_count, mean_v, mean_i, mean_p, E_total_mJ, E_per_adv_µJ, include, exclude_reason[], cluster_id`
  - `adv_count` は TICK を優先し、TICK がない場合は `t_ms/ADV_INTERVAL_MS` から推定。

- **DoD**
  - B‑1/B‑2 のスクリプトが、この表だけを読めば動く状態になる。

---

### B‑1. ΔE/adv 自動算出（主KPI）

- **Why**  
  省電力評価の主語。ON/OFF の差分を 1 ADV あたりに正規化して比較する。

- **What**  
  `compute_delta_energy.py`（仮）を実装する。

  - ON/OFF のペアリング:
    - 距離・環境・interval_ms で OFF 側の代表値（平均 or 中央）を特定。
  - 計算式:
    - `ΔE/adv = (E_ON_trial − E_OFF_ref) / N_adv`
    - 単位は µJ/adv 推奨（mJ/adv でも可）。
  - 出力:
    - 条件別の平均・分散・95% CI。
    - 箱ひげ or バイオリン図。
    - CSV/Parquet の表。

- **DoD**
  - `adv_interval ∈ {100, 500, 1000, 2000} @ 1m` の ΔE/adv がすべて出力される。
  - Manifest の include フラグ適用後の値で、階段構造（省電力の傾向）が解釈可能になっている。

---

### B‑2. 受信品質（PDR / TL / Pout(τ)）

- **Why**  
  エネルギーだけでなく、受信側の品質を同じ行で比較するため。

- **What**  
  `compute_rx_quality.py`（仮）を実装する。

  - 重複除去窓 = `3 × ADV_INTERVAL_MS`。
  - PDR:
    - TICK があれば TICK ベースの期待値、無い場合は `t_ms/ADV_INTERVAL_MS` からの期待値を使用。
  - TL/Pout:
    - アクティビティ変化トリガ（実験ログに応じて）から見た TL 分布。
    - `Pout(τ)`（例: τ=1/2/3 秒）の算出。
  - B‑0 のサマリ表へ join し、**ΔE/adv・PDR・Pout(τ)・TL p50/p95** を横並びにする。

- **DoD**
  - 各条件で ΔE/adv と PDR/TL/Pout(τ) が同じ行で理解できる統合KPI表ができている。
  - Runbook 側に「この表を見て解釈する手順」が簡潔に追記できる。

---

## C) 根治：計測系の堅牢化（優先度: 中〜高）

### C‑1. ASCII 固定長化 →（必要なら）バイナリ＋CRC

- **Why**  
  A‑2 の軽量対処だけでは不十分な場合に備えた根治策。UART 経路での文字化けを構造的に防ぐ。

- **What**

  - C‑1a: TX の UART 出力を **固定桁**（例: `%04d,%06d\n`）にし、TXSD で **行長・桁長・簡易チェックサム（LRC 等）** を検査。
  - C‑1b: 必要になった段階で、STX/len/payload/CRC/ETX 形式のバイナリプロトコルに移行する。

- **DoD**
  - 230400 bps で 1 時間連続計測しても `parse_drop=0`・文字化け=0 が確認できる。
  - 変更後の仕様が `docs/フェーズ0-0/実験装置最終仕様書.md` に反映されている。

---

### C‑2. LED/SYNC の統一と再計測設計

- **Why**  
  旧 100 ms コードと Sweep 版で LED 常点灯 vs パルスのみ などの差があると、ベースラインがズレる可能性がある。

- **What**

  - Sweep 版 TX コード側で trial 中の LED 常点灯を廃止し、旧 100 ms コードの `syncPulse()` に近い形（境界パルスのみ）に揃える。
  - 統一後のコードで 100/500/1000 ms 条件を再取得し、階段構造が LED 差に依存していないか確認する。

- **DoD**
  - ΔE/adv の階段構造（100 > 500 > 1000…）が LED/SYNC 挙動を揃えた上で再確認されている。
  - 仕様書に LED/SYNC 挙動の統一方針が明記される。

---

### C‑3. TICK/同期のリグレッションテスト

- **Why**  
  TICK は ADV カウントのゴールドスタンダード。割込み取りこぼしやパルス幅不足がないかを継続的に確認したい。

- **What**

  - TICK パルス幅の境界値（例: 150µs / 200µs / 250µs）での受信安定性テストを自動化する。
  - `advCountISR` と理論値（`N_ADV_PER_TRIAL`）との差分を試験ログに残す。

- **DoD**
  - 試験スイートで全条件 Green（取りこぼし無し）が確認される。
  - Runbook に TICK の検証項目が追記されている。

---

## D) 運用整備：自動チェック・ドキュメント（優先度: 中）

### D‑1. ログ健全性チェッカー

- **Why**  
  これまで手作業で見ていた #diag/#summary の整合性チェックを自動化して、漏れを防ぐ。

- **What**

  - `check_logs.py`（仮）で、以下を検査:
    - `samples ≈ ms_total / 10`（100 Hz 前提）
    - `rate_hz = 100 ± 10%`
    - `parse_drop=0`
    - `dt_ms_min ≥ 0`, `dt_ms_max ≤ 60` など

- **DoD**
  - 任意のログディレクトリに対して一発で OK/NG と理由が出せる。
  - 可能であれば CI に組み込む。

---

### D‑2. Runbook / 仕様書のアップデート

- **Why**  
  既知の計測系課題（文字化け・単位・外れ trial・旧ログ方言）と、その回避策（Manifest, 復元, 単位監査, ログチェッカー）をドキュメントに反映しておく。

- **What**

  - `docs/フェーズ1/Runbook.md` / `docs/フェーズ0-0/実験装置最終仕様書.md` に:
    - Phase 0‑0 データの既知問題と、分析時の扱い方
    - 単位監査（A‑3）で使う Invariants の概要
    - 旧ログと新ログの取り扱いポリシー
  を追記。

- **DoD**
  - 新しく入った人がドキュメントだけ読んで、同じ前提・同じフィルタで解析を走らせられる。

---

## E) 研究タスク：非理想スキャン / interval 探索（優先度: 低〜中）

### E‑1. 150 ms など非整数倍 interval の評価

- **Why**  
  BLE interval 単位（0.625 ms）への丸めが実装されたので、150/300/750 ms などを試し、高調波関係の回避や Valley Area の変化を見たい。

- **What**

  - 150/300/750 ms などを追加条件として測定し、ΔE/adv と Pout(τ) を既存 100/500/1000/2000 ms と並べて評価する。

- **DoD**
  - “素数系 or 非整数倍 interval” が高調波由来の Valley Area をどの程度回避できるか、簡単な表や図で説明できる。

---

### E‑2. Opportunistic Scan 前提の品質KPI再検討

- **Why**  
  Android/iOS の実装上、実効スキャンウィンドウは他アプリとの合成（Opportunistic Scan）で時間変動する。PDR/TL/Pout の再現性を評価するには、端末・モードごとの振る舞いを整理しておく必要がある。

- **What**

  - Pixel/Galaxy/iPhone など主要端末ごとに、前景/背景・スキャンモード別の**最低限のテストマトリクス**を作る。
  - Runbook に「Opportunistic Scan 前提」「端末内 A/B 比較で完結させる」旨と簡単なチェックポイントを追加。

- **DoD**
  - 端末差による指標のブレ（PDR/TL/Pout）の範囲を定量的に示した表が作成されている。
