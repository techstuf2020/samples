//! Runs the research through the Claude Code CLI, signed in with a Claude subscription
//! (Pro/Max), so no API key is needed.

use std::process::Command;

use anyhow::{Context, Result, bail};

pub fn research(claude_bin: &str, system: &str, prompt: &str) -> Result<String> {
    let output = Command::new(claude_bin)
        .args(["--print", prompt])
        .args(["--append-system-prompt", system])
        // Only web tools are allowed; in print mode anything else is denied.
        .args(["--allowedTools", "WebSearch", "WebFetch"])
        .args(["--output-format", "text"])
        .output()
        .with_context(|| format!("running {claude_bin} (is Claude Code installed?)"))?;

    if !output.status.success() {
        bail!(
            "Claude Code exited with {}: {}",
            output.status,
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }
    let report = String::from_utf8(output.stdout).context("Claude Code output is not UTF-8")?;
    let report = report.trim();
    if report.is_empty() {
        bail!("Claude Code returned an empty report");
    }
    Ok(report.to_string())
}
