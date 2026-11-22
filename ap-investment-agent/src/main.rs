//! Weekly Andhra Pradesh investment report: researches with Claude + web search,
//! saves the report as Markdown, and emails it through Gmail.
//!
//! Usage: ap-investment-agent [--dry-run] [--days N]
//!
//! BACKEND=claude-code (default) runs the Claude Code CLI on a Claude subscription;
//! BACKEND=api calls the Claude API with ANTHROPIC_API_KEY.

mod claude;
mod claude_code;
mod email;
mod prompt;

use std::{env, fs, path::PathBuf};

use anyhow::{Context, Result, bail};
use chrono::{Duration, Local};

fn main() -> Result<()> {
    let mut dry_run = false;
    let mut days = 7;
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--dry-run" => dry_run = true,
            "--days" => days = args.next().context("--days needs a number")?.parse()?,
            other => bail!("unknown argument: {other} (expected --dry-run or --days N)"),
        }
    }

    // Check every setting up front so a scheduled run fails before spending on research.
    let backend = Backend::from_env()?;
    let smtp = if dry_run {
        None
    } else {
        Some(email::Smtp {
            host: env::var("SMTP_HOST").unwrap_or_else(|_| "smtp.gmail.com".into()),
            username: required("SMTP_USERNAME")?,
            password: required("SMTP_PASSWORD")?,
            to: required("REPORT_TO")?,
        })
    };

    let today = Local::now().date_naive();
    let from = today - Duration::days(days);
    let (from, to) = (from.format("%d %b %Y").to_string(), today.format("%d %b %Y").to_string());

    eprintln!("Researching Andhra Pradesh investments from {from} to {to}...");
    let body = backend.research(prompt::SYSTEM, &prompt::weekly(&from, &to))?;
    let report = format!("# Andhra Pradesh investment report\n\n_{from} to {to}_\n\n{body}\n");

    let dir = PathBuf::from(env::var("REPORT_DIR").unwrap_or_else(|_| "reports".into()));
    fs::create_dir_all(&dir)?;
    let path = dir.join(format!("{}.md", today.format("%Y-%m-%d")));
    fs::write(&path, &report)?;
    eprintln!("Saved {}", path.display());

    match smtp {
        Some(smtp) => {
            smtp.send(&format!("AP investment report: {from} to {to}"), &report)?;
            eprintln!("Emailed the report to {}", smtp.to);
        }
        None => println!("{report}"),
    }
    Ok(())
}

enum Backend {
    ClaudeCode { bin: String },
    Api { api_key: String, model: String },
}

impl Backend {
    fn from_env() -> Result<Self> {
        match env::var("BACKEND").as_deref() {
            Err(_) | Ok("claude-code") => Ok(Self::ClaudeCode {
                bin: env::var("CLAUDE_BIN").unwrap_or_else(|_| "claude".into()),
            }),
            Ok("api") => Ok(Self::Api {
                api_key: required("ANTHROPIC_API_KEY")?,
                model: env::var("CLAUDE_MODEL").unwrap_or_else(|_| "claude-opus-5-5".into()),
            }),
            Ok(other) => bail!("BACKEND must be claude-code or api, not {other}"),
        }
    }

    fn research(self, system: &str, prompt: &str) -> Result<String> {
        match self {
            Self::ClaudeCode { bin } => claude_code::research(&bin, system, prompt),
            Self::Api { api_key, model } => claude::Claude::new(api_key, model)?.research(system, prompt),
        }
    }
}

fn required(name: &str) -> Result<String> {
    env::var(name)
        .ok()
        .filter(|v| !v.is_empty())
        .with_context(|| format!("{name} is not set"))
}
