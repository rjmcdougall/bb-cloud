#!/usr/bin/env python3
"""Entry point script for running the mesh MQTT application locally."""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

if __name__ == "__main__":
    # Import and run the main application
    from mesh_mqtt.main import app, start_mqtt_processing, stop_mqtt_processing, logger, settings
    
    try:
        logger.info("Starting mesh MQTT processor...")
        logger.info(f"Configuration: GCP Project={settings.gcp_project}, "
                   f"MQTT Broker={settings.mqtt_broker_host}:{settings.mqtt_broker_port}, "
                   f"Topic={settings.mqtt_topic}")
        
        # Start MQTT processing
        start_mqtt_processing()
        
        # Run Flask app
        app.run(
            host='0.0.0.0',
            port=settings.port,
            debug=settings.debug_enabled
        )
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        stop_mqtt_processing()
        logger.info("Application shutdown complete")
