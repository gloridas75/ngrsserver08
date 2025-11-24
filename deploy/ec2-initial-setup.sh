#!/bin/bash
#
# Initial setup script for EC2 - Run once after creating instance
# This prepares the EC2 to receive deployments from GitHub Actions
#

set -e  # Exit on error

echo "========================================"
echo "NGRS Solver - EC2 Initial Setup"
echo "========================================"

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

echo "Detected OS: $OS"

# Update system
echo ""
echo "=== Updating system packages ==="
if [ "$OS" = "ubuntu" ]; then
    sudo apt-get update -y
    sudo apt-get upgrade -y
elif [ "$OS" = "amzn" ]; then
    sudo yum update -y
fi

# Install Docker
echo ""
echo "=== Installing Docker ==="
if [ "$OS" = "ubuntu" ]; then
    sudo apt-get install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
elif [ "$OS" = "amzn" ]; then
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
fi

# Add current user to docker group
sudo usermod -aG docker $USER
echo "Note: You may need to log out and back in for docker group to take effect"

# Install Python 3.11+ and pip
echo ""
echo "=== Installing Python ==="
if [ "$OS" = "ubuntu" ]; then
    sudo apt-get install -y python3 python3-pip python3-venv
elif [ "$OS" = "amzn" ]; then
    sudo yum install -y python3 python3-pip
fi

# Install git
echo ""
echo "=== Installing Git ==="
if [ "$OS" = "ubuntu" ]; then
    sudo apt-get install -y git
elif [ "$OS" = "amzn" ]; then
    sudo yum install -y git
fi

# Configure git (optional - for better logging)
git config --global user.name "EC2 Deploy"
git config --global user.email "deploy@ec2.local"

# Start Redis container
echo ""
echo "=== Starting Redis container ==="
docker stop ngrs-redis 2>/dev/null || true
docker rm ngrs-redis 2>/dev/null || true
docker run -d \
    --name ngrs-redis \
    --restart unless-stopped \
    -p 6379:6379 \
    redis:7-alpine

echo "Redis started on port 6379"

# Clone repository
echo ""
echo "=== Setting up repository ==="
read -p "Enter your GitHub repository URL (https://github.com/gloridas75/ngrsserver08.git): " REPO_URL

if [ -d ~/ngrssolver ]; then
    echo "Directory ~/ngrssolver already exists. Backing up..."
    mv ~/ngrssolver ~/ngrssolver.backup.$(date +%s)
fi

cd ~
git clone $REPO_URL ngrssolver
cd ngrssolver

# Install Python dependencies
echo ""
echo "=== Installing Python dependencies ==="
pip3 install --user -r requirements.txt

# Create systemd service for API
echo ""
echo "=== Creating systemd service ==="
sudo tee /etc/systemd/system/ngrs-api.service > /dev/null <<EOF
[Unit]
Description=NGRS Solver API with Redis Workers
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/ngrssolver
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="START_WORKERS=true"
Environment="SOLVER_WORKERS=4"
Environment="REDIS_URL=localhost:6379"
Environment="RESULT_TTL_SECONDS=3600"
ExecStart=/usr/bin/python3 -m uvicorn src.api_server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable ngrs-api
sudo systemctl start ngrs-api

echo ""
echo "=== Waiting for service to start ==="
sleep 5

# Health check
echo ""
echo "=== Running health check ==="
if curl -f http://localhost:8080/health; then
    echo ""
    echo "✓ Health check passed!"
else
    echo ""
    echo "✗ Health check failed. Check logs with: sudo journalctl -u ngrs-api -f"
    exit 1
fi

# Check Redis stats
echo ""
echo "=== Checking Redis connection ==="
curl -s http://localhost:8080/solve/async/stats | python3 -m json.tool || echo "Stats endpoint not available yet"

# Setup automatic pull on system reboot (optional)
echo ""
echo "=== Setting up auto-update on reboot (optional) ==="
read -p "Auto-pull from GitHub on system reboot? (y/n): " AUTO_PULL

if [ "$AUTO_PULL" = "y" ]; then
    crontab -l 2>/dev/null > /tmp/crontab.tmp || true
    echo "@reboot sleep 60 && cd $HOME/ngrssolver && git pull origin main && sudo systemctl restart ngrs-api" >> /tmp/crontab.tmp
    crontab /tmp/crontab.tmp
    rm /tmp/crontab.tmp
    echo "Auto-pull enabled on reboot"
fi

echo ""
echo "========================================"
echo "✓ Initial setup complete!"
echo "========================================"
echo ""
echo "Services:"
echo "  - Redis:     docker ps | grep ngrs-redis"
echo "  - API:       sudo systemctl status ngrs-api"
echo ""
echo "Logs:"
echo "  - API logs:  sudo journalctl -u ngrs-api -f"
echo "  - Redis:     docker logs ngrs-redis"
echo ""
echo "Testing:"
echo "  - Health:    curl http://localhost:8080/health"
echo "  - Stats:     curl http://localhost:8080/solve/async/stats"
echo ""
echo "Next steps:"
echo "1. Configure GitHub Actions secrets (see deploy/README.md)"
echo "2. Push code to GitHub - it will auto-deploy!"
echo ""
