#!/bin/bash
#
# NGRS Solver - EC2 Initial Setup Script
# Run this on a fresh Ubuntu 22.04 or Amazon Linux 2023 instance
#
# Usage:
#   chmod +x ec2-setup.sh
#   ./ec2-setup.sh
#

set -e  # Exit on error

echo "=========================================="
echo "NGRS Solver - EC2 Setup"
echo "=========================================="

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

echo "Detected OS: $OS"

# 1. Install Docker
echo ""
echo "[1/6] Installing Docker..."
if [ "$OS" = "ubuntu" ]; then
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
elif [ "$OS" = "amzn" ]; then
    sudo yum update -y
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ec2-user
fi

echo "✓ Docker installed"

# 2. Install Python 3.11+
echo ""
echo "[2/6] Installing Python..."
if [ "$OS" = "ubuntu" ]; then
    sudo apt-get install -y python3 python3-pip python3-venv
elif [ "$OS" = "amzn" ]; then
    sudo yum install -y python3 python3-pip
fi

python3 --version
echo "✓ Python installed"

# 3. Start Redis container
echo ""
echo "[3/6] Starting Redis..."
sudo docker run -d \
    --name ngrs-redis \
    --restart unless-stopped \
    -p 6379:6379 \
    redis:7-alpine

echo "✓ Redis started on port 6379"

# 4. Wait for Redis to be ready
echo ""
echo "[4/6] Waiting for Redis to be ready..."
sleep 3
sudo docker exec ngrs-redis redis-cli ping
echo "✓ Redis is responding"

# 5. Create application directory
echo ""
echo "[5/6] Setting up application directory..."
APP_DIR="$HOME/ngrssolver"

if [ ! -d "$APP_DIR" ]; then
    echo "Please deploy your application code to: $APP_DIR"
    echo "You can use: scp -r ngrssolver/ user@ec2-ip:~/"
else
    echo "✓ Application directory exists: $APP_DIR"
fi

# 6. Create environment file
echo ""
echo "[6/6] Creating environment configuration..."

cat > $HOME/.ngrs-env << 'EOF'
# NGRS Solver Environment Configuration
export START_WORKERS=true
export SOLVER_WORKERS=4
export REDIS_URL=localhost:6379
export REDIS_DB=0
export RESULT_TTL_SECONDS=3600
export PORT=8080
EOF

echo "✓ Environment file created: $HOME/.ngrs-env"

# Summary
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Deploy your code:"
echo "   scp -r ngrssolver/ $USER@<ec2-ip>:~/"
echo ""
echo "2. Install Python dependencies:"
echo "   cd ~/ngrssolver"
echo "   pip3 install -r requirements.txt"
echo ""
echo "3. Start the solver:"
echo "   source ~/.ngrs-env"
echo "   python3 -m uvicorn src.api_server:app --host 0.0.0.0 --port 8080"
echo ""
echo "Or use the start script:"
echo "   cd ~/ngrssolver/deploy"
echo "   ./start-solver.sh"
echo ""
echo "=========================================="
echo ""
echo "NOTE: You may need to log out and back in for Docker permissions."
echo ""
