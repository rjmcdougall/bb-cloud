#!/bin/bash

# Mesh MQTT Local Development Script
# This script sets up and runs the application locally

set -e

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python virtual environment exists
check_venv() {
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
        log_success "Virtual environment created"
    fi
}

# Activate virtual environment and install dependencies
setup_python() {
    log_info "Setting up Python environment..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    pip install -r requirements.txt
    
    log_success "Python environment ready"
}

# Check if .env file exists
check_env() {
    if [ ! -f ".env" ]; then
        log_warning ".env file not found"
        log_info "Creating .env from template..."
        cp .env.example .env
        log_info "Please edit .env file with your configuration before running the application"
        log_warning "You need to set at least GCP_PROJECT in .env file"
        return 1
    fi
    return 0
}

# Run the application
run_app() {
    log_info "Starting Mesh MQTT Processor locally..."
    
    # Export environment variables from .env file
    if [ -f ".env" ]; then
        # Read each line from .env
        while IFS= read -r line; do
            # Skip empty lines, lines starting with #, or lines without an equals sign
            if [[ -z "$line" || "$line" =~ ^# || ! "$line" =~ = ]]; then
                continue
            fi
            # Export the line
            export "$line"
        done < .env
    fi
    
    # Clear potentially conflicting Google Cloud credentials env var
    # to allow Application Default Credentials to work properly
    if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        log_info "Clearing GOOGLE_APPLICATION_CREDENTIALS to use Application Default Credentials"
        unset GOOGLE_APPLICATION_CREDENTIALS
    fi
    
    # Set Python path
    export PYTHONPATH="${PWD}/src:${PYTHONPATH}"
    
    # Check if we have the required GCP_PROJECT
    if [ -z "$GCP_PROJECT" ]; then
        log_error "GCP_PROJECT is not set in .env file"
        log_info "Please edit .env file and set GCP_PROJECT to your Google Cloud project ID"
        exit 1
    fi
    
    log_info "Configuration:"
    log_info "  GCP Project: ${GCP_PROJECT}"
    log_info "  MQTT Broker: ${MQTT_BROKER_HOST:-mqtt.bayme.sh}:${MQTT_BROKER_PORT:-1883}"
    log_info "  MQTT Topic: ${MQTT_TOPIC:-#}"
    log_info "  Port: ${PORT:-8080}"
    echo
    
    # Start the application
    python src/run_app.py
}

# Run with Docker
run_docker() {
    log_info "Building and running with Docker..."
    
    # Build Docker image
    docker build -t mesh-mqtt-local .
    
    # Run container
    docker run --rm -it \\
        --env-file .env \\
        -p 8080:8080 \\
        mesh-mqtt-local
}

# Main function
main() {
    log_info "Mesh MQTT Processor - Local Development"
    echo
    
    # Parse arguments
    USE_DOCKER=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            --docker)
                USE_DOCKER=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --docker    Run using Docker instead of local Python"
                echo "  -h, --help  Show this help message"
                echo ""
                echo "Files:"
                echo "  .env        Environment configuration (copied from .env.example if not exists)"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check environment file
    if ! check_env; then
        exit 1
    fi
    
    if [ "$USE_DOCKER" = true ]; then
        run_docker
    else
        check_venv
        setup_python
        run_app
    fi
}

# Change to script directory
cd "$(dirname "$0")/.."

# Run main function
main "$@"
