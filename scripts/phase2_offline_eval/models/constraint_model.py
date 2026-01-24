"""
Constraint model for Phase 2 offline bandit evaluation.

We model the QoS constraint as:
  g(a) = Pout(tau | a) = Pr[TL > tau]

This implementation is intentionally data-driven:
- If a source provides per-trial Pout columns (pout_1s/pout_2s/pout_3s), we
  aggregate them per fixed advertising interval.
- If a source is a directory with RX logs (RX/*.csv), we infer the fixed interval
  from (seq, ms) slope and compute synthetic TL samples from periodic "events"
  (default: every 60s), then derive Pout(tau).

No placeholder constants are used.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def _mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return float("nan"), float("nan")
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return mean, std


def _parse_seq_from_mfd(mfd: str) -> Optional[int]:
    # Examples: "MF000A", "000A"
    if not isinstance(mfd, str):
        return None
    s = mfd.strip()
    if s.startswith("MF"):
        s = s[2:]
    try:
        return int(s, 16)
    except Exception:
        return None


def _estimate_interval_ms(first_ms_by_seq: Dict[int, float]) -> Optional[float]:
    if len(first_ms_by_seq) < 5:
        return None
    seq0 = min(first_ms_by_seq)
    ms0 = first_ms_by_seq[seq0]
    slopes: List[float] = []
    for seq, ms in first_ms_by_seq.items():
        if seq == seq0:
            continue
        dseq = seq - seq0
        if dseq <= 0:
            continue
        slopes.append((ms - ms0) / dseq)
    return median(slopes) if slopes else None


def _map_to_nominal_interval_ms(est_interval_ms: float, candidates_ms: List[int]) -> Optional[int]:
    if est_interval_ms is None or not candidates_ms:
        return None
    best = min(candidates_ms, key=lambda a: abs(est_interval_ms - a))
    # Accept if within 20% of a known candidate; otherwise treat as non-fixed/dynamic.
    if abs(est_interval_ms - best) / best > 0.20:
        return None
    return int(best)


def _estimate_offset_ms(first_ms_by_seq: Dict[int, float], interval_ms: int) -> Optional[float]:
    deltas = [seq * interval_ms - ms for seq, ms in first_ms_by_seq.items() if seq > 0]
    return median(deltas) if deltas else None


def _compute_tl_samples_ms(
    rx_ms: List[float],
    offset_ms: float,
    duration_ms: float,
    event_period_ms: int,
) -> List[float]:
    if not rx_ms or duration_ms <= 0:
        return []

    rx_aligned = sorted((t + offset_ms) for t in rx_ms)
    tl_samples: List[float] = []
    for t_event in range(event_period_ms, int(duration_ms), int(event_period_ms)):
        tl = float("inf")
        for t in rx_aligned:
            if t > t_event:
                tl = t - t_event
                break
        tl_samples.append(tl)
    return tl_samples


@dataclass(frozen=True)
class _PoutStats:
    mean: float
    std: float
    n: int  # number of per-trial samples used to estimate mean/std


class ConstraintModel:
    SUPPORTED_TAUS_S = (1.0, 2.0, 3.0)
    DEFAULT_EVENT_PERIOD_MS = 60_000  # used by existing fixed-interval analyses
    DEFAULT_INTERVAL_CANDIDATES_MS = (100, 500, 1000, 2000)

    def __init__(self, data_paths: List[str], tau: float = 1.0):
        self.data_paths = [Path(p) for p in data_paths]
        self.tau = float(tau)

        # action -> tau_s -> stats
        self._stats: Dict[int, Dict[float, _PoutStats]] = {}
        # action -> TL samples in ms (optional; only for sources we can derive TL from)
        self._tl_samples_ms: Dict[int, List[float]] = {}
        # action -> tau_s -> list of per-trial Pout values (only for RX-derived sources)
        self._rx_trial_pout: Dict[int, Dict[float, List[float]]] = {}

        self._load_from_sources()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def predict(self, action: int) -> float:
        """Return mean Pout(tau|action)."""
        tau = self.tau
        if action in self._stats and tau in self._stats[action]:
            return self._stats[action][tau].mean

        if action in self._tl_samples_ms and self._tl_samples_ms[action]:
            tau_ms = tau * 1000.0
            tls = self._tl_samples_ms[action]
            return sum(1 for tl in tls if tl > tau_ms) / len(tls)

        raise ValueError(f"Action {action}ms not found (tau={tau}) in constraint model")

    def std(self, action: int) -> float:
        """Return std of per-trial Pout(tau|action) when available; otherwise 0."""
        tau = self.tau
        if action in self._stats and tau in self._stats[action]:
            return self._stats[action][tau].std
        return 0.0

    def n_samples(self, action: int) -> int:
        """Return number of trials used for Pout aggregation (not TL sample count)."""
        tau = self.tau
        if action in self._stats and tau in self._stats[action]:
            return self._stats[action][tau].n
        return 0

    def sample_violation(self, action: int, rng: np.random.Generator) -> float:
        """Sample a constraint violation indicator I[TL > tau]."""
        p = self.predict(action)
        return float(rng.random() < p)

    def confidence(self, action: int) -> float:
        """A rough standard-error term for plotting / simple UCB-style checks."""
        n = self.n_samples(action)
        if n <= 0:
            return 0.0
        return self.std(action) / np.sqrt(n)

    def is_safe(self, action: int, epsilon: float) -> bool:
        """Return True if (mean + confidence) <= epsilon."""
        pout_ucb = self.predict(action) + self.confidence(action)
        return pout_ucb <= epsilon

    # ---------------------------------------------------------------------
    # Loading
    # ---------------------------------------------------------------------
    def _load_from_sources(self) -> None:
        table_paths: List[Path] = []

        for p in self.data_paths:
            if not p.exists():
                print(f"Warning: constraint source not found: {p}")
                continue

            if p.is_file() and p.suffix.lower() == ".csv":
                table_paths.append(p)
                continue

            # uccs_* datasets: read any per_trial.csv under metrics/
            metrics_dir = p / "metrics"
            if metrics_dir.exists():
                table_paths.extend(sorted(metrics_dir.glob("**/per_trial.csv")))

            # RX-log based datasets: attempt to parse RX/*.csv
            rx_dir = p / "RX"
            if rx_dir.exists():
                self._load_from_rx_dir(rx_dir)

        # Aggregate any table sources found
        for csv_path in table_paths:
            self._load_from_pout_table(csv_path)

        # RX-derived sources: aggregate per-trial Pout values (preferred) and fill stats.
        for action, by_tau in self._rx_trial_pout.items():
            self._stats.setdefault(action, {})
            for tau, vals in by_tau.items():
                if tau in self._stats[action]:
                    continue
                mean, std = _mean_std(vals)
                self._stats[action][tau] = _PoutStats(mean=mean, std=std, n=len(vals))

        # If we have TL-derived data but no stats (e.g., no per-trial Pout), create stats from TL samples.
        for action, tls in self._tl_samples_ms.items():
            if not tls:
                continue
            self._stats.setdefault(action, {})
            for tau in self.SUPPORTED_TAUS_S:
                if tau in self._stats[action]:
                    continue
                tau_ms = tau * 1000.0
                pout = sum(1 for tl in tls if tl > tau_ms) / len(tls)
                std = float(np.sqrt(pout * (1.0 - pout))) if len(tls) > 1 else 0.0
                self._stats[action][tau] = _PoutStats(mean=pout, std=std, n=len(tls))

        if not self._stats:
            raise RuntimeError("ConstraintModel: no usable constraint data was loaded")

    def _load_from_pout_table(self, csv_path: Path) -> None:
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"Warning: failed to read constraint table: {csv_path} ({e})")
            return

        # Normalize: ensure interval_ms column exists for FIXED_* rows.
        if "interval_ms" not in df.columns and "mode" in df.columns:
            m = df["mode"].astype(str).str.extract(r"FIXED[_-](\d+)", expand=False)
            df = df.assign(interval_ms=pd.to_numeric(m, errors="coerce"))

        if "interval_ms" not in df.columns:
            return

        # Keep only fixed rows when possible.
        if "mode" in df.columns:
            df = df[df["mode"].astype(str).str.startswith("FIXED")]

        tau_cols = {
            1.0: "pout_1s",
            2.0: "pout_2s",
            3.0: "pout_3s",
        }
        available_tau_cols = {tau: col for tau, col in tau_cols.items() if col in df.columns}
        if not available_tau_cols:
            return

        for action, g in df.groupby("interval_ms"):
            if pd.isna(action):
                continue
            action_i = int(action)
            self._stats.setdefault(action_i, {})
            for tau, col in available_tau_cols.items():
                vals = [float(v) for v in g[col].dropna().tolist()]
                if not vals:
                    continue
                mean, std = _mean_std(vals)
                self._stats[action_i][tau] = _PoutStats(mean=mean, std=std, n=len(vals))

    def _load_from_rx_dir(self, rx_dir: Path) -> None:
        rx_paths = sorted(rx_dir.glob("*.csv"))
        if not rx_paths:
            return

        candidates = list(self.DEFAULT_INTERVAL_CANDIDATES_MS)

        for rx_path in rx_paths:
            rx_ms: List[float] = []
            first_ms_by_seq: Dict[int, float] = {}

            try:
                with open(rx_path, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(line for line in f if not line.startswith("#"))
                    for row in reader:
                        try:
                            ms = float(row.get("ms", ""))
                        except Exception:
                            continue
                        seq = _parse_seq_from_mfd(row.get("mfd", ""))
                        if seq is None:
                            continue
                        rx_ms.append(ms)
                        if (seq not in first_ms_by_seq) or (ms < first_ms_by_seq[seq]):
                            first_ms_by_seq[seq] = ms
            except Exception as e:
                print(f"Warning: failed to parse RX log: {rx_path} ({e})")
                continue

            if not rx_ms or len(first_ms_by_seq) < 5:
                continue

            est_interval = _estimate_interval_ms(first_ms_by_seq)
            if est_interval is None:
                continue
            nominal = _map_to_nominal_interval_ms(est_interval, candidates)
            if nominal is None:
                # Likely a dynamic-interval run; skip.
                continue

            offset_ms = _estimate_offset_ms(first_ms_by_seq, nominal) or 0.0
            duration_ms = max(t + offset_ms for t in rx_ms)
            tl_samples = _compute_tl_samples_ms(
                rx_ms,
                offset_ms=offset_ms,
                duration_ms=duration_ms,
                event_period_ms=self.DEFAULT_EVENT_PERIOD_MS,
            )
            if not tl_samples:
                continue

            self._tl_samples_ms.setdefault(nominal, []).extend(tl_samples)

            # Per-trial Pout values for supported taus
            for tau in self.SUPPORTED_TAUS_S:
                tau_ms = tau * 1000.0
                pout = sum(1 for tl in tl_samples if tl > tau_ms) / len(tl_samples)
                self._rx_trial_pout.setdefault(nominal, {}).setdefault(tau, []).append(pout)


if __name__ == "__main__":
    # Basic smoke test on the E2 fixed-sweep dataset (if present)
    model = ConstraintModel(
        ["data/実験データ/研究室/phase1_e2_fixed_sweep_2026-01-21_v01/"],
        tau=1.0,
    )
    for a in sorted(model._stats.keys()):
        print(a, model.predict(a), model.std(a), model.n_samples(a))
