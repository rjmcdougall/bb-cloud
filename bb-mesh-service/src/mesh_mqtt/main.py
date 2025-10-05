"""Main Flask application for Cloud Run deployment."""

import os
import threading
import signal
import time
import atexit
import requests
import structlog
from flask import Flask, jsonify

from .config import settings
from .mqtt import MeshMQTTClient
from .processor import MeshProcessor

# Configure structured logging
# Use human-readable logs in development, JSON in production
def setup_logging():
    """Setup logging configuration based on environment."""
    import logging
    from .config import settings
    
    # Set Python's root logger level based on LOG_LEVEL setting
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level)
    
    # Also set structlog's level
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Choose renderer based on environment
    if settings.debug_enabled or settings.flask_env == "development":
        # Human-readable format for development
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,  # Enable colors if terminal supports it
            pad_event=30  # Pad event names for alignment
        )
    else:
        # JSON format for production (better for Cloud Logging)
        renderer = structlog.processors.JSONRenderer()
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer  # Dynamic renderer selection
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

setup_logging()

logger = structlog.get_logger(__name__)

# Global instances
mesh_processor = None
mqtt_client = None
mqtt_thread = None
health_ping_thread = None
shutdown_event = threading.Event()

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    @app.route('/')
    def health_check():
        """Health check endpoint for Cloud Run."""
        try:
            stats = {
                "status": "healthy",
                "mqtt_connected": mqtt_client.is_client_connected() if mqtt_client else False,
                "processor_stats": mesh_processor.get_stats() if mesh_processor else {}
            }
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({"status": "unhealthy", "error": str(e)}), 500
    
    @app.route('/health')
    def health():
        """Alternative health check endpoint."""
        return health_check()
    
    @app.route('/stats')
    def stats():
        """Detailed statistics endpoint."""
        try:
            detailed_stats = {
                "mqtt": mqtt_client.get_stats() if mqtt_client else {},
                "processor": mesh_processor.get_stats() if mesh_processor else {},
                "config": {
                    "gcp_project": settings.gcp_project,
                    "mqtt_broker": f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
                    "mqtt_topic": settings.mqtt_topic,
                    "shortname_regex": settings.shortname_regex,
                    "debug_enabled": settings.debug_enabled
                }
            }
            return jsonify(detailed_stats), 200
        except Exception as e:
            logger.error(f"Stats endpoint failed: {e}")
            return jsonify({"error": str(e)}), 500
    
    return app

def start_mqtt_processing():
    """Start MQTT client and message processing in background."""
    global mesh_processor, mqtt_client
    
    try:
        logger.info("Initializing mesh processor...")
        mesh_processor = MeshProcessor()
        
        logger.info("Starting MQTT client...")
        mqtt_client = MeshMQTTClient(
            broker_host=settings.mqtt_broker_host,
            broker_port=settings.mqtt_broker_port,
            username=settings.mqtt_username,
            password=settings.mqtt_password,
            topic=settings.mqtt_topic,
            message_callback=mesh_processor.process_mqtt_message
        )
        
        mqtt_client.start()
        logger.info("MQTT processing started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start MQTT processing: {e}", exc_info=True)
        raise

def health_ping_worker():
    """Background worker to ping health endpoint to prevent idle shutdowns."""
    # Wait a bit for the app to fully start
    time.sleep(10)
    
    while not shutdown_event.is_set():
        try:
            # Try to ping our own health endpoint
            if not shutdown_event.wait(timeout=60):  # Ping every minute
                try:
                    # Use local loopback to avoid external network issues
                    url = f"http://127.0.0.1:{settings.port}/health"
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        logger.debug("Health ping successful")
                    else:
                        logger.warning(f"Health ping returned {response.status_code}")
                except requests.RequestException as e:
                    logger.debug(f"Health ping failed (normal during startup): {e}")
                except Exception as e:
                    logger.warning(f"Health ping error: {e}")
        except Exception as e:
            logger.error(f"Health ping worker error: {e}")
    
    logger.info("Health ping worker exiting")

def stop_mqtt_processing():
    """Stop MQTT client and processing."""
    global mqtt_client, mqtt_thread, health_ping_thread, shutdown_event
    
    logger.info("Shutdown requested, stopping services...")
    shutdown_event.set()
    
    if mqtt_client:
        logger.info("Stopping MQTT client...")
        mqtt_client.stop()
        logger.info("MQTT client stopped")
    
    if mqtt_thread and mqtt_thread.is_alive():
        logger.info("Waiting for MQTT thread to finish...")
        mqtt_thread.join(timeout=10)
        logger.info("MQTT thread finished")
    
    if health_ping_thread and health_ping_thread.is_alive():
        logger.info("Waiting for health ping thread to finish...")
        health_ping_thread.join(timeout=5)
        logger.info("Health ping thread finished")

# Create Flask app
app = create_app()

def mqtt_worker():
    """MQTT worker function that includes keep-alive mechanism."""
    try:
        start_mqtt_processing()
        
        # Keep-alive loop to prevent Cloud Run from terminating
        logger.info("Starting keep-alive loop...")
        while not shutdown_event.is_set():
            # Wait for either shutdown event or timeout
            if shutdown_event.wait(timeout=30):
                logger.info("Shutdown event received, exiting keep-alive loop")
                break
            
            # Log heartbeat to show activity
            if mqtt_client and mesh_processor:
                logger.debug("Heartbeat: MQTT connected=%s, messages processed=%s",
                           mqtt_client.is_client_connected(),
                           mesh_processor.get_stats().get('total_messages', 0))
        
        logger.info("MQTT worker thread exiting")
    except Exception as e:
        logger.error(f"MQTT worker thread failed: {e}", exc_info=True)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    stop_mqtt_processing()

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
atexit.register(stop_mqtt_processing)

# Start MQTT processing when module is imported (for gunicorn)
if __name__ != "__main__":
    # Running under gunicorn or similar WSGI server
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=False)
    mqtt_thread.start()
    logger.info("Started MQTT processing thread (non-daemon)")
    
    # Start health ping worker to prevent idle shutdowns
    health_ping_thread = threading.Thread(target=health_ping_worker, daemon=False)
    health_ping_thread.start()
    logger.info("Started health ping thread")

# Note: Direct script execution moved to src/run_app.py to avoid import conflicts
# This module now only contains the Flask app and MQTT setup for WSGI deployment
