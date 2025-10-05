# Mesh MQTT Processor for Google Cloud

A refactored and modularized version of the original `mqtt_mesh.py` script, designed for deployment on Google Cloud Run. This application processes Meshtastic mesh network messages from MQTT brokers, decrypts encrypted packets, filters by node shortnames, and stores data in Google Cloud Datastore.

## Features

- **Modular Architecture**: Separated into logical modules for maintainability
- **Cloud-Native**: Designed for Google Cloud Run deployment
- **MQTT Processing**: Connects to MQTT brokers to receive Meshtastic messages
- **Packet Decryption**: Supports multiple decryption keys and algorithms
- **Node Filtering**: Filters messages based on configurable shortname patterns (default: BB[0-9][0-9])
- **Data Storage**: Stores node information and telemetry in Google Cloud Datastore
- **Health Monitoring**: Built-in health checks and statistics endpoints
- **Structured Logging**: JSON-formatted logs for Cloud Logging integration

## Project Structure

```
bb-mesh-service/
├── src/mesh_mqtt/              # Main application code
│   ├── config/                 # Configuration management
│   ├── crypto/                 # Encryption/decryption utilities
│   ├── datastore/             # Google Cloud Datastore interface
│   ├── decoder/               # Packet decoding utilities
│   ├── filters/               # Node filtering logic
│   ├── mqtt/                  # MQTT client management
│   ├── processor.py           # Main message processor
│   └── main.py               # Flask application entry point
├── scripts/                   # Deployment and utility scripts
│   ├── deploy.sh             # Deploy to Google Cloud Run
│   ├── run-local.sh          # Run locally for development
│   └── monitor.sh            # Monitoring and health checks
├── deployment/               # Cloud deployment configurations
├── tests/                    # Unit tests (future)
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container configuration
└── .env.example            # Environment variables template
```

## Quick Start

### 1. Local Development

1. Clone or create the project:
```bash
cd /path/to/bb-mesh-service
```

2. Set up environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run locally:
```bash
./scripts/run-local.sh
```

### 2. Google Cloud Deployment

1. Set up Google Cloud project:
```bash
export GCP_PROJECT=your-project-id
gcloud auth login
```

2. Deploy to Cloud Run:
```bash
./scripts/deploy.sh
```

3. Monitor the service:
```bash
./scripts/monitor.sh health    # One-time health check
./scripts/monitor.sh monitor   # Continuous monitoring
```

## Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and modify as needed:

### Required Configuration
- `GCP_PROJECT`: Your Google Cloud project ID

### MQTT Configuration
- `MQTT_BROKER_HOST`: MQTT broker hostname (default: mqtt.bayme.sh)
- `MQTT_BROKER_PORT`: MQTT broker port (default: 1883)
- `MQTT_TOPIC`: MQTT topic to subscribe to (default: #)
- `MQTT_USERNAME`: MQTT username
- `MQTT_PASSWORD`: MQTT password

### Filtering Configuration
- `SHORTNAME_REGEX`: Regex pattern for allowed node shortnames (default: BB[0-9][0-9])

### Decryption Keys
The application supports multiple decryption keys (Base64 encoded):
- `DECRYPTION_KEY_1`: Primary decryption key
- `DECRYPTION_KEY_2`: Secondary decryption key
- `DECRYPTION_KEY_3`: Tertiary decryption key

## API Endpoints

Once deployed, the application provides several HTTP endpoints:

- `GET /`: Health check endpoint (returns service status)
- `GET /health`: Alternative health check endpoint
- `GET /stats`: Detailed service statistics and configuration

## Scripts

### Local Development: `./scripts/run-local.sh`
```bash
./scripts/run-local.sh           # Run with Python virtual environment
./scripts/run-local.sh --docker  # Run with Docker
./scripts/run-local.sh --help    # Show help
```

### Deployment: `./scripts/deploy.sh`
```bash
./scripts/deploy.sh                           # Deploy with environment variables
./scripts/deploy.sh --project my-project      # Specify project
./scripts/deploy.sh --region us-west1         # Specify region
./scripts/deploy.sh --help                    # Show help
```

### Monitoring: `./scripts/monitor.sh`
```bash
./scripts/monitor.sh health      # Check health once
./scripts/monitor.sh stats       # Get service statistics
./scripts/monitor.sh monitor     # Continuous monitoring
./scripts/monitor.sh info        # Show Cloud Run service info
./scripts/monitor.sh logs 100    # Show last 100 log entries
./scripts/monitor.sh metrics     # Open metrics dashboard
./scripts/monitor.sh --help      # Show help
```

## Architecture

The application follows a modular architecture:

1. **MQTT Client** (`mesh_mqtt.mqtt`): Handles MQTT connection and message reception
2. **Message Processor** (`mesh_mqtt.processor`): Orchestrates message processing
3. **Packet Decoder** (`mesh_mqtt.decoder`): Decodes Meshtastic protobuf packets
4. **Crypto Module** (`mesh_mqtt.crypto`): Handles packet decryption
5. **Node Filter** (`mesh_mqtt.filters`): Filters messages by node shortnames
6. **Datastore Client** (`mesh_mqtt.datastore`): Manages Google Cloud Datastore operations
7. **Configuration** (`mesh_mqtt.config`): Environment-based configuration management

## Message Flow

1. MQTT client receives message from broker
2. Processor routes message based on topic type (JSON/protobuf)
3. Protobuf packets are decoded from ServiceEnvelope
4. Node filter checks if packet should be processed
5. Encrypted packets are decrypted using available keys
6. Decoded payloads are processed by type (telemetry, position, nodeinfo, etc.)
7. Node data is stored in Google Cloud Datastore

## Supported Payload Types

- **Telemetry**: Device metrics, power metrics, environmental data
- **Position**: GPS coordinates, altitude, speed, heading
- **Node Info**: Node names, MAC addresses
- **Text Messages**: Plain text communications
- **Routing**: Mesh routing information
- **Neighbor Info**: Neighbor node information

## Deployment Considerations

### Google Cloud Run
- Minimum 1 instance to maintain MQTT connection
- 1 vCPU and 1GB memory recommended
- Timeout set to 3600 seconds for long-running connections
- Health checks configured for `/health` endpoint

### Security
- Service account with Datastore permissions required
- MQTT credentials stored as environment variables
- Decryption keys stored as environment variables (consider Secret Manager for production)

### Monitoring
- Built-in health checks and statistics
- Structured JSON logging for Cloud Logging
- Integration with Cloud Run metrics and monitoring

## Development

### Adding New Payload Types
1. Add decoder in `mesh_mqtt/decoder/packet_decoder.py`
2. Add handler in `mesh_mqtt/processor.py`
3. Update tests

### Modifying Filters
1. Update `mesh_mqtt/filters/node_filter.py`
2. Modify regex patterns in configuration

### Extending Datastore Schema
1. Update `mesh_mqtt/datastore/client.py`
2. Add new fields to store_node method

## Troubleshooting

### Common Issues

1. **MQTT Connection Failed**
   - Check broker host and credentials
   - Verify network connectivity
   - Check logs: `./scripts/monitor.sh logs`

2. **Datastore Permissions**
   - Ensure service account has Datastore User role
   - Check project ID configuration
   - Verify Datastore API is enabled

3. **Decryption Failures**
   - Verify Base64 encoded keys are correct
   - Check if keys match mesh network configuration
   - Monitor debug logs for decryption attempts

### Logs and Monitoring

- View logs: `./scripts/monitor.sh logs [lines]`
- Check health: `./scripts/monitor.sh health`
- Monitor continuously: `./scripts/monitor.sh monitor`
- View metrics: `./scripts/monitor.sh metrics`

## License

This project is based on the original Meshtastic MQTT processing script and adapted for cloud deployment.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Submit a pull request

For issues and feature requests, please create an issue on the project repository.
