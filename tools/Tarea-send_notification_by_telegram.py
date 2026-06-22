"""
Compatibility wrapper for the requested tool file name.

The importable implementation lives in tools/send_notification_by_telegram.py
because Python modules cannot be imported normally when their filename contains
hyphens.
"""

from tools.send_notification_by_telegram import (
    get_send_notification_by_telegram_tool,
    notify_lead_status_change,
    send_notification_by_telegram,
)

__all__ = [
    "get_send_notification_by_telegram_tool",
    "notify_lead_status_change",
    "send_notification_by_telegram",
]
