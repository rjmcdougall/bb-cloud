"""Node filtering based on shortnames and patterns."""

import re
from typing import Set, Dict, Optional
from meshtastic.protobuf.portnums_pb2 import PortNum

import structlog

logger = structlog.get_logger(__name__)


class NodeFilter:
    """Manages node filtering based on shortname patterns."""
    
    def __init__(self, shortname_pattern: str = r"BB[0-9][0-9]"):
        """
        Initialize node filter.
        
        Args:
            shortname_pattern: Regex pattern for allowed shortnames
        """
        self.shortname_regex = re.compile(shortname_pattern)
        self.node_shortnames: Dict[int, str] = {}  # Maps node_id -> shortname
        self.allowed_nodes: Set[int] = set()  # Set of node IDs that match our filter
        
        logger.info(f"Initialized node filter with pattern: {shortname_pattern}")
    
    def update_node_shortname(self, node_id: int, shortname: str) -> bool:
        """
        Updates the shortname for a node and checks if it should be allowed.
        
        Args:
            node_id: Node identifier
            shortname: Node's shortname
            
        Returns:
            True if node is now allowed, False otherwise
        """
        self.node_shortnames[node_id] = shortname
        
        if self.shortname_regex.search(shortname):
            self.allowed_nodes.add(node_id)
            logger.info(f"Added node to allowed list: {node_id:x} ('{shortname}')")
            return True
        else:
            self.allowed_nodes.discard(node_id)
            logger.debug(f"Node excluded from allowed list: {node_id:x} ('{shortname}')")
            return False
    
    def is_node_allowed(self, node_id: int) -> bool:
        """
        Check if a node is in the allowed list.
        
        Args:
            node_id: Node identifier
            
        Returns:
            True if node is allowed, False otherwise
        """
        return node_id in self.allowed_nodes
    
    def get_node_shortname(self, node_id: int) -> str:
        """
        Get shortname for a node.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node shortname or 'unknown' if not found
        """
        return self.node_shortnames.get(node_id, 'unknown')
    
    def should_process_packet(self, packet) -> bool:
        """
        Determines if a packet should be processed based on shortname filtering.
        
        Args:
            packet: MeshPacket to evaluate
            
        Returns:
            True if the packet should be processed, False otherwise
        """
        try:
            # Get the sender node ID
            from_node = getattr(packet, 'from') if hasattr(packet, 'from') else 0
            
            packet_type = packet.WhichOneof("payload_variant")
            
            if packet_type == "decoded":
                decoded = packet.decoded
                if hasattr(decoded, 'portnum') and decoded.portnum == PortNum.NODEINFO_APP:
                    # Always process NODEINFO packets to learn shortnames
                    logger.debug(f"Processing NODEINFO packet from {from_node:x} to learn shortname")
                    return True
                else:
                    # For other packets, check if the sender is in our allowed list
                    if self.is_node_allowed(from_node):
                        shortname = self.get_node_shortname(from_node)
                        logger.debug(f"Processing packet from allowed node: {from_node:x} ('{shortname}')")
                        return True
                    else:
                        shortname = self.get_node_shortname(from_node)
                        logger.debug(f"Blocking packet from non-allowed node: {from_node:x} ('{shortname}')")
                        return False
                        
            elif packet_type == "encrypted":
                # Always process encrypted packets to decrypt and then check
                logger.debug(f"Processing encrypted packet from {from_node:x} for decryption")
                return True
            else:
                logger.debug(f"Unknown packet type: {packet_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error in packet filtering: {e}", exc_info=True)
            # Process packet anyway if filtering fails
            return True
    
    def should_process_after_decryption(self, from_node: int) -> bool:
        """
        Check if a decrypted packet should be processed based on node filtering.
        
        Args:
            from_node: Source node ID
            
        Returns:
            True if packet should be processed, False otherwise
        """
        if self.is_node_allowed(from_node):
            shortname = self.get_node_shortname(from_node)
            logger.debug(f"Processing decrypted packet from allowed node: {from_node:x} ('{shortname}')")
            return True
        else:
            shortname = self.get_node_shortname(from_node)
            logger.debug(f"Blocking decrypted packet from non-allowed node: {from_node:x} ('{shortname}')")
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get filtering statistics.
        
        Returns:
            Dictionary with filtering stats
        """
        return {
            "total_nodes": len(self.node_shortnames),
            "allowed_nodes": len(self.allowed_nodes),
            "blocked_nodes": len(self.node_shortnames) - len(self.allowed_nodes)
        }
