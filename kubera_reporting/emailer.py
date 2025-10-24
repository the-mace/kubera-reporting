"""Send email reports via local mail command."""

import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from kubera_reporting.exceptions import EmailError


class EmailSender:
    """Sends emails via local mail command."""

    def __init__(self, recipient: str) -> None:
        """Initialize email sender.

        Args:
            recipient: Email address to send to
        """
        self.recipient = recipient

    def send_html_email(
        self,
        subject: str,
        html_content: str,
        from_address: str | None = None,
    ) -> None:
        """Send HTML email via local mail command.

        Charts are now embedded as base64 data URLs in the HTML for better forwarding compatibility.

        Args:
            subject: Email subject
            html_content: HTML content with inline styles and base64-embedded images
            from_address: From address (optional)

        Raises:
            EmailError: If sending fails
        """
        try:
            # Create MIME multipart message for text and HTML alternatives
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["To"] = self.recipient

            if from_address:
                msg["From"] = from_address

            # Create plain text version (fallback)
            text_content = "This email requires an HTML-capable email client."
            text_part = MIMEText(text_content, "plain", "utf-8")
            html_part = MIMEText(html_content, "html", "utf-8")

            # Attach parts (text first, then HTML as per RFC 2046)
            msg.attach(text_part)
            msg.attach(html_part)

            # Send via sendmail command (more reliable than mail on macOS)
            sendmail_cmd = ["/usr/sbin/sendmail", "-t", "-oi"]

            result = subprocess.run(
                sendmail_cmd,
                input=msg.as_string(),
                text=True,
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise EmailError(
                    f"Sendmail command failed with return code {result.returncode}: {result.stderr}"
                )

        except subprocess.TimeoutExpired as e:
            raise EmailError("Sendmail command timed out") from e
        except FileNotFoundError as e:
            raise EmailError(
                "Sendmail command not found at /usr/sbin/sendmail. "
                "Please ensure mail system is configured."
            ) from e
        except Exception as e:
            raise EmailError(f"Failed to send email: {e}") from e
