# bb-cloud

This repository contains cloud services for the Burner Board ecosystem.

## Services

### bb-mesh-service
**Bayarea Mesh MQTT to Datastore Status Service**

A Cloud Run service that monitors Meshtastic mesh network traffic via MQTT and stores node data in Google Cloud Datastore. This service:

- Connects to MQTT brokers to receive mesh network messages
- Decodes Meshtastic protobuf packets
- Filters messages based on node naming patterns
- Stores node information, telemetry, and location data
- Provides health check and statistics endpoints

Located in: `bb-mesh-service/`

### bbcloudfunctions
**Cloud Functions for burnerboard.com**

Google Cloud Functions that provide backend services for the Burner Board platform. These functions handle:

- Board management and configuration
- Status reporting and monitoring
- API endpoints for the burnerboard.com platform
- Directory and data synchronization services

Located in: `bbcloudfunctions/`

## Architecture

Both services are designed to run on Google Cloud Platform:
- **bb-mesh-service**: Deployed as a Cloud Run service for always-on MQTT processing
- **bbcloudfunctions**: Deployed as individual Cloud Functions for serverless API endpoints

## Development

Each service directory contains its own documentation, deployment scripts, and configuration files. Refer to the individual service directories for specific setup and deployment instructions.