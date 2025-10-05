#!/bin/bash

# Mesh MQTT GCP Monitoring Script
# This script monitors the deployed service and provides health checks

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT:-""}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"mesh-mqtt-processor"}
INTERVAL=${MONITOR_INTERVAL:-30}

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

# Get service URL
get_service_url() {
    if [ -z "$PROJECT_ID" ]; then
        log_error "GCP_PROJECT environment variable is not set."
        exit 1
    fi
    
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \\
        --project=$PROJECT_ID \\
        --region=$REGION \\
        --format='value(status.url)' 2>/dev/null)
    
    if [ -z "$SERVICE_URL" ]; then
        log_error "Could not find service $SERVICE_NAME in project $PROJECT_ID region $REGION"
        exit 1
    fi
    
    echo $SERVICE_URL
}

# Check service health
check_health() {
    local service_url=$1
    local health_url="${service_url}/health"
    
    # Make HTTP request and capture response
    response=$(curl -s -w "HTTPSTATUS:%{http_code}\\nTIME:%{time_total}" "$health_url" 2>/dev/null || echo "FAILED")
    
    if [[ $response == "FAILED" ]]; then
        echo "FAILED - No response"
        return 1
    fi
    
    # Extract HTTP status and response time
    http_status=$(echo "$response" | grep "HTTPSTATUS:" | cut -d: -f2)
    response_time=$(echo "$response" | grep "TIME:" | cut -d: -f2)
    body=$(echo "$response" | sed -E 's/HTTPSTATUS:[0-9]+//g' | sed -E 's/TIME:[0-9.]+//g')
    
    if [[ $http_status -eq 200 ]]; then
        echo "HEALTHY - ${response_time}s response time"
        return 0
    else
        echo "UNHEALTHY - HTTP $http_status - ${response_time}s response time"
        return 1
    fi
}

# Get service stats
get_stats() {
    local service_url=$1
    local stats_url="${service_url}/stats"
    
    log_info "Fetching service statistics..."
    
    response=$(curl -s "$stats_url" 2>/dev/null || echo "{}")
    
    if [[ $response != "{}" ]]; then
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        log_warning "Could not fetch statistics"
    fi
}

# Monitor service continuously
monitor_service() {
    local service_url=$1
    
    log_info "Starting continuous monitoring (interval: ${INTERVAL}s)"
    log_info "Service URL: $service_url"
    log_info "Press Ctrl+C to stop monitoring"
    echo
    
    consecutive_failures=0
    
    while true; do
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        health_result=$(check_health "$service_url")
        status=$?
        
        if [[ $status -eq 0 ]]; then
            consecutive_failures=0
            log_success "[$timestamp] $health_result"
        else
            consecutive_failures=$((consecutive_failures + 1))
            log_error "[$timestamp] $health_result (consecutive failures: $consecutive_failures)"
            
            # Alert after 3 consecutive failures
            if [[ $consecutive_failures -eq 3 ]]; then
                log_error "ALERT: Service has failed health checks 3 times in a row!"
            fi
        fi
        
        sleep $INTERVAL
    done
}

# Get Cloud Run service info
get_service_info() {
    log_info "Fetching Cloud Run service information..."
    
    gcloud run services describe $SERVICE_NAME \\
        --project=$PROJECT_ID \\
        --region=$REGION \\
        --format="table(
            status.url:label='URL',
            status.traffic[0].percent:label='TRAFFIC%',
            status.conditions[0].status:label='READY',
            spec.template.spec.containers[0].image:label='IMAGE'
        )"
}

# Get recent logs
get_logs() {
    local lines=${1:-50}
    
    log_info "Fetching recent logs (last $lines lines)..."
    
    gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \\
        --project=$PROJECT_ID \\
        --limit=$lines \\
        --format="table(timestamp,severity,textPayload)" \\
        --sort-by="~timestamp"
}

# Show metrics
show_metrics() {
    log_info "Opening Cloud Run metrics dashboard..."
    
    metrics_url="https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME/metrics?project=$PROJECT_ID"
    
    if command -v open &> /dev/null; then
        open "$metrics_url"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$metrics_url"
    else
        echo "Metrics URL: $metrics_url"
    fi
}

# Main function
main() {
    case $1 in
        health|h)
            service_url=$(get_service_url)
            log_info "Checking service health: $service_url"
            result=$(check_health "$service_url")
            status=$?
            if [[ $status -eq 0 ]]; then
                log_success "$result"
            else
                log_error "$result"
            fi
            exit $status
            ;;
        stats|s)
            service_url=$(get_service_url)
            get_stats "$service_url"
            ;;
        monitor|m)
            service_url=$(get_service_url)
            monitor_service "$service_url"
            ;;
        info|i)
            get_service_info
            ;;
        logs|l)
            get_logs ${2:-50}
            ;;
        metrics|mt)
            show_metrics
            ;;
        *)
            echo "Mesh MQTT GCP Monitoring Script"
            echo ""
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  health, h          Check service health once"
            echo "  stats, s           Get service statistics"
            echo "  monitor, m         Monitor service continuously"
            echo "  info, i            Show Cloud Run service information"
            echo "  logs, l [lines]    Show recent logs (default: 50 lines)"
            echo "  metrics, mt        Open metrics dashboard"
            echo ""
            echo "Environment variables:"
            echo "  GCP_PROJECT        Google Cloud project ID"
            echo "  GCP_REGION         Deployment region (default: us-central1)"
            echo "  SERVICE_NAME       Service name (default: mesh-mqtt-processor)"
            echo "  MONITOR_INTERVAL   Monitoring interval in seconds (default: 30)"
            echo ""
            echo "Examples:"
            echo "  $0 health                    # Check health once"
            echo "  $0 monitor                   # Continuous monitoring"
            echo "  $0 logs 100                  # Get last 100 log lines"
            echo "  MONITOR_INTERVAL=10 $0 m     # Monitor every 10 seconds"
            exit 1
            ;;
    esac
}

# Parse global options
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
        *)
            break
            ;;
    esac
done

# Run main function
main "$@"
