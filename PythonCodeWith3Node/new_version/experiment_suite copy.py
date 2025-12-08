#!/usr/bin/env python3
"""
Experiment suite for the hybrid fault-tolerance architecture.

Runs multiple scenarios and prints summary metrics that can be
directly used in the paper's Results section.
"""

import threading
import time
import statistics
from typing import Dict, Any, List

from coordinationlayer import MAPEKMQTTManager
from node import SimulatedNode

BASE_DISTANCE = 75.0   # cm, "true" distance
DURATION_S = 60        # seconds per scenario


def run_scenario(
    name: str,
    node_configs: List[Dict[str, Any]],
    duration_s: float,
    enable_self_healing: bool = True,
) -> Dict[str, Any]:
    """
    node_configs: list of dicts like:
    {
        "node_id": 1,
        "fault_mode": "normal" | "byzantine" | "drift" | "intermittent",
        "fail_after_s": 20.0 or None
    }
    """
    print(f"\n==================== SCENARIO: {name} ====================")

    manager = MAPEKMQTTManager(enable_self_healing=enable_self_healing)

    # Start manager
    manager_thread = threading.Thread(
        target=manager.start_for_duration,
        args=(duration_s,),
        daemon=True,
    )
    manager_thread.start()

    # Give manager time to connect + subscribe
    time.sleep(2)

    # Start nodes
    node_threads = []
    for cfg in node_configs:
        node = SimulatedNode(
            node_id=cfg["node_id"],
            base_distance=BASE_DISTANCE,
            fault_mode=cfg.get("fault_mode", "normal"),
            fail_after_s=cfg.get("fail_after_s", None),
        )
        node.connect()
        t = threading.Thread(
            target=node.loop_for_duration,
            args=(duration_s,),
            daemon=True,
        )
        t.start()
        node_threads.append(t)

    # Wait for completion
    manager_thread.join()
    for t in node_threads:
        t.join()

    # Build metrics summary
    metrics = manager.metrics
    consensus_vals = metrics["consensus_values"]

    if consensus_vals:
        mean_consensus = statistics.mean(consensus_vals)
        std_consensus = (
            statistics.pstdev(consensus_vals)
            if len(consensus_vals) > 1
            else 0.0
        )
        mean_abs_error = statistics.mean(
            abs(c - BASE_DISTANCE) for c in consensus_vals
        )
    else:
        mean_consensus = None
        std_consensus = None
        mean_abs_error = None

    summary = {
        "scenario": name,
        "enable_self_healing": enable_self_healing,
        "byzantine_outliers": metrics["byzantine_outliers"],
        "byzantine_quarantines": metrics["byzantine_quarantines"],
        "node_failures": metrics["node_failures"],
        "reboots_sent": metrics["reboots_sent"],
        "num_consensus_samples": len(consensus_vals),
        "mean_consensus_cm": mean_consensus,
        "std_consensus_cm": std_consensus,
        "mean_abs_error_cm": mean_abs_error,
    }

    print("\n--- Scenario Summary ---")
    for k, v in summary.items():
        print(f"{k}: {v}")

    return summary


def main():
    all_results = []

    # 1. Normal operation
    all_results.append(
        run_scenario(
            name="Normal Operation",
            node_configs=[
                {"node_id": 1, "fault_mode": "normal"},
                {"node_id": 2, "fault_mode": "normal"},
                {"node_id": 3, "fault_mode": "normal"},
            ],
            duration_s=DURATION_S,
            enable_self_healing=True,
        )
    )

    # 2. Byzantine fault on Node 3
    all_results.append(
        run_scenario(
            name="Byzantine Node3",
            node_configs=[
                {"node_id": 1, "fault_mode": "normal"},
                {"node_id": 2, "fault_mode": "normal"},
                {"node_id": 3, "fault_mode": "byzantine"},
            ],
            duration_s=DURATION_S,
            enable_self_healing=True,
        )
    )

    # 3. Node 1 failure without self-healing
    all_results.append(
        run_scenario(
            name="Node1 Failure (no self-healing)",
            node_configs=[
                {"node_id": 1, "fault_mode": "normal", "fail_after_s": 20.0},
                {"node_id": 2, "fault_mode": "normal"},
                {"node_id": 3, "fault_mode": "normal"},
            ],
            duration_s=DURATION_S,
            enable_self_healing=False,
        )
    )

    # 4. Node 1 failure with self-healing and recovery
    all_results.append(
        run_scenario(
            name="Node1 Failure + Recovery (self-healing ON)",
            node_configs=[
                {"node_id": 1, "fault_mode": "normal", "fail_after_s": 20.0},
                {"node_id": 2, "fault_mode": "normal"},
                {"node_id": 3, "fault_mode": "normal"},
            ],
            duration_s=DURATION_S,
            enable_self_healing=True,
        )
    )

    print("\n==================== ALL RESULTS ====================")
    for res in all_results:
        print(res)


if __name__ == "__main__":
    main()
