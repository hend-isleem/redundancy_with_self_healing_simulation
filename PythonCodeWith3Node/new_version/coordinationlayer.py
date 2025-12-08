#!/usr/bin/env python3
"""
MAPE-K coordination layer (manager) for 3-node fault-tolerance system.

- Monitors heartbeats + sensor distances
- Detects Byzantine outliers (median-based)
- Detects node failures (heartbeat timeout)
- Applies quarantine and reboot as self-healing actions (optional)
- Publishes consensus distance
- Collects metrics for experiments / Results section
"""

import time
import logging
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

import paho.mqtt.client as mqtt

BROKER_HOST = "broker.hivemq.com"
BROKER_PORT = 1883

TOPIC_SENSOR_DISTANCE = "ft_demo/sensor/+/distance"
TOPIC_SENSOR_HEARTBEAT = "ft_demo/sensor/+/heartbeat"
TOPIC_CONSENSUS = "ft_demo/consensus"
TOPIC_COMMAND_FMT = "ft_demo/command/{node_id}"

NODE_TIMEOUT_MS = 10000          # 10s heartbeat timeout
CONSENSUS_INTERVAL_MS = 1000     # how often we compute consensus
BYZANTINE_THRESHOLD_CM = 10.0    # deviation threshold to mark outliers


@dataclass
class NodeStatus:
    node_id: int
    last_distance: Optional[float] = None
    last_heartbeat_ms: int = 0
    active: bool = False
    quarantined: bool = False
    fault_count: int = 0


class MAPEKMQTTManager:
    def __init__(self, enable_self_healing: bool = True):
        self.enable_self_healing = enable_self_healing

        self.logger = logging.getLogger("Manager")
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[Manager] %(levelname)s: %(message)s"))
        if not self.logger.handlers:
            self.logger.addHandler(handler)

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="PythonManager"
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Known nodes (1, 2, 3)
        self.nodes: Dict[int, NodeStatus] = {
            1: NodeStatus(node_id=1),
            2: NodeStatus(node_id=2),
            3: NodeStatus(node_id=3),
        }

        self.last_consensus_ms = 0

        # Metrics collected per run
        self.metrics = {
            "byzantine_outliers": 0,
            "byzantine_quarantines": 0,
            "node_failures": 0,
            "reboots_sent": 0,
            "consensus_values": [],  # list[float]
        }

    # ------------------------------------------------------------- MQTT

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.logger.info("Connected to broker")
        else:
            self.logger.error(f"Failed to connect, reason_code={reason_code}")

        client.subscribe(TOPIC_SENSOR_DISTANCE)
        client.subscribe(TOPIC_SENSOR_HEARTBEAT)
        self.logger.info("Subscribed to distance + heartbeat topics")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode().strip()

        if "distance" in topic:
            node_id = self._extract_node_id(topic)
            if node_id is not None:
                self.handle_distance(node_id, payload)
        elif "heartbeat" in topic:
            node_id = self._extract_node_id(topic)
            if node_id is not None:
                self.handle_heartbeat(node_id)

    def connect(self):
        self.logger.info("Connecting to MQTT broker...")
        self.client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)

    # ------------------------------------------------------------- HELPERS

    @staticmethod
    def current_time_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _extract_node_id(topic: str) -> Optional[int]:
        """
        From ft_demo/sensor/<id>/distance or heartbeat.
        """
        try:
            parts = topic.split("/")
            idx = parts.index("sensor") + 1
            return int(parts[idx])
        except (ValueError, IndexError):
            return None

    def handle_distance(self, node_id: int, payload: str):
        try:
            value = float(payload)
        except ValueError:
            self.logger.warning(f"Ignoring non-numeric distance from Node {node_id}: {payload}")
            return

        node = self.nodes.get(node_id)
        if not node:
            return

        node.last_distance = value
        # Mark node as active when we receive any valid data
        node.active = not node.quarantined

    def handle_heartbeat(self, node_id: int):
        node = self.nodes.get(node_id)
        if not node:
            return
        node.last_heartbeat_ms = self.current_time_ms()
        if not node.quarantined:
            node.active = True

    # ------------------------------------------------------------- MAPE-K LOOP

    def run_mape_loop(self):
        """
        One MAPE-K iteration: Monitor + Analyze + Plan + Execute.
        Called periodically from the main loop.
        """
        now_ms = self.current_time_ms()

        # Monitor: we already track heartbeats + distances in on_message

        # Analyze: detect timeouts + Byzantine faults
        self._detect_node_failures(now_ms)
        self._detect_byzantine_faults()

        # Plan & Execute: compute consensus and send commands where needed
        if now_ms - self.last_consensus_ms >= CONSENSUS_INTERVAL_MS:
            self._compute_and_publish_consensus()
            self.last_consensus_ms = now_ms

    # ------------------------------------------------------------- ANALYZE

    def _detect_node_failures(self, now_ms: int):
        for node in self.nodes.values():
            if node.quarantined:
                continue
            if node.last_heartbeat_ms == 0:
                continue

            if now_ms - node.last_heartbeat_ms > NODE_TIMEOUT_MS:
                if node.active:
                    self.logger.warning(
                        f"Node {node.node_id} FAILED (heartbeat timeout)"
                    )
                    node.active = False
                    self.metrics["node_failures"] += 1

                    if self.enable_self_healing:
                        self._send_command(node.node_id, "REBOOT")
                        self.metrics["reboots_sent"] += 1

    def _detect_byzantine_faults(self):
        # Collect active distances
        active_nodes = [
            n for n in self.nodes.values()
            if n.active and not n.quarantined and n.last_distance is not None
        ]
        if len(active_nodes) < 2:
            return

        distances = [n.last_distance for n in active_nodes]
        median_val = statistics.median(distances)

        outliers: List[NodeStatus] = []
        for n in active_nodes:
            if abs(n.last_distance - median_val) > BYZANTINE_THRESHOLD_CM:
                outliers.append(n)

        if not outliers:
            return

        for n in outliers:
            n.fault_count += 1
            self.metrics["byzantine_outliers"] += 1
            self.logger.warning(
                f"Byzantine behavior suspected on Node {n.node_id} "
                f"(value={n.last_distance:.2f}, median={median_val:.2f})"
            )

            # Quarantine after 3 consecutive outliers
            if n.fault_count >= 3 and self.enable_self_healing:
                self._quarantine_node(n)

    # ------------------------------------------------------------- EXECUTE

    def _compute_and_publish_consensus(self):
        active_nodes = [
            n for n in self.nodes.values()
            if n.active and not n.quarantined and n.last_distance is not None
        ]
        if not active_nodes:
            self.logger.info("No active nodes available for consensus")
            return

        values = [n.last_distance for n in active_nodes]

        if len(active_nodes) >= 3:
            consensus = statistics.median(values)
            mode = "median (3 nodes)"
        elif len(active_nodes) == 2:
            consensus = sum(values) / 2.0
            mode = "mean (2 nodes)"
        else:
            consensus = values[0]
            mode = "single-node fallback"

        self.client.publish(TOPIC_CONSENSUS, f"{consensus:.2f}")
        self.logger.info(
            f"Consensus = {consensus:.2f} cm using {mode}, "
            f"active_nodes={len(active_nodes)}"
        )

        self.metrics["consensus_values"].append(consensus)

    def _send_command(self, node_id: int, cmd: str):
        topic = TOPIC_COMMAND_FMT.format(node_id=node_id)
        self.client.publish(topic, cmd)
        self.logger.info(f"Sent command '{cmd}' to Node {node_id}")

    def _quarantine_node(self, node: NodeStatus):
        if node.quarantined:
            return
        node.quarantined = True
        node.active = False
        self.metrics["byzantine_quarantines"] += 1
        self.logger.warning(f"Node {node.node_id} QUARANTINED")
        self._send_command(node.node_id, "QUARANTINE")

    # ------------------------------------------------------------- RUNNERS

    def start_for_duration(self, duration_s: float):
        """
        Run manager for a finite duration (used in automated experiments).
        """
        self.connect()
        self.client.loop_start()
        self.logger.info(
            f"Starting manager for {duration_s}s "
            f"(self-healing={'ON' if self.enable_self_healing else 'OFF'})"
        )
        start = self.current_time_ms()

        try:
            while self.current_time_ms() - start < duration_s * 1000:
                self.run_mape_loop()
                time.sleep(0.2)
        finally:
            self.logger.info("Stopping manager")
            self.client.loop_stop()
            self.client.disconnect()

    def start_forever(self):
        """
        Manual infinite loop (for live demos).
        """
        self.connect()
        self.client.loop_start()
        self.logger.info(
            f"Starting manager (self-healing={'ON' if self.enable_self_healing else 'OFF'})"
        )

        try:
            while True:
                self.run_mape_loop()
                time.sleep(0.2)
        except KeyboardInterrupt:
            self.logger.info("Interrupted, shutting down")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
