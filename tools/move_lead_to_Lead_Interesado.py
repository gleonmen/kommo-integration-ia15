"""
Tool para mover un lead a la etapa "Lead Interesado" en Kommo.
Se activa cuando el cliente hace preguntas exploratorias sobre productos
(sin mostrar intención clara de compra todavía).
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from llama_index.core.tools import FunctionTool
from tools.send_notification_by_telegram import notify_lead_status_change


def move_lead_to_Lead_Interesado(lead_id: int) -> bool:
    """
    Mueve un lead a la etapa "Lead Interesado".

    Args:
        lead_id: ID del lead a mover.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    pipeline_id = int(os.getenv("KOMMO_PIPELINE_ID"))
    status_id = int(os.getenv("KOMMO_LEAD_INTERESADO_STATUS_ID"))

    url = f"https://{subdomain}.kommo.com/api/v4/leads/{lead_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "pipeline_id": pipeline_id,
        "status_id": status_id,
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        notify_lead_status_change(lead_id, "Lead Interesado", status_id)
        print(f"🔀 Lead {lead_id} movido a 'Lead Interesado' (status {status_id})")
        return True
    else:
        print(f"❌ Error moviendo lead a Lead Interesado: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_move_to_Lead_Interesado_tool(lead_id: int) -> FunctionTool:
    """
    Factory que devuelve un FunctionTool con el lead_id cerrado en clausura.
    Permite que el FunctionAgent invoque la acción sin tener que conocer el lead_id.
    """
    def move_to_Lead_Interesado() -> str:
        """Mueve el lead actual a la etapa 'Lead Interesado' del pipeline de Kommo."""
        ok = move_lead_to_Lead_Interesado(lead_id)
        return (
            f"Lead {lead_id} movido a 'Lead Interesado'."
            if ok
            else f"Error al mover el lead {lead_id} a 'Lead Interesado'."
        )

    return FunctionTool.from_defaults(
        fn=move_to_Lead_Interesado,
        name="move_to_Lead_Interesado",
        description=(
            "Mueve el lead actual a la etapa 'Lead Interesado' del pipeline de Kommo. "
            "Úsala cuando el cliente solo hace preguntas EXPLORATORIAS sobre productos "
            "(qué venden, qué es un producto, para qué sirve, comparaciones, "
            "menciona necesidades) sin mostrar intención clara de compra todavía. "
            "No requiere argumentos."
        ),
    )
