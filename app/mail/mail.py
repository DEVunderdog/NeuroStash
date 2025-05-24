import logging
import datetime
import emails
from app.core.config import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

logger = logging.getLogger(__name__)

template_dir = Path(__file__).parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html", "xml"])
)


def send_email(
    *, email_to: str, subject: str = "", html_content: str = "", text_content: str = ""
) -> None:
    message = emails.Message(
        subject=subject,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
        html=html_content,
        text=text_content,
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    try:
        response = message.send(to=email_to, smtp=smtp_options)
        if response and response.status_code in [250, 200]:
            logger.info(
                f"email send successfully to {email_to}, response: {response.status_code}"
            )
        else:
            logger.error(
                f"failed to send email to {email_to}, response: {response.status_code}"
            )
    except Exception as e:
        logger.error(f"exception while sending email to {email_to}: {e}", exc_info=True)
        return


def send_api_email(
    email_to: str,
    project_name: str,
    api_key: str,
) -> None:
    try:
        template = env.get_template("api_key_mail.html")

        current_year = datetime.datetime.now().year
        context = {
            "project_name": project_name,
            "api_key": api_key,
            "current_year": current_year,
        }

        html_content = template.render(context)

        subject = "API KEY"

        send_email(email_to=email_to, subject=subject, html_content=html_content)

        logger.info(f"api key email queue for sending to {email_to}")
    except Exception as e:
        logger.error(f"error in sending api key mail; {email_to}: {e}", exc_info=True)
        return
