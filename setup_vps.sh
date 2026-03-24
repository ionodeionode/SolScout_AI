#!/bin/bash
# ================================================================
# SolScout AI — VPS Auto-Install Script
# Usage: curl -sSL <raw_github_url>/setup_vps.sh | bash
# Or:    chmod +x setup_vps.sh && ./setup_vps.sh
# ================================================================

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  🧠 SolScout AI — VPS Setup                              ║"
echo "║  Solana Agent Economy Hackathon                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ---- 1. System Dependencies ----
echo "📦 [1/6] Installing system dependencies..."
sudo apt update -y && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl nodejs npm

# ---- 2. Clone Repository ----
echo ""
echo "📂 [2/6] Cloning SolScout AI..."
REPO_DIR="$HOME/solscout-ai"
if [ -d "$REPO_DIR" ]; then
    echo "  Directory exists, pulling latest..."
    cd "$REPO_DIR"
    git pull
else
    git clone https://github.com/your-username/solscout-ai.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ---- 3. Python Virtual Environment ----
echo ""
echo "🐍 [3/6] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ---- 4. BWS SDK ----
echo ""
echo "🔧 [4/6] Setting up Bitget Wallet Skill SDK..."
mkdir -p vendor
if [ ! -d "vendor/bitget-wallet-skill" ]; then
    git clone https://github.com/nicola-xrpl/bitget-wallet-skill.git vendor/bitget-wallet-skill
fi
cd vendor/bitget-wallet-skill
npm install
cd "$REPO_DIR"

# ---- 5. Environment Config ----
echo ""
echo "⚙️  [5/6] Setting up environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  ⚠️  IMPORTANT: Edit .env with your API keys!            ║"
    echo "║                                                          ║"
    echo "║  nano ~/solscout-ai/.env                                 ║"
    echo "║                                                          ║"
    echo "║  Required:                                               ║"
    echo "║  - QWEN_API_KEY                                          ║"
    echo "║  - SOLANA_PRIVATE_KEY (for live trading)                 ║"
    echo "║  - SOLANA_WALLET_ADDRESS                                 ║"
    echo "╚══════════════════════════════════════════════════════════╝"
else
    echo "  .env already exists, skipping..."
fi

# ---- 6. Systemd Service ----
echo ""
echo "🚀 [6/6] Creating systemd service..."
sudo tee /etc/systemd/system/solscout.service > /dev/null << EOF
[Unit]
Description=SolScout AI Trading Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$REPO_DIR
Environment=PATH=$REPO_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$REPO_DIR/venv/bin/python main.py dashboard --port 8888
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable solscout

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  ✅ SolScout AI Installed!                                ║"
echo "║                                                          ║"
echo "║  Next Steps:                                             ║"
echo "║  1. Edit config:  nano ~/solscout-ai/.env                ║"
echo "║  2. Start agent:  sudo systemctl start solscout          ║"
echo "║  3. View logs:    sudo journalctl -u solscout -f         ║"
echo "║  4. Dashboard:    http://<your-vps-ip>:8888              ║"
echo "║                                                          ║"
echo "║  Quick Commands:                                         ║"
echo "║  - Stop:    sudo systemctl stop solscout                 ║"
echo "║  - Restart: sudo systemctl restart solscout              ║"
echo "║  - Status:  sudo systemctl status solscout               ║"
echo "╚══════════════════════════════════════════════════════════╝"
