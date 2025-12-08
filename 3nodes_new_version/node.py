#!/usr/bin/env python3
"""
Simulated sensor node for 3-node fault-tolerance system.
Publishes distance readings + heartbeats over MQTT and reacts to manager commands.
"""

import time
import random
import logging
from typing import Optional

import paho.mqtt.client as mqtt

BROKER_HOST = "broker.hivemq.com"
BROKER_PORT = 1883

TOPIC_SENSOR_DISTANCE = "ft_demo/sensor/{node_id}/distance"
TOPIC_SENSOR_HEARTBEAT = "ft_demo/sensor/{node_id}/heartbeat"
TOPIC_COMMAND = "ft_demo/command/{node_id}"  # node-specific command channel


class SimulatedNode:
    """
    Simulated sensor node that can operate in different fault modes.
    - normal: base distance + gaussian noise
    - byzantine: occasionally sends wild outliers
    - drift: gradually drifts away from base distance
    - intermittent: randomly drops or distorts readings
    """

    def __init__(
        self,
        node_id: int,
        base_distance: float = 75.0,
        noise_amplitude: float = 2.0,
        heartbeat_interval_ms: int = 3000,
        distance_interval_ms: int = 1000,
        fault_mode: str = "normal",
        fail_after_s: Optional[float] = None,
    ):
        self.node_id = node_id
        self.base_distance = base_distance
        self.noise_amplitude = noise_amplitude
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.distance_interval_ms = distance_interval_ms
        self.fault_mode = fault_mode
        self.fail_after_s = fail_after_s

        self._running = True
        self._quarantined = False
        self._start_time_s = time.time()
        self._last_heartbeat = 0
        self._last_distance_pub = 0

        self._drift_offset = 0.0

        self.logger = logging.getLogger(f"Node{self.node_id}")
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(f"[Node {self.node_id}] %(levelname)s: %(message)s")
        )
        if not self.logger.handlers:
            self.logger.addHandler(handler)

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"PythonNode{self.node_id}",
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    # ------------------------------------------------------------------ MQTT

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.logger.info("Connected to broker")
        else:
            self.logger.error(f"Failed to connect, reason_code={reason_code}")

        # Subscribe to our command topic
        cmd_topic = TOPIC_COMMAND.format(node_id=self.node_id)
        client.subscribe(cmd_topic)
        self.logger.info(f"Subscribed to command topic: {cmd_topic}")

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode().strip()
        self.logger.info(f"Received command: {payload}")

        if payload == "REBOOT":
            self.handle_reboot()
        elif payload == "QUARANTINE":
            self.handle_quarantine()
        elif payload == "UNQUARANTINE":
            self.handle_unquarantine()

    def connect(self):
        self.logger.info("Connecting to MQTT broker...")
        self.client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)

    # ----------------------------------------------------------------- COMMANDS

    def handle_reboot(self):
        self.logger.warning("Rebooting node...")
        # Simulate a reboot by resetting core state
        self._running = True
        self._quarantined = False
        self._drift_offset = 0.0
        self._start_time_s = time.time()

    def handle_quarantine(self):
        self.logger.warning("Entering quarantine (stop publishing)")
        self._quarantined = True

    def handle_unquarantine(self):
        self.logger.warning("Leaving quarantine (resume publishing)")
        self._quarantined = False

    # ----------------------------------------------------------------- LOGIC

    @staticmethod
    def current_time_ms() -> int:
        return int(time.time() * 1000)

    def _simulate_distance(self) -> float:
        """Generate a distance value according to the current fault mode."""
        t = time.time() - self._start_time_s

        if self.fault_mode == "normal":
            return random.gauss(self.base_distance, self.noise_amplitude)

        if self.fault_mode == "byzantine":
            # Most of the time normal, sometimes big spikes
            if random.random() < 0.2:
                return self.base_distance + random.choice([-1, 1]) * random.uniform(
                    30.0, 80.0
                )
            return random.gauss(self.base_distance, self.noise_amplitude)

        if self.fault_mode == "drift":
            # Gradually drift away over time
            self._drift_offset = 0.05 * t  # 0.05 cm per second
            return random.gauss(
                self.base_distance + self._drift_offset, self.noise_amplitude
            )

        if self.fault_mode == "intermittent":
            # Sometimes drop or send garbage
            r = random.random()
            if r < 0.1:
                # no reading (skip publish by returning a nonsense negative)
                return -1.0
            elif r < 0.2:
                # garbage
                return self.base_distance + random.uniform(20.0, 60.0)
            else:
                return random.gauss(self.base_distance, self.noise_amplitude)

        # Default fallback
        return random.gauss(self.base_distance, self.noise_amplitude)

    def publish_distance(self):
        distance = self._simulate_distance()
        if distance < 0:
            # emulate "no publish" for intermittent missing readings
            self.logger.info("Skipping distance publish (intermittent drop)")
            return

        topic = TOPIC_SENSOR_DISTANCE.format(node_id=self.node_id)
        self.client.publish(topic, f"{distance:.2f}")
        self.logger.info(f"Published distance: {distance:.2f} cm")

    def publish_heartbeat(self):
        topic = TOPIC_SENSOR_HEARTBEAT.format(node_id=self.node_id)
        self.client.publish(topic, "ALIVE")
        self.logger.info("Published heartbeat")

    # ----------------------------------------------------------------- LOOPS

    def loop_for_duration(self, duration_s: float):
        """
        Run this node for a finite duration (used in automated experiments).
        """
        self.client.loop_start()
        self.logger.info(f"Starting node for {duration_s}s in mode '{self.fault_mode}'")
        start = time.time()
        fail_time = start + self.fail_after_s if self.fail_after_s is not None else None

        try:
            while time.time() - start < duration_s:
                now_ms = self.current_time_ms()
                now_s = time.time()

                # Simulate hard failure by stopping publishes
                if fail_time is not None and now_s >= fail_time:
                    time.sleep(0.1)
                    continue

                if not self._quarantined:
                    if now_ms - self._last_distance_pub >= self.distance_interval_ms:
                        self.publish_distance()
                        self._last_distance_pub = now_ms

                    if now_ms - self._last_heartbeat >= self.heartbeat_interval_ms:
                        self.publish_heartbeat()
                        self._last_heartbeat = now_ms
                else:
                    # Quarantined: do nothing but stay connected
                    time.sleep(0.1)

                time.sleep(0.05)
        finally:
            self.logger.info("Stopping node")
            self.client.loop_stop()
            self.client.disconnect()

    def loop_forever(self):
        """
        Manual infinite loop (useful with launcher.py for demos).
        """
        self.client.loop_start()
        self.logger.info(f"Starting infinite loop in mode '{self.fault_mode}'")

        try:
            while True:
                now_ms = self.current_time_ms()
                now_s = time.time()

                if self.fail_after_s is not None and now_s - self._start_time_s >= self.fail_after_s:
                    time.sleep(0.1)
                    continue

                if not self._quarantined:
                    if now_ms - self._last_distance_pub >= self.distance_interval_ms:
                        self.publish_distance()
                        self._last_distance_pub = now_ms

                    if now_ms - self._last_heartbeat >= self.heartbeat_interval_ms:
                        self.publish_heartbeat()
                        self._last_heartbeat = now_ms
                else:
                    time.sleep(0.1)

                time.sleep(0.05)
        except KeyboardInterrupt:
            self.logger.info("Interrupted, shutting down")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
