#!/bin/bash
# Deploy NGRS Solver with Resource Limits
# This script updates the systemd service configuration to include memory/CPU limits

set -e

echo "================================================================="
echo "NGRS Solver - Resource-Limited Deployment"
echo "================================================================="
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run with sudo privileges"
    echo "   Usage: sudo ./deploy-with-resource-limits.sh"
    exit 1
fi

# Detect system resources
TOTAL_RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
TOTAL_CPUS=$(nproc)

echo "System Resources Detected:"
echo "  RAM: ${TOTAL_RAM_GB} GB"
echo "  CPUs: ${TOTAL_CPUS} cores"
echo ""

# Calculate recommended limits
# Memory: Use 70-75% of total RAM
RECOMMENDED_MEM_MAX=$((TOTAL_RAM_GB * 70 / 100))
RECOMMENDED_MEM_HIGH=$((TOTAL_RAM_GB * 60 / 100))

# CPU: Use 75-80% of total cores
RECOMMENDED_CPU_QUOTA=$((TOTAL_CPUS * 75))

echo "Recommended Resource Limits:"
echo "  MemoryMax: ${RECOMMENDED_MEM_MAX}G (70% of RAM)"
echo "  MemoryHigh: ${RECOMMENDED_MEM_HIGH}G (60% of RAM)"
echo "  CPUQuota: ${RECOMMENDED_CPU_QUOTA}% (75% of ${TOTAL_CPUS} cores)"
echo ""

# Allow manual override
read -p "Press ENTER to use recommended values, or type custom values below..."
read -p "  MemoryMax (GB) [${RECOMMENDED_MEM_MAX}]: " CUSTOM_MEM_MAX
read -p "  MemoryHigh (GB) [${RECOMMENDED_MEM_HIGH}]: " CUSTOM_MEM_HIGH
read -p "  CPUQuota (%) [${RECOMMENDED_CPU_QUOTA}]: " CUSTOM_CPU_QUOTA

# Use custom values if provided
MEM_MAX=${CUSTOM_MEM_MAX:-$RECOMMENDED_MEM_MAX}
MEM_HIGH=${CUSTOM_MEM_HIGH:-$RECOMMENDED_MEM_HIGH}
CPU_QUOTA=${CUSTOM_CPU_QUOTA:-$RECOMMENDED_CPU_QUOTA}

echo ""
echo "Applying Resource Limits:"
echo "  MemoryMax: ${MEM_MAX}G"
echo "  MemoryHigh: ${MEM_HIGH}G"
echo "  CPUQuota: ${CPU_QUOTA}%"
echo ""

# Generate service file with actual limits
SERVICE_FILE="/etc/systemd/system/ngrs.service"
TEMP_SERVICE_FILE="/tmp/ngrs.service"

cat > "$TEMP_SERVICE_FILE" << EOF
[Unit]
Description=NGRS Solver API with Resource Limits
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ngrs-solver
Environment="PATH=/home/ubuntu/ngrs-solver/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="SOLVER_MEMORY_LIMIT_PCT=70"

# Resource Limits
MemoryMax=${MEM_MAX}G
MemoryHigh=${MEM_HIGH}G
CPUQuota=${CPU_QUOTA}%
TasksMax=1024
LimitNOFILE=65536

# Restart Policy
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s

# Start Command
ExecStart=/home/ubuntu/ngrs-solver/venv/bin/uvicorn src.api_server:app --host 0.0.0.0 --port 8080 --workers 2 --log-level info

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ngrs-solver

[Install]
WantedBy=multi-user.target
EOF

# Stop the service
echo "Stopping ngrs service..."
systemctl stop ngrs || true

# Install new service file
echo "Installing service file with resource limits..."
cp "$TEMP_SERVICE_FILE" "$SERVICE_FILE"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start service
echo "Starting ngrs service..."
systemctl enable ngrs
systemctl start ngrs

# Check status
sleep 2
echo ""
echo "Service Status:"
systemctl status ngrs --no-pager -l | head -20

echo ""
echo "================================================================="
echo "✓ Deployment Complete with Resource Limits"
echo "================================================================="
echo ""
echo "Resource limits active:"
echo "  Memory: ${MEM_MAX}G max, ${MEM_HIGH}G high"
echo "  CPU: ${CPU_QUOTA}% quota"
echo ""
echo "Monitoring commands:"
echo "  sudo systemctl status ngrs"
echo "  sudo journalctl -u ngrs -f"
echo "  systemd-cgtop"  # Show resource usage by service
echo ""
echo "If solver exceeds limits:"
echo "  - MemoryMax → Process killed (OOM)"
echo "  - CPUQuota → Throttled (slower, but no crash)"
echo "  - Check logs: sudo journalctl -u ngrs --since '10 minutes ago'"
echo ""
