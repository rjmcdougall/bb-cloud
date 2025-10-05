"""Cryptographic functions for decrypting Meshtastic packets."""

import struct
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from typing import List, Tuple, Optional

import structlog

logger = structlog.get_logger(__name__)


class DecryptionError(Exception):
    """Exception raised when decryption fails."""
    pass


def decrypt_meshtastic_packet(key: bytes, encrypted_data: bytes, packet_id: int, from_node: int) -> bytes:
    """
    Decrypts Meshtastic packets using the meshview approach.
    
    Args:
        key: AES key (16 bytes from meshview or other lengths)
        encrypted_data: The encrypted packet data
        packet_id: Packet ID for nonce construction
        from_node: Source node ID for nonce construction
    
    Returns:
        Decrypted packet data
        
    Raises:
        DecryptionError: If decryption fails
    """
    try:
        # Handle different key sizes
        if len(key) == 16:
            # meshview approach: nonce is packet_id (8 bytes) + from_node (8 bytes)
            packet_id_bytes = packet_id.to_bytes(8, "little")
            from_node_bytes = from_node.to_bytes(8, "little")
            nonce = packet_id_bytes + from_node_bytes
            
        elif len(key) == 32:
            # Original approach for 32-byte keys
            nonce = struct.pack('<II', packet_id, from_node) + b'\x00' * 8
            
        elif len(key) == 1:
            # Fallback to XOR for single-byte keys
            decrypted_data = bytearray()
            for i, byte in enumerate(encrypted_data):
                decrypted_data.append(byte ^ key[0])
            return bytes(decrypted_data)
            
        else:
            raise DecryptionError(f"Unsupported key length: {len(key)} bytes. Expected 1, 16, or 32 bytes.")
        
        # Create AES-CTR cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.CTR(nonce),
            backend=default_backend()
        )
        
        # Decrypt the data
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        return decrypted_data
        
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {e}")


class MeshtasticDecryptor:
    """Manages multiple decryption keys and attempts decryption."""
    
    def __init__(self, keys: List[Tuple[bytes, str]]):
        """
        Initialize with a list of (key_bytes, description) tuples.
        
        Args:
            keys: List of (key_bytes, description) tuples to try for decryption
        """
        self.keys = keys
        logger.info(f"Initialized decryptor with {len(keys)} keys")
        
        for key_bytes, description in keys:
            logger.info(f"Loaded decryption key: {description} ({len(key_bytes)} bytes)")
    
    def try_decrypt(self, encrypted_data: bytes, packet_id: int, from_node: int) -> Optional[bytes]:
        """
        Try to decrypt data using all available keys.
        
        Args:
            encrypted_data: The encrypted packet data
            packet_id: Packet ID for nonce construction
            from_node: Source node ID for nonce construction
            
        Returns:
            Decrypted data if successful, None if all keys fail
        """
        # Try each key silently, only log success or final failure
        for i, (key_bytes, key_description) in enumerate(self.keys):
            try:
                decrypted_bytes = decrypt_meshtastic_packet(
                    key_bytes, encrypted_data, packet_id, from_node
                )
                
                # Basic validation - check if decrypted data looks reasonable
                if len(decrypted_bytes) > 0:
                    #logger.info(f"Decryption successful with {key_description}")
                    return decrypted_bytes
                    
            except DecryptionError:
                # Silently continue to next key
                continue
        
        # Only log if all keys fail (reduce spam)
        # logger.warning(f"All decryption attempts failed for packet from {from_node:x}")
        return None
