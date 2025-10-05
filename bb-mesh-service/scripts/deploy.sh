#!/bin/bash

# Mesh MQTT GCP Deployment Script
# This script builds and deploys the application to Google Cloud Run

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT:-""}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"bb-mesh-service"}
REGION=${GCP_REGION:-"us-central1"}
REPO_NAME="bb-mesh"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"

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

# Check requirements
check_requirements() {
    log_info "Checking requirements..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if PROJECT_ID is set
    if [ -z "$PROJECT_ID" ]; then
        log_error "GCP_PROJECT environment variable is not set."
        echo "Please set it with: export GCP_PROJECT=your-project-id"
        exit 1
    fi
    
    log_success "All requirements met"
}

# Authenticate with Google Cloud
authenticate() {
    log_info "Authenticating with Google Cloud..."
    
    # Set the project
    gcloud config set project $PROJECT_ID
    
    # Configure docker for Artifact Registry
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
    
    log_success "Authenticated successfully"
}

# Build and push Docker image using buildx
build_and_push_image() {
    log_info "Building and pushing Docker image for linux/amd64..."
    
    # Use buildx to build for linux/amd64 and push directly
    docker buildx build --platform linux/amd64 --push -t $IMAGE_NAME .
    
    if [ $? -eq 0 ]; then
        log_success "Docker image built and pushed successfully: $IMAGE_NAME"
    else
        log_error "Failed to build and push Docker image"
        exit 1
    fi
}

# Deploy to Cloud Run
deploy_service() {
    log_info "Deploying to Cloud Run..."
    
    # Update the service.yaml with the correct project ID and image
    sed -i.bak "s/PROJECT_ID/$PROJECT_ID/g" deployment/service.yaml
    
    # Deploy using gcloud
    gcloud run services replace deployment/service.yaml \
        --region=$REGION \
        --quiet
    
    if [ $? -eq 0 ]; then
        log_success "Service deployed successfully to Cloud Run"
        
        # Get the service URL
        SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
        log_info "Service URL: $SERVICE_URL"
        
        # Test the service
        log_info "Testing service health check..."
        curl -f "$SERVICE_URL/health" > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            log_success "Service is healthy and responding"
        else
            log_warning "Service health check failed - may need time to start up"
        fi
        
    else
        log_error "Failed to deploy to Cloud Run"
        exit 1
    fi
    
    # Restore original service.yaml
    mv deployment/service.yaml.bak deployment/service.yaml
}

# Main deployment function
main() {
    log_info "Starting deployment of BB Mesh Service to Google Cloud Run"
    log_info "Project: $PROJECT_ID"
    log_info "Region: $REGION"
    log_info "Service: $SERVICE_NAME"
    echo
    
    check_requirements
    authenticate
    build_and_push_image
    deploy_service
    
    echo
    log_success "Deployment completed successfully!"
    log_info "You can monitor your service at: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME/metrics"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --project PROJECT_ID    Set GCP project ID"
            echo "  --region REGION         Set deployment region (default: us-central1)"
            echo "  --service SERVICE_NAME  Set service name (default: bb-mesh-service)"
            echo "  -h, --help             Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  GCP_PROJECT    Google Cloud project ID"
            echo "  GCP_REGION     Deployment region"
            echo "  SERVICE_NAME   Cloud Run service name"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main
