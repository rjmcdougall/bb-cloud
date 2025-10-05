"""Google Cloud Datastore interface for mesh node data."""

import datetime
from typing import Optional, Dict, Any, List
from google.cloud import datastore

import structlog

logger = structlog.get_logger(__name__)


class MeshDatastore:
    """Handles all interactions with Google Cloud Datastore for mesh node data."""
    
    def __init__(self, project_id: str, namespace: Optional[str] = None):
        """
        Initialize datastore client.
        
        Args:
            project_id: Google Cloud project ID
            namespace: Datastore namespace to use (None for default namespace)
        """
        self.project_id = project_id
        self.namespace = namespace
        self.client = None
        self.node_cache: Dict[int, Dict[str, Any]] = {}
        
        try:
            # Try to initialize datastore client with better error handling
            import os
            import google.auth
            from google.auth import exceptions as auth_exceptions
            
            # Check if we can get default credentials
            try:
                credentials, detected_project = google.auth.default()
                logger.info(f"Found Google Cloud credentials, detected project: {detected_project}")
                
                # Initialize with explicit credentials
                self.client = datastore.Client(
                    project=project_id, 
                    namespace=namespace,
                    credentials=credentials
                )
                namespace_desc = namespace if namespace is not None else "(default)"
                logger.info(f"Initialized Datastore client for project: {project_id}, namespace: {namespace_desc}")
                
            except auth_exceptions.DefaultCredentialsError as auth_error:
                logger.warning(f"No Google Cloud credentials found: {auth_error}")
                logger.warning("Datastore will not be available. To fix this:")
                logger.warning("1. Run: gcloud auth application-default login")
                logger.warning("2. Or set GOOGLE_APPLICATION_CREDENTIALS to a service account key file")
                
        except Exception as e:
            logger.error(f"Failed to initialize Datastore client: {e}", exc_info=True)
            
    def is_available(self) -> bool:
        """Check if datastore client is available."""
        return self.client is not None
    
    def load_existing_nodes(self) -> Dict[int, Dict[str, Any]]:
        """
        Load all existing mesh node data from Datastore into local cache.
        
        Returns:
            Dictionary mapping node_id to node data
        """
        if not self.is_available():
            logger.warning("Datastore client not available - starting with empty cache")
            return {}
        
        try:
            logger.info("Loading existing mesh data from Datastore...")
            
            # Query all existing mesh entities
            query = self.client.query(kind='mesh')
            results = list(query.fetch())
            
            nodes_loaded = 0
            for entity in results:
                node_id = entity.get('node_id')
                if node_id is None:
                    continue
                
                # Populate cache with existing data
                self.node_cache[node_id] = {
                    'node_id': node_id,
                    'shortname': entity.get('shortname'),
                    'longname': entity.get('longname'),
                    'latitude': entity.get('latitude'),
                    'longitude': entity.get('longitude'),
                    'last_known_voltage': entity.get('last_known_voltage'),
                    'last_known_battery_percent': entity.get('last_known_battery_percent'),
                    'last_seen_battery': entity.get('last_seen_battery'),
                    'last_seen_location': entity.get('last_seen_location'),
                    # Keep backwards compatibility with old last_seen field
                    'last_seen': entity.get('last_seen')
                }
                nodes_loaded += 1
            
            if nodes_loaded > 0:
                logger.info(f"Loaded {nodes_loaded} existing mesh nodes from Datastore")
            else:
                logger.info("No existing mesh data found in Datastore - starting fresh")
                
            return self.node_cache
            
        except Exception as e:
            logger.error(f"Error loading existing data from Datastore: {e}", exc_info=True)
            return {}
    
    def store_node(self, node_id: int, shortname: Optional[str] = None, 
                   longname: Optional[str] = None, latitude: Optional[float] = None,
                   longitude: Optional[float] = None, voltage: Optional[float] = None,
                   battery_percent: Optional[float] = None, 
                   timestamp_type: Optional[str] = None) -> bool:
        """
        Store or update node information in Datastore.
        
        Args:
            node_id: Node identifier
            shortname: Node short name
            longname: Node long name
            latitude: GPS latitude
            longitude: GPS longitude
            voltage: Battery voltage
            battery_percent: Battery percentage
            timestamp_type: Type of timestamp to update ('battery' or 'location')
            
        Returns:
            True if storage was successful, False otherwise
        """
        if not self.is_available():
            logger.debug("Datastore client not available - skipping storage")
            return False

        logger.debug(f"Storing node {node_id:x} in Datastore: {'shortname'}")
        
        try:
            # Get existing data from cache or create new entry
            if node_id not in self.node_cache:
                self.node_cache[node_id] = {
                    'node_id': node_id,
                    'shortname': None,
                    'longname': None,
                    'latitude': None,
                    'longitude': None,
                    'last_known_voltage': None,
                    'last_known_battery_percent': None,
                    'last_seen_battery': None,
                    'last_seen_location': None,
                    'last_seen': None  # Keep for backwards compatibility
                }
            
            node_data = self.node_cache[node_id]
            
            # Update with new data if provided
            if shortname is not None:
                node_data['shortname'] = shortname
            if longname is not None:
                node_data['longname'] = longname
            if latitude is not None:
                node_data['latitude'] = latitude
            if longitude is not None:
                node_data['longitude'] = longitude
            if voltage is not None:
                node_data['last_known_voltage'] = voltage
            if battery_percent is not None:
                node_data['last_known_battery_percent'] = battery_percent
            
            # Update the appropriate timestamp based on the timestamp_type
            current_time = datetime.datetime.utcnow()
            if timestamp_type == 'battery':
                node_data['last_seen_battery'] = current_time
            elif timestamp_type == 'location':
                node_data['last_seen_location'] = current_time
            else:
                # Default behavior for backwards compatibility or nodeinfo updates
                node_data['last_seen'] = current_time
            
            # Create Datastore entity
            key = self.client.key('mesh', str(node_id))
            
            # Try to get existing entity first to preserve existing data
            try:
                entity = self.client.get(key)
                if entity is None:
                    entity = datastore.Entity(key=key)
            except Exception:
                entity = datastore.Entity(key=key)
            
            # Always set node_id 
            entity['node_id'] = node_id
            
            # Set the appropriate timestamps
            if node_data['last_seen_battery'] is not None:
                entity['last_seen_battery'] = node_data['last_seen_battery']
            if node_data['last_seen_location'] is not None:
                entity['last_seen_location'] = node_data['last_seen_location']
            if node_data['last_seen'] is not None:
                entity['last_seen'] = node_data['last_seen']
            
            # Only update fields that have non-None values in the cache
            for field in ['shortname', 'longname', 'latitude', 'longitude', 
                         'last_known_voltage', 'last_known_battery_percent']:
                if node_data[field] is not None:
                    entity[field] = node_data[field]
            
            # Store in Datastore
            self.client.put(entity)
            
            logger.debug(f"Stored node {node_id:x} in Datastore: {node_data['shortname'] or 'unnamed'}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing node {node_id:x} in Datastore: {e}", exc_info=True)
            return False
    
    def get_node(self, node_id: int) -> Optional[Dict[str, Any]]:
        """
        Get node data from cache.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node data dictionary or None if not found
        """
        return self.node_cache.get(node_id)
    
    def get_all_nodes(self) -> Dict[int, Dict[str, Any]]:
        """
        Get all cached node data.
        
        Returns:
            Dictionary mapping node_id to node data
        """
        return self.node_cache.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get datastore statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "cached_nodes": len(self.node_cache),
            "datastore_available": self.is_available(),
            "project_id": self.project_id,
            "namespace": self.namespace
        }
