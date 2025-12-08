#!/bin/bash
# Setup script for NGRS Solver systemd service on Ubuntu

echo "🚀 Setting up NGRS Solver systemd service..."
echo

# Get the current directory (should be /opt/ngrs-solver)
PROJECT_DIR=$(pwd)
VENV_PATH="$PROJECT_DIR/venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "Please create it first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

echo "✓ Project directory: $PROJECT_DIR"
echo "✓ Virtual environment: $VENV_PATH"
echo

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/ngrs-solver.service"

echo "Creating systemd service file at $SERVICE_FILE..."

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=NGRS Solver API Service
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_PATH/bin"
ExecStart=$VENV_PATH/bin/uvicorn src.api_server:app --host 0.0.0.0 --port 8080 --workers 2
Restart=always
RestartSec=10
StandardOutput=append:/var/log/ngrs-solver.log
StandardError=append:/var/log/ngrs-solver.log

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Service file created"
echo

# Create log file with proper permissions
echo "Creating log file..."
sudo touch /var/log/ngrs-solver.log
sudo chown ubuntu:ubuntu /var/log/ngrs-solver.log
echo "✓ Log file created at /var/log/ngrs-solver.log"
echo

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "✓ Systemd reloaded"
echo

# Enable service
echo "Enabling service to start on boot..."
sudo systemctl enable ngrs-solver
echo "✓ Service enabled"
echo

# Start service
echo "Starting NGRS Solver service..."
sudo systemctl start ngrs-solver
echo "✓ Service started"
echo

# Wait a moment for service to start
sleep 2

# Check status
echo "Checking service status..."
sudo systemctl status ngrs-solver --no-pager
echo

# Test the API
echo "Testing API health endpoint..."
sleep 2
curl -s http://localhost:8080/health | python3 -m json.tool || echo "API not responding yet, check logs"
echo

echo "✅ Setup complete!"
echo
echo "Useful commands:"
echo "  sudo systemctl status ngrs-solver    # Check status"
echo "  sudo systemctl restart ngrs-solver   # Restart service"
echo "  sudo systemctl stop ngrs-solver      # Stop service"
echo "  sudo systemctl start ngrs-solver     # Start service"
echo "  sudo journalctl -u ngrs-solver -f    # View live logs"
echo "  tail -f /var/log/ngrs-solver.log     # View log file"
echo "  curl http://localhost:8080/version   # Check API version"
