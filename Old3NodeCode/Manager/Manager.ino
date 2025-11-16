#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"

WiFiClient espClient;
PubSubClient client(espClient);

typedef struct {
  float distance;
  unsigned long lastHeartbeat;
  bool active;
  int nodeId;
} NodeStatus;

NodeStatus nodes[3] = {
  {0, 0, false, 1},
  {0, 0, false, 2}, 
  {0, 0, false, 3}
};

unsigned long lastConsensusPublish = 0;
unsigned long lastHealthCheck = 0;

unsigned long lastHeartbeat = 0;
unsigned long lastSensorRead = 0;

void setup_wifi() {
 
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(SSID);

  WiFi.begin(SSID, PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void callback(char* topic, byte* payload, unsigned int length) {
  // MONITOR: Receive sensor data and heartbeats
  payload[length] = '\0';
  String message = String((char*)payload);
  String topicStr = String(topic);
  
  Serial.printf("[MONITOR] Received: %s from %s\n", message.c_str(), topic);
  
  
  // Parse sensor data
  if (topicStr.indexOf("sensor") != -1) {

    int sensorIndex = topicStr.indexOf("sensor");
    int nodeId = topicStr.charAt(sensorIndex + 6) - '0';

    if (nodeId >= 1 && nodeId <= 3) {
      nodes[nodeId-1].distance = message.toFloat();
      Serial.printf("[MONITOR] Node %d distance: %.2f cm\n", nodeId, nodes[nodeId-1].distance);
    }
  }
  
  // Parse heartbeat
  if (topicStr.indexOf("heartbeat") != -1) {
    int nodeId = topicStr.charAt(topicStr.length() - 1) - '0';
    if (nodeId >= 1 && nodeId <= 3) {
      nodes[nodeId-1].lastHeartbeat = millis();
      nodes[nodeId-1].active = true;
      Serial.printf("[MONITOR] Node %d heartbeat received\n", nodeId);
    }
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP32-Manager")) {
      Serial.println("connected");
      client.subscribe("esp32/system/sensor1/distance");
      client.subscribe("esp32/system/sensor2/distance");
      client.subscribe("esp32/system/sensor3/distance");
      client.subscribe("esp32/system/heartbeat1");
      client.subscribe("esp32/system/heartbeat2");
      client.subscribe("esp32/system/heartbeat3");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      delay(5000);
    }
  }
}

void analyzeAndPlan() {
  // ANALYZE: Check node health and data consistency
  unsigned long currentTime = millis();
  
  for (int i = 0; i < 3; i++) {
    // Check for node failure (no heartbeat)
    if (nodes[i].active && (currentTime - nodes[i].lastHeartbeat) > NODE_TIMEOUT) {
      Serial.printf("[ANALYZE] Node %d FAILED - No heartbeat for %lu ms\n", 
                   i+1, currentTime - nodes[i].lastHeartbeat);
      nodes[i].active = false;
      
      // PLAN: Attempt to recover the node
      char command[50];
      sprintf(command, "REBOOT:%d", i+1); //I need ti implement this on worker side
      client.publish(TOPIC_COMMAND, command);
      Serial.printf("[PLAN] Sent reboot command for node %d\n", i+1);
    }
    
    // Check for data anomalies (TMR voting)
    if (nodes[i].active) {
      int consistentCount = 0;
      for (int j = 0; j < 3; j++) {
        if (i != j && nodes[j].active) {
          float diff = abs(nodes[i].distance - nodes[j].distance);
          if (diff < 5.0) { // Within 5cm is considered consistent
            consistentCount++;
          }
        }
      }
      
      if (consistentCount == 0 && getActiveNodeCount() >= 2) {
        Serial.printf("[ANALYZE] Node %d data INCONSISTENT: %.2f cm\n", i+1, nodes[i].distance);
        // PLAN: Mark as suspect (in real system, might take different action)
      }
    }
  }
}

int getActiveNodeCount() {
  int count = 0;
  for (int i = 0; i < 3; i++) {
    if (nodes[i].active) count++;
  }
  return count;
}

float calculateConsensus() {
  float sum = 0;
  int count = 0;
  
  for (int i = 0; i < 3; i++) {
    if (nodes[i].active && nodes[i].distance > 0) {
      sum += nodes[i].distance;
      count++;
    }
  }
  if (count == 0) return -1.0;
  return sum / count;
}

void publishConsensus() {
  float consensus = calculateConsensus();
  if (consensus > 0) {
    char message[50];
    sprintf(message, "%.2f", consensus);
    client.publish(TOPIC_CONSENSUS, message);
    
    Serial.printf("[EXECUTE] Consensus distance: %.2f cm (Active nodes: %d)\n", 
                 consensus, getActiveNodeCount());
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  setup_wifi();
  client.setServer(MQTT_BROKER, MQTT_PORT);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long currentMillis = millis();
  

  
  // Publish manager heartbeat
  if (currentMillis - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    client.publish(TOPIC_HEARTBEAT_1, "ALIVE");
    nodes[0].lastHeartbeat = currentMillis;
    nodes[0].active = true;
    lastHeartbeat = currentMillis;
  }
  
  // Perform MAPE-K analysis
  if (currentMillis - lastHealthCheck >= 2000) {
    analyzeAndPlan();
    publishConsensus();
    lastHealthCheck = currentMillis;
  }

   /* 
  if (currentMillis - lastSensorRead >= SENSOR_READ_INTERVAL) {
    float distance = readPingSensor();
    if (distance > 0) {
      nodes[0].distance = distance; // Manager is node 1
      char message[50];
      sprintf(message, "%.2f", distance);
      client.publish(TOPIC_SENSOR_1, message);
    }
    lastSensorRead = currentMillis;
  } */
}

/*
float readPingSensor() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  float distance = duration * SOUND_SPEED / 2;
  
  if (distance > MAX_DISTANCE || distance <= 0) {
    return -1.0;
  }
  return distance;
}*/