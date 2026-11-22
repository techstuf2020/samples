# Andhra Pradesh investment agent

A small Rust program that, once a week:

1. asks Claude to search the web for the past 7 days of Andhra Pradesh news: new investments, MoUs, SIPB approvals, tech and industry projects, infrastructure and policy changes;
2. saves the report as Markdown in `reports/YYYY-MM-DD.md`;
3. emails it to you through Gmail.

It runs every **Monday at 7:30 AM IST** using a systemd timer on an always-on Linux machine, such as an EC2 instance.

## What you need

| Item | Where to get it | Cost |
|---|---|---|
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) > API keys | Pay per use, separate from a Claude Pro plan. Roughly one long research request plus web searches each week |
| Gmail App Password | Google Account > Security > 2-Step Verification > App passwords | Free |
| Always-on Linux machine | e.g. AWS EC2 `t3.micro` with Ubuntu (free-tier eligible) | EC2 hourly price |

## Try it once

```bash
cargo build --release
export ANTHROPIC_API_KEY=...        # your key
./target/release/ap-investment-agent --dry-run   # prints the report, no email
```

Options:

- `--dry-run`: print the report instead of emailing it
- `--days N`: look back N days instead of 7

Settings are read from environment variables; see [`.env.example`](.env.example).

## Install on EC2 (Ubuntu)

```bash
# 1. Build (the swap file stops a 1 GB machine running out of memory while compiling)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
sudo apt-get update && sudo apt-get install -y build-essential git
curl https://sh.rustup.rs -sSf | sh -s -- -y && . "$HOME/.cargo/env"
git clone -b samples https://github.com/techstuf2020/samples.git
cd samples/ap-investment-agent
cargo build --release

# 2. Install the binary and settings
sudo mkdir -p /opt/ap-investment-agent
sudo cp target/release/ap-investment-agent /opt/ap-investment-agent/
sudo cp .env.example /etc/ap-investment-agent.env
sudo chmod 600 /etc/ap-investment-agent.env
sudo nano /etc/ap-investment-agent.env      # fill in your key, Gmail and app password

# 3. Schedule it
sudo cp deploy/ap-investment-agent.service deploy/ap-investment-agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ap-investment-agent.timer

# 4. Check
systemctl list-timers ap-investment-agent.timer   # shows the next run
sudo systemctl start ap-investment-agent.service  # run once now, sends an email
journalctl -u ap-investment-agent.service -n 50   # see the output
```

## Changing what it researches

Edit [`src/prompt.rs`](src/prompt.rs) to change the topics or the report layout, then rebuild and copy the binary again. Edit the `OnCalendar=` line in [`deploy/ap-investment-agent.timer`](deploy/ap-investment-agent.timer) to change the schedule, e.g. `*-*-* 07:30:00 Asia/Kolkata` for daily.

## Files

| File | What it does |
|---|---|
| `src/main.rs` | Reads settings, runs the research, saves and emails the report |
| `src/claude.rs` | Calls the Claude API with the web search tool |
| `src/prompt.rs` | The research instructions and report layout |
| `src/email.rs` | Converts the report to HTML and sends it through Gmail |
| `deploy/` | systemd service and weekly timer |
