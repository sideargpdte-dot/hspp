import discord
from discord import app_commands
from discord.ext import commands
import random
import re
import io
import time
import asyncio
import logging
from typing import Literal, Optional
from datetime import datetime, timedelta
import aiohttp
from PIL import Image, ImageDraw, ImageFont

# pyrefly: ignore [missing-import]
from curl_cffi.requests import AsyncSession

import utils
from tema import Emojis, construir_embed

logger = logging.getLogger("cogs.roleplay")

# ==========================================
#  FUNCIÓN HELPER PARA BÚSQUEDA POR DNI
# ==========================================

async def buscar_usuario_por_dni(db, dni: str):
    """
    Busca un usuario en la base de datos por su número de documento.
    Retorna (id_usuario, slot, nombres, apellidos) o None si no se encuentra.
    """
    async with db.execute(
        "SELECT id_usuario, slot, nombres, apellidos FROM usuarios WHERE nro_doc = ?",
        (dni,)
    ) as cur:
        return await cur.fetchone()

# ==========================================
#  VARIABLES GLOBALES DE IMAGEN Y FUENTES
# ==========================================
try:
    TEMPLATE_DNI_GLOBAL = Image.open(utils.ruta_actual / "dni_template.png").convert("RGBA")
except FileNotFoundError:
    logger.warning("No se encuentra 'dni_template.png'. Creando plantilla por defecto.")
    TEMPLATE_DNI_GLOBAL = Image.new("RGBA", (800, 600), (255, 255, 255, 255))

FONT_PATH_GLOBAL = utils.ruta_actual / "Helvetica-Bold.ttf"
try:
    FONT_DNI_GLOBAL = ImageFont.truetype(str(FONT_PATH_GLOBAL), 26)
    FONT_SMALL_DNI_GLOBAL = ImageFont.truetype(str(FONT_PATH_GLOBAL), 20)
except IOError:
    logger.warning("'Helvetica-Bold.ttf' no encontrada. Usando fuente por defecto.")
    FONT_DNI_GLOBAL = ImageFont.load_default()
    FONT_SMALL_DNI_GLOBAL = FONT_DNI_GLOBAL


def generar_imagen_dni(nombre: str, apellido: str, nacimiento: str, genero: str, nacionalidad: str, roblox_user: str, nro_doc: str, avatar_bytes=None) -> io.BytesIO:
    template = TEMPLATE_DNI_GLOBAL.copy()
    draw = ImageDraw.Draw(template)

    font = FONT_DNI_GLOBAL
    font_small = FONT_SMALL_DNI_GLOBAL

    coord_apellido = (400, 185)
    coord_nombre = (400, 260)
    coord_sexo = (400, 320)
    coord_nacionalidad = (567, 320)
    coord_nacimiento = (400, 390)
    coord_emision = (400, 450)
    coord_venc = (676, 450)
    coord_doc = (90, 535)

    fecha_emision = datetime.now().strftime("%d/%m/%Y")
    fecha_vencimiento = (datetime.now() + timedelta(days=3650)).strftime("%d/%m/%Y")

    draw.text(coord_apellido, apellido.upper(), fill=(40, 40, 40), font=font)
    draw.text(coord_nombre, nombre.upper(), fill=(40, 40, 40), font=font)
    draw.text(coord_sexo, genero[0].upper() if genero else 'N', fill=(40, 40, 40), font=font)
    draw.text(coord_nacionalidad, nacionalidad.upper() if nacionalidad else "ARGENTINA", fill=(40, 40, 40), font=font)
    draw.text(coord_nacimiento, nacimiento, fill=(40, 40, 40), font=font)
    draw.text(coord_emision, fecha_emision, fill=(40, 40, 40), font=font_small)
    draw.text(coord_venc, fecha_vencimiento, fill=(40, 40, 40), font=font_small)

    texto_doc = f"DNI: {nro_doc}  |  RBX: {roblox_user}"
    draw.text(coord_doc, texto_doc, fill=(40, 40, 40), font=font_small)

    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((272, 327))
            template.paste(avatar, (88, 163), avatar)
        except Exception as e:
            logger.error(f"Error pegando la foto en el DNI: {e}")

    buffer = io.BytesIO()
    template.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer


CACHE_AVATARES = {}
CACHE_TTL_SECS = 300  # 5 minutos para caché regular


async def obtener_avatar_roblox(username: str, force_refresh: bool = False):
    username_clean = username.strip() if username else ""
    if not username_clean:
        return None, None

    cache_key = username_clean.lower()
    now = time.time()

    if len(CACHE_AVATARES) > 100:
        keys_to_delete = [k for k, v in CACHE_AVATARES.items() if now - v['time'] > CACHE_TTL_SECS]
        for k in keys_to_delete:
            del CACHE_AVATARES[k]

    if force_refresh and cache_key in CACHE_AVATARES:
        del CACHE_AVATARES[cache_key]

    if not force_refresh and cache_key in CACHE_AVATARES:
        cache_data = CACHE_AVATARES[cache_key]
        if now - cache_data['time'] < CACHE_TTL_SECS:
            return cache_data['content'], cache_data['url']
        else:
            del CACHE_AVATARES[cache_key]

    try:
        async with AsyncSession(impersonate="chrome120") as session:
            payload = {"usernames": [username_clean], "excludeBannedUsers": False}
            resp = await session.post("https://users.roblox.com/v1/usernames/users", json=payload)
            if resp.status_code != 200:
                logger.warning(f"Roblox API error buscando usuario '{username_clean}': Status {resp.status_code}")
                return None, None

            data = resp.json()
            if not data.get("data"):
                logger.warning(f"No se encontró usuario de Roblox '{username_clean}' en API de usuarios.")
                return None, None

            user_id = data["data"][0]["id"]
            # Añadir cache-buster para evitar proxies intermediarios con thumbnails viejos
            thumb_url = f"https://thumbnails.roblox.com/v1/users/avatar-bust?userIds={user_id}&size=420x420&format=Png&isCircular=false&_={int(now)}"

            image_url = None
            # Reintentar hasta 6 veces con pausas de 1.5s (hasta 9 segundos) ante renderizado Pending de Roblox
            for intento in range(6):
                resp = await session.get(thumb_url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
                if resp.status_code == 200:
                    thumb_data = resp.json()
                    if thumb_data.get("data"):
                        item = thumb_data["data"][0]
                        estado = item.get("state")
                        if estado == "Completed":
                            image_url = item.get("imageUrl")
                            break
                        elif estado in ("Pending", "InReview"):
                            logger.info(f"Render de avatar de '{username_clean}' en proceso ({estado}), intento {intento + 1}/6...")
                        elif estado == "Blocked":
                            logger.warning(f"Avatar de '{username_clean}' bloqueado por moderación de Roblox.")
                            break
                await asyncio.sleep(1.5)

            if not image_url:
                logger.warning(f"No se pudo obtener URL del avatar de Roblox para '{username_clean}'.")
                return None, None

            resp = await session.get(image_url)
            if resp.status_code != 200:
                logger.warning(f"Error descargando imagen del avatar desde '{image_url}': Status {resp.status_code}")
                return None, None

            CACHE_AVATARES[cache_key] = {
                'content': resp.content,
                'url': image_url,
                'time': now
            }
            return resp.content, image_url

    except Exception as e:
        logger.error(f"Error de conexión con Roblox: {e}")
        return None, None


# ==========================================
#  MODALES Y VISTAS
# ==========================================
class MotivoRechazoModal(discord.ui.Modal, title='Rechazar Solicitud de DNI'):
    motivo = discord.ui.TextInput(
        label='Motivo Administrativo',
        style=discord.TextStyle.paragraph,
        placeholder='Ej: Nombre irreal, avatar inapropiado, etc.',
        required=True,
        max_length=500
    )

    def __init__(self, view_original: discord.ui.View, solicitante: discord.Member, roblox_user: str):
        super().__init__()
        self.view_original = view_original
        self.solicitante = solicitante
        self.roblox_user = roblox_user

    async def on_submit(self, interaction: discord.Interaction):
        for child in self.view_original.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True

        if hasattr(interaction.client, 'tramites_dni_pendientes'):
            interaction.client.tramites_dni_pendientes.discard((self.solicitante.id, self.view_original.datos['slot']))

        if self.view_original.message:
            datos = self.view_original.datos
            datos_extra = (
                f"**Nacimiento:** {datos['nacimiento']}\n"
                f"**Género:** {datos['genero']}\n"
                f"**Nacionalidad:** {datos['nacionalidad']}\n"
                f"**Domicilio:** {datos['domicilio']}"
            )
            archivo_preview = discord.File(io.BytesIO(self.view_original.buffer_bytes), filename="preview.png")

            container_staff = construir_embed(
                tipo="error",
                titulo="🚫 Solicitud de DNI Rechazada",
                descripcion="Se requiere revisión administrativa para la siguiente solicitud:",
                campos=[
                    ("Identidad", f"{datos['nombre']} {datos['apellido']}", True),
                    ("Usuario Roblox", f"`{self.roblox_user}`", True),
                    ("Datos Adicionales", datos_extra, False),
                    ("Estado Actual", f"{Emojis.ERROR} **RECHAZADO por** {interaction.user.mention}", False),
                    ("Motivo del Rechazo", f"_{self.motivo.value}_", False)
                ],
                imagen="attachment://preview.png"
            )

            self.view_original.clear_items()
            self.view_original.add_item(container_staff)
            await interaction.response.edit_message(view=self.view_original, attachments=[archivo_preview])

            if hasattr(interaction.client, 'registrar_log_ui'):
                await interaction.client.registrar_log_ui(interaction, "Roleplay", "Rechazo de DNI", f"Rechazó el DNI de {self.solicitante.mention}. Motivo: {self.motivo.value}")
        else:
            await interaction.response.edit_message(content=f"{Emojis.ERROR} Solicitud rechazada.", view=self.view_original)

        try:
            desc = (
                f"Estimado ciudadano {self.solicitante.mention},\n"
                f"El Registro Nacional de las Personas (RENAPER) le notifica que su trámite no ha podido completarse.\n"
                f"**Resolución del Trámite:**\n"
                f"• **Estado:** Rechazado.\n"
                f"• **Motivo Administrativo:** {self.motivo.value}\n"
                f"• **Pasos a Seguir:** Por favor, verifique los errores señalados y vuelva a iniciar el trámite con `/rp solicitar_dni`."
            )
            container_md = construir_embed("error", titulo="🚫 Solicitud de Documentación Rechazada", descripcion=desc)
            await self.solicitante.send(view=discord.ui.LayoutView().add_item(container_md))
        except (discord.HTTPException, discord.Forbidden):
            pass


class DniReviewView(discord.ui.LayoutView):
    def __init__(self, solicitante: discord.Member, buffer_bytes: bytes, datos_pj: dict, embed_initial=None, texto_mencion=None):
        super().__init__(timeout=None)
        self.solicitante = solicitante
        self.buffer_bytes = buffer_bytes
        self.datos = datos_pj
        self.message = None
        self._procesado = False

        if texto_mencion:
            self.add_item(discord.ui.TextDisplay(texto_mencion))

        if embed_initial:
            self.add_item(embed_initial)

        ar = discord.ui.ActionRow()
        b1 = discord.ui.Button(label="Aprobar", style=discord.ButtonStyle.success, custom_id="btn_aprobar_dni")
        b1.callback = self.aprobar
        b2 = discord.ui.Button(label="Rechazar", style=discord.ButtonStyle.danger, custom_id="btn_rechazar_dni")
        b2.callback = self.rechazar

        ar.add_item(b1)
        ar.add_item(b2)
        self.add_item(ar)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != utils.ID_DUENO and not any(rol.id in utils.PERMISO_MANEJO_DNI for rol in interaction.user.roles):
            await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="⛔ No tienes autorización administrativa para revisar DNIs.")), ephemeral=True)
            return False
        return True

    async def aprobar(self, interaction: discord.Interaction):
        if self._procesado:
            return await interaction.response.send_message("⛔ Este trámite de DNI ya fue procesado por otro moderador.", ephemeral=True)
        self._procesado = True

        for child in self.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True

        if hasattr(interaction.client, 'tramites_dni_pendientes'):
            interaction.client.tramites_dni_pendientes.discard((self.solicitante.id, self.datos['slot']))

        datos_extra = (
            f"**Nacimiento:** {self.datos['nacimiento']}\n"
            f"**Género:** {self.datos['genero']}\n"
            f"**Nacionalidad:** {self.datos['nacionalidad']}\n"
            f"**Domicilio:** {self.datos['domicilio']}"
        )
        archivo_preview = discord.File(io.BytesIO(self.buffer_bytes), filename="preview.png")

        container_staff = construir_embed(
            tipo="exito",
            titulo="🪪 DNI Aprobado",
            descripcion="Se requiere revisión administrativa para la siguiente solicitud:",
            campos=[
                ("Identidad", f"{self.datos['nombre']} {self.datos['apellido']}", True),
                ("Usuario Roblox", f"`{self.datos['roblox_user']}`", True),
                ("Datos Adicionales", datos_extra, False),
                ("Estado Actual", f"{Emojis.EXITO} **APROBADO Y REGISTRADO por** {interaction.user.mention}", False)
            ],
            imagen="attachment://preview.png"
        )

        self.clear_items()
        self.add_item(container_staff)
        await interaction.response.edit_message(view=self, attachments=[archivo_preview])

        if hasattr(interaction.client, 'registrar_log_ui'):
            await interaction.client.registrar_log_ui(interaction, "Roleplay", "Aprobación de DNI", f"Aprobó el DNI de {self.solicitante.mention} ({self.datos['nombre']} {self.datos['apellido']}).")

        async with interaction.client.db.execute('''INSERT OR REPLACE INTO usuarios 
                       (id_usuario, slot, nombres, apellidos, fecha_nacimiento, genero, nacionalidad, domicilio, dinero_mano, dinero_banco, roblox_user, imagen_url, nro_doc) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (self.solicitante.id, self.datos['slot'], self.datos['nombre'], self.datos['apellido'], 
                        self.datos['nacimiento'], self.datos['genero'], self.datos['nacionalidad'], 
                        self.datos['domicilio'], 500, 1000, self.datos['roblox_user'], self.datos['avatar_url'], self.datos['nro_doc'])):
            pass

        await utils.update_slot_activo_cache(self.solicitante.id, self.datos['slot'], interaction.client.db, interaction.client.sesiones_cache)
        await interaction.client.db.commit()

        try:
            file = discord.File(io.BytesIO(self.buffer_bytes), filename="dni_oficial.png")

            desc = (
                f"Nos complace informarle que su documentación ha sido **validada, aprobada y registrada** exitosamente en la base de datos nacional.\n"
                f"**Detalles del Documento:**\n"
                f"• **Identidad Registrada:** **{self.datos['nombre']} {self.datos['apellido']}**\n"
                f"• **Número de Documento:** **{self.datos['nro_doc']}**\n"
                f"• **Acceso Digital:** Puede consultar su legajo en cualquier momento utilizando el comando `/rp ciudadano`."
            )
            embed_md = construir_embed("exito", titulo=f"{Emojis.EXITO} Documento Nacional de Identidad Emitido", descripcion=desc, imagen="attachment://dni_oficial.png")

            await self.solicitante.send(view=discord.ui.LayoutView().add_item(embed_md), file=file)
        except (discord.HTTPException, discord.Forbidden):
            pass

    async def rechazar(self, interaction: discord.Interaction):
        if self._procesado:
            return await interaction.response.send_message("⛔ Este trámite de DNI ya fue procesado por otro moderador.", ephemeral=True)
        modal_rechazo = MotivoRechazoModal(
            view_original=self, 
            solicitante=self.solicitante, 
            roblox_user=self.datos['roblox_user']
        )
        await interaction.response.send_modal(modal_rechazo)


class DniPreviewView(discord.ui.LayoutView):
    def __init__(self, solicitante: discord.Member, buffer_bytes: bytes, datos_pj: dict, mg=None, embed_initial=None):
        super().__init__(timeout=300)
        self.solicitante = solicitante
        self.buffer_bytes = buffer_bytes
        self.datos = datos_pj

        if mg:
            self.add_item(mg)
        if embed_initial:
            self.add_item(embed_initial)

        ar = discord.ui.ActionRow()
        b1 = discord.ui.Button(label="Confirmar y Enviar", style=discord.ButtonStyle.success, custom_id="btn_confirmar_dni")
        b1.callback = self.confirmar
        b2 = discord.ui.Button(label="Cancelar Trámite", style=discord.ButtonStyle.danger, custom_id="btn_cancelar_dni")
        b2.callback = self.cancelar

        ar.add_item(b1)
        ar.add_item(b2)
        self.add_item(ar)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.solicitante:
            await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="⛔ Solo el solicitante puede interactuar con este mensaje.")), ephemeral=True)
            return False
        return True

    async def confirmar(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Operación denegada. Solo puede ejecutarse dentro de un servidor.", ephemeral=True)

        canal_revision = guild.get_channel(utils.ID_CANAL_REVISION_DNI)
        if not isinstance(canal_revision, discord.TextChannel):
            desc = (
                f"Error de sistema.\n**Motivo:** El canal de revisión administrativa no fue localizado o no está configurado (ID: `{utils.ID_CANAL_REVISION_DNI}`)."
            )
            self.clear_items()
            self.add_item(construir_embed("error", descripcion=desc))
            return await interaction.response.edit_message(view=self)

        perms = canal_revision.permissions_for(guild.me)
        faltantes = []
        if not perms.view_channel:
            faltantes.append("Ver Canal (View Channel)")
        if not perms.send_messages:
            faltantes.append("Enviar Mensajes (Send Messages)")
        if not perms.attach_files:
            faltantes.append("Adjuntar Archivos (Attach Files)")
        if not perms.embed_links:
            faltantes.append("Insertar Enlaces (Embed Links)")

        if faltantes:
            desc = (
                f"Error de permisos en el canal de revisión {canal_revision.mention}.\n"
                f"**El bot carece de los siguientes permisos en ese canal:**\n"
                + "\n".join([f"• {p}" for p in faltantes]) +
                f"\n\nPor favor, solicita a un Administrador que otorgue estos permisos al rol del bot en {canal_revision.mention}."
            )
            self.clear_items()
            self.add_item(construir_embed("error", descripcion=desc))
            return await interaction.response.edit_message(view=self)

        datos_extra = (
            f"**Nacimiento:** {self.datos['nacimiento']}\n"
            f"**Género:** {self.datos['genero']}\n"
            f"**Nacionalidad:** {self.datos['nacionalidad']}\n"
            f"**Domicilio:** {self.datos['domicilio']}"
        )
        archivo_preview = discord.File(io.BytesIO(self.buffer_bytes), filename="preview.png")

        container = construir_embed(
            tipo="roleplay",
            titulo="🔍 Nueva Solicitud de DNI",
            descripcion="Se requiere revisión administrativa para la siguiente solicitud:",
            campos=[
                ("Identidad", f"{self.datos['nombre']} {self.datos['apellido']}", True),
                ("Usuario Roblox", f"`{self.datos['roblox_user']}`", True),
                ("Datos Adicionales", datos_extra, False)
            ],
            imagen="attachment://preview.png"
        )

        vista = DniReviewView(self.solicitante, self.buffer_bytes, self.datos, embed_initial=container, texto_mencion=f"<@&{utils.ID_MANEJO_DNI}>")

        try:
            msg = await canal_revision.send(view=vista, file=archivo_preview)
            vista.message = msg
        except discord.Forbidden as e:
            logger.error(f"Falta de permisos (403 Forbidden) al despachar solicitud de DNI a canal {canal_revision.id}: {e}")
            desc = (
                f"Error al enviar la solicitud al canal de revisión {canal_revision.mention}.\n"
                f"**Motivo:** Error 403 Forbidden (Falta de acceso o permisos del bot en el canal)."
            )
            self.clear_items()
            self.add_item(construir_embed("error", descripcion=desc))
            return await interaction.response.edit_message(view=self)
        except Exception as e:
            logger.error(f"Error inesperado al despachar solicitud de DNI: {e}")
            desc = f"Error al despachar la solicitud al canal de revisión: `{e}`"
            self.clear_items()
            self.add_item(construir_embed("error", descripcion=desc))
            return await interaction.response.edit_message(view=self)

        for child in self.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True

        if not hasattr(interaction.client, 'tramites_dni_pendientes'):
            interaction.client.tramites_dni_pendientes = set()
        interaction.client.tramites_dni_pendientes.add((self.solicitante.id, self.datos['slot']))

        self.clear_items()
        self.add_item(construir_embed("exito", descripcion=f"{Emojis.EXITO} DNI enviado a la municipalidad para su revisión."))
        await interaction.response.edit_message(view=self)

    async def cancelar(self, interaction: discord.Interaction):
        for child in self.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True
        self.clear_items()
        self.add_item(construir_embed("error", descripcion="Operación cancelada.\n**Motivo:** Cancelación manual por parte del usuario."))
        await interaction.response.edit_message(view=self)


class MotivoRechazoRoboModal(discord.ui.Modal, title='Rechazar Reclamo de Robo'):
    motivo = discord.ui.TextInput(
        label='Motivo del rechazo',
        style=discord.TextStyle.paragraph,
        placeholder='Ej: La prueba no es clara...',
        required=True,
        max_length=500
    )

    def __init__(self, view_original: discord.ui.View, original_message: discord.Message, solicitante: discord.Member, tipo_robo: str, monto: int, slot: int):
        super().__init__()
        self.view_original = view_original
        self.original_message = original_message
        self.solicitante = solicitante
        self.tipo_robo = tipo_robo
        self.monto = monto
        self.slot = slot

    async def on_submit(self, interaction: discord.Interaction):
        container = construir_embed(
            tipo="error",
            titulo="🚫 Reclamo de Robo Rechazado",
            descripcion=f"**Solicitante:** {self.solicitante.mention}\n**Robo:** {self.tipo_robo}\n**Monto:** ${self.monto:,}",
            campos=[
                ("Rechazado por", interaction.user.mention, False),
                ("Motivo", self.motivo.value, False)
            ],
            imagen=getattr(self.view_original, "urls", None)
        )

        for child in self.view_original.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True

        self.view_original.clear_items()
        self.view_original.add_item(container)
        await interaction.response.edit_message(view=self.view_original)

        if hasattr(interaction.client, 'registrar_log_ui'):
            await interaction.client.registrar_log_ui(interaction, "Roleplay", "Rechazo de Robo", f"Rechazó reclamo de robo de {self.tipo_robo} por ${self.monto:,} a {self.solicitante.mention}. Motivo: {self.motivo.value}")

        try:
            desc = (
                f"Tu reclamo de indemnización por robo ha sido denegado por la administración.\n"
                f"**Detalles de la Denegación:**\n"
                f"• **Bienes Reclamados:** **{self.tipo_robo}**\n"
                f"• **Monto Solicitado:** **{utils.format_money(self.monto)}**\n"
                f"• **Motivo de Rechazo:** {self.motivo.value}"
            )
            embed_md = construir_embed("error", titulo=f"{Emojis.ERROR} Reclamo Rechazado", descripcion=desc)
            await self.solicitante.send(view=discord.ui.LayoutView().add_item(embed_md))
        except (discord.HTTPException, discord.Forbidden):
            pass


class RoboReclamoView(discord.ui.LayoutView):
    def __init__(self, solicitante: discord.Member, tipo_robo: str, monto: int, slot: int, urls: list, texto_mencion=None):
        super().__init__(timeout=None)
        self.solicitante = solicitante
        self.tipo_robo = tipo_robo
        self.monto = monto
        self.slot = slot
        self.urls = urls
        self._procesado = False

        if texto_mencion:
            self.add_item(discord.ui.TextDisplay(texto_mencion))

        container = construir_embed(
            "advertencias",
            titulo=f"🚨 Nuevo Reclamo de Robo (Slot {slot})",
            descripcion=f"**Solicitante:** {self.solicitante.mention}\n**Tipo:** {self.tipo_robo}\n**Monto Esperado:** ${self.monto:,}",
            imagen=self.urls
        )

        self.add_item(container)

        ar = discord.ui.ActionRow()
        b1 = discord.ui.Button(label="Aprobar", style=discord.ButtonStyle.success, custom_id="btn_aprobar_robo")
        b1.callback = self.aprobar
        b2 = discord.ui.Button(label="Rechazar", style=discord.ButtonStyle.danger, custom_id="btn_rechazar_robo")
        b2.callback = self.rechazar

        ar.add_item(b1)
        ar.add_item(b2)
        self.add_item(ar)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != utils.ID_DUENO and not any(r.id == utils.ID_ROL_SUPERVISOR for r in interaction.user.roles):
            desc = "Operación denegada.\n**Motivo:** Permisos administrativos insuficientes para moderar reclamos."
            await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)
            return False
        return True

    async def aprobar(self, interaction: discord.Interaction):
        if self._procesado:
            return await interaction.response.send_message("⛔ Este reclamo de robo ya fue procesado.", ephemeral=True)
        self._procesado = True

        for child in self.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True

        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_banco = dinero_banco + ? WHERE id_usuario = ? AND slot = ?",
            (self.monto, self.solicitante.id, self.slot)
        ):
            pass
        await interaction.client.db.commit()

        container = construir_embed(
            tipo="exito",
            titulo=f"{Emojis.EXITO} Reclamo de Robo Aprobado",
            descripcion=f"**Solicitante:** {self.solicitante.mention}\n**Robo:** {self.tipo_robo}\n**Monto:** ${self.monto:,}",
            campos=[
                ("Aprobado por", interaction.user.mention, False)
            ],
            imagen=self.urls
        )

        self.clear_items()
        self.add_item(container)
        await interaction.response.edit_message(view=self)

        if hasattr(interaction.client, 'registrar_log_ui'):
            await interaction.client.registrar_log_ui(interaction, "Roleplay", "Aprobación de Robo", f"Aprobó reclamo de robo de {self.tipo_robo} a {self.solicitante.mention} y depositó ${self.monto:,}.")

        try:
            embed_md = construir_embed(
                "exito", 
                f"{Emojis.EXITO} Reclamo Aprobado", 
                f"Tu reclamo de robo de **{self.tipo_robo}** ha sido aprobado. Se han depositado **${self.monto:,}** en tu cuenta bancaria (Slot {self.slot})."
            )
            await self.solicitante.send(view=discord.ui.LayoutView().add_item(embed_md))
        except (discord.HTTPException, discord.Forbidden):
            pass

    async def rechazar(self, interaction: discord.Interaction):
        if self._procesado:
            return await interaction.response.send_message("⛔ Este reclamo de robo ya fue procesado.", ephemeral=True)
        modal = MotivoRechazoRoboModal(self, interaction.message, self.solicitante, self.tipo_robo, self.monto, self.slot)
        await interaction.response.send_modal(modal)


@app_commands.guild_only()
class Roleplay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="solicitar_dni", description="Crea tu personaje y DNI Oficial. Pasa por revisión de Staff.")
    @app_commands.describe(
        slot="Selecciona el Slot (1 o 2)",
        nombre="Tu nombre de pila",
        apellido="Tu apellido",
        fecha_nacimiento="Fecha en formato DD/MM/AAAA",
        nacionalidad="Tu nacionalidad",
        genero="Selecciona tu género",
        domicilio="Tu dirección de residencia",
        usuario_roblox="Tu nombre de usuario en Roblox"
    )
    async def solicitar_dni(
        self, interaction: discord.Interaction, 
        slot: Literal[1, 2],
        nombre: str, 
        apellido: str, 
        fecha_nacimiento: str, 
        nacionalidad: str,
        genero: Literal['Masculino', 'Femenino', 'No Binario'], 
        domicilio: str,
        usuario_roblox: str
    ):
        await interaction.response.defer(ephemeral=False)

        if not hasattr(interaction.client, 'tramites_dni_pendientes'):
            interaction.client.tramites_dni_pendientes = set()

        if (interaction.user.id, slot) in interaction.client.tramites_dni_pendientes:
            desc = f"Solicitud denegada.\n**Motivo:** Ya posees un trámite de DNI pendiente de revisión para el Slot **{slot}**. Espera a que sea resuelto."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        nombre = nombre[:20].strip()
        apellido = apellido[:20].strip()
        nacionalidad = nacionalidad[:25].strip()
        domicilio = domicilio[:40].strip()
        usuario_roblox = usuario_roblox.strip()

        user = interaction.user
        if not interaction.guild:
            desc = "Operación denegada.\n**Motivo:** Este comando únicamente puede ejecutarse dentro de la jurisdicción de un servidor."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        if slot == 2 and interaction.user.id != utils.ID_DUENO and (not isinstance(interaction.user, discord.Member) or not any(r.id == utils.ID_LLAVE_SLOT_2 for r in interaction.user.roles)):
            desc = "Acceso denegado.\n**Motivo:** El Slot 2 requiere autorización especial (Llave de 2do Personaje)."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        edad = utils.calcular_edad(fecha_nacimiento)
        if not re.match(r"^\d{2}/\d{2}/\d{4}$", fecha_nacimiento):
            desc = "Error de formato.\n**Motivo:** La fecha ingresada no corresponde al formato DD/MM/AAAA."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))
        if isinstance(edad, str) or edad < 18 or edad > 120:
            desc = "Validación fallida.\n**Motivo:** La fecha de nacimiento resulta en una edad fuera de los límites permitidos (18 - 120 años)."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute("SELECT nombres FROM usuarios WHERE id_usuario = ? AND slot = ?", (interaction.user.id, slot)) as cur:
            pj_existe = await cur.fetchone()

        if pj_existe:
            desc = f"Creación denegada.\n**Motivo:** El Slot **{slot}** ya contiene un perfil ciudadano registrado."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        avatar_bytes, avatar_url = await obtener_avatar_roblox(usuario_roblox, force_refresh=True)
        if not avatar_bytes:
            desc = f"Validación de identidad fallida.\n**Motivo:** El sistema no pudo ubicar o procesar el avatar del usuario `{usuario_roblox}` en Roblox. Si recién cambiaste de ropa, aguarda unos segundos y vuelve a intentarlo."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        nro_doc = str(random.randint(10000000, 99999999))
        buffer_dni = await asyncio.to_thread(generar_imagen_dni, nombre, apellido, fecha_nacimiento, genero, nacionalidad, usuario_roblox, nro_doc, avatar_bytes)

        datos_pj = {
            'slot': slot, 'nombre': nombre, 'apellido': apellido, 'nacimiento': fecha_nacimiento,
            'nacionalidad': nacionalidad, 'genero': genero, 'domicilio': domicilio,
            'roblox_user': usuario_roblox, 'avatar_url': avatar_url, 'nro_doc': nro_doc
        }

        canal_revision = interaction.guild.get_channel(utils.ID_CANAL_REVISION_DNI)
        if not isinstance(canal_revision, discord.TextChannel):
            desc = f"Error de sistema.\n**Motivo:** El canal de revisión administrativa no se encuentra configurado o no existe (ID: `{utils.ID_CANAL_REVISION_DNI}`)."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        perms = canal_revision.permissions_for(interaction.guild.me)
        faltantes = []
        if not perms.view_channel:
            faltantes.append("Ver Canal (View Channel)")
        if not perms.send_messages:
            faltantes.append("Enviar Mensajes (Send Messages)")
        if not perms.attach_files:
            faltantes.append("Adjuntar Archivos (Attach Files)")
        if not perms.embed_links:
            faltantes.append("Insertar Enlaces (Embed Links)")

        if faltantes:
            desc = (
                f"Error de permisos en el canal de revisión {canal_revision.mention}.\n"
                f"**El bot no tiene los permisos necesarios en ese canal:**\n"
                + "\n".join([f"• {p}" for p in faltantes]) +
                f"\n\nPor favor, solicita a un Administrador que asigne estos permisos al rol del bot en {canal_revision.mention}."
            )
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        buffer_bytes = buffer_dni.getvalue()
        archivo_preview = discord.File(io.BytesIO(buffer_bytes), filename="tu_dni_preview.png")

        embed_preview = construir_embed(
            tipo="roleplay",
            titulo=f"{Emojis.DOCUMENTO} Vista Previa de tu DNI",
            descripcion="Revisa que todos tus datos y tu foto estén correctos.\nEn el caso de que esté todo correcto, confirma el envío al Staff.",
            imagen="attachment://tu_dni_preview.png"
        )

        vista_preview = DniPreviewView(user, buffer_bytes, datos_pj, embed_initial=embed_preview)
        await interaction.followup.send(view=vista_preview, file=archivo_preview)

    @app_commands.command(name="mis_personajes", description="Mira tus slots y cambia de personaje desde un menú.")
    async def mis_personajes(self, interaction: discord.Interaction):
        activo = await utils.get_slot_activo(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)

        async with interaction.client.db.execute("SELECT slot, nombres, apellidos, trabajo FROM usuarios WHERE id_usuario = ? ORDER BY slot ASC", (interaction.user.id,)) as cur:
            pjs = await cur.fetchall()

        if not pjs:
            desc = "Solicitud de consulta rechazada.\n**Motivo:** El sistema no encontró ningún personaje asociado a tu identificador único."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        desc = "**Listado de Identidades Vinculadas:**\n\n"
        for slot, nom, ape, trab in pjs:
            est = f"{Emojis.EXITO} **ACTIVO**" if slot == activo else "💤 Inactivo"
            desc += f"**[ Slot {slot} ]** {nom} {ape}\n• **Profesión:** {trab}\n• **Estado del Perfil:** {est}\n\n"

        embed_container = construir_embed(
            tipo="roleplay",
            titulo=f"{Emojis.PERSONAS} Mis Personajes",
            descripcion=desc
        )

        class SelectPersonaje(discord.ui.Select):
            def __init__(self, pjs):
                options = [
                    discord.SelectOption(
                        label=f"{nom} {ape}",
                        description=f"Profesión: {trab}",
                        value=str(slot),
                        emoji=Emojis.USUARIO
                    ) for slot, nom, ape, trab in pjs
                ]
                super().__init__(placeholder="Selecciona el personaje a activar...", min_values=1, max_values=1, options=options)

            async def callback(self, interaction_select: discord.Interaction):
                slot_elegido = int(self.values[0])
                await utils.update_slot_activo_cache(interaction_select.user.id, slot_elegido, interaction_select.client.db, interaction_select.client.sesiones_cache)

                desc_res = f"{Emojis.EXITO} Perfil principal actualizado al Slot **{slot_elegido}**."
                await interaction_select.response.edit_message(
                    view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc_res)),
                )

        class ViewPersonajes(discord.ui.LayoutView):
            def __init__(self, pjs, container):
                super().__init__(timeout=120)
                # Agregar select en un ActionRow
                action_row = discord.ui.ActionRow()
                action_row.add_item(SelectPersonaje(pjs))
                self.add_item(action_row)
                # Agregar embed como último item
                self.add_item(container)

        vista_ui = ViewPersonajes(pjs, embed_container)
        await interaction.response.send_message(view=vista_ui)

    @app_commands.command(name="cambiar_personaje", description="Cambia entre Slot 1 y 2.")
    @utils.tiene_permiso(*utils.PERMISO_2DO_PERSONAJE)
    async def cambiar_personaje(self, interaction: discord.Interaction, slot: int):
        if slot not in [1, 2]:
            desc = "Solicitud rechazada.\n**Motivo:** El sistema únicamente reconoce el Slot **1** o **2**."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute("SELECT nombres FROM usuarios WHERE id_usuario = ? AND slot = ?", (interaction.user.id, slot)) as cur:
            existe = await cur.fetchone()

        if not existe:
            desc = f"Solicitud de rotación rechazada.\n**Motivo:** El Slot **{slot}** no posee ninguna identidad registrada.\n• **Solución:** Crea un personaje nuevo utilizando `/rp solicitar_dni`."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        await utils.update_slot_activo_cache(interaction.user.id, slot, interaction.client.db, interaction.client.sesiones_cache)
        desc = (
            f"El sistema ha actualizado tu perfil principal con éxito.\n"
            f"**Datos de Rotación:**\n"
            f"• **Perfil Activo Actual:** Slot **{slot}**"
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)))

    @app_commands.command(name="forzar_cambio_pj", description="ADMIN: Cambia forzosamente el slot activo de un usuario.")
    @app_commands.checks.has_permissions(administrator=True)
    async def forzar_cambio_pj(self, interaction: discord.Interaction, usuario: discord.Member, slot: Literal[1, 2]):
        async with interaction.client.db.execute("SELECT nombres FROM usuarios WHERE id_usuario = ? AND slot = ?", (usuario.id, slot)) as cur:
            existe = await cur.fetchone()

        if not existe:
            desc = f"Solicitud administrativa rechazada.\n**Motivo:** El ciudadano {usuario.display_name} no posee un perfil registrado en el Slot **{slot}**."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        await utils.update_slot_activo_cache(usuario.id, slot, interaction.client.db, interaction.client.sesiones_cache)
        desc = (
            f"Intervención Administrativa: El sistema ha forzado la rotación de perfil del ciudadano.\n"
            f"**Datos de Rotación:**\n"
            f"• **Ciudadano Afectado:** {usuario.mention}\n"
            f"• **Nuevo Perfil Activo:** Slot **{slot}**\n"
            f"• **Autoridad:** {interaction.user.mention}"
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)))

    @app_commands.command(name="ciudadano", description="Muestra el DNI Gráfico y la Ficha Policial de un personaje.")
    @utils.tiene_permiso(*utils.PERMISO_CIVIL)
    async def ciudadano(self, interaction: discord.Interaction, usuario: discord.Member | None = None, slot: Literal[1, 2] | None = None):
        await interaction.response.defer()

        target = usuario or interaction.user

        if slot is None:
            char = await utils.get_active_char(target.id, interaction.client.db, interaction.client.sesiones_cache)
            if not char:
                desc = f"Operación denegada.\n**Motivo:** El ciudadano {target.mention} no posee un perfil activo en el sistema."
                return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))
            slot = char[4]

        async with interaction.client.db.execute("""
            SELECT id_usuario, nombres, apellidos, fecha_nacimiento, genero, nacionalidad, domicilio, 
                   dinero_mano, dinero_banco, licencias_conducir, licencias_armas, trabajo, 
                   busqueda_captura, arrestado, tiempo_carcel, imagen_url, roblox_user, nro_doc 
            FROM usuarios WHERE id_usuario = ? AND slot = ?
        """, (target.id, slot)) as cur:
            data = await cur.fetchone()

        if not data:
            desc = f"Operación denegada.\n**Motivo:** El ciudadano {target.mention} no posee un personaje registrado en el Slot **{slot}**."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        id_u, nom, ape, fec, gen, nac, dom, mano, banco, lic_c, lic_a, trab, captura, arrestado, t_carcel, img_url, rbx_user, nro_doc = data

        if not nro_doc:
            nro_doc = str(random.randint(10000000, 99999999))
            async with interaction.client.db.execute("UPDATE usuarios SET nro_doc = ? WHERE id_usuario = ? AND slot = ?", (nro_doc, target.id, slot)):
                pass
            await interaction.client.db.commit()

        async with interaction.client.db.execute("SELECT COUNT(*), SUM(monto) FROM multas WHERE id_usuario = ? AND slot = ? AND pagada = 0", (target.id, slot)) as cur:
            res_multas = await cur.fetchone()
            cant_multas, deuda_total = res_multas[0], res_multas[1] or 0

        async with interaction.client.db.execute("SELECT COUNT(*) FROM antecedentes WHERE id_usuario = ? AND slot = ?", (target.id, slot)) as cur:
            cant_antecedentes = (await cur.fetchone())[0]

        avatar_bytes = None
        if img_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            avatar_bytes = await resp.read()
            except Exception as e:
                logger.warning(f"Error descargando imagen del DNI: {e}")

        if not avatar_bytes and rbx_user:
            logger.info(f"Fallback en /ciudadano activado para '{rbx_user}'. Obteniendo avatar de Roblox...")
            avatar_bytes, nueva_img_url = await obtener_avatar_roblox(rbx_user)
            if nueva_img_url and nueva_img_url != img_url:
                async with interaction.client.db.execute("UPDATE usuarios SET imagen_url = ? WHERE id_usuario = ? AND slot = ?", (nueva_img_url, target.id, slot)):
                    pass
                await interaction.client.db.commit()

        buffer_dni = await asyncio.to_thread(generar_imagen_dni, nom, ape, fec, gen, nac, rbx_user or "Desconocido", nro_doc, avatar_bytes)
        archivo_dni = discord.File(buffer_dni, filename="dni_grafico.png")

        estado_icono = f"{Emojis.BUSCADO} BUSCADO" if captura else f"{Emojis.PRESO} PRESO" if arrestado else f"{Emojis.LIMPIO} LIMPIO"
        tipo_embed = "policial" if captura or arrestado else "roleplay"

        campos = []
        if arrestado:
            campos.append(("⛔ ESTADO PENITENCIARIO", f"**Condena:** {t_carcel}", False))

        async with interaction.client.db.execute("SELECT modelo, patente FROM vehiculos WHERE id_usuario = ? AND slot = ?", (target.id, slot)) as cur:
            vehiculos = await cur.fetchall()

        lista_v = "\n".join([f"• {m} ({p})" for m, p in vehiculos]) if vehiculos else f"{Emojis.ERROR} Ninguno"
        lista_c = "\n".join([f"• {x}" for x in lic_c.split(', ')]) if lic_c else f"{Emojis.ERROR} Ninguna"
        lista_a = "\n".join([f"• {x}" for x in lic_a.split(', ')]) if lic_a else f"{Emojis.ERROR} Ninguna"

        campos.extend([
            ("🛻 Licencias Conducir", lista_c, True),
            (f"{Emojis.ARMA} Licencias Armas", lista_a, True),
            ("🚗 Vehículos Registrados", lista_v, False),
            ("⚖️ Legal", f"**Multas Impagas:** {cant_multas} (${deuda_total:,} si hubiere)\n**Antecedentes:** {cant_antecedentes}", False),
            (f"{Emojis.BANCO} Economía", f"**Mano:** ${mano:,} | **Banco:** ${banco:,}", False)
        ])

        embed = construir_embed(
            tipo=tipo_embed,
            titulo=f"{Emojis.DOCUMENTO} Historial de Sistema | Slot {slot}",
            descripcion=f"**Ciudadano:** {nom} {ape}\n**DNI:** {nro_doc}\n**Estado Actual:** {estado_icono}",
            campos=campos,
            imagen="attachment://dni_grafico.png"
        )

        vista = discord.ui.LayoutView()
        vista.add_item(embed)

        await interaction.followup.send(file=archivo_dni, view=vista)

    @app_commands.command(name="eliminar_ciudadano", description="STAFF: Borrar un personaje permanentemente.")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_DNI)
    @app_commands.describe(confirmacion="Escribe CONFIRMO para proceder.")
    async def eliminar_ciudadano(self, interaction: discord.Interaction, ciudadano: discord.Member, slot: Literal[1, 2], confirmacion: str):
        if confirmacion != "CONFIRMO":
            desc = "Acción de seguridad abortada.\n**Motivo:** Protocolo de confirmación incorrecto (Se requiere ingresar exactamente `CONFIRMO`)."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        async with interaction.client.db.execute("SELECT nombres FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()

        if not res:
            desc = f"Operación abortada.\n**Motivo:** El ciudadano {ciudadano.display_name} no tiene un personaje registrado en el Slot **{slot}**."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute("DELETE FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)):
            pass

        async with interaction.client.db.execute("DELETE FROM vehiculos WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)):
            pass

        async with interaction.client.db.execute("DELETE FROM ruleta_apuestas WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)):
            pass

        otro_slot = 2 if slot == 1 else 1
        async with interaction.client.db.execute("SELECT 1 FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, otro_slot)) as cur:
            tiene_otro = await cur.fetchone()

        nuevo_slot = otro_slot if tiene_otro else 1

        async with interaction.client.db.execute("UPDATE sesiones SET slot_activo = ? WHERE user_id = ? AND slot_activo = ?", (nuevo_slot, ciudadano.id, slot)):
            pass

        if ciudadano.id in interaction.client.sesiones_cache and interaction.client.sesiones_cache[ciudadano.id] == slot:
            interaction.client.sesiones_cache[ciudadano.id] = nuevo_slot

        await interaction.client.db.commit()
        desc = (
            f"Se ha ejecutado la eliminación irreversible de un expediente ciudadano en la base de datos nacional.\n"
            f"**Detalles de Eliminación:**\n"
            f"• **Ciudadano Afectado:** {ciudadano.mention}\n"
            f"• **Expediente Borrado:** Slot **{slot}**\n"
            f"• **Autoridad Administrativa:** {interaction.user.mention}"
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

    @app_commands.command(name="editar_ciudadano", description="STAFF: Modificar datos de un personaje (Soporte Multi-Slot).")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_DNI)
    @app_commands.describe(
        campo="Qué dato quieres cambiar",
        nuevo_valor="Nuevo texto. Si es 'Actualizar Avatar' puedes dejarlo vacío o poner 'mismo'."
    )
    async def editar_ciudadano(
        self, interaction: discord.Interaction, 
        ciudadano: discord.Member, 
        slot: Literal[1, 2], 
        campo: Literal['Nombres', 'Apellidos', 'Edad/Fecha', 'Nacionalidad', 'Domicilio', 'Género', 'Usuario Roblox', 'Actualizar Avatar'], 
        nuevo_valor: str = ""
    ):
        await interaction.response.defer()

        async with interaction.client.db.execute(
            "SELECT nombres, apellidos, fecha_nacimiento, genero, nacionalidad, roblox_user, nro_doc FROM usuarios WHERE id_usuario = ? AND slot = ?", 
            (ciudadano.id, slot)
        ) as cur:
            user_data = await cur.fetchone()

        if not user_data:
            desc = f"Operación abortada.\n**Motivo:** El ciudadano {ciudadano.display_name} no tiene un personaje registrado en el Slot **{slot}**."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        nom_db, ape_db, fec_db, gen_db, nac_db, rbx_db, doc_db = user_data
        nuevo_valor_clean = nuevo_valor.strip() if nuevo_valor else ""

        if campo in ('Usuario Roblox', 'Actualizar Avatar'):
            if campo == 'Actualizar Avatar':
                if nuevo_valor_clean and nuevo_valor_clean.lower() not in ('mismo', 'actual', 'actualizar', '-'):
                    target_roblox = nuevo_valor_clean
                else:
                    target_roblox = (rbx_db or "").strip()

                if not target_roblox:
                    desc = "Operación abortada.\n**Motivo:** El ciudadano no posee un usuario de Roblox registrado en su ficha para actualizar su avatar."
                    return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

                campo_texto = "Avatar de Roblox"
                nuevo_texto = f"Actualizado ({target_roblox})"
            else:
                if not nuevo_valor_clean:
                    desc = "Operación abortada.\n**Motivo:** Debes indicar el nuevo nombre exacto del usuario de Roblox."
                    return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

                target_roblox = nuevo_valor_clean
                campo_texto = "Usuario Roblox"
                nuevo_texto = target_roblox

            avatar_bytes, avatar_url = await obtener_avatar_roblox(target_roblox, force_refresh=True)
            if not avatar_url or not avatar_bytes:
                desc = (
                    f"Operación abortada.\n**Motivo:** No se pudo obtener o renderizar el avatar de `{target_roblox}` en Roblox.\n"
                    f"• Si acabas de cambiar tu ropa/skin en Roblox, aguarda unos segundos a que sus servidores procesen la miniatura y vuelve a intentar.\n"
                    f"• Verifica que el nombre esté bien escrito y la cuenta no esté suspendida."
                )
                return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

            async with interaction.client.db.execute(
                "UPDATE usuarios SET roblox_user = ?, imagen_url = ? WHERE id_usuario = ? AND slot = ?", 
                (target_roblox, avatar_url, ciudadano.id, slot)
            ):
                pass

            await interaction.client.db.commit()

            # Re-generar DNI con la nueva imagen y mostrarlo de confirmación
            buffer_dni = await asyncio.to_thread(
                generar_imagen_dni, 
                nom_db, ape_db, fec_db, gen_db, nac_db, 
                target_roblox, doc_db or "00000000", avatar_bytes
            )
            archivo_dni = discord.File(buffer_dni, filename="dni_actualizado.png")

            desc = (
                f"El Registro Nacional de las Personas ha procesado una actualización de datos.\n"
                f"**Expediente Modificado:**\n"
                f"• **Ciudadano:** {ciudadano.mention} (Slot **{slot}**)\n"
                f"• **Campo Afectado:** **{campo_texto}**\n"
                f"• **Nuevo Registro:** **{nuevo_texto}**\n"
                f"• **Autoridad Revisora:** {interaction.user.mention}"
            )
            embed_exito = construir_embed("exito", descripcion=desc, imagen="attachment://dni_actualizado.png")
            return await interaction.followup.send(file=archivo_dni, view=discord.ui.LayoutView().add_item(embed_exito))

        else:
            if not nuevo_valor_clean:
                desc = f"Operación abortada.\n**Motivo:** Debes proporcionar un nuevo texto para modificar el campo **{campo}**."
                return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

            columnas = {
                'Nombres': 'nombres',
                'Apellidos': 'apellidos',
                'Edad/Fecha': 'fecha_nacimiento',
                'Nacionalidad': 'nacionalidad',
                'Domicilio': 'domicilio',
                'Género': 'genero'
            }
            col_db = columnas[campo]

            if campo == 'Edad/Fecha' and (utils.calcular_edad(nuevo_valor_clean) == "??" or not re.match(r"^\d{2}/\d{2}/\d{4}$", nuevo_valor_clean)):
                desc = "Operación abortada.\n**Motivo:** El formato de fecha ingresado es inválido.\n• **Formato Requerido:** DD/MM/AAAA."
                return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

            async with interaction.client.db.execute(f"UPDATE usuarios SET {col_db} = ? WHERE id_usuario = ? AND slot = ?", (nuevo_valor_clean, ciudadano.id, slot)):
                pass

            await interaction.client.db.commit()
            desc = (
                f"El Registro Nacional de las Personas ha procesado una actualización de datos.\n"
                f"**Expediente Modificado:**\n"
                f"• **Ciudadano:** {ciudadano.mention} (Slot **{slot}**)\n"
                f"• **Campo Afectado:** **{campo}**\n"
                f"• **Nuevo Registro:** **{nuevo_valor_clean}**\n"
                f"• **Autoridad Revisora:** {interaction.user.mention}"
            )
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)))

    @app_commands.command(name="editar_dni", description="STAFF: Modificar datos o avatar del DNI de un personaje (Alias de /editar_ciudadano).")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_DNI)
    @app_commands.describe(
        campo="Qué dato quieres cambiar",
        nuevo_valor="Nuevo texto. Si es 'Actualizar Avatar' puedes dejarlo vacío o poner 'mismo'."
    )
    async def editar_dni(
        self, interaction: discord.Interaction, 
        ciudadano: discord.Member, 
        slot: Literal[1, 2], 
        campo: Literal['Nombres', 'Apellidos', 'Edad/Fecha', 'Nacionalidad', 'Domicilio', 'Género', 'Usuario Roblox', 'Actualizar Avatar'], 
        nuevo_valor: str = ""
    ):
        await self.editar_ciudadano(interaction, ciudadano, slot, campo, nuevo_valor)

    @app_commands.command(name="registrar_vehiculo", description="Registrar un nuevo vehículo a un ciudadano.")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_LICENCIAS)
    @app_commands.describe(
        dni_ciudadano="DNI del ciudadano propietario (ej: 12345678)",
        modelo="Modelo del vehículo",
        patente="Patente/Dominio del vehículo"
    )
    async def registrar_vehiculo(self, interaction: discord.Interaction, dni_ciudadano: str, modelo: str, patente: str):
        await interaction.response.defer(ephemeral=True)
        
        patente = patente.upper().strip()
        
        # Buscar ciudadano por DNI
        ciudadano_data = await buscar_usuario_por_dni(interaction.client.db, dni_ciudadano)
        if not ciudadano_data:
            desc = f"Solicitud de registro vehicular rechazada.\n**Motivo:** No se encontró ningún ciudadano con DNI **{dni_ciudadano}** en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        usuario_id, slot, nombres, apellidos = ciudadano_data
        nombre_completo = f"{nombres} {apellidos}"

        # Obtener usuario de Discord
        ciudadano = interaction.guild.get_member(usuario_id) if interaction.guild else None

        # Verificar si la patente ya existe
        async with interaction.client.db.execute("SELECT id_vehiculo FROM vehiculos WHERE patente = ?", (patente,)) as cur:
            existe = await cur.fetchone()

        if existe:
            desc = f"Solicitud de registro vehicular rechazada.\n**Motivo:** El dominio/patente **{patente}** ya se encuentra asociado a otro vehículo en la base de datos nacional."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        # Registrar vehículo
        async with interaction.client.db.execute(
            "INSERT INTO vehiculos (id_usuario, slot, modelo, patente) VALUES (?, ?, ?, ?)", 
            (usuario_id, slot, modelo, patente)
        ):
            pass
        await interaction.client.db.commit()
        
        # Construir respuesta
        desc = (
            f"El Registro del Automotor ha procesado exitosamente la inscripción del vehículo.\n"
            f"**Datos del Dominio Registrado:**\n"
            f"• **Titular:** **{nombre_completo}** (DNI: {dni_ciudadano}, Slot **{slot}**)" + (f" | {ciudadano.mention}" if ciudadano else "") + "\n"
            f"• **Modelo de Vehículo:** **{modelo}**\n"
            f"• **Dominio (Patente):** **{patente}**"
        )
        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(construir_embed("exito", f"{Emojis.EXITO} Dominio Vehicular Registrado", desc)),
            ephemeral=True
        )

    @app_commands.command(name="retirar_vehiculo", description="Retirar un vehículo de un ciudadano.")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_LICENCIAS)
    async def retirar_vehiculo(self, interaction: discord.Interaction, ciudadano: discord.Member, slot: Literal[1, 2], patente: str):
        patente = patente.upper().strip()
        async with interaction.client.db.execute("SELECT id_vehiculo, modelo FROM vehiculos WHERE id_usuario = ? AND slot = ? AND patente = ?", (ciudadano.id, slot, patente)) as cur:
            vehiculo = await cur.fetchone()

        if not vehiculo:
            desc = f"Operación de baja vehicular rechazada.\n**Motivo:** No se ha encontrado el dominio **{patente}** asociado al ciudadano en el Slot **{slot}**."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        async with interaction.client.db.execute("DELETE FROM vehiculos WHERE id_vehiculo = ?", (vehiculo[0],)):
            pass
        await interaction.client.db.commit()
        desc = (
            f"El Registro del Automotor ha dado de baja permanentemente el vehículo del sistema.\n"
            f"**Detalles de Baja Vehicular:**\n"
            f"• **Titular Afectado:** {ciudadano.mention} (Slot **{slot}**)\n"
            f"• **Modelo de Vehículo:** **{vehiculo[1]}**\n"
            f"• **Dominio Revocado:** **{patente}**"
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("exito", f"{Emojis.EXITO} Baja Vehicular Ejecutada", desc)))

    @app_commands.command(name="licencia_conducir", description="Gestionar licencias de tránsito del PJ ACTIVO.")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_LICENCIAS)
    async def licencia_conducir(
        self, interaction: discord.Interaction, 
        ciudadano: discord.Member, 
        slot: Literal[1, 2],
        accion: Literal['Otorgar', 'Revocar', 'Suspender', 'Reactivar'], 
        clase: Literal['A1 (Ciclomotores)', 'A2 (Cuatriciclos)', 'B1 (Automovíles/Camionetas)', 'B2 (Casas Rodantes)', 'C1 (Camiones sin acoplado 12mil KG)', 'C2 (Camiones sin acoplado 24mil KG)', 'C3 (Camiones sin Acoplado 25+mil Kg)', 'D1 (Ocho plazas)', 'D4 (Emergencias)', 'E2 (Maquinaria especial agricola)', 'G1 (Tractores agricoleas)', 'J1 (Encubiertos)']
    ):
        async with interaction.client.db.execute("SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()

        if not res:
            desc = f"Operación denegada.\n**Motivo:** El ciudadano {ciudadano.mention} no posee un personaje registrado en el Slot **{slot}**."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        nombre_pj = f"{res[0]} {res[1]}"

        async with interaction.client.db.execute("SELECT licencias_conducir FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()

        licencias_actuales = res[0] if res and res[0] else ""
        nueva_lista = utils.gestionar_estado_licencia(licencias_actuales, clase, accion)

        if nueva_lista == licencias_actuales:
            if accion == "Otorgar": motivo_desc = f"El ciudadano ya posee la licencia **{clase}** (o se encuentra suspendida)."
            elif accion == "Revocar": motivo_desc = f"El ciudadano no posee la licencia **{clase}**, por ende no puede ser revocada."
            elif accion == "Suspender": motivo_desc = f"El ciudadano no posee la licencia **{clase}** activa, o ya se encuentra suspendida."
            elif accion == "Reactivar": motivo_desc = f"La licencia **{clase}** no se encuentra en estado suspendido."
            desc = f"Gestión de licencia rechazada.\n**Motivo:** Acción redundante o inválida.\n• **Detalle:** {motivo_desc}"
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute("UPDATE usuarios SET licencias_conducir = ? WHERE id_usuario = ? AND slot = ?", (nueva_lista, ciudadano.id, slot)):
            pass
        await interaction.client.db.commit()

        emoji = Emojis.EXITO if accion in ["Otorgar", "Reactivar"] else Emojis.ERROR if accion == "Revocar" else Emojis.ADVERTENCIA
        tipo_embed = "exito" if accion == "Otorgar" else "advertencia"

        embed = construir_embed(
            tipo=tipo_embed,
            titulo=f"{Emojis.LICENCIA} Licencia de Conducir: {nombre_pj}",
            campos=[
                ("Acción", f"{emoji} **{accion}**", True),
                ("Clase", f"**{clase}**", True),
                (f"Estado Actual (Slot {slot})", f"```{nueva_lista or 'Ninguna'}```", False)
            ]
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(embed))

    @app_commands.command(name="licencia_armas", description="Gestionar credenciales ANMAC del PJ ACTIVO.")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_LICENCIAS)
    async def licencia_armas(
        self, interaction: discord.Interaction, 
        ciudadano: discord.Member, 
        slot: Literal[1, 2],
        accion: Literal['Otorgar', 'Revocar', 'Suspender', 'Reactivar'], 
        tipo: Literal['ANMAC A', 'ANMAC B', 'ANMAC C', 'ANMAC D', 'Tenencia']
    ):
        async with interaction.client.db.execute("SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()

        if not res:
            desc = f"Operación denegada.\n**Motivo:** El ciudadano {ciudadano.mention} no posee un personaje registrado en el Slot **{slot}**."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        nombre_pj = f"{res[0]} {res[1]}"

        async with interaction.client.db.execute("SELECT licencias_armas FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()

        licencias_actuales = res[0] if res and res[0] else ""
        nueva_lista = utils.gestionar_estado_licencia(licencias_actuales, tipo, accion)

        if nueva_lista == licencias_actuales:
            if accion == "Otorgar": motivo_desc = f"El ciudadano ya posee la credencial **{tipo}** (o se encuentra suspendida)."
            elif accion == "Revocar": motivo_desc = f"El ciudadano no posee la credencial **{tipo}**, por ende no puede ser revocada."
            elif accion == "Suspender": motivo_desc = f"El ciudadano no posee la credencial **{tipo}** activa, o ya se encuentra suspendida."
            elif accion == "Reactivar": motivo_desc = f"La credencial **{tipo}** no se encuentra en estado suspendido."
            desc = f"Gestión de credencial rechazada.\n**Motivo:** Acción redundante o inválida.\n• **Detalle:** {motivo_desc}"
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute("UPDATE usuarios SET licencias_armas = ? WHERE id_usuario = ? AND slot = ?", (nueva_lista, ciudadano.id, slot)):
            pass
        await interaction.client.db.commit()

        emoji = Emojis.EXITO if accion in ["Otorgar", "Reactivar"] else Emojis.ERROR if accion == "Revocar" else Emojis.ADVERTENCIA

        embed = construir_embed(
            tipo="policial",
            titulo=f"{Emojis.ARMA} Registro ANMAC: {nombre_pj}",
            campos=[
                ("Acción", f"{emoji} **{accion}**", True),
                ("Categoría", f"**{tipo}**", True),
                (f"Estado Actual (Slot {slot})", f"```{nueva_lista or 'Ninguna'}```", False)
            ]
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(embed))

    @app_commands.command(name="reclamar_robo", description="Genera un reclamo oficial por un robo efectuado.")
    @app_commands.describe(
        tipo_robo="Selecciona qué robaste",
        prueba_1="Sube la captura de pantalla de la recompensa",
        prueba_2="Sube una captura del robo o prueba secundaria"
    )
    async def reclamar_robo(self, interaction: discord.Interaction, tipo_robo: str, prueba_1: discord.Attachment, prueba_2: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not prueba_1.content_type or not prueba_1.content_type.startswith("image/") or not prueba_2.content_type or not prueba_2.content_type.startswith("image/"):
            desc = "Solicitud de reclamo rechazada.\n**Motivo:** Evidencia fotográfica inválida o ausente.\n• **Requisito:** Adjuntar dos capturas de pantalla claras del robo."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        monto = utils.VALORES_ROBOS.get(tipo_robo)
        if not monto:
            desc = f"Solicitud de reclamo rechazada.\n**Motivo:** El objetivo seleccionado (`{tipo_robo}`) no está catalogado en el sistema de recompensas."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Operación denegada.\n**Motivo:** No posees un personaje seleccionado para adjudicar este reclamo."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        slot = char[4]

        guild = interaction.guild
        if not guild:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="Comando exclusivo de servidores.")), ephemeral=True)

        canal_reclamos = guild.get_channel(utils.ID_CANAL_RECLAMOS)
        if not isinstance(canal_reclamos, discord.TextChannel):
            desc = "Error de sistema.\n**Motivo:** El canal de reclamos no se encuentra configurado en el entorno."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        vista = RoboReclamoView(interaction.user, tipo_robo, monto, slot, urls=[prueba_1.url, prueba_2.url], texto_mencion=f"<@&{utils.ID_ROL_SUPERVISOR}>")

        await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("exito", f"{Emojis.EXITO} Reclamo de Robo Enviado", f"Tu reclamo de robo por el tipo **{tipo_robo}** fue enviado al equipo administrativo para su evaluación.")), ephemeral=True)
        msg = await canal_reclamos.send(view=vista)
        vista.message = msg

    @reclamar_robo.autocomplete('tipo_robo')
    async def reclamar_robo_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=k, value=k)
            for k in utils.VALORES_ROBOS.keys() if current.lower() in k.lower()
        ][:25]


async def setup(bot):
    await bot.add_cog(Roleplay(bot))
