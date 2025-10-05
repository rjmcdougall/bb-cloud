"""Configuration management for the mesh MQTT processor."""

import base64
from typing import List, Tuple, Optional
from pydantic import Field, validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Google Cloud Configuration
    gcp_project: str = Field(..., env="GCP_PROJECT")
    google_application_credentials: Optional[str] = Field(None, env="GOOGLE_APPLICATION_CREDENTIALS")
    
    # MQTT Configuration
    mqtt_broker_host: str = Field("mqtt.bayme.sh", env="MQTT_BROKER_HOST")
    mqtt_broker_port: int = Field(1883, env="MQTT_BROKER_PORT")
    mqtt_topic: str = Field("#", env="MQTT_TOPIC")
    mqtt_username: str = Field("meshdev", env="MQTT_USERNAME")
    mqtt_password: str = Field("large4cats", env="MQTT_PASSWORD")
    
    # Application Configuration
    debug_enabled: bool = Field(False, env="DEBUG_ENABLED")
    port: int = Field(8080, env="PORT")
    flask_env: str = Field("production", env="FLASK_ENV")
    
    # Datastore Configuration
    datastore_namespace: Optional[str] = Field(None, env="DATASTORE_NAMESPACE")
    
    # Filtering Configuration
    shortname_regex: str = Field(r"BB[0-9][0-9]", env="SHORTNAME_REGEX")
    
    # Decryption Keys Configuration
    decryption_key_1: str = Field("1PG7OiApB1nwvP+rz05pAQ==", env="DECRYPTION_KEY_1")
    decryption_key_1_desc: str = Field("meshview default key (16 bytes)", env="DECRYPTION_KEY_1_DESC")
    decryption_key_2: str = Field("MgkxoOxSr8pwXSkjvXrjt8pH8eStGHEIwKACN3TavNQ=", env="DECRYPTION_KEY_2")
    decryption_key_2_desc: str = Field("custom key (32 bytes)", env="DECRYPTION_KEY_2_DESC")
    decryption_key_3: str = Field("AQ==", env="DECRYPTION_KEY_3")
    decryption_key_3_desc: str = Field("simple default (1 byte)", env="DECRYPTION_KEY_3_DESC")
    
    # Logging Configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    @validator("mqtt_broker_port")
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    def get_decryption_keys(self) -> List[Tuple[bytes, str]]:
        """Get decoded decryption keys as list of (key_bytes, description) tuples."""
        keys = []
        key_configs = [
            (self.decryption_key_1, self.decryption_key_1_desc),
            (self.decryption_key_2, self.decryption_key_2_desc),
            (self.decryption_key_3, self.decryption_key_3_desc),
        ]
        
        for key_b64, description in key_configs:
            if key_b64:  # Only process non-empty keys
                try:
                    key_bytes = base64.b64decode(key_b64)
                    keys.append((key_bytes, description))
                except Exception as e:
                    print(f"Warning: Could not decode key '{description}': {e}")
        
        return keys
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
