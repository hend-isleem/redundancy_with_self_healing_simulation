# test_manager.py
import time
import paho.mqtt.client as mqtt

def test_manager():
    """Test the MAPE-K manager with 3 nodes and fault scenarios"""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,"TestPublisher")
    client.connect("broker.hivemq.com", 1883, 60)
    client.loop_start()
    
    print("Starting 3-node fault tolerance test...")
    
    try:
        counter = 0
        while True:
            # Test different scenarios based on counter
            if counter < 10:  # Normal operation
                client.publish("esp32/system/sensor1/distance", "75.5")
                client.publish("esp32/system/sensor2/distance", "75.8")
                client.publish("esp32/system/sensor3/distance", "75.3")
                print(f"[{counter}] Normal operation")
                
            elif counter < 40:  # Node 3 Byzantine fault
                client.publish("esp32/system/sensor1/distance", "75.5")
                client.publish("esp32/system/sensor2/distance", "75.8")
                client.publish("esp32/system/sensor3/distance", "150.0")  # Byzantine
                print(f"[{counter}] Node 3 Byzantine fault")
                
            elif counter < 50:  # Node 1 fails (no heartbeat)
                client.publish("esp32/system/sensor2/distance", "75.8")
                client.publish("esp32/system/sensor3/distance", "75.3")
                print(f"[{counter}] Node 1 failure (no heartbeat)")
                
            else:  # Recovery
                client.publish("esp32/system/sensor1/distance", "75.5")
                client.publish("esp32/system/sensor2/distance", "75.8")
                client.publish("esp32/system/sensor3/distance", "75.3")
                print(f"[{counter}] System recovery")
                
            # Send heartbeats (except during node 1 failure)
            if not (20 <= counter < 50):
                client.publish("esp32/system/heartbeat1", "ALIVE")
            client.publish("esp32/system/heartbeat2", "ALIVE")
            client.publish("esp32/system/heartbeat3", "ALIVE")
            
            counter += 1
            if counter > 60:
                counter = 0  # Reset cycle
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("Test stopped")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    test_manager()