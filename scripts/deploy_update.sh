#!/bin/bash
#
# NGRS Solver - Graceful Update & Restart Script
# Usage: ./deploy_update.sh
#
# This script safely deploys code updates and restarts the service.
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="ngrs-solver"
LOG_FILE="/var/log/ngrs-solver.log"
BACKUP_DIR="/opt/ngrs-solver-backups"
APP_DIR="/opt/ngrs-solver"

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}NGRS Solver - Graceful Update & Restart${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if running as correct user
check_user() {
    if [ "$EUID" -eq 0 ]; then 
        print_error "Do not run this script as root. Run as ubuntu user with sudo privileges."
        exit 1
    fi
}

# Function to create backup
create_backup() {
    print_status "Creating backup..."
    
    # Create backup directory if it doesn't exist
    sudo mkdir -p "$BACKUP_DIR"
    
    # Generate timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_PATH="$BACKUP_DIR/ngrs-solver_$TIMESTAMP"
    
    # Copy current code
    sudo cp -r "$APP_DIR" "$BACKUP_PATH"
    
    print_success "Backup created at: $BACKUP_PATH"
    echo ""
}

# Function to cleanup old backups
cleanup_old_backups() {
    print_status "Cleaning up old backups (older than 1 day)..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_status "No backup directory found, skipping cleanup"
        echo ""
        return
    fi
    
    # Find and count backups older than 1 day
    OLD_BACKUPS=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "ngrs-solver_*" -mtime +1 2>/dev/null || true)
    
    if [ -z "$OLD_BACKUPS" ]; then
        print_status "No old backups to clean up"
        echo ""
        return
    fi
    
    # Count old backups
    BACKUP_COUNT=$(echo "$OLD_BACKUPS" | wc -l)
    print_status "Found $BACKUP_COUNT old backup(s) to remove"
    
    # Delete old backups
    echo "$OLD_BACKUPS" | while read -r backup; do
        if [ -d "$backup" ]; then
            BACKUP_NAME=$(basename "$backup")
            print_status "  → Removing $BACKUP_NAME"
            sudo rm -rf "$backup"
        fi
    done
    
    print_success "Old backups cleaned up successfully"
    echo ""
}

# Function to stop service gracefully
stop_service() {
    print_status "Stopping $SERVICE_NAME service gracefully..."
    
    # Check if service is running
    if sudo systemctl is-active --quiet $SERVICE_NAME; then
        # Stop the service
        sudo systemctl stop $SERVICE_NAME
        
        # Wait for service to stop
        for i in {1..10}; do
            if ! sudo systemctl is-active --quiet $SERVICE_NAME; then
                print_success "Service stopped successfully"
                echo ""
                break
            fi
            sleep 1
        done
        
        # Force kill any remaining processes
        print_status "Ensuring all processes are terminated..."
        sudo pkill -9 -f '/opt/ngrs-solver' 2>/dev/null || true
        sudo pkill -9 -f 'uvicorn' 2>/dev/null || true
        sudo pkill -9 -f 'api_server' 2>/dev/null || true
        sleep 2
        print_success "All processes terminated"
        echo ""
    else
        print_status "Service is not running"
        echo ""
    fi
}

# Function to clear Redis job queue and data
clear_redis_data() {
    print_status "Clearing Redis job queue and cached data..."
    
    # Check if Redis is available
    if ! docker ps | grep -q redis 2>/dev/null && ! pgrep -x redis-server >/dev/null 2>&1; then
        print_warning "Redis not running, skipping Redis cleanup"
        echo ""
        return 0
    fi
    
    # Get job statistics before clearing
    if command -v redis-cli &> /dev/null; then
        TOTAL_KEYS=$(redis-cli -h localhost -p 6379 --scan --pattern "ngrs:*" 2>/dev/null | wc -l || echo "0")
        
        if [ "$TOTAL_KEYS" -gt 0 ]; then
            print_status "  Found $TOTAL_KEYS Redis keys with prefix 'ngrs:*'"
            
            # Delete all ngrs:* keys
            print_status "  → Deleting ngrs:* keys..."
            redis-cli -h localhost -p 6379 --scan --pattern "ngrs:*" | xargs -r redis-cli -h localhost -p 6379 DEL >/dev/null 2>&1 || true
            
            print_success "Cleared $TOTAL_KEYS Redis keys"
        else
            print_status "  No Redis keys found with prefix 'ngrs:*'"
        fi
    else
        print_warning "redis-cli not found, attempting Docker-based cleanup..."
        
        # Try via Docker if redis-cli not available
        if docker ps | grep -q redis 2>/dev/null; then
            REDIS_CONTAINER=$(docker ps --filter "ancestor=redis" --format "{{.Names}}" | head -n 1)
            if [ -n "$REDIS_CONTAINER" ]; then
                print_status "  → Clearing Redis via Docker container: $REDIS_CONTAINER"
                docker exec "$REDIS_CONTAINER" redis-cli KEYS "ngrs:*" | xargs -r docker exec "$REDIS_CONTAINER" redis-cli DEL >/dev/null 2>&1 || true
                print_success "Redis cleared via Docker"
            fi
        fi
    fi
    
    echo ""
}

# Function to check for processes on port 8080
check_port() {
    print_status "Checking if port 8080 is free..."
    
    # Try multiple times to ensure port is free
    for attempt in {1..3}; do
        PORT_PIDS=$(sudo lsof -ti :8080 2>/dev/null || true)
        
        if [ -n "$PORT_PIDS" ]; then
            print_warning "Found processes on port 8080 (attempt $attempt): $PORT_PIDS"
            print_status "Killing processes..."
            echo "$PORT_PIDS" | xargs -r sudo kill -9
            sleep 2
        else
            print_success "Port 8080 is free"
            echo ""
            return 0
        fi
    done
    
    # Final check
    PORT_PIDS=$(sudo lsof -ti :8080 2>/dev/null || true)
    if [ -n "$PORT_PIDS" ]; then
        print_error "Unable to free port 8080 after multiple attempts"
        exit 1
    fi
    
    print_success "Port 8080 is now free"
    echo ""
}

# Function to pull latest code
pull_code() {
    print_status "Pulling latest code from GitHub..."
    
    cd "$APP_DIR"
    
    # Show current commit
    CURRENT_COMMIT=$(git rev-parse --short HEAD)
    print_status "Current commit: $CURRENT_COMMIT"
    
    # Pull latest code
    git pull origin main
    
    # Show new commit
    NEW_COMMIT=$(git rev-parse --short HEAD)
    print_status "New commit: $NEW_COMMIT"
    
    if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
        print_warning "No new changes pulled"
    else
        print_success "Code updated successfully"
    fi
    
    echo ""
}

# Function to clear all caches
clear_cache() {
    print_status "Clearing all Python caches..."
    
    cd "$APP_DIR"
    
    # Remove Python bytecode cache files
    print_status "  → Removing .pyc files..."
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove __pycache__ directories
    print_status "  → Removing __pycache__ directories..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    
    # Remove .pytest_cache if exists
    if [ -d ".pytest_cache" ]; then
        print_status "  → Removing .pytest_cache..."
        rm -rf .pytest_cache
    fi
    
    # Clear pip cache (optional, but helps with clean installs)
    if [ -d "venv" ]; then
        print_status "  → Clearing pip cache..."
        source venv/bin/activate
        pip cache purge 2>/dev/null || true
        deactivate
    fi
    
    print_success "All caches cleared"
    echo ""
}

# Function to check Python syntax
check_syntax() {
    print_status "Checking Python syntax..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # Check main files for syntax errors
    SYNTAX_ERROR=0
    
    for file in src/api_server.py context/engine/solver_engine.py context/engine/slot_builder.py; do
        if [ -f "$file" ]; then
            if python3 -m py_compile "$file" 2>/dev/null; then
                echo -e "  ${GREEN}✓${NC} $file"
            else
                echo -e "  ${RED}✗${NC} $file"
                SYNTAX_ERROR=1
            fi
        fi
    done
    
    if [ $SYNTAX_ERROR -eq 1 ]; then
        print_error "Syntax errors found! Aborting deployment."
        exit 1
    fi
    
    print_success "All files passed syntax check"
    echo ""
}

# Function to clear log file
clear_logs() {
    print_status "Clearing old logs..."
    
    if [ -f "$LOG_FILE" ]; then
        # Archive old log
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        sudo mv "$LOG_FILE" "$LOG_FILE.$TIMESTAMP"
        sudo touch "$LOG_FILE"
        sudo chown ubuntu:ubuntu "$LOG_FILE"
        print_success "Old logs archived to $LOG_FILE.$TIMESTAMP"
    else
        sudo touch "$LOG_FILE"
        sudo chown ubuntu:ubuntu "$LOG_FILE"
        print_success "Log file created"
    fi
    echo ""
}

# Function to start service
start_service() {
    print_status "Starting $SERVICE_NAME service..."
    
    sudo systemctl start $SERVICE_NAME
    
    # Wait for service to start
    sleep 3
    
    # Check if service started successfully
    if sudo systemctl is-active --quiet $SERVICE_NAME; then
        print_success "Service started successfully"
    else
        print_error "Service failed to start"
        print_error "Check logs: tail -50 $LOG_FILE"
        exit 1
    fi
    echo ""
}

# Function to verify service
verify_service() {
    print_status "Verifying service health..."
    
    # Wait a bit for service to fully initialize
    sleep 5
    
    # Check if port 8080 is listening
    if sudo lsof -i :8080 | grep -q LISTEN; then
        print_success "Port 8080 is listening"
    else
        print_error "Port 8080 is NOT listening!"
        print_status "Checking logs for errors..."
        tail -30 "$LOG_FILE"
        exit 1
    fi
    
    # Test health endpoint
    print_status "Testing health endpoint..."
    HEALTH_RESPONSE=$(curl -s http://localhost:8080/health || echo "failed")
    
    if [[ "$HEALTH_RESPONSE" == *"ok"* ]]; then
        print_success "Health check passed"
    else
        print_error "Health check failed: $HEALTH_RESPONSE"
        exit 1
    fi
    
    # Test version endpoint
    print_status "Testing version endpoint..."
    VERSION_RESPONSE=$(curl -s http://localhost:8080/version || echo "failed")
    
    if [[ "$VERSION_RESPONSE" == *"version"* ]]; then
        print_success "Version endpoint working"
        echo -e "${GREEN}Version info:${NC}"
        echo "$VERSION_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$VERSION_RESPONSE"
    else
        print_warning "Version endpoint returned: $VERSION_RESPONSE"
    fi
    
    echo ""
}

# Function to show service status
show_status() {
    print_status "Service status:"
    sudo systemctl status $SERVICE_NAME --no-pager -l
    echo ""
}

# Function to show recent logs
show_logs() {
    print_status "Recent logs (last 20 lines):"
    echo -e "${YELLOW}--------------------------------${NC}"
    tail -20 "$LOG_FILE"
    echo -e "${YELLOW}--------------------------------${NC}"
    echo ""
}

# Main execution
main() {
    echo "Starting deployment process..."
    echo ""
    
    # Check user
    check_user
    
    # Create backup
    create_backup
    
    # Cleanup old backups (older than 1 day)
    cleanup_old_backups
    
    # Stop service gracefully
    stop_service
    
    # Clear Redis job queue and data
    clear_redis_data
    
    # Check and free port
    check_port
    
    # Pull latest code
    pull_code
    
    # Clear all caches (critical for Python module reloading)
    clear_cache
    
    # Check syntax
    check_syntax
    
    # Clear logs
    clear_logs
    
    # Start service
    start_service
    
    # Verify service
    verify_service
    
    # Show status
    show_status
    
    # Show recent logs
    show_logs
    
    # Final summary
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}✓ Deployment completed successfully!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo ""
    echo "Service is running and healthy."
    echo "You can now test the API at: https://ngrssolver09.comcentricapps.com"
    echo ""
    echo "Useful commands:"
    echo "  - Check status: sudo systemctl status $SERVICE_NAME"
    echo "  - View logs: tail -f $LOG_FILE"
    echo "  - Restart: sudo systemctl restart $SERVICE_NAME"
    echo "  - Stop: sudo systemctl stop $SERVICE_NAME"
    echo ""
}

# Run main function
main
