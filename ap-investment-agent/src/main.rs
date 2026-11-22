//! Weekly Andhra Pradesh investment report: researches with Claude + web search,
//! saves the report as Markdown, and emails it through Gmail.
//!
//! Usage: ap-investment-agent [--dry-run] [--days N]

mod claude;
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

    // Check every setting up front so a scheduled run fails before spending on the API.
    let api_key = required("ANTHROPIC_API_KEY")?;
    let model = env::var("CLAUDE_MODEL").unwrap_or_else(|_| "claude-opus-5-5".into());
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
    let claude = claude::Claude::new(api_key, model)?;
    let body = claude.research(prompt::SYSTEM, &prompt::weekly(&from, &to))?;
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

fn required(name: &str) -> Result<String> {
    env::var(name)
        .ok()
        .filter(|v| !v.is_empty())
        .with_context(|| format!("{name} is not set"))
}
