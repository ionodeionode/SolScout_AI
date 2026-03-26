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
echo "📦 [1/7] Installing system dependencies..."
sudo apt update -y && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git curl nodejs npm

# ---- 2. Clone Repository ----
echo ""
echo "📂 [2/7] Cloning SolScout AI..."
REPO_DIR="$HOME/solscout-ai"
if [ -d "$REPO_DIR" ]; then
    echo "  Directory exists, pulling latest..."
    cd "$REPO_DIR"
    git pull
else
    git clone https://github.com/ionodeionode/SolScout_AI.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

# ---- 3. Python Virtual Environment ----
echo ""
echo "🐍 [3/7] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ---- 4. BWS SDK ----
echo ""
echo "🔧 [4/7] Setting up Bitget Wallet Skill SDK..."
mkdir -p vendor
if [ ! -d "vendor/bitget-wallet-skill" ]; then
    git clone https://github.com/bitget-wallet-ai-lab/bitget-wallet-skill.git vendor/bitget-wallet-skill
fi
cd vendor/bitget-wallet-skill
npm install
cd "$REPO_DIR"

# ---- 5. Environment Config ----
echo ""
echo "⚙️  [5/7] Setting up environment..."
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
echo "🚀 [6/7] Creating systemd service..."
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

# ---- 7. Daily Restart Cronjob ----
echo ""
echo "⏰ [7/7] Configuring 7 AM Daily Restart Cronjob..."
# Overwrites existing solscout cron entries to prevent duplicates
(crontab -l 2>/dev/null | grep -v "systemctl restart solscout"; echo "0 7 * * * sudo systemctl restart solscout") | crontab -
echo "  ↳ Setup complete: Bot will reset memory daily at 07:00."

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
