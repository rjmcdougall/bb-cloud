"""MQTT client for receiving Meshtastic messages."""

import threading
import time
from typing import Callable, Optional
import paho.mqtt.client as mqtt

import structlog

logger = structlog.get_logger(__name__)


class MeshMQTTClient:
    """MQTT client for receiving Meshtastic mesh messages."""
    
    def __init__(self, broker_host: str, broker_port: int, username: str, password: str,
                 topic: str, message_callback: Callable[[mqtt.Client, any, mqtt.MQTTMessage], None]):
        """
        Initialize MQTT client.
        
        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
            username: MQTT username
            password: MQTT password
            topic: MQTT topic to subscribe to
            message_callback: Callback function for received messages
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.topic = topic
        self.message_callback = message_callback
        
        self.client = None
        self.is_connected = False
        self.is_running = False
        self.connection_thread = None
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_delay = 300  # 5 minutes
        
        logger.info(f"Initialized MQTT client for {broker_host}:{broker_port}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.is_connected = True
            logger.info(f"Connected to MQTT broker and subscribing to topic: {self.topic}")
            client.subscribe(self.topic)
        else:
            self.is_connected = False
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.is_connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker, return code {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        try:
            logger.info(f"Received message on topic: {msg.topic}")
            self.message_callback(client, userdata, msg)
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)
    
    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Callback for when subscription is confirmed."""
        logger.info(f"Subscription confirmed with QoS: {granted_qos}")
    
    def _connection_loop(self):
        """Main connection loop with automatic reconnection."""
        reconnect_delay = self.reconnect_delay
        
        while self.is_running:
            try:
                if not self.is_connected:
                    logger.info(f"Attempting to connect to MQTT broker: {self.broker_host}:{self.broker_port}")
                    
                    # Create new client instance - compatible with paho-mqtt 1.6.1
                    self.client = mqtt.Client()
                    self.client.on_connect = self._on_connect
                    self.client.on_disconnect = self._on_disconnect
                    self.client.on_message = self._on_message
                    self.client.on_subscribe = self._on_subscribe
                    
                    # Set credentials
                    self.client.username_pw_set(self.username, self.password)
                    
                    # Connect to broker
                    self.client.connect(self.broker_host, self.broker_port, 60)
                    
                    # Start the MQTT client loop
                    self.client.loop_start()
                    
                    # Reset reconnect delay on successful connection attempt
                    reconnect_delay = self.reconnect_delay
                    
                # Wait a bit before checking connection status again
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in MQTT connection: {e}", exc_info=True)
                self.is_connected = False
                
                # Clean up client
                if self.client:
                    try:
                        self.client.loop_stop()
                        self.client.disconnect()
                    except:
                        pass
                    self.client = None
                
                # Exponential backoff for reconnection
                logger.info(f"Waiting {reconnect_delay} seconds before reconnecting...")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, self.max_reconnect_delay)
    
    def start(self):
        """Start the MQTT client in a background thread."""
        if self.is_running:
            logger.warning("MQTT client is already running")
            return
        
        self.is_running = True
        self.connection_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self.connection_thread.start()
        logger.info("Started MQTT client thread")
    
    def stop(self):
        """Stop the MQTT client and clean up resources."""
        logger.info("Stopping MQTT client...")
        self.is_running = False
        
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as e:
                logger.error(f"Error stopping MQTT client: {e}")
            finally:
                self.client = None
        
        if self.connection_thread and self.connection_thread.is_alive():
            self.connection_thread.join(timeout=5)
        
        logger.info("MQTT client stopped")
    
    def is_client_connected(self) -> bool:
        """Check if the client is currently connected."""
        return self.is_connected
    
    def get_stats(self) -> dict:
        """Get client statistics."""
        return {
            "connected": self.is_connected,
            "running": self.is_running,
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "topic": self.topic
        }
