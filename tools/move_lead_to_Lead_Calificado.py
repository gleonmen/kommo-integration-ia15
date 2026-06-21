"""
Tool para mover un lead a la etapa "Lead Calificado" en Kommo.
Se activa cuando el cliente muestra intención clara de compra:
pide precio para adquirir, pregunta por métodos de pago, envío,
garantías, plazos o cualquier detalle logístico/contractual.
Usa el endpoint PATCH /api/v4/leads/{id}
Docs: https://developers.kommo.com/reference/updating-single-lead
"""

import os
import requests
from llama_index.core.tools import FunctionTool


def move_lead_to_Lead_Calificado(lead_id: int) -> bool:
    """
    Mueve un lead a la etapa "Lead Calificado".

    Args:
        lead_id: ID del lead a mover.

    Returns:
        True si se actualizó correctamente, False en caso de error.
    """
    subdomain = os.getenv("KOMMO_SUBDOMAIN")
    access_token = os.getenv("KOMMO_ACCESS_TOKEN")
    pipeline_id = int(os.getenv("KOMMO_PIPELINE_ID"))
    status_id = int(os.getenv("KOMMO_LEAD_CALIFICADO_STATUS_ID"))

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
        print(f"🔀 Lead {lead_id} movido a 'Lead Calificado' (status {status_id})")
        return True
    else:
        print(f"❌ Error moviendo lead a Lead Calificado: {response.status_code}")
        print(f"   Detalle: {response.text}")
        return False


def get_move_to_Lead_Calificado_tool(lead_id: int) -> FunctionTool:
    """
    Factory que devuelve un FunctionTool con el lead_id cerrado en clausura.
    """
    def move_to_Lead_Calificado() -> str:
        """Mueve el lead actual a la etapa 'Lead Calificado' del pipeline de Kommo."""
        ok = move_lead_to_Lead_Calificado(lead_id)
        return (
            f"Lead {lead_id} movido a 'Lead Calificado'."
            if ok
            else f"Error al mover el lead {lead_id} a 'Lead Calificado'."
        )

    return FunctionTool.from_defaults(
        fn=move_to_Lead_Calificado,
        name="move_to_Lead_Calificado",
        description=(
            "Mueve el lead actual a la etapa 'Lead Calificado' del pipeline de Kommo. "
            "Úsala cuando el cliente muestra INTENCIÓN CLARA de compra: dice 'lo quiero' / "
            "'me interesa comprarlo', pide PRECIO para adquirir el producto, o pregunta por "
            "formas de pago, métodos de envío, plazos de entrega, garantías o devoluciones. "
            "No requiere argumentos."
        ),
    )
