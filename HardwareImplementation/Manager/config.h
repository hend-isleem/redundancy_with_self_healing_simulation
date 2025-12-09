#ifndef CONFIG_H
#define CONFIG_H

const char* SSID = "";
const char* PASSWORD = "";

const char* MQTT_BROKER = "broker.hivemq.com"; 
const int MQTT_PORT = 1883;

#define TOPIC_SENSOR_1 "esp32/system/sensor1/distance"
#define TOPIC_SENSOR_2 "esp32/system/sensor2/distance" 
#define TOPIC_HEARTBEAT_1 "esp32/system/heartbeat1"
#define TOPIC_HEARTBEAT_2 "esp32/system/heartbeat2"
#define TOPIC_MANAGER_HEARTBEAT "esp32/system/manager/heartbeat"
#define TOPIC_COMMAND "esp32/system/command"
#define TOPIC_CONSENSUS "esp32/system/consensus"

#define TRIG_PIN 23
#define ECHO_PIN 22
#define MAX_DISTANCE 200 // cm
#define SOUND_SPEED 0.034 // cm/microsecond

#define HEARTBEAT_INTERVAL 5000
#define SENSOR_READ_INTERVAL 5000
#define NODE_TIMEOUT 10000 // ms

#endif