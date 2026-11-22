//! Sends the report through Gmail's SMTP server.

use anyhow::{Context, Result};
use lettre::message::MultiPart;
use lettre::transport::smtp::authentication::Credentials;
use lettre::{Message, SmtpTransport, Transport};
use pulldown_cmark::{Options, Parser, html};

pub struct Smtp {
    pub host: String,
    pub username: String,
    pub password: String,
    pub to: String,
}

impl Smtp {
    pub fn send(&self, subject: &str, markdown: &str) -> Result<()> {
        let email = Message::builder()
            .from(self.username.parse().context("SMTP_USERNAME is not an email address")?)
            .to(self.to.parse().context("REPORT_TO is not an email address")?)
            .subject(subject)
            .multipart(MultiPart::alternative_plain_html(
                markdown.to_string(),
                to_html(markdown),
            ))?;

        SmtpTransport::relay(&self.host)?
            .credentials(Credentials::new(self.username.clone(), self.password.clone()))
            .build()
            .send(&email)
            .context("sending the email")?;
        Ok(())
    }
}

fn to_html(markdown: &str) -> String {
    let mut body = String::new();
    html::push_html(&mut body, Parser::new_ext(markdown, Options::ENABLE_TABLES));
    format!(
        "<html><body style=\"font-family:Arial,sans-serif;max-width:800px;line-height:1.5\">\
         <style>table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px}}</style>\
         {body}</body></html>"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_report_tables() {
        let html = to_html("| Company | Amount |\n| --- | --- |\n| ArcelorMittal | 1,35,000 |");
        assert!(html.contains("<table>"));
        assert!(html.contains("<td>ArcelorMittal</td>"));
    }
}
