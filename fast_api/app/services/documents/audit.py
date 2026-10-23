import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("document_audit")


def audit_event(
    *,
    action: str,
    user_id: int | None,
    document_id: int | None = None,
    outcome: str = "success",
    ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user_id": user_id,
        "document_id": document_id,
        "outcome": outcome,
        "ip": ip,
        "details": details or {},
    }
    logger.info(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))