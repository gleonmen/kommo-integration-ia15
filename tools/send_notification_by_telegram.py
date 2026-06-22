"""
Telegram notification tool.

Sends messages with the Telegram Bot HTTP API when a Kommo lead changes status.
Required environment variables:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import html
import os

import requests
from llama_index.core.tools import FunctionTool


def send_notification_by_telegram(message: str, chat_id: str | None = None) -> bool:
    """
    Sends a Telegram message.

    Args:
        message: Text to send.
        chat_id: Optional Telegram chat ID. Defaults to TELEGRAM_CHAT_ID.

    Returns:
        True when Telegram accepts the message, False otherwise.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    target_chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not target_chat_id:
        print("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
    except requests.RequestException as exc:
        print(f"Telegram notification failed: {exc}")
        return False

    if response.status_code == 200:
        print("Telegram notification sent.")
        return True

    print(f"Telegram notification failed: {response.status_code}")
    print(f"   Detail: {response.text}")
    return False


def notify_lead_status_change(lead_id: int, status_name: str, status_id: int | None = None) -> bool:
    """
    Sends a standard Telegram notification for a Kommo lead status change.
    Notification failures do not undo the Kommo status update.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    lead_url = f"https://{subdomain}.kommo.com/leads/detail/{lead_id}" if subdomain else None

    lines = [
        "<b>Lead actualizado en Kommo</b>",
        f"Lead ID: <code>{html.escape(str(lead_id))}</code>",
        f"Nuevo estado: <b>{html.escape(status_name)}</b>",
    ]

    if status_id is not None:
        lines.append(f"Status ID: <code>{html.escape(str(status_id))}</code>")

    if lead_url:
        safe_url = html.escape(lead_url, quote=True)
        lines.append(f'<a href="{safe_url}">Abrir lead en Kommo</a>')

    return send_notification_by_telegram("\n".join(lines))


def get_send_notification_by_telegram_tool(lead_id: int) -> FunctionTool:
    """
    Factory for the FunctionAgent. The explicit tool name matches the requested task name.
    """

    def tarea_send_notification_by_telegram(message: str) -> str:
        """Envia una notificacion manual por Telegram sobre el lead actual."""
        ok = send_notification_by_telegram(f"<b>Lead {lead_id}</b>\n{html.escape(message)}")
        return (
            f"Notificacion de Telegram enviada para el lead {lead_id}."
            if ok
            else f"No se pudo enviar la notificacion de Telegram para el lead {lead_id}."
        )

    return FunctionTool.from_defaults(
        fn=tarea_send_notification_by_telegram,
        name="Tarea-send_notification_by_telegram",
        description=(
            "Envia una notificacion manual por Telegram sobre el lead actual. "
            "Los cambios de estado ya notifican automaticamente; usa esta tool solo "
            "si necesitas avisar algo adicional. Requiere el argumento message."
        ),
    )
