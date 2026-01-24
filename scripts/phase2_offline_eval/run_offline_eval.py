"""
Phase 2 MVP Offline Evaluation - Main Script
Safe-UCBオフライン評価のメインスクリプト

実行方法:
    python scripts/phase2_offline_eval/run_offline_eval.py

出力:
    - results/phase2_offline_eval/*.png (図4枚)
    - results/phase2_offline_eval/summary.csv (数値結果)
"""

import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# modelsディレクトリをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from models.reward_model import RewardModel
from models.constraint_model import ConstraintModel
from models.safe_ucb import SafeUCB, UCB, FixedCCS, Oracle


def load_config(config_path: str) -> dict:
    """config.yamlを読み込む"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def run_simulation(algorithm, reward_model, constraint_model, T, epsilon, rng):
    """シミュレーション実行"""
    history = {
        "t": [],
        "action": [],
        "reward": [],
        "constraint_violation": [],
        "cumulative_reward": 0.0,
        "cumulative_violations": 0,
    }

    for t in range(T):
        # 行動選択（コンテキストは簡易的に固定）
        action = algorithm.select_action(context=0.5)

        # 報酬と制約をサンプル
        reward = reward_model.sample(action, rng)
        constraint_violation = constraint_model.sample_violation(action, rng)

        # 更新
        algorithm.update(action, reward, constraint_violation)

        # 履歴記録
        history["t"].append(t + 1)
        history["action"].append(action)
        history["reward"].append(reward)
        history["constraint_violation"].append(constraint_violation)
        history["cumulative_reward"] += reward
        history["cumulative_violations"] += constraint_violation

    return history


def plot_results(results, output_dir: Path, epsilon: float):
    """結果を図示"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 図1: 累積Regret推移
    plt.figure(figsize=(10, 6))
    oracle_cum_reward = np.cumsum(results["Oracle"]["reward"])

    for method in ["Safe-UCB", "UCB", "Fixed-CCS"]:
        cum_reward = np.cumsum(results[method]["reward"])
        regret = oracle_cum_reward - cum_reward
        plt.plot(results[method]["t"], regret, label=method, linewidth=2)

    plt.xlabel("Time step t", fontsize=12)
    plt.ylabel("Cumulative Regret", fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "regret_curve.png", dpi=300)
    plt.close()
    print(f"Saved: {output_dir / 'regret_curve.png'}")

    # 図2: 制約違反率推移
    plt.figure(figsize=(10, 6))
    for method in ["Safe-UCB", "UCB", "Fixed-CCS"]:
        violations = np.cumsum(results[method]["constraint_violation"])
        t_array = np.array(results[method]["t"])
        violation_rate = violations / t_array
        plt.plot(t_array, violation_rate, label=method, linewidth=2)

    plt.xlabel("Time step t", fontsize=12)
    plt.ylabel("Violation Rate", fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "violation_rate.png", dpi=300)
    plt.close()
    print(f"Saved: {output_dir / 'violation_rate.png'}")

    # 図3: 平均エネルギー推移（負の報酬 = エネルギー）
    plt.figure(figsize=(10, 6))
    for method in ["Safe-UCB", "UCB", "Fixed-CCS", "Oracle"]:
        cum_reward = np.cumsum(results[method]["reward"])
        t_array = np.array(results[method]["t"])
        avg_energy = -cum_reward / t_array  # 報酬は負のエネルギー
        plt.plot(t_array, avg_energy, label=method, linewidth=2)

    plt.xlabel("Time step t", fontsize=12)
    plt.ylabel("Average Energy [μJ/event]", fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "energy_curve.png", dpi=300)
    plt.close()
    print(f"Saved: {output_dir / 'energy_curve.png'}")

    # 図4: Warm-start comparison（段階2で実装予定）
    # 現時点ではプレースホルダー
    plt.figure(figsize=(10, 6))
    plt.text(
        0.5,
        0.5,
        "Warm-start Comparison\n(To be implemented in Stage 2)",
        ha="center",
        va="center",
        fontsize=16,
    )
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_dir / "warmstart_comparison.png", dpi=300)
    plt.close()
    print(f"Saved: {output_dir / 'warmstart_comparison.png'}")


def save_summary(results, output_dir: Path, epsilon: float):
    """数値結果をCSVで保存"""
    summary_data = []

    for method in ["Safe-UCB", "UCB", "Fixed-CCS", "Oracle"]:
        total_reward = np.sum(results[method]["reward"])
        total_violations = np.sum(results[method]["constraint_violation"])
        T = len(results[method]["t"])
        violation_rate = total_violations / T
        avg_energy = -total_reward / T  # μJ/event

        summary_data.append(
            {
                "method": method,
                "total_reward": total_reward,
                "avg_energy_uj": avg_energy,
                "total_violations": total_violations,
                "violation_rate": violation_rate,
                "constraint_satisfied": "OK" if violation_rate <= epsilon else "NG",
            }
        )

    df_summary = pd.DataFrame(summary_data)
    output_file = output_dir / "summary.csv"
    df_summary.to_csv(output_file, index=False)
    print(f"\nSaved: {output_file}")
    print("\n=== Summary ===")
    print(df_summary.to_string(index=False))


def main():
    # 設定読み込み
    config_path = "scripts/phase2_offline_eval/config.yaml"
    config = load_config(config_path)

    print("=== Phase 2 MVP Offline Evaluation ===\n")
    print(f"Config: {config_path}")
    print(f"Actions: {config['actions']}")
    print(f"Constraint: Pout(tau={config['constraint']['tau']}s) <= {config['constraint']['epsilon']}")
    print(f"Simulation steps: T={config['simulation']['T']}\n")

    # モデル初期化
    print("Loading models...")
    reward_model = RewardModel(config["data"]["reward_data"])
    constraint_model = ConstraintModel(
        config["data"]["constraint_data"], tau=config["constraint"]["tau"]
    )

    actions = config["actions"]
    epsilon = config["constraint"]["epsilon"]
    T = config["simulation"]["T"]
    seed = config["simulation"]["seed"]

    # アルゴリズム初期化
    print("\nInitializing algorithms...")
    algorithms = {
        "Safe-UCB": SafeUCB(actions, reward_model, constraint_model, epsilon, seed),
        "UCB": UCB(actions, seed),
        "Fixed-CCS": FixedCCS(actions, seed),
        "Oracle": Oracle(actions, reward_model, constraint_model, epsilon, seed),
    }

    # シミュレーション実行
    print("\nRunning simulations...")
    results = {}
    rng = np.random.default_rng(seed)

    for method, algorithm in algorithms.items():
        print(f"  {method}...", end="", flush=True)
        results[method] = run_simulation(
            algorithm, reward_model, constraint_model, T, epsilon, rng
        )
        print(" done")

    # 結果保存
    output_dir = Path(config["output"]["results_dir"])
    print(f"\nSaving results to {output_dir}...")
    plot_results(results, output_dir, epsilon)
    save_summary(results, output_dir, epsilon)

    print("\n[OK] Evaluation completed.")


if __name__ == "__main__":
    main()
