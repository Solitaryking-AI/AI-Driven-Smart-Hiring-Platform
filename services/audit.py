"""
services/audit.py — Audit logging service for SmartHire AI.
Records security, administrative, and data governance events.
Never raises exceptions to callers.
"""

import json
from typing import Any, Optional
from models import AuditLog


def log_event(
    db,
    actor: Any,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    details: Optional[Any] = None,
) -> Optional[AuditLog]:
    """
    Record an audit log entry in the database.
    Guaranteed never to raise an unhandled exception: wraps execution in try/except
    and rolls back on failure.
    """
    try:
        actor_id = None
        actor_email = None

        if actor is not None:
            if hasattr(actor, "user_id"):
                actor_id = getattr(actor, "user_id", None)
            elif hasattr(actor, "id"):
                actor_id = getattr(actor, "id", None)

            if hasattr(actor, "email"):
                actor_email = getattr(actor, "email", None)

            if isinstance(actor, dict):
                actor_id = actor.get("user_id") or actor.get("id") or actor_id
                actor_email = actor.get("email") or actor_email
            elif isinstance(actor, str):
                if not actor_email:
                    actor_email = actor
            elif isinstance(actor, int) and actor_id is None:
                actor_id = actor

        details_str = None
        if details is not None:
            if isinstance(details, (dict, list)):
                details_str = json.dumps(details)
            else:
                details_str = str(details)

        target_id_str = str(target_id) if target_id is not None else None

        entry = AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action=str(action),
            target_type=str(target_type) if target_type is not None else None,
            target_id=target_id_str,
            details=details_str,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None
