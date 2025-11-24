#!/bin/bash
#
# Install NGRS Solver as systemd service (production mode)
#
# This creates systemd services for:
# 1. Redis (Docker container)
# 2. NGRS API + Workers
#
# Services will auto-start on boot and restart on failure.
#

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
USER_NAME="${SUDO_USER:-$USER}"

echo "=========================================="
echo "Installing NGRS Solver as systemd service"
echo "=========================================="
echo ""
echo "Project directory: $PROJECT_DIR"
echo "User: $USER_NAME"
echo ""

# 1. Create Redis service
echo "[1/3] Creating Redis service..."
cat > /etc/systemd/system/ngrs-redis.service << EOF
[Unit]
Description=Redis for NGRS Solver
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=-/usr/bin/docker stop ngrs-redis
ExecStartPre=-/usr/bin/docker rm ngrs-redis
ExecStart=/usr/bin/docker run -d --name ngrs-redis --restart unless-stopped -p 6379:6379 redis:7-alpine
ExecStop=/usr/bin/docker stop ngrs-redis
ExecStopPost=/usr/bin/docker rm ngrs-redis

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Redis service created"

# 2. Create API service
echo ""
echo "[2/3] Creating API service..."
cat > /etc/systemd/system/ngrs-api.service << EOF
[Unit]
Description=NGRS Solver API Server
After=ngrs-redis.service network.target
Requires=ngrs-redis.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
Environment="START_WORKERS=true"
Environment="SOLVER_WORKERS=4"
Environment="REDIS_URL=localhost:6379"
Environment="REDIS_DB=0"
Environment="RESULT_TTL_SECONDS=3600"
Environment="PORT=8080"
ExecStart=/usr/bin/python3 -m uvicorn src.api_server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "✓ API service created"

# 3. Enable and start services
echo ""
echo "[3/3] Enabling services..."
systemctl daemon-reload
systemctl enable ngrs-redis.service
systemctl enable ngrs-api.service

echo "✓ Services enabled"

# Start services
echo ""
echo "Starting services..."
systemctl start ngrs-redis.service
sleep 2
systemctl start ngrs-api.service
sleep 2

# Check status
echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Service Status:"
echo ""
systemctl status ngrs-redis.service --no-pager -l
echo ""
systemctl status ngrs-api.service --no-pager -l
echo ""
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  Start:   sudo systemctl start ngrs-api"
echo "  Stop:    sudo systemctl stop ngrs-api"
echo "  Restart: sudo systemctl restart ngrs-api"
echo "  Status:  sudo systemctl status ngrs-api"
echo "  Logs:    sudo journalctl -u ngrs-api -f"
echo ""
echo "Redis commands:"
echo "  Status:  sudo systemctl status ngrs-redis"
echo "  Logs:    docker logs ngrs-redis"
echo ""
