import discord
from discord import app_commands
from discord.ext import commands
import random
import math
from typing import Literal, Optional

import utils
from tema import Emojis, construir_embed, crear_vista_con_embed
from utils import ROLES_CRIMINALES, INGRESOS_ROLES

COLUMNAS_VALIDAS = {
    "Mano": "dinero_mano",
    "Banco": "dinero_banco"
}


class ConfirmPayView(discord.ui.LayoutView):
    def __init__(self, emisor_id: int):
        super().__init__(timeout=60)
        self.emisor_id = emisor_id
        self.value = None

        ar = discord.ui.ActionRow()
        btn_confirm = discord.ui.Button(label="Confirmar", style=discord.ButtonStyle.success)
        btn_cancel = discord.ui.Button(label="Cancelar", style=discord.ButtonStyle.danger)
        btn_confirm.callback = self.confirmar
        btn_cancel.callback = self.cancelar
        ar.add_item(btn_confirm)
        ar.add_item(btn_cancel)
        self.add_item(ar)

    async def confirmar(self, interaction: discord.Interaction):
        if interaction.user.id != self.emisor_id:
            desc = "Operación denegada.\n**Motivo:** No posees los permisos necesarios para confirmar o cancelar esta transacción."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)
        self.value = True
        for child in self.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def cancelar(self, interaction: discord.Interaction):
        if interaction.user.id != self.emisor_id:
            desc = "Operación denegada.\n**Motivo:** No posees los permisos necesarios para confirmar o cancelar esta transacción."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)
        self.value = False
        for child in self.walk_children():
            if getattr(child, "disabled", None) is not None:
                child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class LeaderboardView(discord.ui.LayoutView):
    def __init__(self, data: list, user_id: int):
        super().__init__(timeout=60)
        self.data = data
        self.user_id = user_id
        self.per_page = 10
        self.current_page = 0
        self.total_pages = max(1, math.ceil(len(data) / 10))

        self.user_rank = "Fuera del Top"
        for idx, (uid, slot, _, _, _) in enumerate(data, 1):
            if uid == user_id:
                self.user_rank = f"#{idx} (Slot {slot})"
                break

        self.btn_prev = discord.ui.Button(label="Anterior", style=discord.ButtonStyle.primary)
        self.btn_prev.callback = self.prev
        self.btn_next = discord.ui.Button(label="Siguiente", style=discord.ButtonStyle.primary)
        self.btn_next.callback = self.next

        self.refresh_view()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("⛔ No puedes interactuar con el menú de otro usuario.", ephemeral=True)
            return False
        return True

    def update_buttons(self):
        self.btn_prev.disabled = (self.current_page == 0)
        self.btn_next.disabled = (self.current_page >= self.total_pages - 1)

    def refresh_view(self):
        self.clear_items()
        self.add_item(self.get_container())
        self.update_buttons()
        ar = discord.ui.ActionRow()
        ar.add_item(self.btn_prev)
        ar.add_item(self.btn_next)
        self.add_item(ar)

    def get_container(self):
        start = self.current_page * self.per_page
        page_data = self.data[start:start + self.per_page]
        lineas = []

        for i, (uid, slot, nom, ape, total) in enumerate(page_data, start + 1):
            emoji = Emojis.ORO if i == 1 else Emojis.PLATA if i == 2 else Emojis.BRONCE if i == 3 else f"**{i}.**"
            lineas.append(f"{emoji} <@{uid}> • **{nom} {ape}** (Slot {slot}) • **{utils.format_money(total)}**")

        cuerpo = "\n".join(lineas) if lineas else "No hay registros disponibles."
        info_paginacion = f"\n\n───────────────\n📄 **Página {self.current_page + 1}/{self.total_pages}** • **Tu Posición:** {self.user_rank}"

        return construir_embed(
            tipo="economia",
            titulo=f"{Emojis.CORONA} Leaderboard Global",
            descripcion=cuerpo + info_paginacion
        )

    async def prev(self, interaction: discord.Interaction):
        self.current_page -= 1
        self.refresh_view()
        await interaction.response.edit_message(view=self, allowed_mentions=discord.AllowedMentions.none())

    async def next(self, interaction: discord.Interaction):
        self.current_page += 1
        self.refresh_view()
        await interaction.response.edit_message(view=self, allowed_mentions=discord.AllowedMentions.none())


async def actualizar_billetera(interaction: discord.Interaction, view_billetera, desc_exito: str):
    if view_billetera:
        char_updated = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if char_updated:
            desc_w = (
                f"**Efectivo:** {utils.format_money(char_updated[2])}\n"
                f"**Banco:** {utils.format_money(char_updated[3])}\n"
                f"**Total:** {utils.format_money(char_updated[2] + char_updated[3])}\n\n"
                f"📂 **Slot Activo:** {char_updated[4]} • **ID:** `{interaction.user.id}`"
            )
            embed_w = construir_embed(
                tipo="economia",
                titulo=f"💳 Billetera de {char_updated[0]} {char_updated[1]}",
                descripcion=desc_w
            )
            view_billetera.container = embed_w
            view_billetera._setup_main_view()
            await interaction.response.edit_message(view=view_billetera)
            return await interaction.followup.send(view=crear_vista_con_embed("exito", descripcion=desc_exito), ephemeral=True)

    await interaction.response.send_message(view=crear_vista_con_embed("exito", descripcion=desc_exito), ephemeral=True)


class BankModal(discord.ui.Modal):
    monto = discord.ui.TextInput(
        label="Monto",
        placeholder="Ej: 5000 o 'todo'",
        style=discord.TextStyle.short,
        required=True
    )

    def __init__(self, accion: str, view_billetera=None):
        super().__init__(title=f"{accion} Dinero")
        self.accion = accion
        self.view_billetera = view_billetera

    async def on_submit(self, interaction: discord.Interaction):
        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Operación denegada.\n**Motivo:** No se detectó un perfil activo vinculado a tu cuenta para procesar transacciones bancarias."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        cantidad = self.monto.value
        mano, banco, slot = char[2], char[3], char[4]

        if self.accion == "Depositar":
            monto_real = mano if cantidad.lower() in ['todo', 'all', 'max'] else int(cantidad) if cantidad.isdigit() else 0
            if monto_real <= 0 or mano < monto_real:
                desc = "Transacción denegada.\n**Motivo:** Fondos insuficientes en efectivo o el monto especificado es inválido."
                return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

            async with interaction.client.db.execute(
                "UPDATE usuarios SET dinero_mano = dinero_mano - ?, dinero_banco = dinero_banco + ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
                (monto_real, monto_real, interaction.user.id, slot, monto_real)
            ) as cur:
                if cur.rowcount == 0:
                    desc = "Transacción denegada.\n**Motivo:** Se detectó una inconsistencia de fondos al momento de procesar el depósito."
                    return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)
            await interaction.client.db.commit()
            desc = f"Transacción aprobada.\n**Detalles del Movimiento:**\n• **Tipo:** Depósito Bancario\n• **Monto:** **{utils.format_money(monto_real)}**"
            await actualizar_billetera(interaction, self.view_billetera, desc)
            if hasattr(interaction.client, 'registrar_log_ui'):
                await interaction.client.registrar_log_ui(interaction, "Economia", "Depósito Bancario", f"Depositó {utils.format_money(monto_real)}.")

        else:  # Retirar
            monto_real = banco if cantidad.lower() in ['todo', 'all', 'max'] else int(cantidad) if cantidad.isdigit() else 0
            if monto_real <= 0 or banco < monto_real:
                desc = "Transacción denegada.\n**Motivo:** Fondos insuficientes en cuenta bancaria o el monto especificado es inválido."
                return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

            async with interaction.client.db.execute(
                "UPDATE usuarios SET dinero_banco = dinero_banco - ?, dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ? AND dinero_banco >= ?",
                (monto_real, monto_real, interaction.user.id, slot, monto_real)
            ) as cur:
                if cur.rowcount == 0:
                    desc = "Transacción denegada.\n**Motivo:** Se detectó una inconsistencia de fondos al momento de procesar la extracción."
                    return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)
            await interaction.client.db.commit()
            desc = f"Transacción aprobada.\n**Detalles del Movimiento:**\n• **Tipo:** Extracción Bancaria\n• **Monto:** **{utils.format_money(monto_real)}**"
            await actualizar_billetera(interaction, self.view_billetera, desc)
            if hasattr(interaction.client, 'registrar_log_ui'):
                await interaction.client.registrar_log_ui(interaction, "Economia", "Extracción Bancaria", f"Retiró {utils.format_money(monto_real)}.")


class TransferModal(discord.ui.Modal):
    monto = discord.ui.TextInput(
        label="Monto a Transferir",
        placeholder="Ej: 5000 o 'todo'",
        style=discord.TextStyle.short,
        required=True
    )
    slot_destino = discord.ui.TextInput(
        label="Slot del Destinatario (1 o 2) [Opcional]",
        placeholder="Dejar vacío para enviar a su Slot Activo",
        style=discord.TextStyle.short,
        required=False,
        max_length=1
    )

    def __init__(self, target_user: discord.Member, view_billetera=None):
        super().__init__(title=f"Transferir a {target_user.display_name}"[:45])
        self.target_user = target_user
        self.view_billetera = view_billetera

    async def on_submit(self, interaction: discord.Interaction):
        me = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not me:
            desc = "El sistema rechazó la transferencia.\n**Motivo:** No se detectó un personaje activo vinculado a tu cuenta."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        mano_mio, slot_mio = me[2], me[4]

        cantidad = self.monto.value
        monto_real = mano_mio if cantidad.lower() in ['todo', 'all', 'max'] else int(cantidad) if cantidad.isdigit() else 0
        if monto_real <= 0:
            desc = f"El sistema rechazó la transferencia.\n**Motivo:** Monto especificado inválido. Debe ser un número mayor a 0 o 'todo'."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)
        
        # Validación inicial de fondos (solo para dar feedback temprano, la verificación real es en el UPDATE)
        if mano_mio < monto_real:
            desc = f"El sistema rechazó la transferencia.\n**Motivo:** Fondos insuficientes en Efectivo.\n• **Saldo Disponible:** **${mano_mio:,}**\n• **Monto Requerido:** **${monto_real:,}**"
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        target_uid = self.target_user.id
        slot_req = self.slot_destino.value.strip()

        if slot_req in ["1", "2"]:
            async with interaction.client.db.execute("SELECT nombres, apellidos, dinero_mano, dinero_banco, slot FROM usuarios WHERE id_usuario = ? AND slot = ?", (target_uid, int(slot_req))) as cur:
                target = await cur.fetchone()
            if not target:
                desc = f"El sistema rechazó la transferencia.\n**Motivo:** El destinatario no posee un personaje registrado en el Slot {slot_req}."
                return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)
        else:
            target = await utils.get_active_char(target_uid, interaction.client.db, interaction.client.sesiones_cache)
            if not target:
                desc = "El sistema rechazó la transferencia.\n**Motivo:** El destinatario no se encuentra registrado o no posee un personaje activo actualmente."
                return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        if target_uid == interaction.user.id and int(target[4]) == int(slot_mio):
            desc = f"Operación denegada.\n**Motivo:** No puedes transferir fondos al mismo personaje (Slot {slot_mio})."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        # Ejecutar transferencia - La verificación atómica de fondos se hace en el UPDATE
        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano - ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
            (monto_real, interaction.user.id, slot_mio, monto_real)
        ) as cur:
            if cur.rowcount == 0:
                # Verificar saldo actual para mensaje informativo
                me_actual = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
                saldo_actual = me_actual[2] if me_actual else 0
                desc = f"Transacción denegada.\n**Motivo:** Fondos insuficientes al momento de procesar.\n• **Saldo Actual:** {utils.format_money(saldo_actual)}\n• **Monto Requerido:** {utils.format_money(monto_real)}"
                return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
            (monto_real, target_uid, target[4])
        ):
            pass
        await interaction.client.db.commit()

        desc = (
            f"La transferencia de fondos ha sido procesada y registrada exitosamente.\n"
            f"**Comprobante de Transferencia:**\n"
            f"• **Monto Transferido:** **{utils.format_money(monto_real)}**\n"
            f"• **Remitente:** **{me[0]} {me[1]}** (Slot **{slot_mio}**)\n"
            f"• **Destinatario:** **{target[0]} {target[1]}** (Slot **{target[4]}**)"
        )
        await actualizar_billetera(interaction, self.view_billetera, desc)
        if hasattr(interaction.client, 'registrar_log_ui'):
            await interaction.client.registrar_log_ui(interaction, "Economia", "Transferencia", f"Transfirió {utils.format_money(monto_real)} a {self.target_user.mention} (Slot {target[4]}).")


class TransferUserSelect(discord.ui.UserSelect):
    def __init__(self, view_billetera=None):
        super().__init__(placeholder="Selecciona al destinatario de la transferencia...")
        self.view_billetera = view_billetera

    async def callback(self, interaction: discord.Interaction):
        target_user = self.values[0]
        await interaction.response.send_modal(TransferModal(target_user, self.view_billetera))


class BilleteraView(discord.ui.LayoutView):
    def __init__(self, user_id: int, container):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.container = container
        self._setup_main_view()

    def _setup_main_view(self):
        self.clear_items()
        self.add_item(self.container)

        ar = discord.ui.ActionRow()

        btn_transferir = discord.ui.Button(label="Transferir", emoji="💸", style=discord.ButtonStyle.primary)
        btn_transferir.callback = self.btn_transferir
        ar.add_item(btn_transferir)

        btn_depositar = discord.ui.Button(label="Depositar", emoji="📥", style=discord.ButtonStyle.success)
        btn_depositar.callback = self.btn_depositar
        ar.add_item(btn_depositar)

        btn_retirar = discord.ui.Button(label="Retirar", emoji="📤", style=discord.ButtonStyle.danger)
        btn_retirar.callback = self.btn_retirar
        ar.add_item(btn_retirar)

        self.add_item(ar)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("⛔ Esta billetera no te pertenece.", ephemeral=True)
            return False
        return True

    async def btn_transferir(self, interaction: discord.Interaction):
        self.clear_items()
        self.add_item(self.container)

        ar_select = discord.ui.ActionRow()
        ar_select.add_item(TransferUserSelect(self))
        self.add_item(ar_select)

        ar_btn = discord.ui.ActionRow()
        btn_volver = discord.ui.Button(label="Volver", style=discord.ButtonStyle.secondary)

        async def btn_volver_cb(i: discord.Interaction):
            if i.user.id != self.user_id:
                return await i.response.send_message("⛔ No puedes interactuar con el menú de otro usuario.", ephemeral=True)
            self._setup_main_view()
            await i.response.edit_message(view=self)

        btn_volver.callback = btn_volver_cb
        ar_btn.add_item(btn_volver)

        self.add_item(ar_btn)
        await interaction.response.edit_message(view=self)

    async def btn_depositar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BankModal("Depositar", self))

    async def btn_retirar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BankModal("Retirar", self))


@app_commands.guild_only()
class Economia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="work", description="Trabajar (1h).")
    async def work(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        
        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Solicitud laboral denegada.\n**Motivo:** No posees un personaje seleccionado en el sistema."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        slot = char[4]

        ok, ts = await utils.check_cooldown_pro(interaction.user.id, "last_work", 3600, slot, interaction.client.db)
        if not ok:
            desc = (
                f"La Oficina de Empleo ha rechazado la solicitud laboral.\n"
                f"**Motivo del Rechazo:** El ciudadano **{char[0]}** se encuentra en período de descanso legal obligatorio.\n"
                f"• **Próximo turno disponible:** <t:{ts}:R>."
            )
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("advertencia", descripcion=desc)))

        ganancia = random.randint(1000, 5000)
        async with interaction.client.db.execute("UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?", (ganancia, interaction.user.id, slot)):
            pass
        await interaction.client.db.commit()

        await utils.update_cooldown(interaction.user.id, "last_work", slot, interaction.client.db)
        desc = (
            f"El reporte de empleo gubernamental indica que la jornada laboral de **{char[0]}** ha sido completada exitosamente.\n"
            f"**Recibo de Sueldo:**\n"
            f"• **Ganancia Neta:** **{utils.format_money(ganancia)}**"
        )
        embed = construir_embed("economia", titulo="Jornada Laboral Completada", descripcion=desc)
        await interaction.followup.send(view=discord.ui.LayoutView().add_item(embed))

    @app_commands.command(name="crime", description="Crimen (2h).")
    async def crime(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        
        user = interaction.user
        if not isinstance(user, discord.Member):
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="⛔ Este comando no funciona en mensajes directos.")))

        if not any(r.id in ROLES_CRIMINALES for r in user.roles):
            desc = "Operación denegada.\n**Motivo:** Se requiere una credencial criminal de facción autorizada para ejecutar esta acción."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        char = await utils.get_active_char(user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Operación denegada.\n**Motivo:** El usuario no posee un perfil activo en el sistema."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))
        slot = char[4]

        ok, ts = await utils.check_cooldown_pro(user.id, "last_crime", 7200, slot, interaction.client.db)
        if not ok:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("advertencia", descripcion=f"{Emojis.POLICIA} Policía cerca. Espera <t:{ts}:R>.")))

        exito = random.choice([True, True, False])
        if exito:
            gan = random.randint(5000, 8000)
            async with interaction.client.db.execute("UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?", (gan, user.id, slot)):
                pass
            msg = (
                f"El golpe fue un éxito total. Lograste darte a la fuga antes de que llegaran las unidades policiales al perímetro.\n"
                f"**Detalles del Asalto:**\n"
                f"• **Dinero Sucio Obtenido:** **{utils.format_money(gan)}**\n"
                f"• **Estado:** Buscando refugio para enfriar las cosas."
            )
            tipo, titulo = "roleplay", f"{Emojis.ARMA} Golpe Criminal Exitoso"
        else:
            mul = random.randint(1000, 3000)
            async with interaction.client.db.execute("UPDATE usuarios SET dinero_mano = MAX(0, dinero_mano - ?) WHERE id_usuario = ? AND slot = ?", (mul, user.id, slot)):
                pass
            msg = (
                f"Unidades de respuesta rápida te interceptaron antes de poder escapar con el botín de la zona.\n"
                f"**Detalles del Operativo:**\n"
                f"• **Efectivo Confiscado (Soborno):** **{utils.format_money(mul)}**\n"
                f"• **Estado:** Detenido temporalmente. Lograste comprar el silencio de los oficiales."
            )
            tipo, titulo = "error", f"{Emojis.POLICIA} Asalto Frustrado"

        await interaction.client.db.commit()
        await utils.update_cooldown(user.id, "last_crime", slot, interaction.client.db)

        await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed(tipo, titulo=titulo, descripcion=msg)))

    @app_commands.command(name="deposit", description="Depositar dinero (Acepta 'todo').")
    async def deposit(self, interaction: discord.Interaction, cantidad: str):
        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Operación denegada.\n**Motivo:** El usuario no posee un perfil activo en el sistema."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        mano, slot = char[2], char[4]

        if cantidad.lower() in ['todo', 'all', 'max']:
            monto = mano
        elif cantidad.isdigit():
            monto = int(cantidad)
        else:
            desc = "Error de formato.\n**Motivo:** El monto ingresado debe ser un valor numérico superior a 0 o la palabra clave 'todo'."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        if monto <= 0 or mano < monto:
            desc = "Operación denegada.\n**Motivo:** Fondos en efectivo insuficientes para proceder con el depósito."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano - ?, dinero_banco = dinero_banco + ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
            (monto, monto, interaction.user.id, slot, monto)
        ) as cur:
            if cur.rowcount == 0:
                desc = "Transacción denegada.\n**Motivo:** Se detectó una inconsistencia de fondos al momento de procesar la transacción."
                return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))
        await interaction.client.db.commit()
        desc_ex = f"Depósito completado.\n**Detalles del Movimiento:**\n• **Cuenta Destino:** **{char[0]}**\n• **Monto Depositado:** **{utils.format_money(monto)}**"
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc_ex)))

    @app_commands.command(name="withdraw", description="Retirar dinero (Acepta 'todo').")
    async def withdraw(self, interaction: discord.Interaction, cantidad: str):
        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Operación denegada.\n**Motivo:** El usuario no posee un perfil activo en el sistema."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        banco, slot = char[3], char[4]

        if cantidad.lower() in ['todo', 'all', 'max']:
            monto = banco
        elif cantidad.isdigit():
            monto = int(cantidad)
        else:
            desc = "Error de formato.\n**Motivo:** El monto ingresado debe ser un valor numérico superior a 0 o la palabra clave 'todo'."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        if monto <= 0 or banco < monto:
            desc = "Operación denegada.\n**Motivo:** Fondos en banco insuficientes para proceder con la extracción."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_banco = dinero_banco - ?, dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ? AND dinero_banco >= ?",
            (monto, monto, interaction.user.id, slot, monto)
        ) as cur:
            if cur.rowcount == 0:
                desc = "Transacción denegada.\n**Motivo:** Se detectó una inconsistencia de fondos al momento de procesar la transacción."
                return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))
        await interaction.client.db.commit()
        desc_ex = f"Extracción completada.\n**Detalles del Movimiento:**\n• **Cuenta Origen:** **{char[0]}**\n• **Monto Extraído:** **{utils.format_money(monto)}**"
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc_ex)))

    @app_commands.command(name="pay", description="Transferir dinero a otro ciudadano (Acepta 'todo').")
    async def pay(self, interaction: discord.Interaction, ciudadano: discord.Member, monto: str, slot_destino: Literal[1, 2] | None = None):
        me = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not me:
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=f"{Emojis.ERROR} Acceso denegado: No se ha detectado ningún perfil de ciudadano vinculado (Slot activo inexistente)."))

        nombre_mio, mano_mio, slot_mio = f"{me[0]} {me[1]}", me[2], me[4]

        if monto.lower() in ['todo', 'all', 'max']:
            cantidad_final = mano_mio
        elif monto.isdigit():
            cantidad_final = int(monto)
        else:
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=f"{Emojis.ERROR} Error de formato: El monto introducido es inválido. Utilice un valor numérico o 'todo'."))

        if cantidad_final <= 0:
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=f"{Emojis.ERROR} Error de validación: El monto a transferir debe ser superior a $0."))
        if mano_mio < cantidad_final:
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=f"{Emojis.ERROR} Transacción rechazada: Fondos insuficientes en la cartera física de {nombre_mio} (Slot {slot_mio})."))

        if slot_destino is None:
            target = await utils.get_active_char(ciudadano.id, interaction.client.db, interaction.client.sesiones_cache)
        else:
            async with interaction.client.db.execute("SELECT nombres, apellidos, dinero_mano, dinero_banco, slot FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot_destino)) as cur:
                target = await cur.fetchone()

        if not target:
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=f"{Emojis.ERROR} Destinatario inválido: {ciudadano.display_name} no posee un personaje registrado en el slot especificado."))

        slot_target = target[4]
        if ciudadano.id == interaction.user.id and int(slot_target) == int(slot_mio):
            desc = f"Operación denegada.\n**Motivo:** No puedes transferir fondos al mismo personaje (Slot {slot_mio})."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        nombre_target = f"{target[0]} {target[1]}"

        view = ConfirmPayView(interaction.user.id)
        embed_confirm = construir_embed(
            tipo="advertencia",
            titulo="⚠️ Confirmación de Transferencia",
            descripcion=(
                f"¿Estás seguro de transferir **${cantidad_final:,}** desde tu personaje **{nombre_mio} (Slot {slot_mio})** "
                f"hacia **{nombre_target} (Slot {slot_target})** (Usuario: {ciudadano.mention})?\n\n"
                "*Esta acción debitará los fondos de tu mano física de manera inmediata.*"
            )
        )
        view.add_item(embed_confirm)
        await interaction.response.send_message(view=view)

        await view.wait()

        if view.value is None:
            return await interaction.edit_original_response(view=crear_vista_con_embed("error", descripcion=f"{Emojis.RELOJ} Tiempo de confirmación expirado."))
        elif view.value is False:
            return await interaction.edit_original_response(view=crear_vista_con_embed("error", descripcion=f"{Emojis.DENEGADO} Transferencia cancelada por el usuario."))

        # Ejecutar transferencia - la verificación de fondos se hace atómicamente en el UPDATE
        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano - ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
            (cantidad_final, interaction.user.id, slot_mio, cantidad_final)
        ) as cur:
            if cur.rowcount == 0:
                # Verificar el saldo actual para dar un mensaje más informativo
                me_actual = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
                saldo_actual = me_actual[2] if me_actual else 0
                return await interaction.edit_original_response(
                    view=crear_vista_con_embed(
                        "error", 
                        descripcion=f"{Emojis.ERROR} Transacción declinada: Fondos insuficientes.\n• **Saldo Actual en Mano:** {utils.format_money(saldo_actual)}\n• **Monto Requerido:** {utils.format_money(cantidad_final)}"
                    )
                )

        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
            (cantidad_final, ciudadano.id, slot_target)
        ):
            pass
        await interaction.client.db.commit()

        embed_exito = construir_embed("exito", descripcion=f"{Emojis.DINERO} Transferencia exitosa: Se han enviado **${cantidad_final:,}** a {nombre_target} (Slot {slot_target}).")
        view_res = discord.ui.LayoutView()
        view_res.add_item(embed_exito)
        await interaction.edit_original_response(view=view_res, attachments=[])

    @app_commands.command(name="balance", description="Ver saldo.")
    async def balance(self, interaction: discord.Interaction, usuario: discord.Member | None = None, slot: Literal[1, 2] | None = None):
        # Responder INMEDIATAMENTE antes de cualquier operación
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            # Si la interacción expiró, no podemos hacer nada
            return
        
        target = usuario or interaction.user

        if slot is None:
            char = await utils.get_active_char(target.id, interaction.client.db, interaction.client.sesiones_cache)
        else:
            async with interaction.client.db.execute("SELECT nombres, apellidos, dinero_mano, dinero_banco, slot FROM usuarios WHERE id_usuario = ? AND slot = ?", (target.id, slot)) as cur:
                char = await cur.fetchone()

        if not char:
            embed_error = construir_embed("error", descripcion=f"{Emojis.ERROR} {target.display_name} no tiene personaje en el slot indicado.")
            view_error = discord.ui.LayoutView()
            view_error.add_item(embed_error)
            return await interaction.followup.send(view=view_error)

        desc = (
            f"**Efectivo:** {utils.format_money(char[2])}\n"
            f"**Banco:** {utils.format_money(char[3])}\n"
            f"**Total:** {utils.format_money(char[2] + char[3])}\n\n"
            f"📂 **Slot:** {char[4]} • **ID:** `{target.id}`"
        )
        embed = construir_embed(
            tipo="economia",
            titulo=f"💳 Billetera de {char[0]} {char[1]}",
            descripcion=desc
        )

        if target.id == interaction.user.id and (slot is None or slot == char[4]):
            view = BilleteraView(interaction.user.id, embed)
            await interaction.followup.send(view=view)
        else:
            view_simple = discord.ui.LayoutView()
            view_simple.add_item(embed)
            await interaction.followup.send(view=view_simple)

    @app_commands.command(name="top", description="Ranking global de los ciudadanos más adinerados.")
    async def top(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        
        async with interaction.client.db.execute(
            "SELECT id_usuario, slot, nombres, apellidos, (dinero_mano + dinero_banco) as total FROM usuarios ORDER BY total DESC LIMIT 100"
        ) as cur:
            data = await cur.fetchall()

        if not data:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=f"{Emojis.ERROR} La base de datos financiera se encuentra vacía.")))

        view = LeaderboardView(data, interaction.user.id)
        await interaction.followup.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="collect", description="Recoger ingresos de roles autorizados (Cada 24hs).")
    async def collect(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            return
        
        IMPUESTO_MONTO = 50000

        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=f"{Emojis.ERROR} No tienes un personaje seleccionado.")))

        nombre_pj = f"{char[0]} {char[1]}"
        slot_actual = char[4]

        ok, ts = await utils.check_cooldown_pro(interaction.user.id, "last_collect", 86400, slot_actual, interaction.client.db)
        if not ok:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("advertencia", descripcion=f"{Emojis.RELOJ} Ya cobraste hoy con **{nombre_pj}**. Vuelve <t:{ts}:R>.")))

        total_ingresos = 0
        lista_cobrados = ""

        if isinstance(interaction.user, discord.Member):
            for role in interaction.user.roles:
                if role.id in INGRESOS_ROLES:
                    datos = INGRESOS_ROLES[role.id]
                    if isinstance(datos, int):
                        monto, req_slot = datos, 0
                    else:
                        monto, req_slot = datos

                    if req_slot == 0 or req_slot == slot_actual:
                        total_ingresos += monto
                        lista_cobrados += f"{Emojis.EXITO} **${monto:,}** | {role.mention}\n"

        if total_ingresos == 0:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=f"{Emojis.ERROR} Tus roles actuales no generan ingresos autorizados.")))

        if total_ingresos < IMPUESTO_MONTO:
            await utils.update_cooldown(interaction.user.id, "last_collect", slot_actual, interaction.client.db)
            return await interaction.followup.send(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=f"{Emojis.ADVERTENCIA} **Ingresos Insuficientes**\nTus ingresos totales (${total_ingresos:,}) son menores al impuesto obligatorio de **${IMPUESTO_MONTO:,}**. Has perdido tu turno de cobro por insuficiencia fiscal."))
            )

        sueldo_neto = total_ingresos - IMPUESTO_MONTO

        try:
            async with interaction.client.db.execute("UPDATE usuarios SET dinero_banco = dinero_banco + ? WHERE id_usuario = ? AND slot = ?", (sueldo_neto, interaction.user.id, slot_actual)):
                pass
            await interaction.client.db.commit()
            await utils.update_cooldown(interaction.user.id, "last_collect", slot_actual, interaction.client.db)

        except Exception as e:
            await interaction.client.db.rollback()
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=f"{Emojis.ERROR} Error en la base de datos: {e}")))

        desc = (
            f"**Ingresos Brutos:**\n{lista_cobrados or 'Ninguno'}\n"
            f"**Retenciones:**\n📉 **-${IMPUESTO_MONTO:,}** (Impuesto Nacional)\n\n"
            f"💰 **SUELDO NETO ACREDITADO:** **${sueldo_neto:,}**"
        )
        embed = construir_embed(
            tipo="roleplay",
            titulo=f"🏛️ Recaudación Diaria | {nombre_pj}",
            descripcion=desc
        )

        await interaction.followup.send(view=discord.ui.LayoutView().add_item(embed))

    @app_commands.command(name="add_money", description="ADMIN: Añadir dinero (PJ Activo).")
    @utils.tiene_permiso(*utils.PERMISO_ECONOMIA)
    async def add_money(self, interaction: discord.Interaction, ciudadano: discord.Member, slot: Literal[1, 2], destino: Literal['Mano', 'Banco'], monto: int):
        if monto <= 0:
            desc = "Operación abortada.\n**Motivo:** El monto a acreditar debe ser un número entero mayor a 0."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        async with interaction.client.db.execute("SELECT nombres FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()
        if not res:
            desc = f"Operación abortada.\n**Motivo:** El ciudadano {ciudadano.mention} no tiene un personaje registrado en el Slot **{slot}**."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        col = COLUMNAS_VALIDAS.get(destino, "dinero_mano")

        async with interaction.client.db.execute(f"UPDATE usuarios SET {col} = {col} + ? WHERE id_usuario = ? AND slot = ?", (monto, ciudadano.id, slot)):
            pass
        await interaction.client.db.commit()
        desc = (
            f"La inyección de capital ha sido aprobada e impactada en la base de datos.\n"
            f"**Detalles de Operación:**\n"
            f"• **Beneficiario:** {ciudadano.mention} (Slot **{slot}**)\n"
            f"• **Monto Acreditado:** **{utils.format_money(monto)}**\n"
            f"• **Destino:** **{destino}**"
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)))

    @app_commands.command(name="remove_money", description="ADMIN: Quitar dinero (Acepta 'todo' para dejar en 0).")
    @utils.tiene_permiso(*utils.PERMISO_ECONOMIA)
    async def remove_money(self, interaction: discord.Interaction, ciudadano: discord.Member, slot: Literal[1, 2], destino: Literal['Mano', 'Banco'], monto: str):
        async with interaction.client.db.execute("SELECT dinero_mano, dinero_banco FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()
        if not res:
            desc = f"Operación abortada.\n**Motivo:** El ciudadano {ciudadano.mention} no tiene un personaje registrado en el Slot **{slot}**."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        mano_actual, banco_actual = res[0], res[1]
        columna = COLUMNAS_VALIDAS.get(destino, "dinero_mano")
        saldo_target = mano_actual if destino == "Mano" else banco_actual

        if monto.lower() in ['todo', 'all', 'max']:
            cantidad_final = saldo_target
        elif monto.isdigit():
            cantidad_final = int(monto)
        else:
            desc = f"Operación abortada.\n**Motivo:** El monto ingresado (`{monto}`) no posee un formato numérico válido ni es la palabra clave `todo`."
            return await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        if cantidad_final <= 0:
            desc = "Operación abortada.\n**Motivo:** El monto a retirar debe ser mayor a 0."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        async with interaction.client.db.execute(f"UPDATE usuarios SET {columna} = MAX(0, {columna} - ?) WHERE id_usuario = ? AND slot = ?", (cantidad_final, ciudadano.id, slot)):
            pass
        await interaction.client.db.commit()
        desc = (
            f"La deducción de capital ha sido ejecutada en la base de datos central.\n"
            f"**Detalles de Operación:**\n"
            f"• **Afectado:** {ciudadano.mention} (Slot **{slot}**)\n"
            f"• **Monto Retirado:** **{utils.format_money(cantidad_final)}**\n"
            f"• **Origen:** **{destino}**"
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

    @app_commands.command(name="reseteo_personaje", description="ADMIN: Resetear dinero del personaje ACTIVO.")
    @utils.tiene_permiso(*utils.PERMISO_MANEJO_DNI)
    @app_commands.describe(confirmacion="Escribe CONFIRMO para proceder.")
    async def reseteo_personaje(self, interaction: discord.Interaction, ciudadano: discord.Member, slot: Literal[1, 2], confirmacion: str):
        if confirmacion != "CONFIRMO":
            desc = "Acción de seguridad abortada.\n**Motivo:** Protocolo de confirmación incorrecto (Se requiere ingresar exactamente `CONFIRMO`)."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        async with interaction.client.db.execute("SELECT nombres FROM usuarios WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)) as cur:
            res = await cur.fetchone()
        if not res:
            desc = f"Operación abortada.\n**Motivo:** El ciudadano {ciudadano.mention} no tiene un personaje registrado en el Slot **{slot}**."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        async with interaction.client.db.execute("UPDATE usuarios SET dinero_mano = 0, dinero_banco = 0 WHERE id_usuario = ? AND slot = ?", (ciudadano.id, slot)):
            pass
        await interaction.client.db.commit()
        desc = (
            f"Se ha ejecutado un reseteo financiero forzoso.\n"
            f"**Detalles del Reseteo:**\n"
            f"• **Afectado:** {ciudadano.mention} (Slot **{slot}**)\n"
            f"• **Resultado:** Cuentas puestas en **$0**."
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("advertencia", descripcion=desc)))

    @app_commands.command(name="reseteo_economia", description="ADMIN: WIPE TOTAL DE TODOS LOS SLOTS.")
    @utils.tiene_permiso(*utils.PERMISO_ADMIN)
    @app_commands.describe(confirmacion="Escribe CONFIRMO para proceder.")
    async def reseteo_economia(self, interaction: discord.Interaction, confirmacion: str):
        if confirmacion != "CONFIRMO":
            desc = "Acción Crítica abortada.\n**Motivo:** Protocolo de confirmación incorrecto."
            return await interaction.response.send_message(view=crear_vista_con_embed("error", descripcion=desc), ephemeral=True)

        async with interaction.client.db.execute("UPDATE usuarios SET dinero_mano = 0, dinero_banco = 0"):
            pass
        await interaction.client.db.commit()
        desc = (
            f"**¡ALERTA MÁXIMA DE ECONOMÍA!**\n"
            f"Se ha ejecutado un WIPE TOTAL del sistema bancario y civil de AMBA.\n"
            f"**Detalles Técnicos:**\n"
            f"• **Acción:** Vaciado de cuentas a **$0**.\n"
            f"• **Alcance:** **TODOS** los slots y usuarios.\n"
            f"• **Autor:** {interaction.user.mention}"
        )
        await interaction.response.send_message(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))


async def setup(bot):
    await bot.add_cog(Economia(bot))
