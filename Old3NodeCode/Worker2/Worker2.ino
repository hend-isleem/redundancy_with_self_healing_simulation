#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"

const int NODE_ID = 2; 

WiFiClient espClient;
PubSubClient client(espClient);
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

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP32-Worker-";
    clientId += String(NODE_ID);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

float readPingSensor() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
  float distance = duration * SOUND_SPEED / 2;
  
  if (distance > MAX_DISTANCE || distance <= 0) {
    return -1.0; // Error value
  }
  Serial.printf("Distance: %f \n",distance);
  return distance;
}

void publishSensorData() {
  float distance = readPingSensor();
  if (distance > 0) {
    char topic[50];
    sprintf(topic, "esp32/system/sensor%d/distance", NODE_ID);
    
    char message[50];
    sprintf(message, "%.2f", distance);
    
    client.publish(topic, message);
    Serial.printf("Published distance: %s cm to %s\n", message, topic);
  }
}

void publishHeartbeat() {
  char topic[50];
  sprintf(topic, "esp32/system/heartbeat%d", NODE_ID);
  client.publish(topic, "ALIVE");
  Serial.printf("Heartbeat published to %s\n", topic);
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  setup_wifi();
  client.setServer(MQTT_BROKER, MQTT_PORT);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  unsigned long currentMillis = millis();
  
  // Read and publish sensor data
  if (currentMillis - lastSensorRead >= SENSOR_READ_INTERVAL) {
    publishSensorData();
    lastSensorRead = currentMillis;
  }
  
  // Publish heartbeat
  if (currentMillis - lastHeartbeat >= HEARTBEAT_INTERVAL) {
    publishHeartbeat();
    lastHeartbeat = currentMillis;
  }
}