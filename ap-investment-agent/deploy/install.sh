#!/usr/bin/env bash
# One-step installer for the Andhra Pradesh investment agent on Ubuntu (e.g. AWS EC2).
# Run as the normal login user (ubuntu on EC2), not root:
#   curl -fsSL -o install.sh https://raw.githubusercontent.com/techstuf2020/samples/samples/ap-investment-agent/deploy/install.sh
#   bash install.sh
# Safe to run again: it updates the code and keeps existing settings unless you choose to replace them.
set -euo pipefail

REPO=https://github.com/techstuf2020/samples.git
BRANCH=samples
SRC="$HOME/samples"
APP=/opt/ap-investment-agent
ENV_FILE=/etc/ap-investment-agent.env
CLAUDE="$HOME/.local/bin/claude"

step() { printf '\n==> %s\n' "$*"; }
ask() { read -rp "$1" "$2" < /dev/tty; }
ask_secret() { read -rsp "$1" "$2" < /dev/tty; echo; }

if [ "$(id -u)" -eq 0 ]; then
    echo "Run this as your normal user (ubuntu on EC2), not with sudo." >&2
    exit 1
fi

step "Adding swap so compiling fits in memory"
if [ -z "$(swapon --show)" ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile > /dev/null
    sudo swapon /swapfile
else
    echo "Swap already on."
fi

step "Installing build tools"
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential git curl > /dev/null

step "Installing Rust"
if ! command -v cargo > /dev/null && [ ! -x "$HOME/.cargo/bin/cargo" ]; then
    curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal
fi
# shellcheck source=/dev/null
. "$HOME/.cargo/env"

step "Downloading the agent"
if [ -d "$SRC/.git" ]; then
    git -C "$SRC" pull --ff-only origin "$BRANCH"
else
    git clone -b "$BRANCH" "$REPO" "$SRC"
fi

step "Building the agent (5-10 minutes on a small machine)"
(cd "$SRC/ap-investment-agent" && cargo build --release)

step "Installing Claude Code"
if [ ! -x "$CLAUDE" ]; then
    curl -fsSL https://claude.ai/install.sh | bash
fi

configure=yes
if sudo test -f "$ENV_FILE"; then
    ask "Settings already exist. Replace them? [y/N] " answer
    [[ "$answer" =~ ^[Yy] ]] || configure=no
fi

if [ "$configure" = yes ]; then
    step "Connecting your Claude Pro account"
    echo "A link appears below. Open it on your phone or laptop, sign in to Claude and approve."
    echo "When it prints a long token, copy it."
    "$CLAUDE" setup-token < /dev/tty
    ask_secret "Paste the token here (it stays hidden): " token
    ask "Your Gmail address: " gmail
    ask_secret "Your Gmail App Password (hidden): " app_password
    app_password="${app_password// /}"

    if [ -z "$token" ] || [ -z "$gmail" ] || [ -z "$app_password" ]; then
        echo "The token, Gmail address and App Password are all needed. Run the installer again." >&2
        exit 1
    fi

    sudo install -m 600 /dev/null "$ENV_FILE"
    printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\nSMTP_USERNAME=%s\nSMTP_PASSWORD=%s\nREPORT_TO=%s\n' \
        "$token" "$gmail" "$app_password" "$gmail" | sudo tee "$ENV_FILE" > /dev/null
    unset token app_password
fi

step "Installing the agent and the weekly schedule"
sudo mkdir -p "$APP/reports"
sudo install -m 755 "$SRC/ap-investment-agent/target/release/ap-investment-agent" "$APP/"
sudo chown "$USER" "$APP/reports"
# The unit files are written for the ubuntu user; adjust them for whoever runs this.
sed -e "s/^User=ubuntu/User=$USER/" -e "s#/home/ubuntu#$HOME#" \
    "$SRC/ap-investment-agent/deploy/ap-investment-agent.service" \
    | sudo tee /etc/systemd/system/ap-investment-agent.service > /dev/null
sudo cp "$SRC/ap-investment-agent/deploy/ap-investment-agent.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ap-investment-agent.timer > /dev/null

ask "Send a test report now? It takes a few minutes. [Y/n] " answer
if [[ ! "$answer" =~ ^[Nn] ]]; then
    step "Running the research (a few minutes)"
    if sudo systemctl start ap-investment-agent.service; then
        echo "Done. Check your Gmail (and the spam folder) for \"AP investment report\"."
    else
        echo "The test run failed. Here is the log; paste it to Claude for help:" >&2
        sudo journalctl -u ap-investment-agent.service -n 30 --no-pager >&2
        exit 1
    fi
fi

step "All set"
systemctl list-timers ap-investment-agent.timer --no-pager | head -2
echo "The report will arrive every Monday at 7:30 AM IST."
