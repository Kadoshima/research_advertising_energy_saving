# エッジHAR TODO（Mode C2′ / ストレス固定 / 因果CCS・self-UCB 実機検証）

- 最終更新: 2025-12-13
- 対象スコープ:
  - **Mode C2′（ラベル再生）**を用いた「広告間隔制御」の評価（固定 vs 因果CCS vs self-UCB）。
  - まずは **ストレスラベル S1/S4** を主ケースとして、実測とシミュを整合させて論文化に耐える形にする。

- このファイルの役割:
  - **次に何をするか**（優先度付きTODO）を管理する。
  - **凍結した仕様/パラメータ**と、再検討トリガを残す。
  - 実験ログは `logs/worklog_*.txt`、決定理由は `docs/decision_log_*.md` に残す。

---

## 0. TL;DR（いま何が言えるか）

### 0.1 2次情報（他AIに渡してもよい粒度）

- **因果CCS（stress causal）シミュレーション**は完了。
  - 生成: `scripts/generate_modec2_stress_causal.py`
  - ラベル/真値: `Mode_C_2_シミュレート_causal/ccs/stress_causal_S1..S6.csv` と `manifest_stress_causal.json`
  - シミュ集計: `Mode_C_2_シミュレート_causal/sim_timeline_metrics_causal_agg.csv`
    - FIXED_100: acc=1.0
    - FIXED_500: acc≈0.972, TL_mean≈2.9s
    - FIXED_1000: acc≈0.935, TL_mean≈5.3s
    - FIXED_2000: acc≈0.870, TL_mean≈9.4s
    - CCS_causal: acc≈0.916, TL_mean≈6.8s
  - PDRスイープ: `Mode_C_2_シミュレート_causal/sim_timeline_metrics_causal_pdr_sweep.csv`（順位が崩れないことを確認）

- **固定間隔の電力基準（ΔE/adv）**は Mode_C の実測を参照する方針で固定。
  - 参照: `data/1202配線変更後/Mode_C_2_03/pdr_energy_summary.csv`
  - 例（E_per_adv_uJ_mean）: 100ms ≈ 19,872µJ / 500ms ≈ 96,739µJ / 1000ms ≈ 197,036µJ / 2000ms ≈ 394,850µJ

- **実機：ストレス固定（scan90%）フルセット（S1/S4×100/500/1000/2000）**が揃っており、解析も完了。
  - データ: `data/1211_modeC2prime_stress_fixed/full_scan90/`
  - per-trial: `results/stress_causal_real_summary_1211_stress_full_scan90.csv`
  - 集約: `..._modes_scan90.csv`, `..._agg_scan90.csv`, `..._agg_enriched_scan90.csv`
  - 現状の読みどころ:
    - 100ms の `pdr_unique` が **0.80前後まで改善**（scan duty 90% が効いた）
    - 500/1000/2000 は `pdr_unique` がほぼ 1.0（TXSD adv_count 基準でクランプしている前提）
    - ただし **TL/Pout が想定より大きい**（ストレス列の遷移の扱い／真値定義／サブサンプルの有無の確認が必要）

### 0.2 2025-12-13 追記（レター最速ルートの意思決定）

- レター最速ルートは「**U/CCS→interval（ルールベース）を主結果**」に寄せる（Safe-MABはFuture Work）。
  - 決定ログ: `docs/decision_log_2025-12-13_letter_route.md`
- 固定intervalの電力テーブル（sleep_eval, n=2）を取得し、オフライン評価の power 軸を置換可能にした。
  - power table: `results/mhealth_policy_eval/power_table_sleep_eval_2025-12-13.csv`
  - Pareto（power_table反映 + context mixing）: `results/mhealth_policy_eval/pareto_front_v5_power_table/pareto_summary.md`
  - 重要: 電力低下の主効果は 100→500ms。500→2000msは小さい（=「100ms滞在を減らす」設計が効く）。

### 0.2 いま残っている一番重要な論点

- **TL/Pout の「定義」と「実装」が論文で説明できる形に固定されているか**
  - 例: 2000ms で `Pout(1s)` に理論下限が出るかどうかは、
    - 「遷移を 100ms 真値で取る（連続時間に近い評価）」なのか
    - 「TXが実際に送ったサブサンプル列で遷移を取る（可観測遷移のみ評価）」なのか
    で結論が変わる。
  - ここを曖昧にすると、**scan90 の改善や CCS/self-UCB の優位性を主張できない**。

### 0.3 次のゲート（ここを超えると後半が楽）

- Gate-0（図表の土台）: 
  - scan90 固定フルセットを **「定義が固定された指標」**で集約し、
  - 実測 vs シミュの差（桁差）が **説明可能な仮説**（burst loss / 可観測性 / 真値の粒度）で書ける。

---

## 1. 凍結仕様（再現性のために明文化）

### 1.1 解析指標（PDR/TL/Pout）

- `adv_count` は **TXSD の summary** を真値とする（RX側で再推定しない）。
- `pdr_raw` / `pdr_unique` を併記する。
  - `pdr_raw = min(rx_count, adv_count) / adv_count`（重複込みの受信量。>1 を避けるためクランプ）
  - `pdr_unique = min(rx_unique_seq, adv_count) / adv_count`（seqユニークのカバレッジ指標）
- TL/Pout は「どの真値の遷移」を対象にしているかが本質。
  - **現行実装の定義を `docs/metrics_definition.md` に固定**し、
  - もし実装が「サブサンプル真値」になっているなら、その意図を明記する。

> TODO（重要）: `scripts/analyze_stress_causal_real.py` が遷移抽出に使う truth が
> - 100msの完全列なのか
> - interval stepCount で間引いた列なのか
> を 1回確認して、ドキュメント定義と一致させる。

### 1.2 truth 長さ（末端遷移）

- TX は `EFFECTIVE_LEN=6352`（100msステップ）で再生範囲をクランプ。
- truth も同じ長さにクリップする（末端遷移が TX 範囲外に出て TL が暴れるのを防ぐ）。

### 1.3 因果CCS（A-3 凍結）

- CCS 形: `CCS = 0.7*(1−U) + 0.3*S`
- `S_causal = clip(time_since_last_transition / 5.0, 0, 1)`
- `U_causal = clip(1 − S_causal + N(0, 0.05^2), 0, 1)`
- `T_adv` 写像（stress凍結）:
  - CCS < 0.30 → 100ms
  - 0.30 ≤ CCS < 0.70 → 500ms
  - CCS ≥ 0.70 → 2000ms
- stressケースでは **ヒステリシス無し**（まずは評価を簡単にするため）

### 1.4 RX スキャン設定（scan90 を主）

- `RX_ModeC2prime_1210`:
  - `SCAN_INTERVAL_MS=100, SCAN_WINDOW_MS=90`（duty 90%）
  - `ActiveScan=false`, duplicate filter OFF
- scan50 のデータは「改善前の参考」として残し、主張は scan90 で行う。

### 1.5 再検討トリガ（値を変えるべき時）

- CCSパラメータ（閾値/重み）
  - **固定フルセット（scan90）と同じ定義の TL/Pout** で CCS_causal が FIXED_500/1000 に勝てない場合
  - 2000ms 偏重で missed-state が増えすぎる場合
- RX設定
  - scan90 でも 100ms の `pdr_unique < 0.7` が再発する場合（環境起因 vs 設定起因を切り分け）
- 指標定義
  - `Pout(1s)` の下限議論が食い違う場合 → まず定義/実装を揃える（パラメータ調整ではなく）

---

## 2. 成果物インデックス（場所が分かることが最優先）

### 2.1 実機データ

- scan90 固定フルセット: `data/1211_modeC2prime_stress_fixed/full_scan90/`
  - RX: `RX/rx_trial_042..049.csv`
  - TXSD: `TX/trial_048_on..055_on.csv`
  - manifest: `manifest.csv`（S1/S4 × 100/500/1000/2000 の対応）

### 2.2 実機解析出力

- per-trial: `results/stress_causal_real_summary_1211_stress_full_scan90.csv`
- 集約（modes/agg/enriched）:
  - `results/stress_causal_real_summary_1211_stress_modes_scan90.csv`
  - `results/stress_causal_real_summary_1211_stress_agg_scan90.csv`
  - `results/stress_causal_real_summary_1211_stress_agg_enriched_scan90.csv`
- gap 統計: `results/gap_stats_scan90.csv`
- missed-state（定義を固定した版）: `results/missed_state_scan90_v2.csv`

### 2.3 シミュレーション

- `Mode_C_2_シミュレート_causal/`
  - `ccs/stress_causal_S*.csv`
  - `sim_timeline_metrics_causal_agg.csv`
  - `sim_timeline_metrics_causal_pdr_sweep.csv`

### 2.4 スクリプト

- `scripts/generate_modec2_stress_causal.py`（因果CCS生成）
- `scripts/analyze_stress_causal_real.py`（RX/TXSD→PDR/TL/Pout/E/Power）
- `scripts/plot_stress_causal_real_vs_sim.py`（実測vsシミュ図表、matplotlib）
- `scripts/export_labels_all_to_csv.py`（labels_all.h→truth CSV; EFFECTIVE_LEN でclip）

---

## 3. 優先度付き TODO（最短で論文化できる順）

> 記法: (ME)=実機/配線/取得が必要、(AI)=ローカル処理・解析のみ、(ME+AI)=両方

### P0: 定義固定 + 図表化（最優先）

- [ ] (AI) **TL/Pout の真値定義を確定**
  - `analyze_stress_causal_real.py` の truth 遷移抽出が「100ms真値」か「サブサンプル真値」かを確認
  - `docs/metrics_definition.md` と一致させる（必要なら修正して再解析）
  - ここが確定するまで、TL/Pout を主張の中心に置かない（図にも注記）

- [ ] (AI) scan90 固定フルセットの図表（論文用）を確定
  - 図1: intervalごとの `pdr_unique`, `Pout(1s)`, `TL_mean`, `E_per_adv`, `avg_power`
  - 図2: 実測 vs シミュ（pdr_sweep から最接近でマッチ）比較（`results/compare_*` を再生成）
  - 図3: scan50→scan90 の改善（特に 100ms の pdr_unique）

- [ ] (AI) 「実測がシミュより悪い」説明の文章骨子を作る
  - 候補: burst loss（時間相関ロス）、可観測遷移の欠落（間引き）、干渉・スキャン窓
  - どれが効いているかは gap_stats / missed-state / 実測の重尾（p95/max）で裏付ける

### P1: CCS_causal 実機（ストレス S1/S4）

- [ ] (ME+AI) TX に CCS_causal モードを追加（固定100/500/2000と同じI/Oでログが取れる形）
  - 実装方式: まずは **T_adv 列再生（オフライン決定）**が安全
  - 解析側は manifest に mode=`CCS_causal` を足すだけで回るようにする

- [ ] (ME) CCS_causal を S1/S4 で実行（E1）
  - 推奨: 1 trialずつ（10.6分×2本）→ まずは動作確認
  - その後、外れが大きい条件（2000偏重など）は追加1本

- [ ] (AI) 固定（scan90）と CCS_causal の比較表/図（同指標・同定義）
  - 主張の形: 「同電力でQoS↑」or「同QoSで電力↓」のどちらかに寄せる

### P2: self-UCB（不確実性駆動）

- [ ] (AI) self-UCB の設計（状態・報酬・制約）を 1ページで固定
  - 状態候補: (S,U,CCS,直近遷移からの時間, gap統計)
  - 報酬候補: −λ·E + QoS（遅延/アウトエイジ）
  - まずはシミュで λ をスイープして Pareto を出す

- [ ] (ME+AI) self-UCB の TX 実装（まずはオフラインpolicy再生でも可）

### P3: チャネル劣化（E2/E3）

- [ ] (ME) PDR を意図的に落とす環境を 1種類だけ固定（距離/遮蔽/干渉）
- [ ] (ME) 固定100 と CCS_causal と self-UCB を最小本数で比較（各1本）

### P4: 論文・スライド

- [ ] (AI) 章立てに合わせて図表を配置（少なくとも「固定 vs CCS_causal」を主結果に）
- [ ] (AI) 実装詳細（指標定義/凍結パラメータ/配線）を Appendix に逃がす

---

## 4. Done（主要な完了項目）

- [x] 因果CCSのストレス生成（A-1）
- [x] 因果CCSシミュ（PDR=1）＋集約（A-1/A-2）
- [x] A-3（CCS形/しきい値/重み）凍結
- [x] A-4（PDRスイープ）で順位安定性チェック
- [x] 実機解析スクリプト `analyze_stress_causal_real.py` の整備（pdr_raw/pdr_unique対応、manifest対応）
- [x] ストレス固定フルセット（scan90）取得・解析（S1/S4×100/500/1000/2000）

---

## 5. 付記（運用ルール）

- **データ命名**: 解析が走る最小情報を `manifest.csv` に持たせる（trial_id/セッション/interval/真値/モード）。
- **短いabort試行**は `manifest` から除外（残す場合は `mode=ABORT` 等で明示）。
- **1本増やす前に**: 指標定義と解析の一致を優先（同じバグを増幅させない）。
