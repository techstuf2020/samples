# Andhra Pradesh investment agent

A small Rust program that, once a week:

1. has Claude search the web for the past 7 days of Andhra Pradesh news: new investments, MoUs, SIPB approvals, tech and industry projects, infrastructure and policy changes;
2. saves the report as Markdown in `reports/YYYY-MM-DD.md`;
3. emails it to you through Gmail.

It runs every **Monday at 7:30 AM IST** using a systemd timer on an always-on Linux machine, such as an EC2 instance.

By default it runs the research through **Claude Code signed in with your Claude Pro plan**, so no API key is needed; it uses your plan's usage limits. Set `BACKEND=api` to call the Claude API with an API key instead.

## What you need

| Item | Where to get it | Cost |
|---|---|---|
| Claude Pro (or Max) plan | claude.ai | Your existing plan |
| Gmail App Password | Google Account > Security > 2-Step Verification > App passwords | Free |
| Always-on Linux machine | e.g. AWS EC2 `t3.micro` with Ubuntu (free-tier eligible) | EC2 hourly price |

## Install on EC2 (Ubuntu)

Run these as the default `ubuntu` user.

```bash
# 1. Build (the swap file stops a 1 GB machine running out of memory while compiling)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
sudo apt-get update && sudo apt-get install -y build-essential git
curl https://sh.rustup.rs -sSf | sh -s -- -y && . "$HOME/.cargo/env"
git clone -b samples https://github.com/techstuf2020/samples.git
cd samples/ap-investment-agent
cargo build --release

# 2. Install Claude Code and get a sign-in token for your Pro plan
curl -fsSL https://claude.ai/install.sh | bash
~/.local/bin/claude setup-token      # opens a link to sign in; prints a token

# 3. Install the agent and its settings
sudo mkdir -p /opt/ap-investment-agent/reports
sudo cp target/release/ap-investment-agent /opt/ap-investment-agent/
sudo chown ubuntu /opt/ap-investment-agent/reports
sudo cp .env.example /etc/ap-investment-agent.env
sudo chmod 600 /etc/ap-investment-agent.env
sudo nano /etc/ap-investment-agent.env   # paste the token, your Gmail and app password

# 4. Schedule it
sudo cp deploy/ap-investment-agent.service deploy/ap-investment-agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ap-investment-agent.timer

# 5. Check
sudo systemctl start ap-investment-agent.service  # run once now, sends an email
journalctl -u ap-investment-agent.service -n 50   # see the output
systemctl list-timers ap-investment-agent.timer   # shows the next run
```

## Try it by hand

```bash
export CLAUDE_CODE_OAUTH_TOKEN=...       # from `claude setup-token`
./target/release/ap-investment-agent --dry-run   # prints the report, no email
```

Options:

- `--dry-run`: print the report instead of emailing it
- `--days N`: look back N days instead of 7

Settings are read from environment variables; see [`.env.example`](.env.example).

## Changing what it researches

Edit [`src/prompt.rs`](src/prompt.rs) to change the topics or the report layout, then rebuild and copy the binary again. Edit the `OnCalendar=` line in [`deploy/ap-investment-agent.timer`](deploy/ap-investment-agent.timer) to change the schedule, e.g. `*-*-* 07:30:00 Asia/Kolkata` for daily.

## Files

| File | What it does |
|---|---|
| `src/main.rs` | Reads settings, runs the research, saves and emails the report |
| `src/claude_code.rs` | Runs the research through the Claude Code CLI (default) |
| `src/claude.rs` | Calls the Claude API with the web search tool (`BACKEND=api`) |
| `src/prompt.rs` | The research instructions and report layout |
| `src/email.rs` | Converts the report to HTML and sends it through Gmail |
| `deploy/` | systemd service and weekly timer |
