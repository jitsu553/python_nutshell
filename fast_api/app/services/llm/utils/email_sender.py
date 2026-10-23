import logging
import uuid

logger = logging.getLogger(__name__)


def deliver(to_email: str, subject: str, body: str) -> str:
    """Send an email and return the provider's message id."""
    # ponytail: stub, logs instead of sending; swap the body for smtplib/SendGrid
    # when real delivery is needed. Keep the signature.
    message_id = f"stub-{uuid.uuid4().hex[:12]}"
    logger.info("EMAIL to=%s subject=%r id=%s\n%s", to_email, subject, message_id, body)
    return message_id