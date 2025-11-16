#ifndef CONFIG_H
#define CONFIG_H

// WiFi Configuration
const char* SSID = "JadeGiraffe3";
const char* PASSWORD = "BelloJuliano3";

// MQTT Configuration
const char* MQTT_BROKER = "broker.hivemq.com"; // or your local broker
const int MQTT_PORT = 1883;

// MQTT Topics
#define TOPIC_SENSOR_1 "esp32/system/sensor1/distance"
#define TOPIC_SENSOR_2 "esp32/system/sensor2/distance" 
#define TOPIC_SENSOR_3 "esp32/system/sensor3/distance"
#define TOPIC_HEARTBEAT_1 "esp32/system/heartbeat1"
#define TOPIC_HEARTBEAT_2 "esp32/system/heartbeat2"
#define TOPIC_HEARTBEAT_3 "esp32/system/heartbeat3"
#define TOPIC_COMMAND "esp32/system/command"
#define TOPIC_CONSENSUS "esp32/system/consensus"

// PING Sensor Configuration
#define PING_PIN 5
#define MAX_DISTANCE 200 // cm
#define SOUND_SPEED 0.034 // cm/microsecond

// System Parameters
#define HEARTBEAT_INTERVAL 5000
#define SENSOR_READ_INTERVAL 4000
#define NODE_TIMEOUT 10000 // ms

#endif
