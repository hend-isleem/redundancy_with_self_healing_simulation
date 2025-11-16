# test_manager.py
import time
import paho.mqtt.client as mqtt

def test_manager():
    """Test the MAPE-K manager by publishing mock data"""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,"TestPublisher")
    client.connect("broker.hivemq.com", 1883, 60)
    client.loop_start()
    
    print("Starting test data publication...")
    
    try:
        counter = 0
        while True:
            # Simulate normal operation
            if counter % 10 < 8:  # 80% normal operation
                client.publish("esp32/system/sensor1/distance", "25.5")
                client.publish("esp32/system/sensor2/distance", "25.8")
            else:  # 20% simulated discrepancy
                client.publish("esp32/system/sensor1/distance", "25.5")
                client.publish("esp32/system/sensor2/distance", "35.2")  # Different value
                
            # Always send heartbeats
            client.publish("esp32/system/heartbeat1", "ALIVE")
            client.publish("esp32/system/heartbeat2", "ALIVE")
            
            counter += 1
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("Test stopped")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    test_manager()