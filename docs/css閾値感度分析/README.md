# CCSしきい値感度分析 実装仕様（グリッドスイープ版）

## 2025-12-03 更新メモ
- **CCS定義**: 本分析は v2 定義 `CCS = 0.6U + 0.4(1−S)` を基準とする。旧 `0.7(1−U)+0.3S` は歴史的案として扱う。
- **しきい値グリッド**: 分布準拠グリッド（θ_low≈0.001〜0.10, θ_high≈0.16〜0.40）＋代表ポリシー P1〜P3 を正式採用。以下に示す旧高域グリッドは「分布とミスマッチだった失敗例」として残す。
- **エネルギーモデル**: Phase0-0(row1120/1123_off)の ΔE/adv / P_off は破棄。再計測の v3 rig 基準を使用する（Mode B 待機ベース P_off≈23 mW をデフォルト、Mode A≈11.8 mW は下限として併記）。
- **ヒステリシス**: 本感度分析はヒステリシス無し・即時切替モデルのまま。実機ポリシ（Phase1）は min_stay=2s, ヒステリシス±0.05 を採用していることを明記する。

## 目的
- 要件定義に基づき、ヒステリシス無しの純粋なしきい値写像で (θ_low, θ_high) をグリッドスイープし、Pout–μC の感度をオフラインで評価する。
- 入力は mHealth ベースの U/S/CCS 時系列（0.5s刻み想定）と Phase0-0 の ΔE/adv, p_d。出力は KPI 表と Pout–μC 散布図＋Pareto フロント。

## 入力と前提
- CCS時系列: セッション単位で {t_s, CCS, U, S, label}（0.5s刻み）。存在しない場合は mHealth→HAR A0 から再生成（1.0s窓, 50%重畳）。
- イベント定義: Stationary ↔ (Locomotion|Transition) の遷移時刻をイベント起点とし、前後10s区間をイベント区間とみなす。イベント数 N_event も出力する。
- エネルギーモデル: Phase0-0 の ΔE/adv テーブル（100/500/1000/2000ms）から 1広告あたり電荷 q_adv(T) を使用。
- 受信成功率: p_d = 0.85（フェーズ0-0の下限）。Pout(τ|T) ≈ (1 − p_d)^⌊τ/T⌋ を用いる（理想スキャナ近似）。
- 評価 τ: 主に 2s、補助で 1s, 3s。

## しきい値グリッド
- θ_low ∈ {0.70, 0.75, 0.80, 0.85}
- θ_high ∈ {0.82, 0.86, 0.90, 0.94}
- 制約: θ_high − θ_low ≥ 0.06
- 写像: CCS≥θ_high→100ms, θ_low≤CCS<θ_high→500ms, CCS<θ_low→2000ms（ヒステリシス無し、即時切替）。

## 出力（KPI表カラム案）
- theta_low, theta_high
- w_100, w_500, w_2000 [%]（interval滞在比率）
- muC_event_mean, muC_event_std
- Pout_1s, Pout_2s, Pout_3s
- energy_saving_vs_100 [%] = 1 − muC_event_mean / muC_event_fixed100
- N_events（イベント数）
- notes（極端な2値化などの補足）

## 図表レイアウト
- 図1: Pout(2s)–μC/event 散布図。点=しきい値ペア、色=θ_high、形=θ_low。固定100ms/2000ms基準点と Pout=5% 制約線を重ねる。Pareto フロントを強調。
- 図2: しきい値平面ヒートマップ（カラー=省エネ率 1−μC/μC_fixed100）。必要なら別図で Pout(2s) ヒートマップ。
- 表1: KPI表（上記カラム）。滞在比率で「ほぼ2値」ケースが一目でわかるようにする。

## アルゴリズム擬似コード
```python
for sess in sessions:
    ccs_ts = load_ccs(sess)  # t, ccs, u, s, label
    events = detect_events(label, kind="Stationary<->(Loc|Trans)", pre=10, post=10)
    for tlow in theta_low_grid:
        for thigh in theta_high_grid:
            if thigh - tlow < 0.06: continue
            interval = map_ccs_to_adv(ccs_ts.ccs, tlow, thigh)  # 100/500/2000, no hysteresis
            w = dwell_ratio(interval)  # w_100, w_500, w_2000
            muC = sum(q_adv[T] for T in interval) / len(events)  # μC/event
            pout = {tau: sum(w[T]*(1-p_d)**floor(tau/T) for T in [100,500,2000]) for tau in [1,2,3]}
            save_row(sess, tlow, thigh, w, muC, pout, len(events))

# 集計
df = concat(rows).groupby(["tlow","thigh"]).aggregate(mean/std as needed)
add_energy_saving_vs_100(df, muC_fixed100)
plot_scatter(df["muC_event_mean"], df["Pout_2s"], color=thigh, marker=tlow)
plot_heatmap(df, value="energy_saving_vs_100")
```

## 実行手順（人間オペレーション）
1. CCS時系列を確認（存在しなければ mHealth→HAR 推論で生成）。
2. ΔE/adv テーブルと p_d=0.85 を設定。
3. 上記擬似コード相当で全セッションを処理し、KPI表を生成。
4. 図1/図2を描画し、Pareto フロント点と固定100/2000ms基準をマーク。
5. 表・図を `docs/css閾値感度分析/results` などに保存（PNG/SVG/CSV）。本文に引用。

## 注意・チェックリスト
- 滞在比率 w の極端化を確認（例: 100ms が 1% 未満など）。極端ケースは注記する。
- イベント数 N_events がしきい値で変わらないことを確認（変わる場合は理由を記載）。
- Pout モデルは理想化（i.i.d）。HIL節で非理想スキャンとの差分を説明する。
- Phase0-1 原本（docs/フェーズ0-1/）は参照のみ、派生ファイルは本ディレクトリ以下に置く。
