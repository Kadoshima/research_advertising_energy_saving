# Equation List (single-line for Word)

Each equation is on one line to ease copy into Word.
Inline math is excluded.

## chapters/appx_a_metrics.tex

- Lines: 10-13
```tex
}}$，seqでユニーク化した受信数を$N_{\mathrm{rx,uniq}}$とする． \begin{equation} \mathrm{PDR}_{\mathrm{raw}} = \frac{N_{\mathrm{rx}}}{N_{\mathrm{adv}}},\qquad \mathrm{PDR}_{\mathrm{unique}} = \frac{N_{\math
```

- Lines: 20-22
```tex
m{rx},j}$とする．ログ上の時刻はmsで記録されるため，TLは秒単位に変換して扱う． \begin{equation} \mathrm{TL}_j = \frac{t_{\mathrm{rx},j} - t_{\mathrm{eve
```

- Lines: 22-26
```tex
rm{s}] \end{equation} である．期限$\tau$に対する期限超過率は， \begin{equation} P_{\mathrm{out}}(\tau)=\frac{1}{N_{\mathrm{event}}}\sum_{j=1}^{N_{\mathrm{event}}
```

- Lines: 32-34
```tex
長を$T_{\mathrm{trial}}$とする．このとき評価に用いる真値系列の有効長を \begin{equation} \mathrm{EFFECTIVE\_LEN}=\min(T_{\mat
```

- Lines: 39-42
```tex
の観点では電荷で整理すると解釈が容易である． 電流を$I(t)$とすると，総電荷$Q$は \be
```

- Lines: 45-47
```tex
と定義する．TXSDログでは電流が$\mu$A，時刻がmsで記録されるため，離散近似として \begin{equation} Q_{\si{\micro\coulomb}} \approx \sum_{i} I_{\si{\micro\ampere},i}\cdot \frac{\Delta
```

- Lines: 51-53
```tex
ジング間隔による差分が総電荷に検出されにくい．このため，アドバタイジングONとOFFの差分 \begin{equation} \Delta Q = Q
```

- Lines: 57-59
```tex
L/Poutの評価対象となるイベント数を$N_{\mathrm{event}}$とすると， \begin{equation} q_{\mathrm{event}}=\fra
```

## chapters/ch2_proposed.tex

- Lines: 11-16
```tex
tainty}）． \subsection{複合スコアCCS} 不確実度と安定度から複合スコアCCSを構成する： \begin{equation
```

- Lines: 23-29
```tex
low}}$，$\theta_{\mathrm{high}}$とヒステリシス$h$を用いて，3段階の間隔に写像する： \begin{equation} a(\mathrm{CCS}) = \begin{cases} 2000\,\si{\milli\second} & (\mathrm{CCS}\ge\theta_{\mathrm{high}})\\ 500\,\si{\milli\second} & (\theta_{\mathrm{low}}\le\mathrm{CCS}<\theta_{\mathrm{high}})\\ 100\,\si{\milli\second} & (\math
```

## chapters/ch3_system_design.tex

- Lines: 56-59
```tex
(\pi)]$を目的関数，期限超過率$P_{\mathrm{out}}(\tau;\pi)$を制約として \begin{equation} \text{minimize}\quad \mathbb{E}[q_{\mathrm{event}}(\pi)] \quad \text{subject to}\quad
```

## chapters/ch6_stress_fixed.tex

- Lines: 11-15
```tex
ある． 補正後の手法では，受信ログのseqと期待時刻の差分の中央値をオフセットとして推定し，時刻を補正する： \begin{equation} \mathrm{offset} = \mathrm{median}(\mathrm{seq}\cdot\De
```

## chapters/ch7_offline_eval.tex

- Lines: 11-13
```tex
隔の電力テーブルと，方策の各間隔への滞在比率$\rho_\pi(a)$から，平均電力を推定する： \begin{equation} \overlin
```

## chapters/ch8_experiment_design.tex

- Lines: 96-100
```tex
t}}(\tau)$を整理する． イベント$j$の遅延を$\mathrm{TL}_j$とすると， \begin{equation} P_{\mathrm{out}}(\tau)=\frac{1}{N_{\mathrm{event}}}\sum_{j=1}^{N_{\mathrm{eve
```

- Lines: 105-107
```tex
，期限$\tau$内のアドバタイジング回数$\lfloor \tau/a \rfloor$を用いて \begin{equation} P_{\mathrm{out}}(\tau\mid a)\app
```

## chapters/ch9_har_uncertainty.tex

- Lines: 11-13
```tex
クラス数$K$で正規化したシャノンエントロピー\scite{shannon1948}として，以下のように定義する． \begin{equation} U(t) = -\fra
```

- Lines: 21-23
```tex
近$W$窓の推定ラベル列$\{\hat{y}_{t-W+1},\dots,\hat{y}_t\}$に対して遷移回数 \begin{equation} n_{\mathrm{tr}}(t)=\sum_{i=1}^{W-1} \mat
```

- Lines: 23-26
```tex
at{y}_{t-i}\neq \hat{y}_{t-i-1}\} \end{equation} を数え，安定度を \begin{equati
```

- Lines: 35-37
```tex
合スコアCCSは，確信度$(1-U)$と安定度$S$の線形結合として，係数$\alpha\in[0,1]$を用いて \begin{equation} \mathr
```
