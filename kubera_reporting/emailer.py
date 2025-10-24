"""Send email reports via local mail command."""

import subprocess
from email.mime.image import MIMEImage
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
        chart_image: bytes | None = None,
    ) -> None:
        """Send HTML email via local mail command.

        Args:
            subject: Email subject
            html_content: HTML content
            from_address: From address (optional)
            chart_image: Optional pie chart image as bytes

        Raises:
            EmailError: If sending fails
        """
        try:
            # Create MIME multipart message with related parts for inline images
            msg = MIMEMultipart("related")
            msg["Subject"] = subject
            msg["To"] = self.recipient

            if from_address:
                msg["From"] = from_address

            # Create alternative part for text and HTML
            msg_alternative = MIMEMultipart("alternative")

            # Create plain text version (fallback)
            text_content = "This email requires an HTML-capable email client."
            text_part = MIMEText(text_content, "plain", "utf-8")
            html_part = MIMEText(html_content, "html", "utf-8")

            # Attach parts (text first, then HTML as per RFC 2046)
            msg_alternative.attach(text_part)
            msg_alternative.attach(html_part)

            # Attach the alternative part to the main message
            msg.attach(msg_alternative)

            # Attach chart image as inline if provided
            if chart_image:
                image = MIMEImage(chart_image, _subtype="png")
                image.add_header("Content-ID", "<allocation_chart>")
                image.add_header("Content-Disposition", "inline", filename="allocation_chart.png")
                msg.attach(image)

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
