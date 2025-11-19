import time
import random
import logging
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

TOPIC_COMMAND = "esp32/system/command"

class SimulatedNode:
    def __init__(
        self,
        node_id: int,
        base_distance: float = 50.0,
        noise_amplitude: float = 2.0,
        heartbeat_interval_ms: int = 3000,
        distance_interval_ms: int = 1000,
        fault_mode: str = "normal",
    ):
        """
        A simulated sensor node that:
        - publishes distance readings
        - publishes heartbeats
        - listens for REBOOT:<node_id> commands
        """
        self.node_id = node_id
        self.base_distance = base_distance
        self.noise_amplitude = noise_amplitude
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.distance_interval_ms = distance_interval_ms
        self.fault_mode = fault_mode

        # MQTT topics specific to this node
        self.sensor_topic = f"esp32/system/sensor{self.node_id}/distance"
        self.heartbeat_topic = f"esp32/system/heartbeat{self.node_id}"

        # Internal timers
        self._last_heartbeat = 0
        self._last_distance_pub = 0

        # Simple "running" flag to simulate reboot etc.
        self._running = True
        self._quarantined = False

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - NODE:%(name)s - %(levelname)s - %(message)s"
        )
        # Add node_id to log records
        self.logger = logging.getLogger(f"SimulatedNode{self.node_id}")
        for handler in self.logger.handlers:
            handler.addFilter(lambda record: setattr(record, "node_id", self.node_id) or True)

        # Setup MQTT client
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"SimNode{self.node_id}"
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    # ---------- MQTT callbacks ----------

    def on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            # Listen for commands from manager (e.g., REBOOT:1)
            client.subscribe(TOPIC_COMMAND)
            self.logger.info(f"Subscribed to command topic: {TOPIC_COMMAND}")
        else:
            self.logger.error(f"Failed to connect, return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8").strip()
            topic = msg.topic

            self.logger.info(f"Received message on {topic}: {payload}")

            if topic == TOPIC_COMMAND:
                if payload.startswith("REBOOT:"):
                    try:
                        target_id = int(payload.split(":")[1])
                        if target_id == self.node_id:
                            self.logger.warning("Received REBOOT command for this node")
                            self.reboot()
                    except ValueError:
                        self.logger.warning(f"Invalid REBOOT command payload: {payload}")
                elif payload.startswith("QUARANTINE:"):
                    try:
                        target_id = int(payload.split(":")[1])
                        if target_id == self.node_id:
                            self.logger.warning("Node quarantined by manager")
                            self._quarantined = True
                    except ValueError:
                        self.logger.warning(f"Invalid QUARANTINE command payload: {payload}")
        except Exception as e:
            self.logger.error(f"Error in on_message: {e}")

    def on_disconnect(self, client, userdata, df, rc, properties):
        self.logger.warning("Disconnected from MQTT broker")

    # ---------- Node behavior ----------

    def get_current_time_ms(self) -> int:
        return int(time.time() * 1000)

    def generate_distance(self) -> float:
        """
        Distance model with fault injection capabilities
        """
        if self.fault_mode == "byzantine":
            # Generate completely wrong readings
            return random.uniform(100, 200)
        elif self.fault_mode == "drift":
            # Gradual drift from correct value
            drift = time.time() % 100  # Increases over time
            return self.base_distance + drift
        elif self.fault_mode == "intermittent":
            # Occasionally send wrong data
            if random.random() < 0.3:  # 30% chance of fault
                return self.base_distance + random.uniform(50, 100)
        
        # Normal operation
        noise = random.uniform(-self.noise_amplitude, self.noise_amplitude)
        return self.base_distance + noise

    def publish_distance(self):
        distance = self.generate_distance()
        self.client.publish(self.sensor_topic, f"{distance:.2f}")
        self.logger.info(f"Published distance: {distance:.2f} cm to {self.sensor_topic}")

    def publish_heartbeat(self):
        self.client.publish(self.heartbeat_topic, "ALIVE")
        self.logger.info(f"Published heartbeat to {self.heartbeat_topic}")

    def reboot(self):
        """
        Simulate a reboot:
        - log
        - briefly sleep
        - reset timers and internal state
        """
        self.logger.warning("Simulating node reboot...")
        self._running = False
        time.sleep(2)  # downtime
        self._last_heartbeat = 0
        self._last_distance_pub = 0
        self._running = True
        self.logger.info("Node reboot complete, resuming normal operation")

    def connect(self):
        self.logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    def loop_forever(self):
        """
        Main loop for the simulated node:
        - keep MQTT network loop running
        - periodically publish distance and heartbeat
        """
        self.client.loop_start()
        self.logger.info(f"Simulated Node {self.node_id} started")

        try:
            while True:
                now = self.get_current_time_ms()

                if self._running and not self._quarantined:
                    # distance publishing
                    if now - self._last_distance_pub >= self.distance_interval_ms:
                        self.publish_distance()
                        self._last_distance_pub = now

                    # heartbeat publishing
                    if now - self._last_heartbeat >= self.heartbeat_interval_ms:
                        self.publish_heartbeat()
                        self._last_heartbeat = now
                elif self._quarantined:
                    self.logger.info("Node quarantined, not publishing data")
                    time.sleep(5)  # Wait before checking again

                time.sleep(0.1)

        except KeyboardInterrupt:
            self.logger.info("Shutting down simulated node")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    # Example: run node 1
    node = SimulatedNode(node_id=1)
    node.connect()
    node.loop_forever()
