"""Main mesh processor that integrates all modules."""

import paho.mqtt.client as mqtt
from meshtastic.protobuf import mesh_pb2
from google.protobuf import text_format

from .config import settings
from .crypto import MeshtasticDecryptor
from .filters import NodeFilter
from .datastore import MeshDatastore
from .decoder import PacketDecoder

import structlog

logger = structlog.get_logger(__name__)


class MeshProcessor:
    """Main processor for Meshtastic mesh messages."""
    
    def __init__(self):
        """Initialize the mesh processor with all components."""
        self.settings = settings
        
        # Initialize components
        self.decryptor = MeshtasticDecryptor(settings.get_decryption_keys())
        self.node_filter = NodeFilter(settings.shortname_regex)
        self.datastore = MeshDatastore(settings.gcp_project, settings.datastore_namespace)
        self.packet_decoder = PacketDecoder()
        
        # Load existing node data and populate filter
        self._load_existing_data()
        
        logger.info("Initialized MeshProcessor with all components")
    
    def _load_existing_data(self):
        """Load existing mesh data from Datastore and populate node filter."""
        try:
            existing_nodes = self.datastore.load_existing_nodes()
            
            # Populate node filter with existing shortnames
            for node_id, node_data in existing_nodes.items():
                shortname = node_data.get('shortname')
                if shortname:
                    self.node_filter.update_node_shortname(node_id, shortname)
            
            logger.info(f"Populated node filter with {len(existing_nodes)} existing nodes")
        except Exception as e:
            logger.error(f"Error loading existing data: {e}", exc_info=True)
    
    def process_mqtt_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
        """
        Process an MQTT message from the mesh network.
        
        Args:
            client: MQTT client instance
            userdata: User data from MQTT client
            msg: MQTT message
        """
        try:
            logger.debug(f"Processing message from topic: {msg.topic}")
            
            # Route message based on topic type
            if "/json/" in msg.topic:
                self._handle_json_packet(msg.payload, msg.topic)
            elif "/e/" in msg.topic:
                self._handle_protobuf_packet(msg.payload, msg.topic)
            else:
                logger.debug(f"Ignoring message on unhandled topic: {msg.topic}")
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)
    
    def _handle_json_packet(self, payload: bytes, topic: str):
        """Handle JSON packet from MQTT."""
        json_data = self.packet_decoder.decode_json_packet(payload)
        if json_data:
            logger.info(f"Received JSON packet from {topic}")
            logger.debug(f"JSON data: {json_data}")
    
    def _handle_protobuf_packet(self, payload: bytes, topic: str):
        """Handle protobuf packet from MQTT."""
        packet = self.packet_decoder.decode_protobuf_packet(payload)
        if not packet:
            logger.warning(f"Failed to decode protobuf packet from {topic}")
            return
        
        # Get sender node ID
        from_node = getattr(packet, 'from') if hasattr(packet, 'from') else 0
        logger.debug(f"Processing packet from node {from_node:x}")
        
        # Check if packet should be processed based on filtering
        if not self.node_filter.should_process_packet(packet):
            logger.debug(f"Packet from {from_node:x} filtered out")
            return
        
        # Process packet based on type
        packet_type = packet.WhichOneof("payload_variant")
        
        if packet_type == "decoded":
            self._process_decoded_packet(packet, from_node)
        elif packet_type == "encrypted":
            self._process_encrypted_packet(packet, from_node)
        else:
            logger.debug(f"Unhandled packet type: {packet_type}")
    
    def _process_decoded_packet(self, packet, from_node: int):
        """Process a decoded packet."""
        try:
            decoded = packet.decoded
            
            # Check if we have portnum and payload
            if hasattr(decoded, 'portnum') and hasattr(decoded, 'payload'):
                portnum = decoded.portnum
                payload_bytes = decoded.payload
                
                logger.info(f"📦 Decoded packet from {from_node:x}, port {portnum}")
                
                # Decode the payload based on port number
                payload_type, payload_content = self.packet_decoder.decode_payload_by_portnum(
                    portnum, payload_bytes
                )
                
                self._handle_payload(payload_type, payload_content, from_node)
            else:
                logger.debug(f"Decoded packet from {from_node:x} has no portnum/payload structure")
                
        except Exception as e:
            logger.error(f"Error processing decoded packet: {e}", exc_info=True)
    
    def _process_encrypted_packet(self, packet, from_node: int):
        """Process an encrypted packet by attempting decryption."""
        try:
            packet_id = packet.id if hasattr(packet, 'id') else 0
            encrypted_data = packet.encrypted
            
            logger.debug(f"Attempting to decrypt packet from {from_node:x}")
            
            # Try to decrypt
            decrypted_bytes = self.decryptor.try_decrypt(encrypted_data, packet_id, from_node)
            if not decrypted_bytes:
                logger.warning(f"Failed to decrypt packet from {from_node:x}")
                return
            
            # Parse decrypted data as mesh_pb2.Data
            try:
                decoded_payload = mesh_pb2.Data()
                decoded_payload.ParseFromString(decrypted_bytes)
                
                # Check if decryption was successful (has fields)
                if not decoded_payload.ListFields():
                    logger.warning(f"Decrypted packet from {from_node:x} has no valid fields")
                    return
                
                # Check if we should process this decrypted packet
                if not self.node_filter.should_process_after_decryption(from_node):
                    logger.debug(f"Decrypted packet from {from_node:x} filtered out")
                    return
                
                logger.info(f"🔓 Successfully decrypted packet from {from_node:x}")
                
                # Process the decrypted payload
                if hasattr(decoded_payload, 'portnum') and hasattr(decoded_payload, 'payload'):
                    portnum = decoded_payload.portnum
                    payload_bytes = decoded_payload.payload
                    
                    payload_type, payload_content = self.packet_decoder.decode_payload_by_portnum(
                        portnum, payload_bytes
                    )
                    
                    self._handle_payload(payload_type, payload_content, from_node)
                
            except Exception as e:
                logger.error(f"Error parsing decrypted data: {e}")
                
        except Exception as e:
            logger.error(f"Error processing encrypted packet: {e}", exc_info=True)
    
    def _handle_payload(self, payload_type: str, payload_content, from_node: int):
        """Handle different types of decoded payloads."""
        try:
            if payload_type == 'telemetry':
                self._handle_telemetry(payload_content, from_node)
            elif payload_type == 'position':
                self._handle_position(payload_content, from_node)
            elif payload_type == 'nodeinfo':
                self._handle_nodeinfo(payload_content, from_node)
            elif payload_type == 'text_message':
                self._handle_text_message(payload_content, from_node)
            else:
                logger.debug(f"Unhandled payload type: {payload_type} from {from_node:x}")
                
        except Exception as e:
            logger.error(f"Error handling {payload_type} payload: {e}", exc_info=True)
    
    def _handle_telemetry(self, telemetry, from_node: int):
        """Handle telemetry data."""
        logger.info(f"🔬 Telemetry from {from_node:x}")
        
        # Format and log telemetry
        formatted = self.packet_decoder.format_telemetry_data(telemetry)
        logger.info(f"Telemetry data:\n{formatted}")
        
        # Extract power metrics for storage
        voltage, battery_percent = self.packet_decoder.extract_power_metrics(telemetry)
        
        # Only store power metrics if node is allowed and voltage > 20.0V
        if not self.node_filter.is_node_allowed(from_node):
            shortname = self.node_filter.get_node_shortname(from_node)
            logger.debug(f"⚠️  Skipping telemetry storage for non-allowed node: {from_node:x} ('{shortname}')")
        elif voltage is not None and voltage > 20.0:
            logger.info(f"🔋 Storing power data (voltage {voltage:.2f}V > 20.0V threshold)")
            self.datastore.store_node(
                node_id=from_node,
                voltage=voltage,
                battery_percent=battery_percent,
                timestamp_type='battery'
            )
        elif voltage is not None:
            logger.debug(f"⚠️  Skipping power data storage (voltage {voltage:.2f}V <= 20.0V threshold)")
    
    def _handle_position(self, position, from_node: int):
        """Handle position data."""
        logger.info(f"📍 Position from {from_node:x}")
        
        # Format position data
        pos_data = self.packet_decoder.format_position_data(position)
        
        if 'coordinates' in pos_data:
            logger.info(f"🌍 Location: {pos_data['coordinates']}")
            if 'maps_url' in pos_data:
                logger.info(f"🗺️  Google Maps: {pos_data['maps_url']}")
            
            # Only store position data for allowed nodes
            if not self.node_filter.is_node_allowed(from_node):
                shortname = self.node_filter.get_node_shortname(from_node)
                logger.debug(f"⚠️  Skipping position storage for non-allowed node: {from_node:x} ('{shortname}')")
            else:
                # Store position in datastore
                self.datastore.store_node(
                    node_id=from_node,
                    latitude=pos_data.get('latitude'),
                    longitude=pos_data.get('longitude'),
                    timestamp_type='location'
                )
        else:
            logger.info("🌍 Location: Not available")
        
        # Log other position details
        for key, value in pos_data.items():
            if key not in ['latitude', 'longitude', 'coordinates', 'maps_url']:
                logger.info(f"📊 {key.title()}: {value}")
    
    def _handle_nodeinfo(self, user, from_node: int):
        """Handle node info data."""
        logger.info(f"👤 Node info from {from_node:x}")
        
        shortname = None
        longname = None
        
        if hasattr(user, 'short_name') and user.short_name:
            shortname = user.short_name
            logger.info(f"📛 Short Name: {shortname}")
            
        # Update node filter with new shortname
            self.node_filter.update_node_shortname(from_node, shortname)
        
        if hasattr(user, 'long_name') and user.long_name:
            longname = user.long_name
            logger.info(f"📝 Long Name: {longname}")
        
        if hasattr(user, 'macaddr'):
            mac = ':'.join([f'{b:02x}' for b in user.macaddr])
            logger.info(f"🔌 MAC Address: {mac}")
        
        # Only store node info in datastore if node passes the filter
        if not self.node_filter.is_node_allowed(from_node):
            shortname_display = shortname or 'unknown'
            logger.debug(f"⚠️  Skipping nodeinfo storage for non-allowed node: {from_node:x} ('{shortname_display}')")
        else:
            # Store node info in datastore
            self.datastore.store_node(
                node_id=from_node,
                shortname=shortname,
                longname=longname
            )
    
    def _handle_text_message(self, message: str, from_node: int):
        """Handle text message."""
        shortname = self.node_filter.get_node_shortname(from_node)
        logger.info(f"💬 Text message from {from_node:x} ({shortname}): \"{message}\"")
    
    def get_stats(self) -> dict:
        """Get processor statistics."""
        return {
            "node_filter": self.node_filter.get_stats(),
            "datastore": self.datastore.get_stats(),
            "decryption_keys": len(self.settings.get_decryption_keys()),
            "settings": {
                "gcp_project": self.settings.gcp_project,
                "mqtt_broker": f"{self.settings.mqtt_broker_host}:{self.settings.mqtt_broker_port}",
                "mqtt_topic": self.settings.mqtt_topic,
                "shortname_regex": self.settings.shortname_regex
            }
        }
