"""Meshtastic packet decoder with payload processing."""

import json
import datetime
from typing import Tuple, Optional, Dict, Any
from google.protobuf import text_format
from google.protobuf.message import DecodeError
from meshtastic.protobuf import mqtt_pb2, mesh_pb2
from meshtastic.protobuf.telemetry_pb2 import Telemetry
from meshtastic.protobuf.portnums_pb2 import PortNum

import structlog

logger = structlog.get_logger(__name__)


class PacketDecoder:
    """Handles decoding of Meshtastic packets from MQTT."""
    
    @staticmethod
    def decode_payload_by_portnum(portnum: int, payload_bytes: bytes) -> Tuple[str, Any]:
        """
        Decode payload based on the port number (application type).
        
        Args:
            portnum: Port number indicating payload type
            payload_bytes: Raw payload bytes
            
        Returns:
            Tuple of (payload_type, payload_content)
        """
        try:
            if portnum == PortNum.TEXT_MESSAGE_APP:
                # Text message - decode as UTF-8
                message = payload_bytes.decode('utf-8')
                return 'text_message', message
            
            elif portnum == PortNum.TELEMETRY_APP:
                # Telemetry data
                telemetry = Telemetry()
                telemetry.ParseFromString(payload_bytes)
                return 'telemetry', telemetry
            
            elif portnum == PortNum.POSITION_APP:
                # Position data
                from meshtastic.protobuf.mesh_pb2 import Position
                position = Position()
                position.ParseFromString(payload_bytes)
                return 'position', position
            
            elif portnum == PortNum.NODEINFO_APP:
                # Node info / User data
                from meshtastic.protobuf.mesh_pb2 import User
                user = User()
                user.ParseFromString(payload_bytes)
                return 'nodeinfo', user
            
            elif portnum == PortNum.ROUTING_APP:
                # Routing data
                from meshtastic.protobuf.mesh_pb2 import Routing
                routing = Routing()
                routing.ParseFromString(payload_bytes)
                return 'routing', routing
            
            elif portnum == PortNum.NEIGHBORINFO_APP:
                # Neighbor info
                from meshtastic.protobuf.mesh_pb2 import NeighborInfo
                neighbor_info = NeighborInfo()
                neighbor_info.ParseFromString(payload_bytes)
                return 'neighborinfo', neighbor_info
                
            elif portnum == PortNum.TRACEROUTE_APP:
                # Traceroute
                from meshtastic.protobuf.mesh_pb2 import RouteDiscovery
                route_discovery = RouteDiscovery()
                route_discovery.ParseFromString(payload_bytes)
                return 'traceroute', route_discovery
            
            else:
                # Unknown port type - return raw data
                return 'unknown', payload_bytes
                
        except Exception as e:
            logger.error(f"Failed to decode payload for port {portnum}: {e}")
            return 'decode_error', payload_bytes
    
    @staticmethod
    def format_telemetry_data(telemetry: Telemetry) -> str:
        """
        Format telemetry data in a human-readable way.
        
        Args:
            telemetry: Telemetry protobuf object
            
        Returns:
            Formatted telemetry string
        """
        output = []
        
        if telemetry.HasField('device_metrics'):
            dm = telemetry.device_metrics
            output.append("📱 Device Metrics:")
            if dm.HasField('battery_level'):
                output.append(f"  🔋 Battery: {dm.battery_level}%")
            if dm.HasField('voltage'):
                output.append(f"  ⚡ Voltage: {dm.voltage:.2f}V")
            if dm.HasField('channel_utilization'):
                output.append(f"  📡 Channel Usage: {dm.channel_utilization:.1f}%")
            if dm.HasField('air_util_tx'):
                output.append(f"  📤 Air Util TX: {dm.air_util_tx:.1f}%")
            if dm.HasField('uptime_seconds'):
                uptime_hours = dm.uptime_seconds / 3600
                output.append(f"  ⏱️  Uptime: {uptime_hours:.1f} hours")
        
        if telemetry.HasField('environment_metrics'):
            em = telemetry.environment_metrics
            output.append("🌡️  Environment Metrics:")
            if em.HasField('temperature'):
                output.append(f"  🌡️  Temperature: {em.temperature:.1f}°C")
            if em.HasField('relative_humidity'):
                output.append(f"  💧 Humidity: {em.relative_humidity:.1f}%")
            if em.HasField('barometric_pressure'):
                output.append(f"  🌪️  Pressure: {em.barometric_pressure:.1f} hPa")
            if em.HasField('gas_resistance'):
                output.append(f"  💨 Gas Resistance: {em.gas_resistance:.1f}")
            if em.HasField('voltage'):
                output.append(f"  ⚡ Voltage: {em.voltage:.2f}V")
            if em.HasField('current'):
                output.append(f"  🔌 Current: {em.current:.2f}mA")
        
        if telemetry.HasField('power_metrics'):
            pm = telemetry.power_metrics
            output.append("⚡ Power Metrics:")
            if pm.HasField('ch1_voltage'):
                output.append(f"  📊 Ch1 Voltage: {pm.ch1_voltage:.2f}V")
            if pm.HasField('ch1_current'):
                output.append(f"  📊 Ch1 Current: {pm.ch1_current:.2f}mA")
            if pm.HasField('ch2_voltage'):
                output.append(f"  📊 Ch2 Voltage: {pm.ch2_voltage:.2f}V")
            if pm.HasField('ch2_current'):
                output.append(f"  📊 Ch2 Current: {pm.ch2_current:.2f}mA")
            if pm.HasField('ch3_voltage'):
                output.append(f"  📊 Ch3 Voltage: {pm.ch3_voltage:.2f}V")
            if pm.HasField('ch3_current'):
                output.append(f"  📊 Ch3 Current: {pm.ch3_current:.2f}mA")
        
        return "\n".join(output) if output else "No telemetry data found"
    
    @staticmethod
    def extract_power_metrics(telemetry: Telemetry) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract power metrics for storage.
        
        Args:
            telemetry: Telemetry protobuf object
            
        Returns:
            Tuple of (voltage, battery_percent)
        """
        voltage = None
        battery_percent = None
        
        if telemetry.HasField('power_metrics'):
            pm = telemetry.power_metrics
            
            # Store ch1_voltage as last_known_voltage
            if pm.HasField('ch1_voltage'):
                voltage = pm.ch1_voltage
            
            # Store ch2_voltage * 100 as last_known_battery_percent 
            if pm.HasField('ch2_voltage'):
                battery_percent = pm.ch2_voltage * 100
        
        return voltage, battery_percent
    
    @staticmethod
    def format_position_data(position) -> Dict[str, Any]:
        """
        Format position data into a structured dictionary.
        
        Args:
            position: Position protobuf object
            
        Returns:
            Dictionary with formatted position data
        """
        result = {}
        
        try:
            # Coordinates
            if hasattr(position, 'latitude_i') and hasattr(position, 'longitude_i'):
                if position.latitude_i != 0 or position.longitude_i != 0:
                    lat = position.latitude_i * 1e-7
                    lon = position.longitude_i * 1e-7
                    result['latitude'] = lat
                    result['longitude'] = lon
                    result['coordinates'] = f"{lat:.6f}, {lon:.6f}"
                    result['maps_url'] = f"https://maps.google.com/maps?q={lat},{lon}"
            
            # Altitude
            if hasattr(position, 'altitude') and position.altitude != 0:
                result['altitude'] = position.altitude
            
            # GPS quality indicators
            if hasattr(position, 'sats_in_view') and position.sats_in_view > 0:
                result['satellites'] = position.sats_in_view
            
            if hasattr(position, 'PDOP') and position.PDOP > 0:
                result['pdop'] = position.PDOP
            
            if hasattr(position, 'HDOP') and position.HDOP > 0:
                result['hdop'] = position.HDOP
            
            if hasattr(position, 'VDOP') and position.VDOP > 0:
                result['vdop'] = position.VDOP
            
            # Timestamp
            if hasattr(position, 'time') and position.time > 0:
                result['gps_time'] = datetime.datetime.fromtimestamp(position.time)
            
            # Ground speed and heading
            if hasattr(position, 'ground_speed') and position.ground_speed > 0:
                speed_ms = position.ground_speed / 1000.0  # mm/s to m/s
                speed_kmh = speed_ms * 3.6  # m/s to km/h
                speed_mph = speed_kmh * 0.621371  # km/h to mph
                result['ground_speed'] = {
                    'ms': speed_ms,
                    'kmh': speed_kmh,
                    'mph': speed_mph
                }
            
            if hasattr(position, 'ground_track') and position.ground_track > 0:
                heading = position.ground_track / 1e5
                directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                dir_index = int((heading + 11.25) / 22.5) % 16
                compass_dir = directions[dir_index]
                result['heading'] = {
                    'degrees': heading,
                    'compass': compass_dir
                }
            
            # Location source
            if hasattr(position, 'location_source'):
                from meshtastic.protobuf.mesh_pb2 import Position
                if hasattr(Position, 'LocSource'):
                    result['location_source'] = Position.LocSource.Name(position.location_source)
            
            # Precision bits
            if hasattr(position, 'precision_bits') and position.precision_bits > 0:
                result['precision_bits'] = position.precision_bits
                
        except Exception as e:
            logger.error(f"Error formatting position data: {e}")
        
        return result
    
    @staticmethod
    def decode_protobuf_packet(payload: bytes) -> Optional[mesh_pb2.MeshPacket]:
        """
        Decode a protobuf packet from MQTT payload.
        
        Args:
            payload: Raw MQTT payload bytes
            
        Returns:
            Decoded MeshPacket or None if decoding fails
        """
        try:
            service_envelope = mqtt_pb2.ServiceEnvelope()
            service_envelope.ParseFromString(payload)
            
            logger.debug(f"Decoded ServiceEnvelope with gateway_id: {service_envelope.gateway_id}")
            
            if not service_envelope.HasField("packet"):
                logger.warning("ServiceEnvelope has no packet field")
                return None
                
            packet = service_envelope.packet
            return packet
            
        except Exception as e:
            logger.error(f"Failed to decode protobuf packet: {e}")
            return None
    
    @staticmethod
    def decode_json_packet(payload: bytes) -> Optional[Dict[str, Any]]:
        """
        Decode a JSON packet from MQTT payload.
        
        Args:
            payload: Raw MQTT payload bytes
            
        Returns:
            Decoded JSON data or None if decoding fails
        """
        try:
            json_string = payload.decode('utf-8')
            data = json.loads(json_string)
            logger.debug("Successfully decoded JSON packet")
            return data
        except Exception as e:
            logger.error(f"Failed to decode JSON packet: {e}")
            return None
