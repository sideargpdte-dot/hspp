import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from typing import Literal, Optional
import io
import logging
from PIL import Image, ImageDraw, ImageFont

from cogs.roleplay import obtener_avatar_roblox
from cogs import codigo_penal
import utils
from tema import Emojis, construir_embed

logger = logging.getLogger("cogs.policia")

# Roles para alerta de búsqueda y captura
ROLES_ALERTA_BUSQUEDA = [1492967075906457670, 1516568543129243648, 1491464077799723008, 1491464209836277862]

# ==========================================
#  SISTEMA DE SELECT MENU PARA PAGAR MULTAS
# ==========================================

class SeleccionMultaView(discord.ui.LayoutView):
    def __init__(self, interaction_original: discord.Interaction, multas: list, slot: int):
        super().__init__(timeout=60)
        self.interaction_original = interaction_original
        self.multas = multas  # Lista de tuplas (id_multa, motivo, monto, fecha)
        self.slot = slot
        
        # Crear select menu con las multas
        self.select = discord.ui.Select(
            placeholder="Selecciona la multa que deseas pagar...",
            min_values=1,
            max_values=1
        )
        
        for id_multa, motivo, monto, fecha in multas[:25]:  # Discord limita a 25 opciones
            descripcion = f"{utils.format_money(monto)} - {fecha}"
            if len(motivo) > 50:
                motivo = motivo[:47] + "..."
            self.select.add_option(
                label=f"#{id_multa} - {motivo[:50]}",
                value=str(id_multa),
                description=descripcion
            )
        
        self.select.callback = self.select_callback
        
        action_row = discord.ui.ActionRow()
        action_row.add_item(self.select)
        self.add_item(action_row)
        
        # Agregar embed informativo
        desc = (
            f"Tienes **{len(multas)}** multa(s) pendiente(s) de pago.\n\n"
            f"Selecciona la multa que deseas abonar del menú desplegable."
        )
        embed = construir_embed(
            "advertencia",
            titulo=f"{Emojis.MULTA} Multas Pendientes",
            descripcion=desc
        )
        self.add_item(embed)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("error", descripcion="No puedes interactuar con este menú.")
                ),
                ephemeral=True
            )
        
        # Obtener ID de multa seleccionada desde self.select.values
        id_multa = int(self.select.values[0])
        
        # Buscar los datos de la multa seleccionada
        multa_seleccionada = next((m for m in self.multas if m[0] == id_multa), None)
        if not multa_seleccionada:
            desc = "Error al procesar selección.\n**Motivo:** La multa seleccionada no se encontró."
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )
        
        _, motivo, monto, fecha = multa_seleccionada
        
        # Verificar fondos
        async with interaction.client.db.execute(
            "SELECT dinero_mano, dinero_banco FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (interaction.user.id, self.slot)
        ) as cur:
            economia = await cur.fetchone()
        
        if not economia:
            desc = "Error de sistema.\n**Motivo:** No se encontraron datos económicos de tu personaje."
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )
        
        mano, banco = economia
        
        if mano < monto:
            if (mano + banco) >= monto:
                desc = "Transacción declinada.\n**Motivo:** Fondos insuficientes en **Efectivo**.\n• **Sugerencia:** Tienes fondos en tu cuenta bancaria. Retira el dinero en un cajero e inténtalo nuevamente."
            else:
                desc = f"Transacción declinada.\n**Motivo:** Fondos totales insuficientes para cubrir el monto adeudado de **{utils.format_money(monto)}**."
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )
        
        # Procesar pago
        async with interaction.client.db.execute(
            "UPDATE multas SET pagada = 1 WHERE id_multa = ? AND pagada = 0",
            (id_multa,)
        ) as cur_m:
            if cur_m.rowcount == 0:
                desc = "Pago rechazado.\n**Motivo:** La multa ya fue procesada por otra transacción."
                return await interaction.response.send_message(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )
        
        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano - ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
            (monto, interaction.user.id, self.slot, monto)
        ) as cur_u:
            if cur_u.rowcount == 0:
                await interaction.client.db.execute("UPDATE multas SET pagada = 0 WHERE id_multa = ?", (id_multa,))
                await interaction.client.db.commit()
                desc = "Transacción declinada.\n**Motivo:** Fondos en efectivo insuficientes al momento de procesar el cobro."
                return await interaction.response.send_message(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )
        
        await interaction.client.db.commit()
        
        # Confirmar pago
        desc = (
            f"El pago de tu infracción ha sido procesado exitosamente por el Sistema de Rentas.\n"
            f"**Recibo de Pago:**\n"
            f"• **Folio Abonado:** **#{id_multa}**\n"
            f"• **Monto Pagado:** **{utils.format_money(monto)}**\n"
            f"• **Motivo:** {motivo}\n"
            f"• **Estado Legal:** Deuda saldada formalmente."
        )
        
        # Deshabilitar el menú
        self.clear_items()
        self.add_item(construir_embed("exito", f"{Emojis.EXITO} Multa Procesada Satisfactoriamente", desc))
        
        await interaction.response.edit_message(view=self)

# ==========================================
#  SISTEMA DE PAGINACIÓN PARA DENUNCIAS
# ==========================================

class DenunciaPaginationView(discord.ui.LayoutView):
    def __init__(self, interaction_original: discord.Interaction, seguimientos_con_evidencias: list, numero_denuncia: str, info_denuncia: dict):
        super().__init__(timeout=180)  # 3 minutos
        self.interaction_original = interaction_original
        self.seguimientos = seguimientos_con_evidencias  # Lista de tuplas (oficial, accion, descripcion, fecha, imagen_url)
        self.numero_denuncia = numero_denuncia
        self.info_denuncia = info_denuncia  # Dict con información general de la denuncia
        self.pagina_actual = 0
        self.total_paginas = len(seguimientos_con_evidencias)
        
        # Crear primera página
        self.crear_pagina()
        
        # Crear botones
        self.crear_botones()
    
    def crear_pagina(self):
        # Limpiar items previos (excepto botones)
        self.clear_items()
        
        # Obtener seguimiento actual
        oficial, accion, descripcion_seg, fecha, imagen_url = self.seguimientos[self.pagina_actual]
        
        # Construir descripción general en la primera página
        if self.pagina_actual == 0:
            desc = (
                f"**Información General:**\n"
                f"• **Número:** {self.numero_denuncia}\n"
                f"• **Tipo:** {self.info_denuncia['tipo']}\n"
                f"• **Estado:** **{self.info_denuncia['estado']}**\n"
                f"• **Prioridad:** **{self.info_denuncia['prioridad']}**\n"
                f"• **Denunciante:** {self.info_denuncia['denunciante']}\n"
                f"• **Oficial Receptor:** {self.info_denuncia['oficial_receptor']}\n"
                f"• **Fecha de Registro:** {self.info_denuncia['fecha_denuncia']}\n\n"
                f"**Descripción de los Hechos:**\n{self.info_denuncia['descripcion']}\n\n"
                f"---\n\n"
                f"**Seguimiento {self.pagina_actual + 1}/{self.total_paginas}:**\n"
                f"• **Acción:** {accion}\n"
                f"• **Oficial:** {oficial}\n"
                f"• **Fecha:** {fecha}\n"
                f"• **Descripción:** {descripcion_seg}"
            )
        else:
            desc = (
                f"**Seguimiento {self.pagina_actual + 1}/{self.total_paginas}:**\n"
                f"• **Acción:** {accion}\n"
                f"• **Oficial:** {oficial}\n"
                f"• **Fecha:** {fecha}\n"
                f"• **Descripción:** {descripcion_seg}"
            )
        
        # Crear embed
        embed = construir_embed(
            tipo="policial",
            titulo=f"{Emojis.DOCUMENTO} DENUNCIA: {self.numero_denuncia}",
            descripcion=desc,
            imagen=imagen_url if imagen_url else None
        )
        
        self.add_item(embed)
    
    def crear_botones(self):
        # Botón anterior
        boton_anterior = discord.ui.Button(
            label="◀️ Anterior",
            style=discord.ButtonStyle.secondary,
            disabled=(self.pagina_actual == 0)
        )
        boton_anterior.callback = self.boton_anterior_callback
        
        # Indicador de página
        boton_pagina = discord.ui.Button(
            label=f"Seguimiento {self.pagina_actual + 1}/{self.total_paginas}",
            style=discord.ButtonStyle.primary,
            disabled=True
        )
        
        # Botón siguiente
        boton_siguiente = discord.ui.Button(
            label="Siguiente ▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.pagina_actual == self.total_paginas - 1)
        )
        boton_siguiente.callback = self.boton_siguiente_callback
        
        # Botón cerrar
        boton_cerrar = discord.ui.Button(
            label="✖️ Cerrar",
            style=discord.ButtonStyle.danger
        )
        boton_cerrar.callback = self.boton_cerrar_callback
        
        # Agregar botones en una fila
        action_row = discord.ui.ActionRow()
        action_row.add_item(boton_anterior)
        action_row.add_item(boton_pagina)
        action_row.add_item(boton_siguiente)
        action_row.add_item(boton_cerrar)
        
        self.add_item(action_row)
    
    async def boton_anterior_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("error", descripcion="No puedes interactuar con esta paginación.")
                ),
                ephemeral=True
            )
        
        self.pagina_actual -= 1
        self.crear_pagina()
        self.crear_botones()
        
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass
    
    async def boton_siguiente_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("error", descripcion="No puedes interactuar con esta paginación.")
                ),
                ephemeral=True
            )
        
        self.pagina_actual += 1
        self.crear_pagina()
        self.crear_botones()
        
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass
    
    async def boton_cerrar_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("error", descripcion="No puedes interactuar con esta paginación.")
                ),
                ephemeral=True
            )
        
        self.clear_items()
        self.add_item(construir_embed("advertencia", descripcion="Consulta de denuncia cerrada por el usuario."))
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass
    
    async def on_timeout(self):
        # Deshabilitar todos los botones cuando expira el timeout
        for child in self.walk_children():
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        
        try:
            if hasattr(self, '_message') and self._message:
                await self._message.edit(view=self)
        except:
            pass

# ==========================================
#  SISTEMA DE PAGINACIÓN PARA CÓDIGO PENAL
# ==========================================

class CodigoPenalPaginationView(discord.ui.LayoutView):
    def __init__(self, interaction_original: discord.Interaction, paginas: list, tipo_consulta: str):
        super().__init__(timeout=180)  # 3 minutos
        self.interaction_original = interaction_original
        self.paginas = paginas
        self.tipo_consulta = tipo_consulta
        self.pagina_actual = 0
        self.total_paginas = len(paginas)
        
        # Agregar embed inicial
        self.add_item(self.paginas[self.pagina_actual])
        
        # Crear botones
        self.crear_botones()
    
    def crear_botones(self):
        # Botón anterior
        boton_anterior = discord.ui.Button(
            label="◀️ Anterior",
            style=discord.ButtonStyle.secondary,
            disabled=(self.pagina_actual == 0)
        )
        boton_anterior.callback = self.boton_anterior_callback
        
        # Indicador de página
        boton_pagina = discord.ui.Button(
            label=f"Página {self.pagina_actual + 1}/{self.total_paginas}",
            style=discord.ButtonStyle.primary,
            disabled=True
        )
        
        # Botón siguiente
        boton_siguiente = discord.ui.Button(
            label="Siguiente ▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.pagina_actual == self.total_paginas - 1)
        )
        boton_siguiente.callback = self.boton_siguiente_callback
        
        # Botón cerrar
        boton_cerrar = discord.ui.Button(
            label="✖️ Cerrar",
            style=discord.ButtonStyle.danger
        )
        boton_cerrar.callback = self.boton_cerrar_callback
        
        # Agregar botones en una fila
        action_row = discord.ui.ActionRow()
        action_row.add_item(boton_anterior)
        action_row.add_item(boton_pagina)
        action_row.add_item(boton_siguiente)
        action_row.add_item(boton_cerrar)
        
        self.add_item(action_row)
    
    async def boton_anterior_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("error", descripcion="No puedes interactuar con esta paginación.")
                ),
                ephemeral=True
            )
        
        self.pagina_actual -= 1
        await self.actualizar_vista(interaction)
    
    async def boton_siguiente_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("error", descripcion="No puedes interactuar con esta paginación.")
                ),
                ephemeral=True
            )
        
        self.pagina_actual += 1
        await self.actualizar_vista(interaction)
    
    async def boton_cerrar_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("error", descripcion="No puedes interactuar con esta paginación.")
                ),
                ephemeral=True
            )
        
        self.clear_items()
        self.add_item(construir_embed("advertencia", descripcion="Consulta cerrada por el usuario."))
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass
    
    async def actualizar_vista(self, interaction: discord.Interaction):
        # Limpiar vista
        self.clear_items()
        
        # Agregar embed de la página actual
        self.add_item(self.paginas[self.pagina_actual])
        
        # Recrear botones
        self.crear_botones()
        
        # Actualizar mensaje
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass
    
    async def on_timeout(self):
        # Deshabilitar todos los botones cuando expira el timeout
        for child in self.walk_children():
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        
        try:
            # Intentar actualizar el mensaje (puede fallar si ya fue eliminado)
            if hasattr(self, '_message') and self._message:
                await self._message.edit(view=self)
        except:
            pass

# ==========================================
#  VARIABLES GLOBALES DE IMAGEN Y FUENTES
# ==========================================
try:
    TEMPLATE_PROFUGO_GLOBAL = Image.open(utils.ruta_actual / "profugo_template.png").convert("RGBA")
except FileNotFoundError:
    logger.warning("No se encuentra 'profugo_template.png'. Creando plantilla por defecto.")
    TEMPLATE_PROFUGO_GLOBAL = Image.new("RGBA", (1000, 1000), (255, 255, 255, 255))
except Exception as e:
    logger.error(f"Error al cargar plantilla: {e}")
    TEMPLATE_PROFUGO_GLOBAL = Image.new("RGBA", (1000, 1000), (255, 255, 255, 255))

FONT_PATH_GLOBAL = utils.ruta_actual / "Helvetica-Bold.ttf"
FONT_CACHE = {}


def get_cached_font(size: int):
    if size not in FONT_CACHE:
        try:
            FONT_CACHE[size] = ImageFont.truetype(str(FONT_PATH_GLOBAL), size)
        except IOError:
            FONT_CACHE[size] = ImageFont.load_default()
    return FONT_CACHE[size]


def generar_cartel_busqueda(nombre_pj: str, nacionalidad: str, fecha_nacimiento: str, motivo: str, estado: str, avatar_bytes: bytes | None = None) -> io.BytesIO:
    template = TEMPLATE_PROFUGO_GLOBAL.copy()
    draw = ImageDraw.Draw(template)
    font_tiny = get_cached_font(14)

    if avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            avatar = avatar.resize((582, 618))
            template.paste(avatar, (678, 63), avatar)
        except Exception as e:
            logger.error(f"Error procesando avatar: {e}")

    try:
        font_size = 50
        font_name = get_cached_font(font_size)
        bbox = draw.textbbox((0, 0), nombre_pj.upper(), font=font_name)
        w = bbox[2] - bbox[0]

        max_width = 640
        while w > max_width and font_size > 20:
            font_size -= 2
            font_name = get_cached_font(font_size)
            bbox = draw.textbbox((0, 0), nombre_pj.upper(), font=font_name)
            w = bbox[2] - bbox[0]
    except IOError:
        font_name = ImageFont.load_default()
        font_size = 50
        bbox = draw.textbbox((0, 0), nombre_pj.upper(), font=font_name)
        w = bbox[2] - bbox[0]

    center_x = 678 // 2
    x_pos = max(10, center_x - (w // 2))
    y_pos = 395 + (50 - font_size) // 2

    draw.text((x_pos, y_pos), nombre_pj.upper(), font=font_name, fill=(255, 255, 255))
    draw.text((132, 540), nacionalidad.upper(), font=font_tiny, fill=(0, 0, 0))
    draw.text((392, 540), fecha_nacimiento, font=font_tiny, fill=(0, 0, 0))
    draw.text((122, 521), motivo.upper(), font=font_tiny, fill=(0, 0, 0))

    if estado == 'Desactivar':
        font_sello = get_cached_font(120)
        txt_img = Image.new("RGBA", template.size, (255, 255, 255, 0))
        d = ImageDraw.Draw(txt_img)
        bbox = d.textbbox((0, 0), "CAPTURADO", font=font_sello)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        d.text(((1280 - w) // 2, (720 - h) // 2), "CAPTURADO", font=font_sello, fill=(200, 20, 20, 200))
        txt_img = txt_img.rotate(25, expand=0)
        template.alpha_composite(txt_img)

    buffer = io.BytesIO()
    template.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


class ConfirmacionPoliciaView(discord.ui.LayoutView):
    def __init__(self, interaction_original: discord.Interaction, embed_container, callback, *args, **kwargs):
        super().__init__(timeout=60)
        self.interaction_original = interaction_original
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

        self.add_item(embed_container)

        ar = discord.ui.ActionRow()
        b1 = discord.ui.Button(label="Confirmar Acción", style=discord.ButtonStyle.danger, emoji="⚠️")
        b1.callback = self.confirmar
        ar.add_item(b1)

        b2 = discord.ui.Button(label="Cancelar", style=discord.ButtonStyle.secondary)
        b2.callback = self.cancelar
        ar.add_item(b2)
        self.add_item(ar)

    async def confirmar(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="No puedes interactuar con esta advertencia.")),
                ephemeral=True
            )

        for child in self.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass

        await self.callback(interaction, *self.args, **self.kwargs)

    async def cancelar(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_original.user.id:
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="No puedes interactuar con esta advertencia.")),
                ephemeral=True
            )

        self.clear_items()
        self.add_item(construir_embed("advertencia", descripcion="Acción policial cancelada por el usuario."))
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass


async def enviar_respuesta(interaction: discord.Interaction, **kwargs):
    if interaction.response.is_done():
        return await interaction.followup.send(**kwargs)
    else:
        return await interaction.response.send_message(**kwargs)


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


@app_commands.guild_only()
class Policia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_presos.start()

    def cog_unload(self):
        self.check_presos.cancel()

    @tasks.loop(seconds=60)
    async def check_presos(self):
        if not self.bot.db:
            return

        try:
            ahora = datetime.now().timestamp()

            async with self.bot.db.execute("SELECT id_usuario, id_guild FROM arrestos WHERE fecha_liberacion <= ?", (ahora,)) as cur:
                presos_vencidos = await cur.fetchall()

            for datos in presos_vencidos:
                user_id, guild_id = datos
                guild = self.bot.get_guild(guild_id)

                if not guild:
                    async with self.bot.db.execute("DELETE FROM arrestos WHERE id_usuario = ?", (user_id,)):
                        pass
                    await self.bot.db.commit()
                    continue

                member = guild.get_member(user_id)
                if not member:
                    try:
                        member = await guild.fetch_member(user_id)
                    except discord.NotFound:
                        async with self.bot.db.execute("DELETE FROM arrestos WHERE id_usuario = ?", (user_id,)):
                            pass
                        await self.bot.db.commit()
                        continue
                    except discord.HTTPException as e:
                        logger.error(f"Error buscando miembro {user_id}: {e}")
                        continue

                if member:
                    try:
                        await member.timeout(None, reason="Condena cumplida")
                    except discord.HTTPException as e:
                        logger.warning(f"No se pudo revocar timeout a {user_id}: {e}")

                    role = guild.get_role(utils.ID_ROL_PRESO)
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Condena cumplida")
                            desc_md = (
                                "Tu tiempo de condena ha finalizado por completo.\n"
                                "**Estado Legal:** Eres nuevamente un ciudadano libre.\n\n"
                                "Las puertas de la prisión están abiertas. Procura no volver."
                            )
                            embed_md = construir_embed("exito", titulo=f"{Emojis.EXITO} CONDENA CUMPLIDA", descripcion=desc_md)
                            await member.send(view=discord.ui.LayoutView().add_item(embed_md))
                        except (discord.HTTPException, discord.Forbidden):
                            pass

                # Mover arresto al historial antes de eliminarlo
                async with self.bot.db.execute(
                    """SELECT numero_arresto, articulos, multa_total, gravedad, 
                       oficiales_a_cargo, es_ck FROM arrestos WHERE id_usuario = ?""",
                    (user_id,)
                ) as cur:
                    arresto_data = await cur.fetchone()
                
                if arresto_data:
                    num_arr, arts, multa, grav, oficiales, es_ck = arresto_data
                    # Obtener slot del usuario (usar slot 1 por defecto si no se encuentra)
                    async with self.bot.db.execute(
                        "SELECT slot FROM usuarios WHERE id_usuario = ? LIMIT 1",
                        (user_id,)
                    ) as cur_slot:
                        slot_data = await cur_slot.fetchone()
                        slot = slot_data[0] if slot_data else 1
                    
                    # Guardar en historial
                    async with self.bot.db.execute(
                        """INSERT INTO historial_arrestos (
                            id_usuario, slot, numero_arresto, fecha_arresto, fecha_liberacion,
                            articulos, multa_total, gravedad, oficiales_a_cargo, es_ck, estado
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CUMPLIDO')""",
                        (user_id, slot, num_arr, ahora, ahora, arts, multa, grav, oficiales, es_ck)
                    ):
                        pass
                    await self.bot.db.commit()

                # Eliminar arresto activo
                async with self.bot.db.execute("DELETE FROM arrestos WHERE id_usuario = ?", (user_id,)):
                    pass
                await self.bot.db.commit()

        except Exception as e:
            logger.error(f"Error general en loop check_presos: {e}")

    @check_presos.before_loop
    async def before_check_presos(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="arrestar", description="Arrestar a un usuario con artículos del Código Penal.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        dni_arrestado="DNI del ciudadano a arrestar (ej: 12345678)",
        articulos="Artículos separados por ' - ' (Ej: Art.1.1 - Art.2.3)",
        gravedad="Nivel de gravedad del delito",
        dni_oficial_principal="DNI del oficial principal a cargo del arresto",
        foto_prueba="Evidencia fotográfica del arresto (obligatorio)",
        dni_oficial_2="DNI del oficial adicional (opcional)",
        dni_oficial_3="DNI del oficial adicional (opcional)",
        dni_oficial_4="DNI del oficial adicional (opcional)",
        dni_oficial_5="DNI del oficial adicional (opcional)",
        dni_oficial_6="DNI del oficial adicional (opcional)",
        dni_oficial_7="DNI del oficial adicional (opcional)",
        dni_oficial_8="DNI del oficial adicional (opcional)",
        dni_oficial_9="DNI del oficial adicional (opcional)",
        dni_oficial_10="DNI del oficial adicional (opcional)",
        link_imagen="Link de imagen como evidencia adicional (opcional)"
    )
    async def arrestar(
        self, 
        interaction: discord.Interaction,
        dni_arrestado: str,
        articulos: str,
        gravedad: Literal['leve', 'medio', 'grave'],
        dni_oficial_principal: str,
        foto_prueba: discord.Attachment,
        dni_oficial_2: str = None,
        dni_oficial_3: str = None,
        dni_oficial_4: str = None,
        dni_oficial_5: str = None,
        dni_oficial_6: str = None,
        dni_oficial_7: str = None,
        dni_oficial_8: str = None,
        dni_oficial_9: str = None,
        dni_oficial_10: str = None,
        link_imagen: str = None
    ):
        await interaction.response.defer()
        await self._execute_arrestar(
            interaction, dni_arrestado, articulos, gravedad, dni_oficial_principal, foto_prueba,
            dni_oficial_2, dni_oficial_3, dni_oficial_4, dni_oficial_5, dni_oficial_6,
            dni_oficial_7, dni_oficial_8, dni_oficial_9, dni_oficial_10, link_imagen
        )

    async def _execute_arrestar(
        self, 
        interaction: discord.Interaction,
        dni_arrestado: str,
        articulos: str,
        gravedad: Literal['leve', 'medio', 'grave'],
        dni_oficial_principal: str,
        foto_prueba: discord.Attachment,
        dni_oficial_2: str = None,
        dni_oficial_3: str = None,
        dni_oficial_4: str = None,
        dni_oficial_5: str = None,
        dni_oficial_6: str = None,
        dni_oficial_7: str = None,
        dni_oficial_8: str = None,
        dni_oficial_9: str = None,
        dni_oficial_10: str = None,
        link_imagen: str = None
    ):
        if not interaction.guild:
            desc = "Operación denegada.\n**Motivo:** Este comando únicamente puede ejecutarse dentro de la jurisdicción de un servidor."
            return await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        # Validar formato de foto_prueba (obligatorio)
        if not foto_prueba.content_type or not foto_prueba.content_type.startswith("image/"):
            desc = "Solicitud policial rechazada.\n**Motivo:** Evidencia fotográfica inválida o ausente.\n• **Requisito:** Adjuntar una imagen válida que justifique el arresto."
            return await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        # Determinar URL de la imagen a usar (usa link_imagen si está presente, sino foto_prueba)
        imagen_url = link_imagen if link_imagen else foto_prueba.url

        # Buscar usuario arrestado por DNI
        arrestado_data = await buscar_usuario_por_dni(interaction.client.db, dni_arrestado)
        if not arrestado_data:
            desc = f"Solicitud policial rechazada.\n**Motivo:** No se encontró ningún ciudadano con DNI **{dni_arrestado}** en el sistema."
            return await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        usuario_id, slot, nombres, apellidos = arrestado_data
        nom_preso = f"{nombres} {apellidos}"

        # Obtener usuario de Discord
        usuario = interaction.guild.get_member(usuario_id)
        if not usuario:
            try:
                usuario = await interaction.guild.fetch_member(usuario_id)
            except discord.NotFound:
                desc = f"Error al procesar arresto.\n**Motivo:** El usuario asociado al DNI **{dni_arrestado}** no se encuentra en el servidor."
                return await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        # Procesar artículos del Código Penal
        resultado = codigo_penal.procesar_articulos(articulos, gravedad)
        
        if 'error' in resultado:
            desc = f"Error en Código Penal.\n**Motivo:** {resultado['error']}"
            return await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        multa_total = resultado['multa_total']
        tiempo_total_minutos = resultado['tiempo_total']
        es_ck = resultado['es_ck']
        detalles_articulos = resultado['detalles']
        sanciones_especiales = resultado['sanciones']

        # Recopilar oficiales a cargo por DNI
        dnis_oficiales = [dni_oficial_principal, dni_oficial_2, dni_oficial_3, dni_oficial_4, 
                         dni_oficial_5, dni_oficial_6, dni_oficial_7, dni_oficial_8, 
                         dni_oficial_9, dni_oficial_10]
        
        # Buscar oficial principal primero (para guardar en multa)
        oficial_principal_data = await buscar_usuario_por_dni(interaction.client.db, dni_oficial_principal)
        if not oficial_principal_data:
            desc = f"Error en oficial.\n**Motivo:** No se encontró ningún oficial con DNI **{dni_oficial_principal}** en el sistema."
            return await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)
        
        oficiales_nombres = [f"{oficial_principal_data[2]} {oficial_principal_data[3]}"]
        
        # Buscar oficiales adicionales
        for dni in [dni_oficial_2, dni_oficial_3, dni_oficial_4, dni_oficial_5, dni_oficial_6,
                    dni_oficial_7, dni_oficial_8, dni_oficial_9, dni_oficial_10]:
            if dni:
                oficial_data = await buscar_usuario_por_dni(interaction.client.db, dni)
                if oficial_data:
                    oficiales_nombres.append(f"{oficial_data[2]} {oficial_data[3]}")
                else:
                    desc = f"Error en oficial.\n**Motivo:** No se encontró ningún oficial con DNI **{dni}** en el sistema."
                    return await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)
        
        oficiales_texto = ", ".join(oficiales_nombres)

        # Determinar tiempo de prisión (SIN TIMEOUT - solo rol y registro)
        if es_ck:
            tiempo_delta = timedelta(days=36500)  # 100 años = CK
            texto_tiempo = "Cadena Perpetua (CK)"
        else:
            tiempo_delta = timedelta(minutes=tiempo_total_minutos)
            horas = tiempo_total_minutos // 60
            minutos = tiempo_total_minutos % 60
            if horas > 0:
                texto_tiempo = f"{horas}h {minutos}m" if minutos > 0 else f"{horas}h"
            else:
                texto_tiempo = f"{minutos}m"

        # Asignar rol de preso (SIN TIMEOUT)
        role = interaction.guild.get_role(utils.ID_ROL_PRESO)
        if role:
            try:
                await usuario.add_roles(role)
            except discord.HTTPException as e:
                logger.warning(f"No se pudo asignar el rol de preso a {usuario.id}: {e}")

        # Registrar en base de datos
        fecha_salida = datetime.now() + tiempo_delta
        timestamp_salida = fecha_salida.timestamp()
        numero_arresto = utils.generar_numero_arresto()

        async with interaction.client.db.execute(
            """REPLACE INTO arrestos (
                id_usuario, id_guild, fecha_liberacion, articulos, multa_total, 
                gravedad, oficiales_a_cargo, numero_arresto, es_ck
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (usuario.id, interaction.guild.id, timestamp_salida, articulos, 
             multa_total, gravedad, oficiales_texto, numero_arresto, 1 if es_ck else 0)
        ):
            pass
        await interaction.client.db.commit()

        # Guardar también en el historial de arrestos
        async with interaction.client.db.execute(
            """INSERT INTO historial_arrestos (
                id_usuario, slot, numero_arresto, fecha_arresto, fecha_liberacion,
                articulos, multa_total, gravedad, oficiales_a_cargo, es_ck, estado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO')""",
            (usuario.id, slot, numero_arresto, datetime.now().timestamp(), timestamp_salida,
             articulos, multa_total, gravedad, oficiales_texto, 1 if es_ck else 0)
        ):
            pass
        await interaction.client.db.commit()

        # Registrar antecedente
        delitos_texto = ", ".join([d['infraccion'] for d in detalles_articulos])
        async with interaction.client.db.execute(
            "INSERT INTO antecedentes (id_usuario, delito, oficial_id, fecha, slot) VALUES (?, ?, ?, ?, ?)",
            (usuario.id, delitos_texto[:500], interaction.user.id, datetime.now().strftime("%d/%m/%Y"), slot)
        ):
            pass
        await interaction.client.db.commit()

        # Registrar multa asociada al arresto
        async with interaction.client.db.execute(
            """INSERT INTO multas (
                id_usuario, motivo, monto, oficial_id, pagada, fecha, 
                articulos, gravedad, slot
            ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (usuario.id, f"Arresto #{numero_arresto}: {delitos_texto[:200]}", multa_total, 
             oficial_principal_data[0], datetime.now().strftime("%d/%m/%Y"), articulos, gravedad, slot)
        ):
            pass
        await interaction.client.db.commit()

        # Construir detalles de artículos para el embed
        articulos_detalle = []
        for det in detalles_articulos:
            tiempo_txt = f"{det['tiempo_minutos']} min OOC" if det['tiempo_minutos'] != 'CK' else 'CK'
            articulos_detalle.append(
                (f"{det['codigo']} - {utils.format_money(det['multa'])}", 
                 f"{det['infraccion']}\n**Sanción:** {det['sancion']}\n**Tiempo:** {tiempo_txt}", 
                 False)
            )

        ts_discord = int(timestamp_salida) if not es_ck else None
        desc = (
            f"Se ha ingresado un nuevo recluso a la penitenciaría bajo mandato oficial.\n"
            f"**Expediente de Arresto ({numero_arresto}):**\n"
            f"• **Recluso:** **{nom_preso}** (DNI: {dni_arrestado}, Slot **{slot}**) | {usuario.mention}\n"
            f"• **Oficiales a Cargo:** **{oficiales_texto}**\n"
            f"• **Multa Total:** **{utils.format_money(multa_total)}**\n"
            f"• **Gravedad:** **{gravedad.upper()}**\n"
            f"• **Tiempo de Condena:** **{texto_tiempo}**\n"
        )
        
        if not es_ck and ts_discord:
            desc += f"• **Fecha de Liberación:** <t:{ts_discord}:R> (<t:{ts_discord}:f>)\n"
        
        desc += f"\n**Artículos Aplicados:**"
        
        if sanciones_especiales:
            desc += f"\n\n{Emojis.ADVERTENCIA} **Sanciones Especiales:** {', '.join(sanciones_especiales)}"

        embed = construir_embed(
            tipo="policial",
            titulo=f"{Emojis.POLICIA} REGISTRO DE ARRESTO APLICADO",
            descripcion=desc,
            campos=articulos_detalle,
            imagen=imagen_url
        )
        await enviar_respuesta(interaction, view=discord.ui.LayoutView().add_item(embed))

        # Notificar al usuario arrestado
        try:
            articulos_md = "\n".join([f"• **{d['codigo']}**: {d['infraccion']}" for d in detalles_articulos])
            desc_md = (
                f"Has sido ingresado a la penitenciaría central.\n"
                f"**Detalles de tu Condena ({numero_arresto}):**\n"
                f"• **Oficiales a Cargo:** **{oficiales_texto}**\n"
                f"• **Multa Total:** **{utils.format_money(multa_total)}**\n"
                f"• **Duración:** **{texto_tiempo}**\n"
                f"• **Gravedad:** **{gravedad.upper()}**\n\n"
                f"**Cargos Aplicados:**\n{articulos_md}\n\n"
                f"El sistema te liberará automáticamente cuando se cumpla tu condena."
            )
            embed_md = construir_embed("error", titulo=f"{Emojis.PRESO} NOTIFICACIÓN DE ARRESTO", descripcion=desc_md, imagen=imagen_url)
            await usuario.send(view=discord.ui.LayoutView().add_item(embed_md))
        except (discord.HTTPException, discord.Forbidden):
            pass

    @app_commands.command(name="codigo-penal", description="Consultar artículos del Código Penal.")
    @utils.tiene_permiso(*utils.PERMISO_CIVIL)
    @app_commands.describe(
        consulta_tipo="Tipo de consulta a realizar",
        codigo_articulo="Código del artículo (Ej: Art.1.1) - Solo para consulta de artículo",
        numero_capitulo="Número del capítulo romano (Ej: I, II, III) - Solo para consulta de capítulo"
    )
    async def codigo_penal(
        self,
        interaction: discord.Interaction,
        consulta_tipo: Literal['articulo', 'capitulo', 'completo'],
        codigo_articulo: str = None,
        numero_capitulo: Literal['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'] = None
    ):
        await interaction.response.defer(ephemeral=True)

        if consulta_tipo == 'articulo':
            if not codigo_articulo:
                desc = "Error en consulta.\n**Motivo:** Debes proporcionar el código del artículo a consultar (Ej: Art.1.1)."
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )
            
            articulo = codigo_penal.obtener_articulo(codigo_articulo)
            if not articulo:
                desc = f"Artículo no encontrado.\n**Motivo:** El código **{codigo_articulo}** no existe en el Código Penal de AMBA."
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )
            
            # Calcular tiempos para las tres gravedades
            tiempo_leve = codigo_penal.convertir_tiempo_a_minutos(articulo['condena'], 'leve')
            tiempo_medio = codigo_penal.convertir_tiempo_a_minutos(articulo['condena'], 'medio')
            tiempo_grave = codigo_penal.convertir_tiempo_a_minutos(articulo['condena'], 'grave')
            
            tiempo_leve_txt = 'CK' if tiempo_leve == 'CK' else f"{tiempo_leve} min OOC"
            tiempo_medio_txt = 'CK' if tiempo_medio == 'CK' else f"{tiempo_medio} min OOC"
            tiempo_grave_txt = 'CK' if tiempo_grave == 'CK' else f"{tiempo_grave} min OOC"
            
            desc = (
                f"**Capítulo {articulo['cap']}**\n\n"
                f"**Infracción:** {articulo['infraccion']}\n"
                f"**Multa Base:** {utils.format_money(articulo['multa'])}\n"
                f"**Sanción:** {articulo['sancion']}\n"
                f"**Condena IC:** {articulo['condena']}\n\n"
                f"**Tiempos OOC por Gravedad:**\n"
                f"• **Leve (33%):** {tiempo_leve_txt}\n"
                f"• **Medio (66%):** {tiempo_medio_txt}\n"
                f"• **Grave (100%):** {tiempo_grave_txt}"
            )
            
            embed = construir_embed(
                tipo="policial",
                titulo=f"📖 Código Penal - {codigo_articulo}",
                descripcion=desc
            )
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(embed),
                ephemeral=True
            )
        
        elif consulta_tipo == 'capitulo':
            if not numero_capitulo:
                desc = "Error en consulta.\n**Motivo:** Debes seleccionar el número del capítulo (I-X)."
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )
            
            capitulo_data = codigo_penal.obtener_capitulo(numero_capitulo)
            articulos = capitulo_data['articulos']
            
            if not articulos:
                desc = f"Capítulo vacío.\n**Motivo:** El capítulo **{numero_capitulo}** no contiene artículos."
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )
            
            # Crear páginas (máximo 8 artículos por página para evitar límites de Discord)
            articulos_por_pagina = 8
            total_paginas = (len(articulos) + articulos_por_pagina - 1) // articulos_por_pagina
            
            paginas = []
            for num_pagina in range(total_paginas):
                inicio = num_pagina * articulos_por_pagina
                fin = min(inicio + articulos_por_pagina, len(articulos))
                articulos_pagina = articulos[inicio:fin]
                
                campos = []
                for art in articulos_pagina:
                    tiempo_medio = codigo_penal.convertir_tiempo_a_minutos(art['condena'], 'medio')
                    tiempo_txt = 'CK' if tiempo_medio == 'CK' else f"{tiempo_medio} min OOC"
                    
                    campos.append((
                        f"{art['codigo']} - {utils.format_money(art['multa'])}",
                        f"{art['infraccion']}\n**Tiempo (medio):** {tiempo_txt}",
                        False
                    ))
                
                desc = f"**{capitulo_data['nombre']}**\n\nTotal de artículos: {len(articulos)}"
                if total_paginas > 1:
                    desc += f"\n\n*Página {num_pagina + 1} de {total_paginas}*"
                
                embed = construir_embed(
                    tipo="policial",
                    titulo=f"📖 Código Penal - Capítulo {numero_capitulo}",
                    descripcion=desc,
                    campos=campos
                )
                paginas.append(embed)
            
            # Si solo hay una página, enviar directamente
            if len(paginas) == 1:
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(paginas[0]),
                    ephemeral=True
                )
            
            # Si hay múltiples páginas, usar paginación
            view = CodigoPenalPaginationView(interaction, paginas, 'capitulo')
            mensaje = await interaction.followup.send(view=view, ephemeral=True)
            view._message = mensaje  # Guardar referencia al mensaje para timeout
        
        elif consulta_tipo == 'completo':
            codigo_completo = codigo_penal.obtener_codigo_penal_completo()
            
            # Crear lista de capítulos en un solo embed
            campos = []
            for numero, cap_data in codigo_completo.items():
                campos.append((
                    f"Capítulo {numero}: {cap_data['nombre']}",
                    f"Total de artículos: **{len(cap_data['articulos'])}**",
                    False
                ))
            
            desc = (
                "**Código Penal de AMBA Reborn 2**\n\n"
                "El Código Penal está dividido en 10 capítulos.\n\n"
                f"{Emojis.INFO} *Para consultar un capítulo específico usa:*\n"
                f"`/codigo-penal consulta_tipo:capitulo numero_capitulo:I`\n\n"
                f"{Emojis.INFO} *Para consultar un artículo específico usa:*\n"
                f"`/codigo-penal consulta_tipo:articulo codigo_articulo:Art.1.1`"
            )
            
            embed = construir_embed(
                tipo="policial",
                titulo="📖 Código Penal - Índice Completo",
                descripcion=desc,
                campos=campos
            )
            
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(embed),
                ephemeral=True
            )

    @app_commands.command(name="liberar", description="OVERRIDE: Liberar a un preso inmediatamente (Solo Admins).")
    @app_commands.checks.has_permissions(administrator=True)
    async def liberar(self, interaction: discord.Interaction, usuario: discord.Member):
        if not interaction.guild:
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="Comando exclusivo de servidores.")))

        timeout_removido = True
        try:
            await usuario.timeout(None, reason=f"Liberación manual por Admin: {interaction.user}")
        except discord.HTTPException:
            timeout_removido = False

        role = interaction.guild.get_role(utils.ID_ROL_PRESO)
        if role:
            try:
                await usuario.remove_roles(role)
            except discord.HTTPException:
                pass

        async with interaction.client.db.execute("DELETE FROM arrestos WHERE id_usuario = ?", (usuario.id,)):
            pass
        await interaction.client.db.commit()
        desc = (
            f"Intervención Administrativa: El recluso ha sido puesto en libertad inmediata.\n"
            f"**Detalles de la Acción:**\n"
            f"• **Ciudadano Liberado:** {usuario.mention}\n"
            f"• **Autoridad Administrativa:** {interaction.user.mention}"
        )
        if not timeout_removido:
            desc += f"\n\n> {Emojis.ADVERTENCIA} **Nota:** No se pudo remover el aislamiento temporal (Timeout) vía Discord por falta de jerarquía/permisos, pero se removió el rol de preso y el registro penitenciario."
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)))

        try:
            desc_md = (
                f"Un Administrador ha emitido una orden de liberación manual.\n"
                f"**Detalles de la Liberación:**\n"
                f"• **Autoridad:** **{interaction.user.display_name}**\n"
                f"• **Estado:** Eres libre, tu historial penitenciario ha sido limpiado.\n\n"
                f"Procura mantener un buen comportamiento ciudadano."
            )
            embed_md = construir_embed("exito", titulo=f"{Emojis.EXITO} NOTIFICACIÓN DE LIBERACIÓN", descripcion=desc_md)
            await usuario.send(view=discord.ui.LayoutView().add_item(embed_md))
        except (discord.HTTPException, discord.Forbidden):
            pass

    @app_commands.command(name="multar", description="Emitir multa con artículos del Código Penal.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        dni_infractor="DNI del ciudadano infractor (ej: 12345678)",
        dni_oficial="DNI del oficial emisor (ej: 87654321)",
        foto_prueba="Evidencia fotográfica de la infracción (obligatorio)",
        articulos="Artículos separados por ' - ' (Ej: Art.1.1 - Art.2.3) o monto manual",
        gravedad="Nivel de gravedad (solo si usas artículos)",
        motivo_manual="Motivo si no usas artículos del código penal",
        monto_manual="Monto manual si no usas artículos (dejar en 0 para usar código penal)",
        link_imagen="Link de imagen como evidencia adicional (opcional)"
    )
    async def multar(
        self, 
        interaction: discord.Interaction,
        dni_infractor: str,
        dni_oficial: str,
        foto_prueba: discord.Attachment,
        articulos: str = None,
        gravedad: Literal['leve', 'medio', 'grave'] = 'medio',
        motivo_manual: str = None,
        monto_manual: int = 0,
        link_imagen: str = None
    ):
        await interaction.response.defer()
        
        # Validación: debe usar artículos O monto manual
        if not articulos and monto_manual <= 0:
            desc = "Parámetros insuficientes.\n**Motivo:** Debes especificar artículos del Código Penal O un monto manual con motivo."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        # Validar formato de foto_prueba (obligatorio)
        if not foto_prueba.content_type or not foto_prueba.content_type.startswith("image/"):
            desc = "Solicitud de multa rechazada.\n**Motivo:** Evidencia fotográfica inválida o ausente.\n• **Requisito:** Adjuntar un archivo de imagen válido."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        # Determinar URL de la imagen a usar (usa link_imagen si está presente, sino foto_prueba)
        imagen_url = link_imagen if link_imagen else foto_prueba.url

        # Buscar oficial por DNI
        oficial_data = await buscar_usuario_por_dni(interaction.client.db, dni_oficial)
        if not oficial_data:
            desc = f"Oficial no encontrado.\n**Motivo:** No se encontró ningún oficial con DNI **{dni_oficial}** en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )
        
        oficial_id, oficial_slot, oficial_nombres, oficial_apellidos = oficial_data
        nom_oficial = f"{oficial_nombres} {oficial_apellidos}"

        # Buscar infractor por DNI
        infractor_data = await buscar_usuario_por_dni(interaction.client.db, dni_infractor)
        if not infractor_data:
            desc = f"Infractor no encontrado.\n**Motivo:** No se encontró ningún ciudadano con DNI **{dni_infractor}** en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        infractor_id, infractor_slot, infractor_nombres, infractor_apellidos = infractor_data
        nom_multado = f"{infractor_nombres} {infractor_apellidos}"

        # Obtener usuario de Discord del infractor
        ciudadano = interaction.guild.get_member(infractor_id) if interaction.guild else None
        if not ciudadano:
            try:
                ciudadano = await interaction.guild.fetch_member(infractor_id)
            except discord.NotFound:
                pass

        # Procesar multa según si usa código penal o monto manual
        multa_total = 0
        motivo_final = ""
        articulos_detalle = []
        usar_codigo_penal = False

        if articulos:
            # Usar código penal
            usar_codigo_penal = True
            resultado = codigo_penal.procesar_articulos(articulos, gravedad)
            
            if 'error' in resultado:
                desc = f"Error en Código Penal.\n**Motivo:** {resultado['error']}"
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )

            multa_total = resultado['multa_total']
            detalles_articulos = resultado['detalles']
            
            # Construir detalles para el embed
            for det in detalles_articulos:
                articulos_detalle.append(
                    (f"{det['codigo']} - {utils.format_money(det['multa'])}", 
                     f"{det['infraccion']}\n**Sanción:** {det['sancion']}", 
                     False)
                )
            
            motivo_final = f"Código Penal: {articulos} (Gravedad: {gravedad.upper()})"
        else:
            # Usar monto manual
            multa_total = monto_manual
            motivo_final = motivo_manual if motivo_manual else "Multa sin especificación de motivo"

        if multa_total <= 0:
            desc = "Solicitud de multa rechazada.\n**Motivo:** El monto de la multa debe ser mayor a $0."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        # Registrar multa en base de datos
        async with interaction.client.db.execute(
            """INSERT INTO multas (
                id_usuario, motivo, monto, oficial_id, pagada, fecha, 
                articulos, gravedad, slot
            ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (infractor_id, motivo_final, multa_total, oficial_id, 
             datetime.now().strftime("%d/%m/%Y"), articulos if usar_codigo_penal else None, 
             gravedad if usar_codigo_penal else None, infractor_slot)
        ) as cur:
            id_multa = cur.lastrowid
        await interaction.client.db.commit()

        # Construir embed de respuesta
        desc = (
            f"Se ha registrado una infracción oficial en la base de datos central de AMBA.\n"
            f"**Registro de la Multa (#{id_multa}):**\n"
            f"• **Infractor:** **{nom_multado}** (DNI: {dni_infractor}, Slot **{infractor_slot}**)" + (f" | {ciudadano.mention}" if ciudadano else "") + "\n"
            f"• **Monto a Pagar:** **{utils.format_money(multa_total)}**\n"
            f"• **Oficial Emisor:** **{nom_oficial}** (DNI: {dni_oficial})\n"
        )

        if usar_codigo_penal:
            desc += f"• **Gravedad:** **{gravedad.upper()}**\n\n**Artículos Aplicados:**"
            embed = construir_embed(
                tipo="advertencia",
                titulo=f"{Emojis.MULTA} Multa Emitida (Folio #{id_multa})",
                descripcion=desc,
                campos=articulos_detalle,
                imagen=imagen_url
            )
        else:
            desc += f"• **Cargo/Motivo:** **{motivo_final}**"
            embed = construir_embed(
                tipo="advertencia",
                titulo=f"{Emojis.MULTA} Multa Emitida (Folio #{id_multa})",
                descripcion=desc,
                imagen=imagen_url
            )

        await interaction.followup.send(view=discord.ui.LayoutView().add_item(embed))

        # Notificar al multado
        if ciudadano:
            try:
                if usar_codigo_penal:
                    articulos_md = "\n".join([f"• **{d['codigo']}**: {d['infraccion']}" for d in detalles_articulos])
                    desc_md = (
                        f"El oficial **{nom_oficial}** ha labrado un acta de infracción a tu nombre.\n"
                        f"**Detalles de tu Infracción:**\n"
                        f"• **Monto a Pagar:** **{utils.format_money(multa_total)}**\n"
                        f"• **Gravedad:** **{gravedad.upper()}**\n"
                        f"• **Folio de Sistema:** **#{id_multa}**\n\n"
                        f"**Artículos Aplicados:**\n{articulos_md}\n\n"
                        f"Para abonar la deuda y evitar recargos fiscales, dirígete a un cajero automático o comisaría y utiliza el comando `/pagar_multa`."
                    )
                else:
                    desc_md = (
                        f"El oficial **{nom_oficial}** ha labrado un acta de infracción a tu nombre.\n"
                        f"**Detalles de tu Infracción:**\n"
                        f"• **Monto a Pagar:** **{utils.format_money(multa_total)}**\n"
                        f"• **Motivo de Infracción:** **{motivo_final}**\n"
                        f"• **Folio de Sistema:** **#{id_multa}**\n\n"
                        f"Para abonar la deuda y evitar recargos fiscales, dirígete a un cajero automático o comisaría y utiliza el comando `/pagar_multa`."
                    )
                
                embed_md = construir_embed(
                    tipo="advertencia",
                    titulo=f"{Emojis.MULTA} Notificación de Infracción",
                    descripcion=desc_md,
                    imagen=imagen_url
                )
                await ciudadano.send(view=discord.ui.LayoutView().add_item(embed_md))
            except (discord.HTTPException, discord.Forbidden):
                pass

    @app_commands.command(name="ver_multas", description="Ver multas pendientes de un ciudadano.")
    @utils.tiene_permiso(*utils.PERMISO_CIVIL)
    @app_commands.describe(
        dni_ciudadano="DNI del ciudadano (opcional, si no se pone ve tus propias multas)",
        slot="Slot del personaje (opcional, si no se pone usa el activo)"
    )
    async def ver_multas(self, interaction: discord.Interaction, dni_ciudadano: str = None, slot: Literal[1, 2] = None):
        await interaction.response.defer(ephemeral=True)
        
        # Si no se proporciona DNI, usar el usuario que ejecuta el comando
        if dni_ciudadano is None:
            target_id = interaction.user.id
            # Si no se proporciona slot, usar el activo
            if slot is None:
                char = await utils.get_active_char(target_id, interaction.client.db, interaction.client.sesiones_cache)
                if not char:
                    desc = "Operación denegada.\n**Motivo:** No posees un personaje seleccionado en el sistema."
                    return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)
                slot = char[4]
                target_nombre = f"{char[1]} {char[2]}"
            else:
                # Buscar nombres del slot especificado
                async with interaction.client.db.execute(
                    "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
                    (target_id, slot)
                ) as cur:
                    datos = await cur.fetchone()
                if not datos:
                    desc = f"No tienes un personaje registrado en el Slot **{slot}**."
                    return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)
                target_nombre = f"{datos[0]} {datos[1]}"
        else:
            # Buscar por DNI
            usuario_data = await buscar_usuario_por_dni(interaction.client.db, dni_ciudadano)
            if not usuario_data:
                desc = f"Ciudadano no encontrado.\n**Motivo:** No se encontró ningún ciudadano con DNI **{dni_ciudadano}** en el sistema."
                return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)
            
            target_id, slot_dni, nombres, apellidos = usuario_data
            target_nombre = f"{nombres} {apellidos}"
            
            # Si se proporciona slot, usar ese; si no, usar el del DNI encontrado
            if slot is None:
                slot = slot_dni
            else:
                # Verificar que el slot existe para ese usuario
                async with interaction.client.db.execute(
                    "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
                    (target_id, slot)
                ) as cur:
                    datos = await cur.fetchone()
                if not datos:
                    desc = f"El ciudadano con DNI **{dni_ciudadano}** no tiene un personaje en el Slot **{slot}**."
                    return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)
                target_nombre = f"{datos[0]} {datos[1]}"
            
            # Verificar permisos si está consultando a otra persona
            if target_id != interaction.user.id:
                if interaction.user.id != utils.ID_DUENO and (not isinstance(interaction.user, discord.Member) or not any(r.id in utils.PERMISO_POLICIAL for r in interaction.user.roles)):
                    desc = "Operación denegada.\n**Motivo:** Restricción de privacidad. Solo el infractor o autoridades superiores pueden visualizar multas ajenas."
                    return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        # Buscar multas del usuario y slot específico
        async with interaction.client.db.execute(
            "SELECT id_multa, motivo, monto, fecha FROM multas WHERE id_usuario = ? AND slot = ? AND pagada = 0 ORDER BY fecha DESC",
            (target_id, slot)
        ) as cur:
            multas = await cur.fetchall()

        if not multas:
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(
                    construir_embed("exito", descripcion=f"{Emojis.EXITO} **{target_nombre}** (Slot {slot}) no tiene multas pendientes.")
                ), 
                ephemeral=True
            )

        total_deuda = sum(m[2] for m in multas)
        campos_multas = [
            (f"#{id_m} ({utils.format_money(mon)})", f"{fec} - {mot}", False)
            for id_m, mot, mon, fec in multas
        ]
        
        embed = construir_embed(
            tipo="advertencia",
            titulo=f"{Emojis.MULTA} Multas de {target_nombre} (Slot {slot})",
            descripcion=f"**Total Adeudado:** {utils.format_money(total_deuda)}\n**Cantidad de Multas:** {len(multas)}",
            campos=campos_multas
        )
        await interaction.followup.send(view=discord.ui.LayoutView().add_item(embed), ephemeral=True)

    @app_commands.command(name="revocar_multa", description="ADMIN: Revoca una multa sin cobrar.")
    @utils.tiene_permiso(*utils.PERMISO_ADMIN)
    async def revocar_multa(self, interaction: discord.Interaction, id_multa: int):
        await interaction.response.defer(ephemeral=True)
        async with interaction.client.db.execute("SELECT pagada FROM multas WHERE id_multa = ?", (id_multa,)) as cur:
            multa = await cur.fetchone()

        if not multa:
            desc = f"Solicitud denegada.\n**Motivo:** El Folio **#{id_multa}** no existe en el registro central."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        async with interaction.client.db.execute("UPDATE multas SET pagada = 1 WHERE id_multa = ?", (id_multa,)):
            pass
        await interaction.client.db.commit()

        desc = (
            f"El mandato judicial ha cancelado oficialmente la infracción en el sistema.\n"
            f"**Detalles de Cancelación:**\n"
            f"• **Folio Revocado:** **#{id_multa}**\n"
            f"• **Estado Legal:** Marcada como Pagada / Revocada sin deducción de fondos.\n"
            f"• **Autoridad Administrativa:** {interaction.user.mention}"
        )
        await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("exito", f"{Emojis.EXITO} Multa Revocada Exitosamente", desc)), ephemeral=True)

    @app_commands.command(name="buscar_dominio", description="POLICIA: Busca los datos de registro de una patente vehicular.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    async def buscar_dominio(self, interaction: discord.Interaction, patente: str):
        await interaction.response.defer(ephemeral=True)
        patente = patente.upper().strip()
        async with interaction.client.db.execute("SELECT id_usuario, slot, modelo FROM vehiculos WHERE patente = ?", (patente,)) as cur:
            vehiculo = await cur.fetchone()

        if not vehiculo:
            desc = f"Consulta de dominio fallida.\n**Motivo:** No se encontraron registros vehiculares asociados a la patente **{patente}**."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        id_usuario, slot, modelo = vehiculo

        async with interaction.client.db.execute("SELECT nombres, apellidos, nro_doc FROM usuarios WHERE id_usuario = ? AND slot = ?", (id_usuario, slot)) as cur:
            propietario = await cur.fetchone()

        if not propietario:
            desc = "Error de sistema.\n**Motivo:** Base de datos desincronizada o perfil de propietario corrupto."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)), ephemeral=True)

        nombres, apellidos, nro_doc = propietario

        miembro_discord = interaction.guild.get_member(id_usuario) if interaction.guild else None
        mencion = miembro_discord.mention if miembro_discord else f"ID: {id_usuario}"

        campos = [
            ("Patente", f"**{patente}**", True),
            ("Modelo", modelo, True),
            ("Propietario Registrado", f"{nombres} {apellidos}", False),
            ("Documento", nro_doc, True),
            ("Contacto Discord", mencion, True)
        ]
        embed = construir_embed(
            "policial",
            titulo="🔎 Consulta de Dominio",
            campos=campos
        )

        await interaction.followup.send(view=discord.ui.LayoutView().add_item(embed), ephemeral=True)

    # ==========================================
    #  SISTEMA DE BÚSQUEDA Y CAPTURA COMPLETO
    # ==========================================

    @app_commands.command(name="busqueda", description="POLICIA: Activar/Desactivar Búsqueda y Captura.")
    @utils.tiene_permiso(*utils.PERMISO_ADMIN)
    async def busqueda(self, interaction: discord.Interaction, ciudadano: discord.Member, slot: Literal[1, 2], estado: Literal['Activar', 'Desactivar'], motivo: str):
        await interaction.response.defer()
        char = await utils.get_active_char(ciudadano.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = f"Operación denegada.\n**Motivo:** El ciudadano {ciudadano.mention} no posee un perfil activo en el sistema."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute("SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()

        if not res:
            desc = f"Operación denegada.\n**Motivo:** El ciudadano {ciudadano.mention} no posee un personaje registrado en el Slot **{slot}**."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        nombre_pj = f"{res[0]} {res[1]}"
        valor_db = 1 if estado == 'Activar' else 0

        async with interaction.client.db.execute("UPDATE usuarios SET busqueda_captura = ? WHERE id_usuario = ? AND slot = ?", (valor_db, ciudadano.id, slot)):
            pass
        await interaction.client.db.commit()

        async with interaction.client.db.execute("SELECT roblox_user, nacionalidad, fecha_nacimiento, imagen_url FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            r_user_row = await cur.fetchone()
        roblox_user = r_user_row[0] if r_user_row and r_user_row[0] else "Desconocido"
        nacionalidad = r_user_row[1] if r_user_row and r_user_row[1] else "Desconocida"
        fecha_nacimiento = r_user_row[2] if r_user_row and r_user_row[2] else "Desconocida"
        imagen_url = r_user_row[3] if r_user_row and len(r_user_row) > 3 and r_user_row[3] else None

        if estado == 'Activar':
            tipo_embed = "error"
            titulo = f"{Emojis.POLICIA} ORDEN DE BÚSQUEDA Y CAPTURA EMITIDA"
            desc = (
                f"El Ministerio de Seguridad de la Nación ha emitido una orden de búsqueda y captura en todo el territorio nacional.\n"
                f"**Expediente del Prófugo:**\n"
                f"• **Nombre Registrado:** **{nombre_pj}** (Slot **{slot}**)\n"
                f"• **Cargos Formales:** **{motivo}**\n\n"
                f"{Emojis.ADVERTENCIA} *Se comunica a todos los ciudadanos la orden y se realiza un llamado a todo aquel que pueda aportar información a las autoridades de seguridad.*"
            )
        else:
            tipo_embed = "exito"
            titulo = f"{Emojis.EXITO} ORDEN DE CAPTURA REVOCADA"
            desc = (
                f"El Ministerio de Seguridad de la Nación ha levantado la orden de búsqueda sobre este ciudadano.\n"
                f"**Expediente de Resolución:**\n"
                f"• **Nombre Registrado:** **{nombre_pj}** (Slot **{slot}**)\n"
                f"• **Motivo de Cancelación:** **{motivo}**\n\n"
                f"{Emojis.EXITO} *La alerta en el territorio nacional fue retirada, el ciudadano se encuentra bajo el mando de las autoridades correspondientes.*"
            )

        embed = construir_embed(
            tipo=tipo_embed,
            titulo=titulo,
            descripcion=desc
        )

        archivo_imagen = None
        try:
            avatar_bytes = None
            if imagen_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(imagen_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                avatar_bytes = await resp.read()
                except Exception as e:
                    logger.warning(f"Error descargando imagen del DNI: {e}")

            if not avatar_bytes:
                avatar_bytes, _ = await obtener_avatar_roblox(roblox_user)

            buffer = await asyncio.to_thread(
                generar_cartel_busqueda,
                nombre_pj,
                nacionalidad,
                fecha_nacimiento,
                motivo,
                estado,
                avatar_bytes
            )
            archivo_imagen = discord.File(fp=buffer, filename="busqueda.png")
        except Exception as e:
            logger.error(f"Error generando imagen de búsqueda: {e}")

        vista = discord.ui.LayoutView()

        texto_mencion = ciudadano.mention
        if estado == 'Activar':
            menciones_roles = "".join([f"<@&{r_id}>" for r_id in ROLES_ALERTA_BUSQUEDA])
            texto_mencion = f"{menciones_roles} {ciudadano.mention}"

        vista.add_item(discord.ui.TextDisplay(texto_mencion))
        vista.add_item(embed)

        if archivo_imagen:
            await interaction.followup.send(view=vista, file=archivo_imagen)
        else:
            await interaction.followup.send(view=vista)

    # ==========================================
    #  SISTEMA DE VEHÍCULOS EXTENDIDO
    # ==========================================

    @app_commands.command(name="vehiculo_antecedente", description="POLICIA: Registrar antecedente sobre un vehículo.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        patente="Patente del vehículo",
        tipo_incidente="Tipo de incidente",
        descripcion="Descripción detallada del incidente"
    )
    async def vehiculo_antecedente(
        self,
        interaction: discord.Interaction,
        patente: str,
        tipo_incidente: Literal[
            'Infracción de tránsito', 'Conducción temeraria', 'Accidente',
            'Fuga', 'Vehículo involucrado en delito', 'Transporte ilegal',
            'Modificación ilegal', 'Documentación falsa', 'Otro'
        ],
        descripcion: str
    ):
        await interaction.response.defer(ephemeral=True)

        patente = patente.upper().strip()

        # Verificar que el vehículo existe
        async with interaction.client.db.execute(
            "SELECT id_usuario, slot, modelo FROM vehiculos WHERE patente = ?",
            (patente,)
        ) as cur:
            vehiculo = await cur.fetchone()

        if not vehiculo:
            desc = f"Vehículo no encontrado.\n**Motivo:** No existe un vehículo registrado con la patente **{patente}**."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        id_usuario, slot, modelo = vehiculo

        # Obtener datos del oficial
        char_oficial = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        nom_oficial = f"{char_oficial[0]} {char_oficial[1]}" if char_oficial else interaction.user.display_name

        # Registrar antecedente
        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        async with interaction.client.db.execute(
            """INSERT INTO vehiculos_antecedentes (
                patente, tipo_incidente, descripcion, oficial_id, oficial_nombre, fecha
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (patente, tipo_incidente, descripcion, interaction.user.id, nom_oficial, fecha_actual)
        ) as cur:
            id_antecedente = cur.lastrowid

        await interaction.client.db.commit()

        desc = (
            f"Se ha registrado un antecedente vehicular en el sistema.\n"
            f"**Detalles del Registro:**\n"
            f"• **ID Antecedente:** #{id_antecedente}\n"
            f"• **Patente:** **{patente}**\n"
            f"• **Modelo:** {modelo}\n"
            f"• **Tipo de Incidente:** {tipo_incidente}\n"
            f"• **Oficial:** {nom_oficial}\n"
            f"• **Fecha:** {fecha_actual}\n\n"
            f"**Descripción:**\n{descripcion}"
        )

        embed = construir_embed(
            tipo="policial",
            titulo=f"{Emojis.DOCUMENTO} ANTECEDENTE VEHICULAR REGISTRADO",
            descripcion=desc
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    @app_commands.command(name="vehiculo_consultar", description="POLICIA: Consultar antecedentes e historial de un vehículo.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(patente="Patente del vehículo a consultar")
    async def vehiculo_consultar(self, interaction: discord.Interaction, patente: str):
        await interaction.response.defer(ephemeral=True)

        patente = patente.upper().strip()

        # Verificar vehículo
        async with interaction.client.db.execute(
            "SELECT id_usuario, slot, modelo FROM vehiculos WHERE patente = ?",
            (patente,)
        ) as cur:
            vehiculo = await cur.fetchone()

        if not vehiculo:
            desc = f"Vehículo no encontrado.\n**Motivo:** No existe un vehículo registrado con la patente **{patente}**."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        id_usuario, slot, modelo = vehiculo

        # Obtener propietario actual
        async with interaction.client.db.execute(
            "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (id_usuario, slot)
        ) as cur:
            propietario = await cur.fetchone()

        propietario_nombre = f"{propietario[0]} {propietario[1]}" if propietario else "Desconocido"

        # Obtener antecedentes
        async with interaction.client.db.execute(
            """SELECT tipo_incidente, fecha, oficial_nombre 
               FROM vehiculos_antecedentes WHERE patente = ? 
               ORDER BY fecha DESC LIMIT 5""",
            (patente,)
        ) as cur:
            antecedentes = await cur.fetchall()

        # Verificar si está robado
        async with interaction.client.db.execute(
            """SELECT estado, fecha_robo, propietario_nombre 
               FROM vehiculos_robados WHERE patente = ?""",
            (patente,)
        ) as cur:
            robo = await cur.fetchone()

        # Obtener historial de propietarios
        async with interaction.client.db.execute(
            """SELECT nombre_anterior, nombre_nuevo, fecha_transferencia, precio_venta
               FROM vehiculos_historial_propietarios WHERE patente = ? 
               ORDER BY fecha_transferencia DESC LIMIT 3""",
            (patente,)
        ) as cur:
            historial = await cur.fetchall()

        # Construir embed
        campos = [
            ("Patente", f"**{patente}**", True),
            ("Modelo", modelo, True),
            ("Propietario Actual", propietario_nombre, False),
        ]

        # Estado de robo
        if robo and robo[0] == 'ACTIVO':
            campos.append(("⚠️ ALERTA DE ROBO", f"Vehículo reportado como ROBADO desde {robo[1]}\nPropietario legítimo: {robo[2]}", False))

        # Antecedentes
        if antecedentes:
            antec_texto = "\n".join([
                f"• **{ant[0]}** - {ant[1]} (Oficial: {ant[2]})"
                for ant in antecedentes
            ])
            campos.append(("Antecedentes Recientes", antec_texto, False))
        else:
            campos.append(("Antecedentes", "Sin antecedentes registrados", False))

        # Historial de propietarios
        if historial:
            hist_texto = "\n".join([
                f"• {h[0]} → {h[1]} ({h[2]}) - {utils.format_money(h[3]) if h[3] > 0 else 'Sin registro de precio'}"
                for h in historial
            ])
            campos.append(("Historial de Transferencias", hist_texto, False))

        desc = f"Consulta vehicular completa del sistema de registro nacional."

        embed = construir_embed(
            tipo="policial",
            titulo=f"🚗 CONSULTA VEHICULAR - {patente}",
            descripcion=desc,
            campos=campos
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    @app_commands.command(name="vehiculo_robo", description="POLICIA: Registrar o recuperar un vehículo robado.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        patente="Patente del vehículo",
        accion="Acción a realizar",
        descripcion="Descripción del robo o recuperación"
    )
    async def vehiculo_robo(
        self,
        interaction: discord.Interaction,
        patente: str,
        accion: Literal['REPORTAR_ROBO', 'RECUPERAR'],
        descripcion: str
    ):
        await interaction.response.defer(ephemeral=True)

        patente = patente.upper().strip()

        # Verificar vehículo
        async with interaction.client.db.execute(
            "SELECT id_usuario, slot, modelo FROM vehiculos WHERE patente = ?",
            (patente,)
        ) as cur:
            vehiculo = await cur.fetchone()

        if not vehiculo:
            desc = f"Vehículo no encontrado.\n**Motivo:** No existe un vehículo registrado con la patente **{patente}**."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        id_usuario, slot, modelo = vehiculo

        # Obtener propietario
        async with interaction.client.db.execute(
            "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (id_usuario, slot)
        ) as cur:
            propietario = await cur.fetchone()

        propietario_nombre = f"{propietario[0]} {propietario[1]}" if propietario else "Desconocido"

        # Obtener datos del oficial
        char_oficial = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        nom_oficial = f"{char_oficial[0]} {char_oficial[1]}" if char_oficial else interaction.user.display_name

        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if accion == 'REPORTAR_ROBO':
            # Verificar si ya está reportado como robado
            async with interaction.client.db.execute(
                "SELECT estado FROM vehiculos_robados WHERE patente = ?",
                (patente,)
            ) as cur:
                robo_existente = await cur.fetchone()

            if robo_existente and robo_existente[0] == 'ACTIVO':
                desc = f"Operación denegada.\n**Motivo:** El vehículo **{patente}** ya figura como robado en el sistema."
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )

            # Registrar robo
            async with interaction.client.db.execute(
                """INSERT OR REPLACE INTO vehiculos_robados (
                    patente, modelo, propietario_id, propietario_nombre, fecha_robo,
                    descripcion, oficial_registro_id, oficial_registro_nombre, estado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO')""",
                (patente, modelo, id_usuario, propietario_nombre, fecha_actual,
                 descripcion, interaction.user.id, nom_oficial)
            ) as cur:
                id_robo = cur.lastrowid

            await interaction.client.db.commit()

            desc = (
                f"Se ha registrado un vehículo como robado en el sistema nacional.\n"
                f"**Detalles del Reporte:**\n"
                f"• **ID Reporte:** #{id_robo}\n"
                f"• **Patente:** **{patente}**\n"
                f"• **Modelo:** {modelo}\n"
                f"• **Propietario Legítimo:** {propietario_nombre}\n"
                f"• **Oficial:** {nom_oficial}\n"
                f"• **Fecha de Robo:** {fecha_actual}\n\n"
                f"**Descripción:**\n{descripcion}\n\n"
                f"{Emojis.ADVERTENCIA} *Todos los agentes están alertados. El vehículo será incautado si se localiza.*"
            )

            embed = construir_embed(
                tipo="error",
                titulo=f"🚨 VEHÍCULO REPORTADO COMO ROBADO",
                descripcion=desc
            )

        else:  # RECUPERAR
            # Verificar que está reportado como robado
            async with interaction.client.db.execute(
                "SELECT id_robo, estado FROM vehiculos_robados WHERE patente = ?",
                (patente,)
            ) as cur:
                robo = await cur.fetchone()

            if not robo or robo[1] != 'ACTIVO':
                desc = f"Operación denegada.\n**Motivo:** El vehículo **{patente}** no figura como robado activamente en el sistema."
                return await interaction.followup.send(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                    ephemeral=True
                )

            id_robo = robo[0]

            # Actualizar como recuperado
            async with interaction.client.db.execute(
                """UPDATE vehiculos_robados SET 
                   estado = 'RECUPERADO',
                   fecha_recuperacion = ?,
                   oficial_recuperacion_id = ?,
                   oficial_recuperacion_nombre = ?
                   WHERE id_robo = ?""",
                (fecha_actual, interaction.user.id, nom_oficial, id_robo)
            ):
                pass

            await interaction.client.db.commit()

            desc = (
                f"El vehículo ha sido recuperado exitosamente.\n"
                f"**Detalles de la Recuperación:**\n"
                f"• **Patente:** **{patente}**\n"
                f"• **Modelo:** {modelo}\n"
                f"• **Propietario Legítimo:** {propietario_nombre}\n"
                f"• **Oficial de Recuperación:** {nom_oficial}\n"
                f"• **Fecha de Recuperación:** {fecha_actual}\n\n"
                f"**Descripción:**\n{descripcion}\n\n"
                f"{Emojis.EXITO} *El estado de robo ha sido levantado. El propietario puede ser contactado para devolución.*"
            )

            embed = construir_embed(
                tipo="exito",
                titulo=f"✅ VEHÍCULO RECUPERADO",
                descripcion=desc
            )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    @app_commands.command(name="vehiculo_transferir", description="ADMIN: Registrar transferencia de propiedad de un vehículo.")
    @utils.tiene_permiso(*utils.PERMISO_ADMIN)
    @app_commands.describe(
        patente="Patente del vehículo",
        nuevo_propietario="Nuevo propietario del vehículo",
        nuevo_slot="Slot del nuevo propietario",
        precio_venta="Precio de venta (opcional)"
    )
    async def vehiculo_transferir(
        self,
        interaction: discord.Interaction,
        patente: str,
        nuevo_propietario: discord.Member,
        nuevo_slot: Literal[1, 2],
        precio_venta: int = 0
    ):
        await interaction.response.defer(ephemeral=True)

        patente = patente.upper().strip()

        # Verificar vehículo
        async with interaction.client.db.execute(
            "SELECT id_usuario, slot, modelo FROM vehiculos WHERE patente = ?",
            (patente,)
        ) as cur:
            vehiculo = await cur.fetchone()

        if not vehiculo:
            desc = f"Vehículo no encontrado.\n**Motivo:** No existe un vehículo registrado con la patente **{patente}**."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        id_usuario_anterior, slot_anterior, modelo = vehiculo

        # Obtener datos del propietario anterior
        async with interaction.client.db.execute(
            "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (id_usuario_anterior, slot_anterior)
        ) as cur:
            prop_anterior = await cur.fetchone()

        nombre_anterior = f"{prop_anterior[0]} {prop_anterior[1]}" if prop_anterior else "Desconocido"

        # Obtener datos del nuevo propietario
        async with interaction.client.db.execute(
            "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (nuevo_propietario.id, nuevo_slot)
        ) as cur:
            prop_nuevo = await cur.fetchone()

        if not prop_nuevo:
            desc = f"Operación denegada.\n**Motivo:** El nuevo propietario {nuevo_propietario.mention} no tiene un personaje en el Slot **{nuevo_slot}**."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        nombre_nuevo = f"{prop_nuevo[0]} {prop_nuevo[1]}"

        # Registrar en historial
        fecha_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        async with interaction.client.db.execute(
            """INSERT INTO vehiculos_historial_propietarios (
                patente, id_usuario_anterior, nombre_anterior, id_usuario_nuevo, 
                nombre_nuevo, fecha_transferencia, precio_venta
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (patente, id_usuario_anterior, nombre_anterior, nuevo_propietario.id, 
             nombre_nuevo, fecha_actual, precio_venta)
        ):
            pass

        # Actualizar propietario del vehículo
        async with interaction.client.db.execute(
            "UPDATE vehiculos SET id_usuario = ?, slot = ? WHERE patente = ?",
            (nuevo_propietario.id, nuevo_slot, patente)
        ):
            pass

        await interaction.client.db.commit()

        desc = (
            f"La transferencia vehicular ha sido registrada en el sistema.\n"
            f"**Detalles de la Transferencia:**\n"
            f"• **Patente:** **{patente}**\n"
            f"• **Modelo:** {modelo}\n"
            f"• **Propietario Anterior:** {nombre_anterior}\n"
            f"• **Nuevo Propietario:** {nombre_nuevo} (Slot **{nuevo_slot}**)\n"
            f"• **Fecha de Transferencia:** {fecha_actual}\n"
        )

        if precio_venta > 0:
            desc += f"• **Precio de Venta:** {utils.format_money(precio_venta)}\n"

        embed = construir_embed(
            tipo="policial",
            titulo=f"📋 TRANSFERENCIA VEHICULAR REGISTRADA",
            descripcion=desc
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    # ==========================================
    #  COMANDOS DE CONSULTA Y LISTADOS
    # ==========================================

    @app_commands.command(name="ver_arrestos", description="POLICIA: Ver historial completo de arrestos de un ciudadano.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(dni_ciudadano="DNI del ciudadano a consultar")
    async def ver_arrestos(self, interaction: discord.Interaction, dni_ciudadano: str):
        await interaction.response.defer(ephemeral=True)

        # Buscar ciudadano por DNI
        ciudadano_data = await buscar_usuario_por_dni(interaction.client.db, dni_ciudadano)
        if not ciudadano_data:
            desc = f"Ciudadano no encontrado.\n**Motivo:** No existe un ciudadano con DNI **{dni_ciudadano}** en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        usuario_id, slot, nombres, apellidos = ciudadano_data
        nombre_completo = f"{nombres} {apellidos}"

        # Obtener TODOS los arrestos del historial (ordenados por más reciente)
        async with interaction.client.db.execute(
            """SELECT numero_arresto, fecha_arresto, fecha_liberacion, articulos, 
               multa_total, gravedad, oficiales_a_cargo, es_ck, estado
               FROM historial_arrestos WHERE id_usuario = ?
               ORDER BY fecha_arresto DESC""",
            (usuario_id,)
        ) as cur:
            todos_arrestos = await cur.fetchall()

        if not todos_arrestos:
            desc = f"**{nombre_completo}** (DNI: {dni_ciudadano}, Slot {slot})\n\nNo hay registros de arrestos en el historial de este ciudadano."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("exito", titulo="📋 HISTORIAL DE ARRESTOS", descripcion=desc)),
                ephemeral=True
            )

        # Crear una página por cada arresto (1 arresto = 1 página)
        ahora = datetime.now().timestamp()
        paginas = []
        
        for idx, arr in enumerate(todos_arrestos, 1):
            num_arr, fecha_arr, fecha_lib, arts, multa, grav, oficiales, es_ck, estado_hist = arr
            
            # Valores por defecto para arrestos antiguos/legacy
            num_arr = num_arr if num_arr else 'LEGACY'
            arts = arts if arts else 'No registrado'
            multa = multa if multa else 0
            oficiales = oficiales if oficiales else 'No registrado'
            grav = grav if grav else 'medio'
            es_ck = es_ck if es_ck else 0
            
            # Determinar estado del arresto (usar estado del historial o calcular)
            if estado_hist == 'ACTIVO' and fecha_lib > ahora:
                estado = "🔴 ACTIVO"
                if es_ck:
                    tiempo_info = "**Condena:** Cadena Perpetua (CK)"
                else:
                    ts = int(fecha_lib)
                    tiempo_info = f"**Liberación Programada:** <t:{ts}:R> (<t:{ts}:f>)"
            else:
                estado = "✅ CUMPLIDO"
                ts = int(fecha_lib)
                tiempo_info = f"**Fecha de Cumplimiento:** <t:{ts}:d>"
            
            # Formatear fecha de arresto
            ts_arresto = int(fecha_arr)
            fecha_arresto_txt = f"<t:{ts_arresto}:d>"
            
            # Procesar artículos aplicados
            campos = []
            if arts and arts != 'No registrado':
                try:
                    resultado = codigo_penal.procesar_articulos(arts, grav)
                    if 'error' not in resultado:
                        detalles_articulos = resultado['detalles']
                        for det in detalles_articulos:
                            tiempo_txt = f"{det['tiempo_minutos']} min OOC" if det['tiempo_minutos'] != 'CK' else 'CK'
                            campos.append((
                                f"{det['codigo']} - {utils.format_money(det['multa'])}",
                                f"{det['infraccion']}\n**Sanción:** {det['sancion']}\n**Tiempo:** {tiempo_txt}",
                                False
                            ))
                    else:
                        # Si hay error al procesar, mostrar artículos como texto
                        campos = [("Artículos Aplicados", arts, False)]
                except Exception as e:
                    # Si falla el procesamiento, mostrar como texto simple
                    campos = [("Artículos Aplicados", arts, False)]
            else:
                campos = [("Artículos Aplicados", "No registrado", False)]
            
            desc = (
                f"**Ciudadano:** {nombre_completo}\n"
                f"**DNI:** {dni_ciudadano} (Slot {slot})\n"
                f"**Estado:** {estado}\n"
                f"**Número de Arresto:** #{num_arr}\n"
                f"**Fecha de Arresto:** {fecha_arresto_txt}\n"
                f"**Gravedad:** {grav.upper()}\n"
                f"**Multa Total:** {utils.format_money(multa)}\n"
                f"**Oficiales a Cargo:** {oficiales}\n"
                f"{tiempo_info}\n\n"
                f"**Artículos del Código Penal:**"
            )
            
            if len(todos_arrestos) > 1:
                desc += f"\n\n*Arresto {idx} de {len(todos_arrestos)}*"
            
            tipo_embed = "error" if (estado_hist == 'ACTIVO' and fecha_lib > ahora) else "policial"
            
            embed = construir_embed(
                tipo=tipo_embed,
                titulo=f"📋 ARRESTO #{num_arr}",
                descripcion=desc,
                campos=campos
            )
            paginas.append(embed)
        
        # Si solo hay un arresto, enviar directamente
        if len(paginas) == 1:
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(paginas[0]),
                ephemeral=True
            )
        
        # Si hay múltiples arrestos, usar paginación (1 arresto por página)
        view = CodigoPenalPaginationView(interaction, paginas, 'arrestos')
        mensaje = await interaction.followup.send(view=view, ephemeral=True)
        view._message = mensaje

    @app_commands.command(name="listar_denuncias", description="POLICIA: Ver lista de denuncias según estado.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        estado="Filtrar por estado de denuncia",
        prioridad="Filtrar por nivel de prioridad (opcional)"
    )
    async def listar_denuncias(
        self,
        interaction: discord.Interaction,
        estado: Literal['PENDIENTE', 'EN_INVESTIGACION', 'RESUELTA', 'ARCHIVADA', 'DERIVADA', 'TODAS'] = 'PENDIENTE',
        prioridad: Literal['BAJA', 'MEDIA', 'ALTA', 'URGENTE', 'TODAS'] = 'TODAS'
    ):
        await interaction.response.defer(ephemeral=True)

        # Construir query según filtros
        query = "SELECT numero_denuncia, tipo_denuncia, denunciante_nombre, denunciado_nombre, fecha_denuncia, prioridad, estado FROM denuncias"
        params = []
        
        condiciones = []
        if estado != 'TODAS':
            condiciones.append("estado = ?")
            params.append(estado)
        
        if prioridad != 'TODAS':
            condiciones.append("prioridad = ?")
            params.append(prioridad)
        
        if condiciones:
            query += " WHERE " + " AND ".join(condiciones)
        
        query += " ORDER BY fecha_denuncia DESC LIMIT 10"

        async with interaction.client.db.execute(query, tuple(params)) as cur:
            denuncias = await cur.fetchall()

        if not denuncias:
            desc = f"No se encontraron denuncias con los filtros aplicados.\n**Estado:** {estado}\n**Prioridad:** {prioridad}"
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("advertencia", descripcion=desc)),
                ephemeral=True
            )

        campos = []
        for den in denuncias:
            numero, tipo, denunciante, denunciado, fecha, prior, est = den
            
            info = (
                f"**Tipo:** {tipo}\n"
                f"**Denunciante:** {denunciante}\n"
                f"**Denunciado:** {denunciado if denunciado else 'No especificado'}\n"
                f"**Fecha:** {fecha}\n"
                f"**Estado:** {est} | **Prioridad:** {prior}"
            )
            
            campos.append((f"Denuncia #{numero}", info, False))

        filtros_txt = f"**Filtros:** Estado: {estado} | Prioridad: {prioridad}"
        desc = f"{filtros_txt}\n**Total encontradas:** {len(denuncias)}\n\n*Mostrando últimas 10 denuncias.*"

        embed = construir_embed(
            tipo="policial",
            titulo=f"{Emojis.DOCUMENTO} LISTADO DE DENUNCIAS",
            descripcion=desc,
            campos=campos
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    @app_commands.command(name="listar_buscados", description="POLICIA: Ver lista de órdenes de búsqueda activas.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    async def listar_buscados(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Obtener búsquedas activas
        async with interaction.client.db.execute(
            """SELECT numero_orden, id_usuario, slot, motivo, oficial_emisor_nombre, fecha_emision
               FROM busqueda_captura WHERE estado = 'ACTIVA'
               ORDER BY fecha_emision DESC LIMIT 10""",
        ) as cur:
            buscados = await cur.fetchall()

        if not buscados:
            desc = "No hay órdenes de búsqueda y captura activas en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)),
                ephemeral=True
            )

        campos = []
        for bus in buscados:
            numero_orden, id_usuario, slot, motivo, oficial, fecha = bus
            
            # Obtener nombre del prófugo
            async with interaction.client.db.execute(
                "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
                (id_usuario, slot)
            ) as cur_nom:
                nombre_row = await cur_nom.fetchone()
            
            if nombre_row:
                nombre_profugo = f"{nombre_row[0]} {nombre_row[1]}"
            else:
                nombre_profugo = "Desconocido"
            
            # Obtener usuario de Discord
            member = interaction.guild.get_member(id_usuario) if interaction.guild else None
            mencion = member.mention if member else f"ID: {id_usuario}"
            
            # Contar avistamientos
            async with interaction.client.db.execute(
                "SELECT COUNT(*) FROM busqueda_avistamientos WHERE id_busqueda = (SELECT id_busqueda FROM busqueda_captura WHERE numero_orden = ?)",
                (numero_orden,)
            ) as cur_avist:
                num_avistamientos = (await cur_avist.fetchone())[0]
            
            info = (
                f"**Prófugo:** {nombre_profugo} (Slot {slot}) | {mencion}\n"
                f"**Motivo:** {motivo}\n"
                f"**Emisor:** {oficial}\n"
                f"**Fecha Emisión:** {fecha}\n"
                f"**Avistamientos:** {num_avistamientos}"
            )
            
            campos.append((f"Orden {numero_orden}", info, False))

        desc = f"**Total de Prófugos Activos:** {len(buscados)}\n\n{Emojis.ADVERTENCIA} *Si avistas a alguno de estos individuos, usa `/avistar` para reportar.*"

        embed = construir_embed(
            tipo="error",
            titulo=f"{Emojis.BUSCADO} REGISTRO DE PRÓFUGOS ACTIVOS",
            descripcion=desc,
            campos=campos
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    @app_commands.command(name="expediente", description="POLICIA: Consultar expediente completo de un ciudadano.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        ciudadano="Usuario de Discord del ciudadano",
        slot="Slot del personaje (1 o 2)"
    )
    async def expediente(self, interaction: discord.Interaction, ciudadano: discord.Member, slot: Literal[1, 2]):
        await interaction.response.defer(ephemeral=True)

        # Obtener datos del ciudadano
        async with interaction.client.db.execute(
            "SELECT nombres, apellidos, nro_doc, fecha_nacimiento, nacionalidad FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (ciudadano.id, slot)
        ) as cur:
            datos = await cur.fetchone()

        if not datos:
            desc = f"Expediente no encontrado.\n**Motivo:** El usuario {ciudadano.mention} no tiene un personaje registrado en el Slot **{slot}**."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        nombres, apellidos, dni, fecha_nac, nacionalidad = datos
        nombre_completo = f"{nombres} {apellidos}"
        fecha_nac = fecha_nac if fecha_nac else "Desconocida"
        nacionalidad = nacionalidad if nacionalidad else "Desconocida"

        # Información básica
        campos = [
            ("Nombre Completo", nombre_completo, True),
            ("Documento (DNI)", dni, True),
            ("Nacionalidad", nacionalidad, True),
            ("Fecha de Nacimiento", fecha_nac, True),
            ("Discord", ciudadano.mention, True),
            ("Slot", str(slot), True),
        ]

        # Verificar si está arrestado
        ahora = datetime.now().timestamp()
        async with interaction.client.db.execute(
            "SELECT fecha_liberacion, numero_arresto, articulos, multa_total, es_ck FROM arrestos WHERE id_usuario = ? AND fecha_liberacion > ?",
            (ciudadano.id, ahora)
        ) as cur:
            arresto_actual = await cur.fetchone()

        if arresto_actual:
            fecha_lib, num_arr, arts, multa, es_ck = arresto_actual
            if es_ck:
                campos.append(("⚠️ ESTADO LEGAL", f"**PRIVADO DE LIBERTAD (CADENA PERPETUA)**\nArresto: {num_arr}", False))
            else:
                ts = int(fecha_lib)
                campos.append(("⚠️ ESTADO LEGAL", f"**PRIVADO DE LIBERTAD**\nLiberación: <t:{ts}:R>\nArresto: {num_arr}", False))

        # Verificar órdenes de búsqueda ACTIVAS
        async with interaction.client.db.execute(
            "SELECT numero_orden, motivo FROM busqueda_captura WHERE id_usuario = ? AND slot = ? AND estado = 'ACTIVA' ORDER BY fecha_emision DESC LIMIT 1",
            (ciudadano.id, slot)
        ) as cur:
            busqueda = await cur.fetchone()

        if busqueda:
            campos.append(("🚨 ORDEN DE BÚSQUEDA Y CAPTURA", f"**PRÓFUGO - BÚSQUEDA ACTIVA**\nOrden: {busqueda[0]}\nMotivo: {busqueda[1]}", False))
        else:
            # Verificar si tiene búsqueda no activa
            async with interaction.client.db.execute(
                "SELECT estado FROM busqueda_captura WHERE id_usuario = ? AND slot = ? ORDER BY fecha_emision DESC LIMIT 1",
                (ciudadano.id, slot)
            ) as cur:
                busqueda_hist = await cur.fetchone()
            
            if busqueda_hist:
                campos.append(("🔒 BÚSQUEDA Y CAPTURA", f"Sin órdenes activas (Última: {busqueda_hist[0]})", False))
            else:
                campos.append(("✅ BÚSQUEDA Y CAPTURA", "Sin órdenes registradas", False))

        # Antecedentes penales
        async with interaction.client.db.execute(
            "SELECT delito, fecha FROM antecedentes WHERE id_usuario = ? AND slot = ? ORDER BY fecha DESC LIMIT 5",
            (ciudadano.id, slot)
        ) as cur:
            antecedentes = await cur.fetchall()

        if antecedentes:
            antec_texto = "\n".join([f"• {ant[0]} ({ant[1]})" for ant in antecedentes])
            campos.append(("Antecedentes Penales", antec_texto, False))
        else:
            campos.append(("Antecedentes Penales", "Sin antecedentes registrados", False))

        # Multas pendientes
        async with interaction.client.db.execute(
            "SELECT COUNT(*), SUM(monto) FROM multas WHERE id_usuario = ? AND slot = ? AND pagada = 0",
            (ciudadano.id, slot)
        ) as cur:
            multas_info = await cur.fetchone()

        if multas_info and multas_info[0] > 0:
            campos.append(("💰 Multas Pendientes", f"**{multas_info[0]}** multa(s) sin pagar\nTotal adeudado: **{utils.format_money(multas_info[1])}**", False))
        else:
            campos.append(("💰 Multas Pendientes", "Sin multas pendientes", False))

        # Vehículos registrados
        async with interaction.client.db.execute(
            "SELECT modelo, patente FROM vehiculos WHERE id_usuario = ? AND slot = ?",
            (ciudadano.id, slot)
        ) as cur:
            vehiculos = await cur.fetchall()

        if vehiculos:
            vehiculos_texto = "\n".join([f"• {modelo} - **{patente}**" for modelo, patente in vehiculos])
            campos.append(("🚗 Vehículos Registrados", vehiculos_texto, False))
        else:
            campos.append(("🚗 Vehículos Registrados", "Sin vehículos registrados", False))

        desc = f"Expediente policial completo del ciudadano."

        embed = construir_embed(
            tipo="policial",
            titulo=f"📋 EXPEDIENTE POLICIAL - {nombre_completo}",
            descripcion=desc,
            campos=campos,
            thumbnail=ciudadano.display_avatar.url
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    @app_commands.command(name="pay_multas", description="Paga multas de tu personaje con un menú de selección.")
    @utils.tiene_permiso(*utils.PERMISO_CIVIL)
    @app_commands.describe(slot="Slot del personaje (1 o 2)")
    async def pay_multas(self, interaction: discord.Interaction, slot: Literal[1, 2]):
        await interaction.response.defer(ephemeral=True)

        # Obtener personaje del usuario que ejecuta el comando
        ciudadano = interaction.user

        # Verificar que el personaje existe
        async with interaction.client.db.execute(
            "SELECT nombres, apellidos FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (ciudadano.id, slot)
        ) as cur:
            personaje = await cur.fetchone()

        if not personaje:
            desc = f"Personaje no encontrado.\n**Motivo:** No tienes un personaje registrado en el Slot **{slot}**."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        nombre_personaje = f"{personaje[0]} {personaje[1]}"

        # Buscar multas pendientes del slot especificado
        async with interaction.client.db.execute(
            "SELECT id_multa, motivo, monto, fecha FROM multas WHERE id_usuario = ? AND slot = ? AND pagada = 0 ORDER BY fecha DESC",
            (ciudadano.id, slot)
        ) as cur:
            multas = await cur.fetchall()

        if not multas:
            desc = f"{Emojis.EXITO} **{nombre_personaje}** (Slot {slot}) no tiene multas pendientes.\n\nTu historial está limpio."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)),
                ephemeral=True
            )

        # Crear vista con select menu (reutilizamos SeleccionMultaView)
        view = SeleccionMultaView(interaction, multas, slot)
        await interaction.followup.send(view=view, ephemeral=True)

    # ==========================================
    #  SISTEMA DE DENUNCIAS
    # ==========================================

    @app_commands.command(name="denuncia", description="POLICIA: Registrar una denuncia ciudadana.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        dni_denunciante="DNI del ciudadano que realiza la denuncia (ej: 12345678)",
        tipo_denuncia="Tipo de denuncia",
        descripcion="Descripción detallada de los hechos",
        dni_denunciado="DNI del ciudadano denunciado (opcional si no se conoce)",
        ubicacion="Ubicación de los hechos (opcional)",
        fecha_hechos="Fecha de los hechos en formato DD/MM/YYYY (opcional)",
        prioridad="Nivel de prioridad de la denuncia"
    )
    async def denuncia(
        self,
        interaction: discord.Interaction,
        dni_denunciante: str,
        tipo_denuncia: Literal[
            'Robo', 'Asalto', 'Agresión', 'Amenazas', 'Extorsión', 
            'Fraude', 'Estafa', 'Vandalismo', 'Secuestro', 'Homicidio',
            'Tráfico de drogas', 'Tráfico de armas', 'Corrupción', 
            'Abuso de autoridad', 'Violencia doméstica', 'Otro'
        ],
        descripcion: str,
        prioridad: Literal['BAJA', 'MEDIA', 'ALTA', 'URGENTE'] = 'MEDIA',
        dni_denunciado: str = None,
        ubicacion: str = None,
        fecha_hechos: str = None
    ):
        await interaction.response.defer(ephemeral=True)

        # Buscar denunciante por DNI
        denunciante_data = await buscar_usuario_por_dni(interaction.client.db, dni_denunciante)
        if not denunciante_data:
            desc = f"Solicitud denegada.\n**Motivo:** No se encontró ningún ciudadano con DNI **{dni_denunciante}** en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )
        
        denunciante_id, denunciante_slot, denunciante_nombres, denunciante_apellidos = denunciante_data
        nombre_denunciante = f"{denunciante_nombres} {denunciante_apellidos}"

        # Obtener usuario de Discord del denunciante
        denunciante = interaction.guild.get_member(denunciante_id) if interaction.guild else None
        if not denunciante:
            try:
                denunciante = await interaction.guild.fetch_member(denunciante_id)
            except discord.NotFound:
                pass

        # Obtener datos del oficial receptor
        char_oficial = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        nom_oficial = f"{char_oficial[0]} {char_oficial[1]}" if char_oficial else interaction.user.display_name

        # Procesar denunciado si existe
        denunciado_id = None
        denunciado_nombre = None
        denunciado = None
        if dni_denunciado:
            denunciado_data = await buscar_usuario_por_dni(interaction.client.db, dni_denunciado)
            if denunciado_data:
                denunciado_id = denunciado_data[0]
                denunciado_nombre = f"{denunciado_data[2]} {denunciado_data[3]}"
                # Obtener usuario de Discord del denunciado
                denunciado = interaction.guild.get_member(denunciado_id) if interaction.guild else None
                if not denunciado:
                    try:
                        denunciado = await interaction.guild.fetch_member(denunciado_id)
                    except discord.NotFound:
                        pass
            else:
                desc = f"Advertencia: No se encontró ciudadano con DNI **{dni_denunciado}**. Se registrará la denuncia sin datos del denunciado."
                denunciado_nombre = f"DNI: {dni_denunciado} (No encontrado)"

        # Generar número de denuncia
        numero_denuncia = utils.generar_numero_denuncia()
        fecha_denuncia = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Registrar en base de datos
        async with interaction.client.db.execute(
            """INSERT INTO denuncias (
                numero_denuncia, denunciante_id, denunciante_nombre, denunciado_id, denunciado_nombre,
                tipo_denuncia, descripcion, ubicacion, fecha_hechos, fecha_denuncia,
                oficial_receptor_id, oficial_receptor_nombre, estado, prioridad
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE', ?)""",
            (numero_denuncia, denunciante_id, nombre_denunciante, denunciado_id, denunciado_nombre,
             tipo_denuncia, descripcion, ubicacion, fecha_hechos, fecha_denuncia,
             interaction.user.id, nom_oficial, prioridad)
        ) as cur:
            id_denuncia = cur.lastrowid

        # Registrar primer seguimiento (apertura)
        async with interaction.client.db.execute(
            """INSERT INTO denuncias_seguimiento (
                id_denuncia, oficial_id, oficial_nombre, accion, descripcion, fecha
            ) VALUES (?, ?, ?, 'APERTURA', 'Denuncia registrada en el sistema', ?)""",
            (id_denuncia, interaction.user.id, nom_oficial, fecha_denuncia)
        ):
            pass

        await interaction.client.db.commit()

        # Construir embed de respuesta
        campos = [
            ("Número de Denuncia", f"**{numero_denuncia}**", True),
            ("Tipo", tipo_denuncia, True),
            ("Prioridad", f"**{prioridad}**", True),
            ("Denunciante", f"{nombre_denunciante} (DNI: {dni_denunciante})" + (f" | {denunciante.mention}" if denunciante else ""), False),
            ("Oficial Receptor", nom_oficial, True),
            ("Fecha de Registro", fecha_denuncia, True),
        ]

        if denunciado_nombre:
            mencion_denunciado = denunciado.mention if denunciado else ""
            campos.append(("Denunciado", f"{denunciado_nombre}" + (f" | {mencion_denunciado}" if mencion_denunciado else ""), False))

        if ubicacion:
            campos.append(("Ubicación de los Hechos", ubicacion, False))

        if fecha_hechos:
            campos.append(("Fecha de los Hechos", fecha_hechos, True))

        desc = (
            f"Se ha registrado una nueva denuncia en el sistema.\n\n"
            f"**Descripción de los Hechos:**\n{descripcion}\n\n"
            f"{Emojis.INFO} *La denuncia ha sido asignada al estado **PENDIENTE** y puede ser consultada con `/seguimiento numero_denuncia:{numero_denuncia}`*"
        )

        embed = construir_embed(
            tipo="policial",
            titulo=f"{Emojis.DOCUMENTO} DENUNCIA REGISTRADA",
            descripcion=desc,
            campos=campos
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

        # Notificar al denunciante
        if denunciante:
            try:
                desc_md = (
                    f"Tu denuncia ha sido registrada oficialmente en el sistema policial.\n"
                    f"**Datos de tu Denuncia:**\n"
                    f"• **Número:** **{numero_denuncia}**\n"
                    f"• **Tipo:** {tipo_denuncia}\n"
                    f"• **Oficial Receptor:** {nom_oficial}\n"
                    f"• **Estado:** PENDIENTE\n\n"
                    f"Puedes consultar el seguimiento de tu denuncia contactando a las autoridades."
                )
                embed_md = construir_embed(
                    "policial",
                    titulo=f"{Emojis.DOCUMENTO} CONFIRMACIÓN DE DENUNCIA",
                    descripcion=desc_md
                )
                await denunciante.send(view=discord.ui.LayoutView().add_item(embed_md))
            except (discord.HTTPException, discord.Forbidden):
                pass

    @app_commands.command(name="seguimiento", description="POLICIA: Agregar seguimiento o actualizar estado de una denuncia.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(
        numero_denuncia="Número de la denuncia (Ej: DEN-20260909-143052)",
        accion="Tipo de acción realizada",
        descripcion="Descripción detallada de la acción",
        nuevo_estado="Cambiar estado de la denuncia (opcional)",
        foto_evidencia="Adjuntar evidencia fotográfica (opcional)"
    )
    async def seguimiento(
        self,
        interaction: discord.Interaction,
        numero_denuncia: str,
        accion: Literal[
            'INVESTIGACIÓN', 'DECLARACIÓN', 'INSPECCIÓN', 'CITACIÓN',
            'ARRESTO', 'INCAUTACIÓN', 'INFORME', 'CIERRE', 'DERIVACIÓN', 'OTRO'
        ],
        descripcion: str,
        nuevo_estado: Literal['PENDIENTE', 'EN_INVESTIGACION', 'RESUELTA', 'ARCHIVADA', 'DERIVADA'] = None,
        foto_evidencia: discord.Attachment = None
    ):
        await interaction.response.defer(ephemeral=True)

        # Validar evidencia fotográfica si se proporcionó
        if foto_evidencia and (not foto_evidencia.content_type or not foto_evidencia.content_type.startswith("image/")):
            desc = "Archivo inválido.\n**Motivo:** La evidencia debe ser una imagen válida."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        # Buscar denuncia
        async with interaction.client.db.execute(
            """SELECT id_denuncia, denunciante_id, tipo_denuncia, estado, prioridad, fecha_denuncia 
               FROM denuncias WHERE numero_denuncia = ?""",
            (numero_denuncia,)
        ) as cur:
            denuncia = await cur.fetchone()

        if not denuncia:
            desc = f"Denuncia no encontrada.\n**Motivo:** El número **{numero_denuncia}** no existe en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        id_denuncia, denunciante_id, tipo_denuncia, estado_actual, prioridad, fecha_denuncia = denuncia

        # Obtener datos del oficial
        char_oficial = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        nom_oficial = f"{char_oficial[0]} {char_oficial[1]}" if char_oficial else interaction.user.display_name

        # Registrar seguimiento
        fecha_seguimiento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        async with interaction.client.db.execute(
            """INSERT INTO denuncias_seguimiento (
                id_denuncia, oficial_id, oficial_nombre, accion, descripcion, fecha
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (id_denuncia, interaction.user.id, nom_oficial, accion, descripcion, fecha_seguimiento)
        ):
            pass

        # Registrar evidencia si se proporcionó
        if foto_evidencia:
            async with interaction.client.db.execute(
                """INSERT INTO denuncias_evidencias (
                    id_denuncia, tipo_evidencia, url_archivo, descripcion, fecha_agregada
                ) VALUES (?, 'FOTOGRAFIA', ?, ?, ?)""",
                (id_denuncia, foto_evidencia.url, f"Evidencia adjunta en seguimiento: {accion}", fecha_seguimiento)
            ):
                pass

        # Actualizar estado si se proporcionó
        estado_final = estado_actual
        if nuevo_estado:
            async with interaction.client.db.execute(
                "UPDATE denuncias SET estado = ? WHERE id_denuncia = ?",
                (nuevo_estado, id_denuncia)
            ):
                pass
            estado_final = nuevo_estado

        await interaction.client.db.commit()

        # Construir respuesta
        campos = [
            ("Número de Denuncia", f"**{numero_denuncia}**", True),
            ("Tipo de Denuncia", tipo_denuncia, True),
            ("Acción Realizada", f"**{accion}**", True),
            ("Oficial", nom_oficial, True),
            ("Fecha", fecha_seguimiento, True),
            ("Estado Actual", f"**{estado_final}**", True),
        ]

        if nuevo_estado:
            campos.append(("Cambio de Estado", f"{estado_actual} → **{nuevo_estado}**", False))

        if foto_evidencia:
            campos.append(("Evidencia", "✅ Fotografía adjunta", True))

        desc = (
            f"Se ha registrado un nuevo seguimiento en la denuncia.\n\n"
            f"**Detalles de la Acción:**\n{descripcion}"
        )

        embed = construir_embed(
            tipo="policial",
            titulo=f"{Emojis.DOCUMENTO} SEGUIMIENTO REGISTRADO",
            descripcion=desc,
            campos=campos,
            imagen=foto_evidencia.url if foto_evidencia else None
        )

        await interaction.followup.send(
            view=discord.ui.LayoutView().add_item(embed),
            ephemeral=True
        )

    @app_commands.command(name="consultar_denuncia", description="POLICIA: Consultar información completa de una denuncia.")
    @utils.tiene_permiso(*utils.PERMISO_POLICIAL)
    @app_commands.describe(numero_denuncia="Número de la denuncia (Ej: DEN-20260909-143052)")
    async def consultar_denuncia(self, interaction: discord.Interaction, numero_denuncia: str):
        await interaction.response.defer(ephemeral=True)

        # Buscar denuncia
        async with interaction.client.db.execute(
            """SELECT id_denuncia, denunciante_nombre, denunciado_nombre, tipo_denuncia, 
               descripcion, ubicacion, fecha_hechos, fecha_denuncia, oficial_receptor_nombre,
               estado, prioridad 
               FROM denuncias WHERE numero_denuncia = ?""",
            (numero_denuncia,)
        ) as cur:
            denuncia = await cur.fetchone()

        if not denuncia:
            desc = f"Denuncia no encontrada.\n**Motivo:** El número **{numero_denuncia}** no existe en el sistema."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        (id_denuncia, denunciante, denunciado, tipo_den, descripcion, ubicacion, 
         fecha_hechos, fecha_denuncia, oficial_receptor, estado, prioridad) = denuncia

        # Obtener TODOS los seguimientos (no solo 5)
        async with interaction.client.db.execute(
            """SELECT s.oficial_nombre, s.accion, s.descripcion, s.fecha, s.id_seguimiento
               FROM denuncias_seguimiento s
               WHERE s.id_denuncia = ? 
               ORDER BY s.fecha ASC""",
            (id_denuncia,)
        ) as cur:
            seguimientos = await cur.fetchall()

        if not seguimientos:
            desc = f"Denuncia sin seguimientos.\n**Motivo:** La denuncia **{numero_denuncia}** no tiene seguimientos registrados."
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )

        # Obtener evidencias para cada seguimiento
        seguimientos_con_evidencias = []
        for oficial, accion, desc_seg, fecha, id_seg in seguimientos:
            # Buscar si hay evidencia para este seguimiento
            async with interaction.client.db.execute(
                """SELECT url_archivo FROM denuncias_evidencias 
                   WHERE id_denuncia = ? LIMIT 1""",
                (id_denuncia,)
            ) as cur:
                evidencia = await cur.fetchone()
            
            imagen_url = evidencia[0] if evidencia else None
            seguimientos_con_evidencias.append((oficial, accion, desc_seg, fecha, imagen_url))

        # Preparar información general
        info_denuncia = {
            'tipo': tipo_den,
            'estado': estado,
            'prioridad': prioridad,
            'denunciante': denunciante,
            'denunciado': denunciado if denunciado else "No especificado",
            'oficial_receptor': oficial_receptor,
            'fecha_denuncia': fecha_denuncia,
            'descripcion': descripcion,
            'ubicacion': ubicacion,
            'fecha_hechos': fecha_hechos
        }

        # Si solo hay un seguimiento, mostrar sin paginación
        if len(seguimientos_con_evidencias) == 1:
            oficial, accion, desc_seg, fecha, imagen_url = seguimientos_con_evidencias[0]
            
            desc = (
                f"**Información General:**\n"
                f"• **Número:** {numero_denuncia}\n"
                f"• **Tipo:** {tipo_den}\n"
                f"• **Estado:** **{estado}**\n"
                f"• **Prioridad:** **{prioridad}**\n"
                f"• **Denunciante:** {denunciante}\n"
                f"• **Oficial Receptor:** {oficial_receptor}\n"
                f"• **Fecha de Registro:** {fecha_denuncia}\n\n"
                f"**Descripción de los Hechos:**\n{descripcion}\n\n"
                f"---\n\n"
                f"**Seguimiento:**\n"
                f"• **Acción:** {accion}\n"
                f"• **Oficial:** {oficial}\n"
                f"• **Fecha:** {fecha}\n"
                f"• **Descripción:** {desc_seg}"
            )
            
            if denunciado:
                desc = desc.replace(f"**Fecha de Registro:** {fecha_denuncia}\n\n", 
                                  f"**Fecha de Registro:** {fecha_denuncia}\n• **Denunciado:** {denunciado}\n\n")
            
            embed = construir_embed(
                tipo="policial",
                titulo=f"{Emojis.DOCUMENTO} DENUNCIA: {numero_denuncia}",
                descripcion=desc,
                imagen=imagen_url if imagen_url else None
            )
            
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(embed),
                ephemeral=True
            )

        # Si hay múltiples seguimientos, usar paginación
        view = DenunciaPaginationView(interaction, seguimientos_con_evidencias, numero_denuncia, info_denuncia)
        mensaje = await interaction.followup.send(view=view, ephemeral=True)
        view._message = mensaje  # Guardar referencia al mensaje para timeout


async def setup(bot):
    await bot.add_cog(Policia(bot))
