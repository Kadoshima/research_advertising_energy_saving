# D4B Pout tail decomposition (TL>1.0s)

- input: `uccs_d4b_scan90/plots/outage_story_01/per_transition.csv` / `uccs_d4b_scan90/plots/outage_story_01/outage_ranking.csv`
- output dir: `uccs_d4b_scan90/plots/pout_tail_01`

## Trial-level outage counts

- Policy (U+CCS): mean pout_est=0.0488 (n_trials=3)
- U-only (CCS-off): mean pout_est=0.0650 (n_trials=3)

## Concentration across transitions

- #transitions with positive ΔPout (U-only worse): 2 / 41 total transitions
- top-1 explains 50.0% of positive ΔPout; top-2 explains 100.0%
- see `fig_delta_pout_cum.svg` + `delta_pout_contrib.csv`

## Figures

- `fig_outage_count_hist.svg`: outage-count distribution per trial
- `fig_delta_pout_cum.svg`: cumulative ΔPout concentration curve (top-K transitions)

