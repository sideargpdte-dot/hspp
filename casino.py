import discord
from discord import app_commands
from discord.ext import commands
import random
import secrets
import asyncio
import logging
from typing import List, Tuple, Optional

import utils
from tema import Emojis, TemaBot, construir_embed

logger = logging.getLogger("cogs.casino")


def validar_apuesta(apuesta_str: str, saldo_mano: int) -> Tuple[Optional[int], Optional[str]]:
    """Valida y parsea la apuesta del usuario, asegurando fondos y monto mínimo."""
    ap = apuesta_str.lower().strip()
    if ap in ['todo', 'all', 'max']:
        monto = saldo_mano
    elif ap.isdigit():
        monto = int(ap)
    else:
        return None, "La apuesta ingresada debe ser un valor numérico o la palabra clave 'todo'."

    if monto < 50:
        return None, "La apuesta mínima permitida para esta sala es de **$50**."
    if saldo_mano < monto:
        return None, "Fondos en efectivo insuficientes para cubrir la apuesta."

    return monto, None


class BlackjackView(discord.ui.LayoutView):
    def __init__(self, user_id: int, apuesta: int, mazo: list, mano_j: list, mano_d: list, slot: int, embed_initial=None):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.apuesta = apuesta
        self.mazo = mazo
        self.mano_j = mano_j
        self.mano_d = mano_d
        self.slot = slot
        self._bloqueado = False
        self.message = None

        if embed_initial:
            self.add_item(embed_initial)

        self._armar_botones()

    def _armar_botones(self, permitir_doblar: bool = True):
        ar = discord.ui.ActionRow()
        b1 = discord.ui.Button(label="Pedir", style=discord.ButtonStyle.success)
        b1.callback = self.pedir
        b2 = discord.ui.Button(label="Plantarse", style=discord.ButtonStyle.danger)
        b2.callback = self.plantarse
        ar.add_item(b1)
        ar.add_item(b2)
        if permitir_doblar:
            b3 = discord.ui.Button(label="Doblar", style=discord.ButtonStyle.primary)
            b3.callback = self.doblar
            ar.add_item(b3)
        self.add_item(ar)

    @staticmethod
    def calcular(mano: list) -> int:
        v, a = 0, 0
        for c in mano:
            if c.startswith('10') or c.startswith(('J', 'Q', 'K')):
                val = 10
            elif c.startswith('A'):
                val = 11
                a += 1
            else:
                val = int(c[0])
            v += val
        while v > 21 and a:
            v -= 10
            a -= 1
        return v

    @staticmethod
    def format_mano(mano: list, oculta: bool = False) -> str:
        res = []
        cartas_map = getattr(Emojis, 'CARTAS_COMPLETAS', {})
        for i, c in enumerate(mano):
            if oculta and i > 0:
                emoji_carta = cartas_map.get('OCULTA', '🎴 `[ ? ]`')
            else:
                emoji_carta = cartas_map.get(c, c)
            res.append(emoji_carta)
        return " ".join(res)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="⛔ No es tu partida.")),
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.clear_items()
        embed_timeout = construir_embed(
            tipo="errores",
            titulo=f"{Emojis.CASINO} Partida Cancelada",
            descripcion=f"⏱️ **Tiempo agotado:** La partida finalizó por inactividad. La apuesta de **${self.apuesta:,}** se ha perdido."
        )
        self.add_item(embed_timeout)
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def fin(self, interaction: discord.Interaction, res: str, color: int):
        self.stop()
        vd = self.calcular(self.mano_d)

        embed = construir_embed(
            tipo="casino",
            titulo=f"{Emojis.CASINO} Blackjack",
            descripcion=f"**{res}**",
            campos=[
                (f"{Emojis.USUARIO} Tu Mano ({BlackjackView.calcular(self.mano_j)})", BlackjackView.format_mano(self.mano_j), True),
                (f"🤵 Dealer ({vd})", BlackjackView.format_mano(self.mano_d), True)
            ],
            color_override=color
        )

        if color == TemaBot.EXITO:
            pago = self.apuesta * 2
            async with interaction.client.db.execute(
                "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
                (pago, self.user_id, self.slot)
            ):
                pass
        elif color == TemaBot.ADVERTENCIA:
            async with interaction.client.db.execute(
                "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
                (self.apuesta, self.user_id, self.slot)
            ):
                pass
        await interaction.client.db.commit()

        try:
            self.clear_items()
            self.add_item(embed)
            if not interaction.response.is_done():
                await interaction.response.edit_message(view=self)
            elif self.message:
                await self.message.edit(view=self)
            elif interaction.message:
                await interaction.message.edit(view=self)
        except discord.HTTPException as e:
            logger.error(f"Error actualizando mensaje de fin de Blackjack: {e}")

    async def pedir(self, interaction: discord.Interaction):
        if self._bloqueado:
            return
        self._bloqueado = True

        self.mano_j.append(self.mazo.pop())
        val = self.calcular(self.mano_j)

        if val > 21:
            await self.fin(interaction, f"{Emojis.ERROR} **Resolución de Crupier:** Superaste el límite de 21. Pierdes **${self.apuesta:,}**.", TemaBot.ERROR)
        else:
            embed = construir_embed(
                tipo="casino",
                titulo=f"{Emojis.CASINO} Blackjack",
                campos=[
                    (f"{Emojis.USUARIO} Mano ({val})", self.format_mano(self.mano_j), True),
                    ("Dealer", self.format_mano(self.mano_d, True), True)
                ]
            )
            self.clear_items()
            self.add_item(embed)
            self._armar_botones(permitir_doblar=False)

            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(view=self)
                elif self.message:
                    await self.message.edit(view=self)
                elif interaction.message:
                    await interaction.message.edit(view=self)
            except discord.HTTPException as e:
                logger.error(f"Error actualizando mano de Blackjack: {e}")
            finally:
                self._bloqueado = False

    async def doblar(self, interaction: discord.Interaction):
        if self._bloqueado:
            return
        self._bloqueado = True

        async with interaction.client.db.execute(
            "SELECT dinero_mano FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (self.user_id, self.slot)
        ) as cur:
            row = await cur.fetchone()

        if not row or row[0] < self.apuesta:
            self._bloqueado = False
            return await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="❌ No tienes suficientes fondos en efectivo para doblar la apuesta.")),
                ephemeral=True
            )

        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano - ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
            (self.apuesta, self.user_id, self.slot, self.apuesta)
        ) as cur:
            if cur.rowcount == 0:
                self._bloqueado = False
                return await interaction.response.send_message(
                    view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion="❌ No tienes suficientes fondos en efectivo para doblar la apuesta.")),
                    ephemeral=True
                )
        await interaction.client.db.commit()

        self.apuesta *= 2
        self.mano_j.append(self.mazo.pop())
        val = self.calcular(self.mano_j)

        if val > 21:
            return await self.fin(interaction, f"{Emojis.ERROR} **Resolución de Crupier:** Superaste el límite de 21 tras doblar. Pierdes **${self.apuesta:,}**.", TemaBot.ERROR)

        while self.calcular(self.mano_d) < 17:
            self.mano_d.append(self.mazo.pop())

        vj, vd = self.calcular(self.mano_j), self.calcular(self.mano_d)

        if vd > 21:
            await self.fin(interaction, f"🎉 **Resolución de Crupier:** La casa superó el límite. Ganancia Acreditada: **+${self.apuesta:,}**.", TemaBot.EXITO)
        elif vd > vj:
            await self.fin(interaction, f"{Emojis.ERROR} **Resolución de Crupier:** La casa gana. Pierdes **${self.apuesta:,}**.", TemaBot.ERROR)
        elif vd < vj:
            await self.fin(interaction, f"🎉 **Resolución de Crupier:** Has vencido a la casa. Ganancia Acreditada: **+${self.apuesta:,}**.", TemaBot.EXITO)
        else:
            await self.fin(interaction, f"⚖️ **Resolución de Crupier:** Empate. Se reintegra la apuesta total.", TemaBot.ADVERTENCIA)

    async def plantarse(self, interaction: discord.Interaction):
        if self._bloqueado:
            return
        self._bloqueado = True

        while self.calcular(self.mano_d) < 17:
            self.mano_d.append(self.mazo.pop())

        vj, vd = self.calcular(self.mano_j), self.calcular(self.mano_d)

        if vd > 21:
            await self.fin(interaction, f"🎉 **Resolución de Crupier:** La casa superó el límite. Ganancia Acreditada: **+${self.apuesta:,}**.", TemaBot.EXITO)
        elif vd > vj:
            await self.fin(interaction, f"{Emojis.ERROR} **Resolución de Crupier:** La casa gana. Pierdes **${self.apuesta:,}**.", TemaBot.ERROR)
        elif vd < vj:
            await self.fin(interaction, f"🎉 **Resolución de Crupier:** Has vencido a la casa. Ganancia Acreditada: **+${self.apuesta:,}**.", TemaBot.EXITO)
        else:
            await self.fin(interaction, f"⚖️ **Resolución de Crupier:** Empate. Se reintegra la apuesta inicial.", TemaBot.ADVERTENCIA)


async def roulette_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    opciones_base = ['Rojo', 'Negro', 'Verde', 'Par', 'Impar', '1-18', '19-36']
    numeros = [str(i) for i in range(37)]
    todas_opciones = opciones_base + numeros
    return [
        app_commands.Choice(name=op, value=op)
        for op in todas_opciones if current.lower() in op.lower()
    ][:25]


@app_commands.guild_only()
class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.locks_ruleta = {}

    async def cog_load(self):
        # Parche de seguridad para la ruleta:
        # Reembolsar cualquier apuesta de ruleta pendiente si el bot se reinició
        async with self.bot.db.execute("SELECT id_usuario, slot, monto FROM ruleta_apuestas") as cur:
            apuestas_pendientes = await cur.fetchall()

        if apuestas_pendientes:
            datos_reembolso = [(monto, uid, slot) for uid, slot, monto in apuestas_pendientes]
            await self.bot.db.executemany(
                "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
                datos_reembolso
            )
            await self.bot.db.execute("DELETE FROM ruleta_apuestas")
            await self.bot.db.execute("UPDATE ruleta_estado SET activa = 0")
            await self.bot.db.commit()
            logger.info(f"Reembolsadas {len(apuestas_pendientes)} apuestas de ruleta atrapadas en DB.")

    async def _ejecutar_ruleta(self, guild_id: int, channel: Optional[discord.abc.Messageable]):
        """Tarea en segundo plano que gestiona la cuenta regresiva y resolución de la ruleta."""
        await asyncio.sleep(30)

        res = secrets.randbelow(37)
        col = "verde" if res == 0 else "rojo" if res in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36] else "negro"
        par = (res % 2 == 0 and res != 0)

        lock = self.locks_ruleta.setdefault(guild_id, asyncio.Lock())
        async with lock:
            async with self.bot.db.execute(
                "SELECT id_usuario, slot, monto, opcion FROM ruleta_apuestas WHERE guild_id = ?",
                (guild_id,)
            ) as cur:
                apuestas = await cur.fetchall()

            pagos = []
            txt_ganadores = []
            txt_perdedores = []

            for uid, uslot, umonto, uop in apuestas:
                w, mult = False, 0
                if uop.isdigit() and int(uop) == res:
                    w, mult = True, 35
                elif uop == col:
                    w, mult = True, 35 if col == "verde" else 1
                elif uop == "par" and par:
                    w, mult = True, 1
                elif uop == "impar" and not par and res != 0:
                    w, mult = True, 1
                elif uop == "1-18" and 1 <= res <= 18:
                    w, mult = True, 1
                elif uop == "19-36" and 19 <= res <= 36:
                    w, mult = True, 1

                if w:
                    pay = umonto * (mult + 1)
                    pagos.append((pay, uid, uslot))
                    txt_ganadores.append(f"🎉 <@{uid}>: +${int(umonto * mult):,} (Apostó ${umonto:,} a {uop})")
                else:
                    txt_perdedores.append(f"💀 <@{uid}>: -${umonto:,} (Apostó a {uop})")

            if pagos:
                await self.bot.db.executemany(
                    "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
                    pagos
                )

            await self.bot.db.execute("DELETE FROM ruleta_apuestas WHERE guild_id = ?", (guild_id,))
            await self.bot.db.execute("UPDATE ruleta_estado SET activa = 0 WHERE guild_id = ?", (guild_id,))
            await self.bot.db.commit()

        # Formatear resultados protegiendo contra límites de caracteres de Discord
        def limitar_lineas(lineas: list, max_items: int = 15) -> str:
            if not lineas:
                return "Ninguna en esta ronda"
            if len(lineas) <= max_items:
                return "\n".join(lineas)
            restantes = len(lineas) - max_items
            return "\n".join(lineas[:max_items]) + f"\n*... y {restantes} más.*"

        str_ganadores = limitar_lineas(txt_ganadores)
        str_perdedores = limitar_lineas(txt_perdedores)

        emo = "🟢" if col == "verde" else "🔴" if col == "rojo" else "⚫"
        desc = (
            f"**{emo} Número Ganador:** **{res}** ({col.capitalize()})\n\n"
            f"**Apuestas Ganadoras:**\n{str_ganadores}\n\n"
            f"**Apuestas Perdidas:**\n{str_perdedores}"
        )
        res_embed = construir_embed("casino", titulo=f"{Emojis.CASINO} RESULTADO DE RULETA", descripcion=desc)

        try:
            if channel:
                await channel.send(view=discord.ui.LayoutView().add_item(res_embed))
        except discord.HTTPException as e:
            logger.error(f"Error enviando resultados de ruleta: {e}")

    @app_commands.command(name="blackjack", description="Juega al Blackjack (Acepta 'todo').")
    async def blackjack(self, interaction: discord.Interaction, apuesta: str):
        await interaction.response.defer()
        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Operación denegada.\n**Motivo:** El usuario no posee un perfil activo en el sistema."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        mano, slot = char[2], char[4]

        monto, error_apuesta = validar_apuesta(apuesta, mano)
        if error_apuesta:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=f"Operación denegada.\n**Motivo:** {error_apuesta}")))

        async with interaction.client.db.execute(
            "UPDATE usuarios SET dinero_mano = dinero_mano - ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
            (monto, interaction.user.id, slot, monto)
        ) as cur:
            if cur.rowcount == 0:
                desc = "Operación denegada.\n**Motivo:** Se detectó una inconsistencia de fondos al momento de procesar la apuesta."
                return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))
        await interaction.client.db.commit()

        p, v = ['♠️', '♥️', '♦️', '♣️'], ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        mazo = [x + y for x in v for y in p] * 6
        random.shuffle(mazo)
        mj, md = [mazo.pop(), mazo.pop()], [mazo.pop(), mazo.pop()]

        vj = BlackjackView.calcular(mj)

        if vj == 21:
            vd = BlackjackView.calcular(md)
            campos_resultado = [
                (f"{Emojis.USUARIO} Tu Mano ({vj})", BlackjackView.format_mano(mj), True),
                (f"🤵 Dealer ({vd})", BlackjackView.format_mano(md), True)
            ]

            if vd == 21:
                async with interaction.client.db.execute(
                    "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
                    (monto, interaction.user.id, slot)
                ):
                    pass
                await interaction.client.db.commit()
                embed = construir_embed("advertencias", titulo=f"{Emojis.CASINO} Blackjack", descripcion="⚖️ **Empate:** Ambos obtuvieron Blackjack natural. Se reintegra la apuesta.", campos=campos_resultado)
            else:
                pago = monto * 2
                async with interaction.client.db.execute(
                    "UPDATE usuarios SET dinero_mano = dinero_mano + ? WHERE id_usuario = ? AND slot = ?",
                    (pago, interaction.user.id, slot)
                ):
                    pass
                await interaction.client.db.commit()
                embed = construir_embed("exito", titulo=f"{Emojis.CASINO} Blackjack", descripcion=f"🔥 **BLACKJACK NATURAL:** Ganancia Acreditada: **+${monto:,}**.", campos=campos_resultado)

            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(embed))

        embed = construir_embed(
            tipo="casino",
            titulo=f"{Emojis.CASINO} Blackjack",
            campos=[
                (f"{Emojis.USUARIO} Mano ({vj})", BlackjackView.format_mano(mj), True),
                ("Dealer", BlackjackView.format_mano(md, True), True)
            ]
        )

        view = BlackjackView(interaction.user.id, monto, mazo, mj, md, slot, embed_initial=embed)
        msg = await interaction.followup.send(view=view)
        view.message = msg

    @app_commands.command(name="roulette", description="Ruleta Multijugador (Acepta 'todo').")
    @app_commands.autocomplete(opcion=roulette_autocomplete)
    async def roulette(self, interaction: discord.Interaction, apuesta: str, opcion: str):
        await interaction.response.defer()
        guild_id = interaction.guild_id
        if not guild_id:
            desc = "Operación denegada.\n**Motivo:** Este comando únicamente puede ejecutarse dentro de un servidor."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        char = await utils.get_active_char(interaction.user.id, interaction.client.db, interaction.client.sesiones_cache)
        if not char:
            desc = "Operación denegada.\n**Motivo:** El usuario no posee un perfil activo en el sistema."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        nombre_rp = f"{char[0]} {char[1]}"
        mano, slot = char[2], char[4]

        monto, error_apuesta = validar_apuesta(apuesta, mano)
        if error_apuesta:
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=f"Operación denegada.\n**Motivo:** {error_apuesta}")))

        op = opcion.lower().strip()
        validos = ["rojo", "negro", "verde", "par", "impar", "1-18", "19-36"]
        if not (op.isdigit() and 0 <= int(op) <= 36) and op not in validos:
            desc = "Operación denegada.\n**Motivo:** Opción de ruleta inválida. Selecciona un número (0-36) o un color/paridad."
            return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

        lock = self.locks_ruleta.setdefault(guild_id, asyncio.Lock())
        async with lock:
            async with interaction.client.db.execute("SELECT activa FROM ruleta_estado WHERE guild_id = ?", (guild_id,)) as cur:
                estado = await cur.fetchone()

            juego_activo = bool(estado[0]) if estado else False

            async with interaction.client.db.execute(
                "UPDATE usuarios SET dinero_mano = dinero_mano - ? WHERE id_usuario = ? AND slot = ? AND dinero_mano >= ?",
                (monto, interaction.user.id, slot, monto)
            ) as cur:
                if cur.rowcount == 0:
                    desc = "Operación denegada.\n**Motivo:** Se detectó una inconsistencia de fondos al momento de procesar la apuesta."
                    return await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)))

            await interaction.client.db.execute(
                "INSERT INTO ruleta_apuestas (guild_id, id_usuario, slot, monto, opcion) VALUES (?, ?, ?, ?, ?)",
                (guild_id, interaction.user.id, slot, monto, op)
            )

            if not juego_activo:
                await interaction.client.db.execute(
                    "INSERT OR REPLACE INTO ruleta_estado (guild_id, activa) VALUES (?, 1)",
                    (guild_id,)
                )
            await interaction.client.db.commit()

        if not juego_activo:
            embed_inicio = construir_embed(
                tipo="casino",
                titulo=f"{Emojis.CASINO} RULETA INICIADA",
                descripcion=(
                    f"👤 **Crupier de Sala:** {nombre_rp} ({interaction.user.display_name}) ha iniciado una ronda de ruleta francesa.\n"
                    f"⏳ **Tiempo Restante:** Girando en 30 segundos...\n"
                    f"• Utiliza el comando `/roulette` para realizar tus apuestas."
                )
            )
            await interaction.followup.send(view=discord.ui.LayoutView().add_item(embed_inicio))
            self.bot.loop.create_task(self._ejecutar_ruleta(guild_id, interaction.channel))
        else:
            desc = f"{Emojis.EXITO} **Apuesta Registrada:** **{utils.format_money(monto)}** asignados a **{op}**. A la espera del crupier..."
            await interaction.followup.send(view=discord.ui.LayoutView().add_item(construir_embed("exito", descripcion=desc)))


async def setup(bot):
    await bot.add_cog(Casino(bot))
