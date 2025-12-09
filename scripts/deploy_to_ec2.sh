#!/bin/bash
##############################################################################
# NGRS Solver - Automated EC2 Deployment Script
# 
# This script automates deployment of updates to the production EC2 server.
# It safely stops services, pulls latest code, updates dependencies, and
# restarts services with health verification.
#
# Usage: ./deploy_to_ec2.sh
#
# Prerequisites:
# - SSH access to EC2 instance
# - EC2_IP, EC2_USER, and SSH_KEY configured below
# - Git repository access on EC2
##############################################################################

set -e  # Exit on error

##############################################################################
# CONFIGURATION - Update these values for your environment
##############################################################################

EC2_IP="${EC2_IP:-your-ec2-public-ip}"
EC2_USER="${EC2_USER:-ubuntu}"
SSH_KEY="${SSH_KEY:-~/.ssh/your-key.pem}"
APP_DIR="ngrsserver08"
BRANCH="${BRANCH:-main}"

##############################################################################
# Color output
##############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

function log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function log_error() {
    echo -e "${RED}❌ $1${NC}"
}

##############################################################################
# Validation
##############################################################################

function validate_config() {
    log_info "Validating configuration..."
    
    if [ "$EC2_IP" == "your-ec2-public-ip" ]; then
        log_error "Please configure EC2_IP in the script or set as environment variable"
        exit 1
    fi
    
    if [ ! -f "$SSH_KEY" ]; then
        log_error "SSH key not found: $SSH_KEY"
        exit 1
    fi
    
    log_success "Configuration validated"
}

function test_connection() {
    log_info "Testing SSH connection to $EC2_USER@$EC2_IP..."
    
    if ! ssh -i "$SSH_KEY" -o ConnectTimeout=10 "$EC2_USER@$EC2_IP" "echo 'Connection successful'" &> /dev/null; then
        log_error "Cannot connect to EC2 instance"
        exit 1
    fi
    
    log_success "SSH connection successful"
}

##############################################################################
# Deployment Steps
##############################################################################

function get_current_version() {
    log_info "Getting current version..."
    
    CURRENT_VERSION=$(ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" \
        "curl -sf http://localhost:8080/version | jq -r '.apiVersion' 2>/dev/null || echo 'unknown'")
    
    log_info "Current version: $CURRENT_VERSION"
}

function stop_services() {
    log_info "Stopping NGRS services..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
        sudo systemctl stop ngrs-api
        
        # Wait for processes to stop
        sleep 3
        
        # Verify stopped
        if pgrep -f "uvicorn.*server:app" > /dev/null; then
            echo "Warning: Some processes still running"
            pkill -9 -f "uvicorn.*server:app" || true
        fi
EOF
    
    log_success "Services stopped"
}

function backup_current() {
    log_info "Creating backup of current deployment..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << EOF
        cd ~/$APP_DIR
        
        # Get current commit hash
        COMMIT=\$(git rev-parse --short HEAD)
        TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
        
        # Backup ratio cache if exists
        if [ -f config/ratio_cache.json ]; then
            mkdir -p ~/backups
            cp config/ratio_cache.json ~/backups/ratio_cache_\${TIMESTAMP}.json
            echo "Cache backed up to ~/backups/ratio_cache_\${TIMESTAMP}.json"
        fi
        
        echo "Current commit: \$COMMIT"
EOF
    
    log_success "Backup created"
}

function pull_updates() {
    log_info "Pulling latest code from $BRANCH branch..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << EOF
        cd ~/$APP_DIR
        
        # Stash any local changes (if any)
        git stash
        
        # Pull latest
        git pull origin $BRANCH
        
        # Show what changed
        git log --oneline -5
EOF
    
    log_success "Code updated"
}

function update_dependencies() {
    log_info "Updating Python dependencies..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << EOF
        cd ~/$APP_DIR
        pip3 install -r requirements.txt --upgrade --quiet
EOF
    
    log_success "Dependencies updated"
}

function start_services() {
    log_info "Starting NGRS services..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
        sudo systemctl start ngrs-api
        
        # Wait for startup
        sleep 5
EOF
    
    log_success "Services started"
}

function verify_deployment() {
    log_info "Verifying deployment..."
    
    # Wait for full startup
    sleep 5
    
    # Run health check on EC2
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
        cd ~/ngrsserver08/deploy
        ./health-check.sh
EOF
    
    if [ $? -eq 0 ]; then
        log_success "Health check passed"
    else
        log_error "Health check failed"
        return 1
    fi
    
    # Get new version
    NEW_VERSION=$(ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" \
        "curl -sf http://localhost:8080/version | jq -r '.apiVersion' 2>/dev/null || echo 'unknown'")
    
    log_success "New version deployed: $NEW_VERSION"
}

function test_endpoints() {
    log_info "Testing API endpoints..."
    
    # Test health
    if ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "curl -sf http://localhost:8080/health" > /dev/null; then
        log_success "/health - OK"
    else
        log_error "/health - FAILED"
    fi
    
    # Test version
    if ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "curl -sf http://localhost:8080/version" > /dev/null; then
        log_success "/version - OK"
    else
        log_error "/version - FAILED"
    fi
    
    # Test async stats
    if ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "curl -sf http://localhost:8080/solve/async/stats" > /dev/null; then
        log_success "/solve/async/stats - OK"
    else
        log_error "/solve/async/stats - FAILED"
    fi
}

function show_logs() {
    log_info "Recent logs (last 20 lines):"
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
        sudo journalctl -u ngrs-api -n 20 --no-pager
EOF
}

##############################################################################
# Rollback Function
##############################################################################

function rollback() {
    log_warning "Rolling back deployment..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
        cd ~/ngrsserver08
        
        # Stop services
        sudo systemctl stop ngrs-api
        
        # Revert to previous commit
        git reset --hard HEAD~1
        
        # Reinstall dependencies
        pip3 install -r requirements.txt --quiet
        
        # Start services
        sudo systemctl start ngrs-api
        
        sleep 5
        
        # Health check
        cd deploy
        ./health-check.sh
EOF
    
    if [ $? -eq 0 ]; then
        log_success "Rollback successful"
    else
        log_error "Rollback failed - manual intervention required"
    fi
}

##############################################################################
# Main Deployment Flow
##############################################################################

function deploy() {
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  NGRS Solver - EC2 Deployment"
    echo "  Target: $EC2_USER@$EC2_IP"
    echo "  Branch: $BRANCH"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    
    validate_config
    test_connection
    get_current_version
    
    echo ""
    read -p "Continue with deployment? (y/N) " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Deployment cancelled"
        exit 0
    fi
    
    echo ""
    log_info "Starting deployment..."
    echo ""
    
    stop_services
    backup_current
    pull_updates
    update_dependencies
    start_services
    
    echo ""
    log_info "Running verification tests..."
    echo ""
    
    if verify_deployment && test_endpoints; then
        echo ""
        echo "════════════════════════════════════════════════════════════════"
        log_success "🎉 Deployment completed successfully!"
        echo "════════════════════════════════════════════════════════════════"
        echo ""
        log_info "Version: $CURRENT_VERSION → $NEW_VERSION"
        log_info "Public URL: http://$EC2_IP:8080"
        echo ""
        
        # Show recent logs
        show_logs
        
        return 0
    else
        echo ""
        echo "════════════════════════════════════════════════════════════════"
        log_error "Deployment verification failed!"
        echo "════════════════════════════════════════════════════════════════"
        echo ""
        
        read -p "Rollback to previous version? (y/N) " -n 1 -r
        echo ""
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback
        else
            log_warning "Please check logs and fix manually"
            show_logs
        fi
        
        return 1
    fi
}

##############################################################################
# Script Entry Point
##############################################################################

# Check for required commands
for cmd in ssh jq; do
    if ! command -v $cmd &> /dev/null; then
        log_error "Required command not found: $cmd"
        exit 1
    fi
done

# Run deployment
deploy

exit $?
