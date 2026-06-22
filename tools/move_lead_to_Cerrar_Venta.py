"""
Tool para mover un lead a la etapa "Cerrar Venta" en Kommo.
Se activa cuando el cliente confirma que va a pagar de forma inminente:
"voy a pagar ahora", "en 5 min envío la transferencia/comprobante".
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from llama_index.core.tools import FunctionTool
from tools.send_notification_by_telegram import notify_lead_status_change


def move_lead_to_Cerrar_Venta(lead_id: int) -> bool:
    """
    Mueve un lead a la etapa "Cerrar Venta" (pago inminente confirmado).

    Args:
        lead_id: ID del lead a mover.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    pipeline_id = int(os.getenv("KOMMO_PIPELINE_ID"))
    status_id = int(os.getenv("KOMMO_LEAD_CERRAR_VENTA_STATUS_ID"))

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
        notify_lead_status_change(lead_id, "Cerrar Venta", status_id)
        print(f"🔀 Lead {lead_id} movido a 'Cerrar Venta' (status {status_id})")
        return True
    else:
        print(f"❌ Error moviendo lead a Cerrar Venta: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_move_to_Cerrar_Venta_tool(lead_id: int) -> FunctionTool:
    """
    Factory que devuelve un FunctionTool con el lead_id cerrado en clausura.
    """
    def move_to_Cerrar_Venta() -> str:
        """Mueve el lead actual a la etapa 'Cerrar Venta' del pipeline de Kommo."""
        ok = move_lead_to_Cerrar_Venta(lead_id)
        return (
            f"Lead {lead_id} movido a 'Cerrar Venta'."
            if ok
            else f"Error al mover el lead {lead_id} a 'Cerrar Venta'."
        )

    return FunctionTool.from_defaults(
        fn=move_to_Cerrar_Venta,
        name="move_to_Cerrar_Venta",
        description=(
            "Mueve el lead actual a la etapa 'Cerrar Venta' del pipeline de Kommo. "
            "Úsala SOLO cuando el cliente CONFIRMA explícitamente que va a pagar de forma "
            "inminente: 'voy a transferir ahora', 'hago el pago ahora', 'en 5 min envío "
            "el comprobante', 'te mando el voucher en un momento'. "
            "No la uses si solo está preguntando por métodos de pago — para eso usa "
            "move_to_Lead_Calificado. No requiere argumentos."
        ),
    )
