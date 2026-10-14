"""
services/settings_store.py — Platform configuration and feature toggle storage.
Provides get_setting and set_setting backed by the platform_settings table.
"""

from typing import Any, Optional
from models import PlatformSetting, utc_now

DEFAULT_SETTINGS = {
    "registration_open": "true",
    "feature_mock_interview": "true",
    "feature_voice": "true",
    "feature_resume_ai": "true",
    "feature_practice": "true",
    "maintenance_banner": "",
}


def get_setting(db, key: str, default: Optional[Any] = None) -> str:
    """
    Retrieve a platform setting value.
    If the key does not exist in the database, falls back to the provided default
    or the platform DEFAULT_SETTINGS dictionary.
    """
    try:
        row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
        if row is not None and row.value is not None:
            return row.value
    except Exception:
        pass

    if default is not None:
        return str(default)
    return DEFAULT_SETTINGS.get(key, "")


def set_setting(db, key: str, value: Any, actor: Optional[Any] = None) -> PlatformSetting:
    """
    Create or update a platform setting.
    """
    updated_by_str = "system"
    if actor is not None:
        if hasattr(actor, "email"):
            updated_by_str = getattr(actor, "email", None) or "system"
        elif isinstance(actor, dict):
            updated_by_str = actor.get("email") or "system"
        elif isinstance(actor, str):
            updated_by_str = actor

    val_str = "" if value is None else str(value)

    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if row:
        row.value = val_str
        row.updated_by = updated_by_str
        row.updated_at = utc_now()
    else:
        row = PlatformSetting(
            key=key,
            value=val_str,
            updated_by=updated_by_str,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    return row
