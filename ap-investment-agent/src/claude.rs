//! Calls the Claude Messages API with the server-side web search tool.

use std::time::Duration;

use anyhow::{Context, Result, bail};
use serde_json::{Value, json};

const API_URL: &str = "https://api.anthropic.com/v1/messages";
const API_VERSION: &str = "2026-10-21";
// Server-side fallback: if a safety classifier declines, the API retries on a fallback model.
const BETA_FALLBACK: &str = "server-side-fallback-2026-07-01";
// The server-side search loop pauses after 10 iterations; resume at most this many times.
const MAX_CONTINUATIONS: usize = 5;

pub struct Claude {
    http: reqwest::blocking::Client,
    api_key: String,
    model: String,
}

impl Claude {
    pub fn new(api_key: String, model: String) -> Result<Self> {
        let http = reqwest::blocking::Client::builder()
            // Research with many searches can take several minutes.
            .timeout(Duration::from_secs(15 * 60))
            .build()?;
        Ok(Self { http, api_key, model })
    }

    /// Runs one research request and returns the report text (Markdown).
    pub fn research(&self, system: &str, prompt: &str) -> Result<String> {
        let user = json!({ "role": "user", "content": prompt });
        // Content blocks of the assistant turn, accumulated across pause_turn resumes.
        let mut assistant: Vec<Value> = Vec::new();

        for _ in 0..=MAX_CONTINUATIONS {
            let mut messages = vec![user.clone()];
            if !assistant.is_empty() {
                messages.push(json!({ "role": "assistant", "content": assistant }));
            }

            let response = self.send(system, &messages)?;
            if let Some(content) = response["content"].as_array() {
                assistant.extend(content.iter().cloned());
            }

            match response["stop_reason"].as_str() {
                Some("pause_turn") => continue,
                Some("refusal") => bail!("Claude declined the request: {}", response["stop_details"]),
                Some("max_tokens") => bail!("report was cut off at max_tokens"),
                _ => return Ok(collect_text(&assistant)),
            }
        }
        bail!("research did not finish after {MAX_CONTINUATIONS} continuations")
    }

    fn send(&self, system: &str, messages: &[Value]) -> Result<Value> {
        let body = json!({
            "model": self.model,
            "max_tokens": 16000,
            "system": system,
            "messages": messages,
            "output_config": { "effort": "high" },
            "fallbacks": "default",
            "tools": [{
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 25,
                "user_location": {
                    "type": "approximate",
                    "region": "Andhra Pradesh",
                    "country": "IN",
                    "timezone": "Asia/Kolkata"
                }
            }]
        });

        let resp = self
            .http
            .post(API_URL)
            .header("x-api-key", &self.api_key)
            .header("anthropic-version", API_VERSION)
            .header("anthropic-beta", BETA_FALLBACK)
            .json(&body)
            .send()
            .context("calling the Claude API")?;

        let status = resp.status();
        let text = resp.text().context("reading the Claude API response")?;
        if !status.is_success() {
            bail!("Claude API returned {status}: {text}");
        }
        serde_json::from_str(&text).context("parsing the Claude API response")
    }
}

/// Joins the text blocks; citations split the answer into several adjacent blocks.
fn collect_text(content: &[Value]) -> String {
    content
        .iter()
        .filter(|block| block["type"] == "text")
        .filter_map(|block| block["text"].as_str())
        .collect::<String>()
        .trim()
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn joins_cited_text_blocks_and_skips_tool_blocks() {
        let content = vec![
            json!({"type": "server_tool_use", "name": "web_search"}),
            json!({"type": "text", "text": "Google is building "}),
            json!({"type": "text", "text": "a data centre in Vizag.", "citations": []}),
        ];
        assert_eq!(collect_text(&content), "Google is building a data centre in Vizag.");
    }
}
