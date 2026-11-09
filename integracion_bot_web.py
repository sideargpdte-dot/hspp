"""
Script de integración Bot → Web.
Agrega este código al bot para emitir eventos a la web en tiempo real.

INSTALACIÓN:
1. Copia este archivo a la carpeta del bot
2. Importa las funciones en main.py:
   from integracion_bot_web import emitir_evento_web, inicializar_integracion
3. Llama a inicializar_integracion() en setup_hook()
4. Usa emitir_evento_web() después de cada acción importante
"""

import aiohttp
import os
import logging
from typing import Dict, Any

logger = logging.getLogger("integracion_web")

# Configuración
WEB_API_URL = os.getenv("WEB_API_URL", "http://localhost:8000")
WEB_API_SECRET = os.getenv("WEB_API_SECRET", "secret_compartido_bot_web")

# Cliente HTTP reutilizable
_http_session: aiohttp.ClientSession = None


def inicializar_integracion():
    """Inicializa la integración con la web. Llamar en setup_hook()"""
    global _http_session
    _http_session = aiohttp.ClientSession()
    logger.info("✅ Integración con plataforma web inicializada")


async def cerrar_integracion():
    """Cierra la sesión HTTP. Llamar en close()"""
    global _http_session
    if _http_session:
        await _http_session.close()
        logger.info("🔌 Integración con plataforma web cerrada")


async def emitir_evento_web(tipo_evento: str, user_id: int, datos: Dict[str, Any]):
    """
    Emite un evento a la plataforma web para notificar cambios.
    
    Args:
        tipo_evento: Tipo de evento (ej: 'economia.transferencia')
        user_id: Discord ID del usuario afectado
        datos: Datos del evento
    
    Ejemplos:
        # Después de una transferencia
        await emitir_evento_web(
            'economia.transferencia',
            destinatario_id,
            {
                'tipo': 'recibida',
                'monto': 5000,
                'remitente': 'Juan Pérez',
                'nuevo_saldo': 15000
            }
        )
        
        # Después de un arresto
        await emitir_evento_web(
            'arresto.nuevo',
            arrestado_id,
            {
                'numero_arresto': '#ARR-0123',
                'articulos': 'Art. 1.1',
                'oficial': 'Oficial Gómez',
                'tiempo': '10 minutos'
            }
        )
        
        # Después de emitir una multa
        await emitir_evento_web(
            'multa.nueva',
            multado_id,
            {
                'folio': 45,
                'monto': 2500,
                'motivo': 'Exceso de velocidad',
                'oficial': 'Oficial Rodríguez'
            }
        )
    """
    if not _http_session:
        logger.warning("⚠️ Sesión HTTP no inicializada. Llama a inicializar_integracion() primero.")
        return
    
    try:
        headers = {
            'Authorization': f'Bearer {WEB_API_SECRET}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'event_type': tipo_evento,
            'user_id': user_id,
            'data': datos
        }
        
        async with _http_session.post(
            f'{WEB_API_URL}/api/v1/events/emit',
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            if resp.status == 200:
                logger.debug(f"📡 Evento '{tipo_evento}' enviado a web para usuario {user_id}")
            else:
                error_text = await resp.text()
                logger.warning(f"⚠️ Error enviando evento a web (status {resp.status}): {error_text}")
                
    except asyncio.TimeoutError:
        logger.warning(f"⏱️ Timeout enviando evento a web")
    except Exception as e:
        logger.error(f"❌ Error enviando evento a web: {e}")


# ==================================================
#  EJEMPLOS DE USO EN LOS COGS
# ==================================================

"""
=== EN cogs/economia.py ===

# Al final del comando /pay (después de commit)
await emitir_evento_web(
    'economia.transferencia',
    target_uid,
    {
        'tipo': 'recibida',
        'monto': monto_real,
        'remitente': f"{me[0]} {me[1]}",
        'slot': target[4],
        'nuevo_saldo_mano': target[2] + monto_real
    }
)

# También notificar al remitente
await emitir_evento_web(
    'economia.transferencia',
    interaction.user.id,
    {
        'tipo': 'enviada',
        'monto': monto_real,
        'destinatario': f"{target[0]} {target[1]}",
        'slot': slot_mio,
        'nuevo_saldo_mano': mano_mio - monto_real
    }
)


=== EN cogs/policia.py ===

# Al final del comando /arrestar (después de commit)
await emitir_evento_web(
    'arresto.nuevo',
    usuario_arrestado.id,
    {
        'numero_arresto': numero_arresto,
        'articulos': articulos,
        'tiempo_minutos': tiempo_minutos,
        'oficial': interaction.user.display_name,
        'fecha_liberacion': fecha_liberacion
    }
)

# Al final del comando /multar (después de commit)
await emitir_evento_web(
    'multa.nueva',
    usuario_multado_id,
    {
        'folio': folio,
        'monto': monto,
        'motivo': motivo,
        'oficial': interaction.user.display_name,
        'fecha': fecha
    }
)


=== EN main.py (AmbaBot) ===

# En setup_hook(), DESPUÉS de cargar los cogs
from integracion_bot_web import inicializar_integracion
inicializar_integracion()

# En close(), ANTES de super().close()
from integracion_bot_web import cerrar_integracion
await cerrar_integracion()
"""
