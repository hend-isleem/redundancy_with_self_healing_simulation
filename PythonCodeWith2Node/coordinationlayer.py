import paho.mqtt.client as mqtt
import time
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

# Source - https://stackoverflow.com/a
# Posted by joeld, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-19, License - CC BY-SA 4.0

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

#Configuration
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
NODE_TIMEOUT = 10000
HEARTBEAT_INTERVAL = 5000  
CONSENSUS_INTERVAL = 2000 
MEDIAN_THRESHOLD = 10.0  # Threshold for detecting Byzantine faults

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
    fault_count: int = 0
    quarantined: bool = False

class MAPEKMQTTManager:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "PythonManager")
        self.nodes: Dict[int, NodeStatus] = {
            1: NodeStatus(node_id=1),
            2: NodeStatus(node_id=2),
            3: NodeStatus(node_id=3)
        }
        self.registered_nodes = len(self.nodes)
        self.majority_size = 2  # Majority of 3 nodes
        
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
            self.logger.info(f"{bcolors.OKGREEN}Subscribed to topics{bcolors.ENDC}")
        else:
            self.logger.error(f"{bcolors.FAIL}Failed to connect to MQTT broker, return code {rc}{bcolors.ENDC}")

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
                        self.logger.warning(f"{bcolors.WARNING}[MONITOR] Invalid distance value from node {node_id}: {payload}{bcolors.ENDC}")
            
            elif "heartbeat" in topic:
                node_id = int(topic[-1])
                if node_id in self.nodes:
                    self.nodes[node_id].last_heartbeat = current_time
                    self.nodes[node_id].active = True
                    self.logger.info(f"[MONITOR] Node {node_id} heartbeat received")
                    
        except Exception as e:
            self.logger.error(f"{bcolors.FAIL}[MONITOR] Error processing message: {e}{bcolors.ENDC}")

    def on_disconnect(self, client, userdata, df, rc, properties):
        """Handle disconnection from MQTT broker"""
        self.logger.warning(f"{bcolors.WARNING}Disconnected from MQTT broker{bcolors.ENDC}")
        if rc != 0:
            self.logger.warning(f"{bcolors.WARNING}Unexpected disconnection, attempting reconnect{bcolors.ENDC}")

    def get_current_time(self) -> int:
        """Get current time in milliseconds"""
        return int(time.time() * 1000)

    def get_active_node_count(self) -> int:
        """Count how many nodes are currently active and not quarantined"""
        return sum(1 for node in self.nodes.values() if node.active and not node.quarantined)

    def analyze_and_plan(self):
        """ANALYZE & PLAN: Check node health and data consistency"""
        current_time = self.get_current_time()
        
        for node_id, node in self.nodes.items():
            if node.active and (current_time - node.last_heartbeat) > NODE_TIMEOUT:
                self.logger.warning(f"{bcolors.WARNING}[ANALYZE] Node {node_id} FAILED - No heartbeat for {current_time - node.last_heartbeat} ms{bcolors.ENDC}")
                node.active = False
                command = f"REBOOT:{node_id}"
                self.client.publish(TOPIC_COMMAND, command)
                self.logger.info(f"[PLAN] Sent reboot command for node {node_id}")
            
            if node.active and not node.quarantined:
                self.check_data_consistency(node_id, current_time)

    def check_data_consistency(self, node_id: int, current_time: int):
        """Check data consistency using majority voting with 3 nodes"""
        active_nodes = [n for n in self.nodes.values() if n.active and not n.quarantined]
        
        if len(active_nodes) < self.majority_size:
            self.logger.warning(f"[ANALYZE] Insufficient nodes for majority decision ({len(active_nodes)}/{self.majority_size})")
            return
            
        distances = [node.distance for node in active_nodes if node.distance > 0]
        if len(distances) < self.majority_size:
            return
            
        # Byzantine fault tolerance: detect outliers
        outliers = self.detect_byzantine_faults(distances, active_nodes)
        
        if outliers:
            for outlier_node in outliers:
                outlier_node.fault_count += 1
                self.logger.warning(f"[ANALYZE] Byzantine fault detected in Node {outlier_node.node_id}")
                
                if outlier_node.fault_count >= 3:
                    self.quarantine_node(outlier_node)
        
        if current_time - self.last_consensus_publish > CONSENSUS_INTERVAL:
            self.publish_consensus()

    def detect_byzantine_faults(self, distances: List[float], nodes: List[NodeStatus]) -> List[NodeStatus]:
        """Detect Byzantine faults using statistical analysis"""
 
        median_distance = sorted(distances)[len(distances)//2]
        outliers = []
        
        for i, distance in enumerate(distances):
            if abs(distance - median_distance) > MEDIAN_THRESHOLD:  # 10cm threshold
                outliers.append(nodes[i])
                
        return outliers
    
    def quarantine_node(self, node: NodeStatus):
        """Quarantine a faulty node"""
        node.quarantined = True
        self.logger.warning(f"{bcolors.WARNING}[PLAN] Node {node.node_id} QUARANTINED due to repeated faults{bcolors.ENDC}")
        command = f"QUARANTINE:{node.node_id}"
        self.client.publish(TOPIC_COMMAND, command)

    def calculate_consensus(self) -> Optional[float]:
        """Calculate consensus using majority voting"""
        active_nodes = [node for node in self.nodes.values() 
                       if node.active and not node.quarantined and node.distance > 0]
        
        if len(active_nodes) < self.majority_size:
            return None
            
        distances = [node.distance for node in active_nodes]
        
        # Use median for Byzantine fault tolerance
        distances.sort()
        return distances[len(distances)//2]

    def publish_consensus(self, consensus: Optional[float] = None):
        """EXECUTE: Publish consensus distance"""
        if consensus is None:
            consensus = self.calculate_consensus()
            
        if consensus is not None and consensus > 0:
            self.client.publish(TOPIC_CONSENSUS, f"{consensus:.2f}")
            active_count = self.get_active_node_count()
            self.logger.info(f"{bcolors.OKGREEN}[EXECUTE] Consensus distance: {consensus:.2f} cm (Active nodes: {active_count}){bcolors.ENDC}")
            self.last_consensus_publish = self.get_current_time()
        else:
            self.logger.warning(f"{bcolors.WARNING}[EXECUTE] No valid consensus available{bcolors.ENDC}")

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
            self.logger.info(f"{bcolors.OKGREEN}Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}{bcolors.ENDC}")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        except Exception as e:
            self.logger.error(f"{bcolors.FAIL}Failed to connect to MQTT broker: {e}{bcolors.ENDC}")
            raise

    def start(self):
        """Start the MAPE-K manager"""
        self.connect()
        self.client.loop_start()
        
        self.logger.info(f"{bcolors.OKGREEN}MAPE-K Manager started{bcolors.ENDC}")
        self.logger.info(f"{bcolors.OKGREEN}Using Dual Modular Redundancy with 3 worker nodes{bcolors.ENDC}")
        
        try:
            while True:
                self.publish_heartbeat()
                self.run_mape_loop()
                time.sleep(2) 
                
        except KeyboardInterrupt:
            self.logger.info(f"{bcolors.FAIL}Shutting down MAPE-K Manager{bcolors.ENDC}")
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    manager = MAPEKMQTTManager()
    manager.start()