#!/usr/bin/env python3
"""
Launch a single node for manual testing / demos.

Example:
    python launcher.py 1 normal
    python launcher.py 3 byzantine
"""

import sys
from node import SimulatedNode


def launch_node(node_id: int, fault_mode: str = "normal", base_distance: float = 75.0):
    node = SimulatedNode(
        node_id=node_id,
        base_distance=base_distance,
        fault_mode=fault_mode,
    )
    node.connect()
    node.loop_forever()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python launcher.py <node_id> [fault_mode] [base_distance]")
        print("Fault modes: normal, byzantine, drift, intermittent")
        sys.exit(1)

    node_id = int(sys.argv[1])
    fault_mode = sys.argv[2] if len(sys.argv) > 2 else "normal"
    base_distance = float(sys.argv[3]) if len(sys.argv) > 3 else 75.0

    launch_node(node_id, fault_mode, base_distance)
