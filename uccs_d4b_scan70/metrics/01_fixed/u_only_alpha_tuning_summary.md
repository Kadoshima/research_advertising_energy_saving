# U-only 閾値調整（追加データ無しの検討）: `uccs_d4b_scan70/data/01`

目的：D4B（scan70）の **U-only（CCS-off）** と **Policy（U+CCS）** を「同じα（=同じエネルギー配分）」に揃えて、CCSの効きを公平に比較する。

## 結論

- **追加データ無しで確認できる範囲では、U-only は既に Policy と同じ“mix度合い”になっている**。
- したがって、このrunでは **U-onlyの閾値を上げてαを揃える作業は不要**（むしろ閾値を動かすと“同条件”比較にならず説明が難しくなる）。

## 根拠（オフライン再生 + 実測ログ）

### 1) U-onlyの切替列は frozen U-series で再生できる

- U-series: `uccs_d2_scan90/src/tx/stress_causal_s1_s4_180s.h` の `S4_U_Q`（1800 steps, 100ms grid）
- U-only制御（TX実装）:
  - 500→100: `U_ema >= U_HIGH`
  - 100→500: `U_ema < (U_MID - HYST)`
  - `EMA_ALPHA=0.20`, `HYST=0.02`

この再生で **adv_count_est=1323** が得られ、実測の `adv_count=1323` と整合した。

### 2) adv_count に基づく正規化（イベント密度のα）は Policy と U-onlyで一致

180sで

- fixed100: `adv_count=1800`
- fixed500: `adv_count=360`
- policy/u-only: `adv_count=1323`

より

```
alpha_adv = (adv_count - 360) / (1800 - 360)
         ≈ (1323 - 360) / 1440
         ≈ 0.6687
```

PolicyとU-onlyは同じ `adv_count` なので **alpha_advも同一**。

## 注意（power-mix αとの差）

`summary_by_condition.csv` の `share100_power_mix_mean` は平均電力（TXSD）から算出しているため、run内の電圧・電流ドリフト等で Policy/U-only の値が僅かにズレることがある。
このrunでも `avg_power_mW` は 0.8mW 程度の差があり、`share100_power_mix_mean` が一致しないが、
**adv_countが一致しているので “制御が同じ割合で100/500を使っている” という意味では揃っている**。

## 生成物

- 閾値の簡易スイープスクリプト：`uccs_d4b_scan70/analysis/tune_u_only_alpha.py`

