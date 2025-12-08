#!/usr/bin/env python3
"""
Node launcher for testing 3-node fault tolerance system
"""
import sys
import subprocess
import time
from node import SimulatedNode

def launch_node(node_id: int, fault_mode: str = "normal", base_distance: float = 50.0):
    """Launch a single node with specified configuration"""
    print(f"Starting Node {node_id} with fault mode: {fault_mode}")
    
    node = SimulatedNode(
        node_id=node_id,
        base_distance=base_distance,
        fault_mode=fault_mode
    )
    
    try:
        node.connect()
        node.loop_forever()
    except KeyboardInterrupt:
        print(f"Node {node_id} shutting down")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python launcher.py <node_id> [fault_mode] [base_distance]")
        print("Fault modes: normal, byzantine, drift, intermittent")
        sys.exit(1)
    
    node_id = int(sys.argv[1])
    fault_mode = sys.argv[2] if len(sys.argv) > 2 else "normal"
    base_distance = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0
    
    launch_node(node_id, fault_mode, base_distance)