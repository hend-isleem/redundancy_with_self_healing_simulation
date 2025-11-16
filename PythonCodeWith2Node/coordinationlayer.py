import paho.mqtt.client as mqtt
import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

#Configuration
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
NODE_TIMEOUT = 10000
HEARTBEAT_INTERVAL = 5000  
CONSENSUS_INTERVAL = 2000 

# MQTT Topics
TOPIC_SENSOR_1 = "esp32/system/sensor1/distance"
TOPIC_SENSOR_2 = "esp32/system/sensor2/distance"
TOPIC_SENSOR_3 = "esp32/system/sensor3/distance"
TOPIC_HEARTBEAT_1 = "esp32/system/heartbeat1"
TOPIC_HEARTBEAT_2 = "esp32/system/heartbeat2"
TOPIC_HEARTBEAT_3 = "esp32/system/heartbeat3"
TOPIC_COMMAND = "esp32/system/command"
TOPIC_CONSENSUS = "esp32/system/consensus"

@dataclass
class NodeStatus:
    node_id: int
    distance: float = 0.0
    last_heartbeat: int = 0
    active: bool = False
    consistent_count: int = 0

class MAPEKMQTTManager:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "PythonManager")
        self.nodes: Dict[int, NodeStatus] = {
            1: NodeStatus(node_id=1),
            2: NodeStatus(node_id=2)
        }
        self.regesterd_nodes = len(self.nodes)
        
        self.last_heartbeat = 0
        self.last_health_check = 0
        self.last_consensus_publish = 0
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def on_connect(self, client, userdata, flags, rc, properties):
        """MONITOR: Called when connected to MQTT broker"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            client.subscribe([
                (TOPIC_SENSOR_1, 0),
                (TOPIC_SENSOR_2, 0),
                (TOPIC_SENSOR_3, 0),
                (TOPIC_HEARTBEAT_1, 0),
                (TOPIC_HEARTBEAT_2, 0),
                (TOPIC_HEARTBEAT_3, 0)
            ])
            self.logger.info("Subscribed to topics")
        else:
            self.logger.error(f"Failed to connect to MQTT broker, return code {rc}")

    def on_message(self, client, userdata, msg):
        """MONITOR: Handle incoming MQTT messages"""
        try:
            payload = msg.payload.decode('utf-8')
            topic = msg.topic
            current_time = self.get_current_time()
            
            self.logger.info(f"[MONITOR] Received: {payload} from {topic}")
            
            if "sensor" in topic:
                node_id = int(topic.split("sensor")[1].split("/")[0])
                if node_id in self.nodes:
                    try:
                        distance = float(payload)
                        self.nodes[node_id].distance = distance
                        self.logger.info(f"[MONITOR] Node {node_id} distance: {distance:.2f} cm")
                    except ValueError:
                        self.logger.warning(f"[MONITOR] Invalid distance value from node {node_id}: {payload}")
            
            elif "heartbeat" in topic:
                node_id = int(topic[-1])
                if node_id in self.nodes:
                    self.nodes[node_id].last_heartbeat = current_time
                    self.nodes[node_id].active = True
                    self.logger.info(f"[MONITOR] Node {node_id} heartbeat received")
                    
        except Exception as e:
            self.logger.error(f"[MONITOR] Error processing message: {e}")

    def on_disconnect(self, client, userdata, df, rc, properties):
        """Handle disconnection from MQTT broker"""
        self.logger.warning("Disconnected from MQTT broker")
        if rc != 0:
            self.logger.warning("Unexpected disconnection, attempting reconnect")

    def get_current_time(self) -> int:
        """Get current time in milliseconds"""
        return int(time.time() * 1000)

    def get_active_node_count(self) -> int:
        """Count how many nodes are currently active"""
        return sum(1 for node in self.nodes.values() if node.active)

    def analyze_and_plan(self):
        """ANALYZE & PLAN: Check node health and data consistency"""
        current_time = self.get_current_time()
        
        for node_id, node in self.nodes.items():
            if node.active and (current_time - node.last_heartbeat) > NODE_TIMEOUT:
                self.logger.warning(f"[ANALYZE] Node {node_id} FAILED - No heartbeat for {current_time - node.last_heartbeat} ms")
                node.active = False
                command = f"REBOOT:{node_id}"
                self.client.publish(TOPIC_COMMAND, command)
                self.logger.info(f"[PLAN] Sent reboot command for node {node_id}")
            
            if node.active and self.get_active_node_count() >= self.regesterd_nodes:
                self.check_data_consistency(node_id, current_time)

    def check_data_consistency(self, node_id: int, current_time: int):
        """Check data consistency between active nodes using voting"""
        #  TODO: Maybe we can add a third node for the voting system to be valid
        current_node = self.nodes[node_id]
        other_node_id = 2 if node_id == 1 else 1
        other_node = self.nodes[other_node_id]
        
        if other_node.active:
            distance_diff = abs(current_node.distance - other_node.distance)
            
            if distance_diff < 5.0:  #Within 5cm is considered consistent
                current_node.consistent_count += 1
                if current_node.consistent_count >= 3:
                    self.logger.info(f"[ANALYZE] Nodes {node_id} and {other_node_id} data CONSISTENT")
            else:
                current_node.consistent_count = 0
                self.logger.warning(f"[ANALYZE] Data INCONSISTENT - Node {node_id}: {current_node.distance:.2f} cm, "
                                  f"Node {other_node_id}: {other_node.distance:.2f} cm, Diff: {distance_diff:.2f} cm")
                
                if current_time - self.last_consensus_publish > CONSENSUS_INTERVAL:
                    self.handle_data_discrepancy(node_id, other_node_id)

    def handle_data_discrepancy(self, node1_id: int, node2_id: int):
        """PLAN: Handle data discrepancies between nodes"""
        node1 = self.nodes[node1_id]
        node2 = self.nodes[node2_id]
        
        consensus_distance = (node1.distance + node2.distance) / 2
        self.publish_consensus(consensus_distance)
        
        self.logger.info(f"[PLAN] Using average consensus due to discrepancy: {consensus_distance:.2f} cm")
        
        #Could implement more sophisticated strategies here

    def calculate_consensus(self) -> Optional[float]:
        """Calculate consensus distance from active nodes"""
        active_nodes = [node for node in self.nodes.values() if node.active and node.distance > 0] # TODO: this can be a function 
        
        if not active_nodes:
            return None
        
        if len(active_nodes) == 1:
            return active_nodes[0].distance
        else:
            total_distance = sum(node.distance for node in active_nodes)
            return total_distance / len(active_nodes)

    def publish_consensus(self, consensus: Optional[float] = None):
        """EXECUTE: Publish consensus distance"""
        if consensus is None:
            consensus = self.calculate_consensus()
            
        if consensus is not None and consensus > 0:
            self.client.publish(TOPIC_CONSENSUS, f"{consensus:.2f}")
            active_count = self.get_active_node_count()
            self.logger.info(f"[EXECUTE] Consensus distance: {consensus:.2f} cm (Active nodes: {active_count})")
            self.last_consensus_publish = self.get_current_time()
        else:
            self.logger.warning("[EXECUTE] No valid consensus available")

    def publish_heartbeat(self):
        """Publish manager heartbeat"""
        current_time = self.get_current_time()
        if current_time - self.last_heartbeat >= HEARTBEAT_INTERVAL:
            self.client.publish("esp32/system/manager/heartbeat", "ALIVE")
            self.last_heartbeat = current_time
            self.logger.debug("[MANAGER] Heartbeat published")

    def run_mape_loop(self):
        """Run the MAPE-K control loop"""
        current_time = self.get_current_time()
        
        if current_time - self.last_health_check >= 2000:
            self.analyze_and_plan()
            self.publish_consensus()
            self.last_health_check = current_time

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def start(self):
        """Start the MAPE-K manager"""
        self.connect()
        self.client.loop_start()
        
        self.logger.info("MAPE-K Manager started")
        self.logger.info("Using Dual Modular Redundancy with 2 worker nodes")
        
        try:
            while True:
                self.publish_heartbeat()
                self.run_mape_loop()
                time.sleep(0.1) 
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down MAPE-K Manager")
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    manager = MAPEKMQTTManager()
    manager.start()