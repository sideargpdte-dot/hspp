import discord
from discord import app_commands
from discord.ext import commands
import os
import aiosqlite
import pathlib
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configuración inicial de codificación de salida
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Cargar variables de entorno al inicio
ruta_actual = pathlib.Path(__file__).parent.absolute()
load_dotenv(dotenv_path=ruta_actual / ".env")

if sys.platform != 'win32':
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        print("⚡ uvloop activado (Modo Alto Rendimiento).")
    except ImportError:
        print("⚠️ uvloop no está instalado. Para mayor rendimiento en Linux, ejecuta: pip install uvloop")

import utils
from tema import TemaBot, Emojis, construir_embed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger("main")

TOKEN = os.getenv('DISCORD_TOKEN', '').strip()
if not TOKEN:
    print("❌ CRÍTICO: El token en .env está vacío.")
    sys.exit(1)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


async def enviar_alerta_seguridad(interaction: discord.Interaction, descripcion: str, tipo_alerta="error"):
    view = discord.ui.LayoutView().add_item(construir_embed(tipo_alerta, descripcion=descripcion))
    if interaction.response.is_done():
        try:
            await interaction.followup.send(view=view, ephemeral=True)
        except discord.HTTPException:
            pass
    else:
        try:
            await interaction.response.send_message(view=view, ephemeral=True)
        except discord.HTTPException:
            pass

    canal_alertas = interaction.client.get_channel(utils.ID_CANAL_ALERTAS)
    if canal_alertas and isinstance(canal_alertas, discord.TextChannel):
        cmd_name = interaction.command.name if interaction.command else "Desconocido"
        embed_alerta = construir_embed(
            tipo_alerta,
            titulo="⚠️ Alerta de Seguridad",
            descripcion=f"**Usuario:** {interaction.user.mention} (`{interaction.user.id}`)\n**Comando:** `/{cmd_name}`\n\n{descripcion}",
            thumbnail=interaction.user.display_avatar.url
        )
        try:
            await canal_alertas.send(view=discord.ui.LayoutView().add_item(embed_alerta), allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            logger.error(f"Error al enviar alerta de seguridad: {e}")


class AmbaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="am!", intents=intents)
        self.db: aiosqlite.Connection | None = None
        self.sesiones_cache = {}

    async def init_db(self):
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS sesiones (
                user_id INTEGER PRIMARY KEY,
                slot_activo INTEGER DEFAULT 1
            )
        ''')
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id_usuario INTEGER,
                slot INTEGER,
                nombres TEXT,
                apellidos TEXT,
                fecha_nacimiento TEXT,
                genero TEXT,
                nacionalidad TEXT,
                domicilio TEXT,
                dinero_mano INTEGER DEFAULT 0,
                dinero_banco INTEGER DEFAULT 0,
                licencias_conducir TEXT DEFAULT '',
                licencias_armas TEXT DEFAULT '',
                trabajo TEXT DEFAULT 'Desempleado',
                busqueda_captura BOOLEAN DEFAULT 0,
                arrestado BOOLEAN DEFAULT 0,
                tiempo_carcel TEXT DEFAULT '',
                last_work TEXT DEFAULT NULL,
                last_crime TEXT DEFAULT NULL,
                last_collect TEXT DEFAULT NULL,
                PRIMARY KEY (id_usuario, slot)
            )
        ''')
        try:
            await self.db.execute("ALTER TABLE usuarios ADD COLUMN imagen_url TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass

        try:
            await self.db.execute("ALTER TABLE usuarios ADD COLUMN nro_doc TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass

        try:
            await self.db.execute("ALTER TABLE usuarios ADD COLUMN roblox_user TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass

        await self.db.execute('''CREATE TABLE IF NOT EXISTS vehiculos (id_vehiculo INTEGER PRIMARY KEY AUTOINCREMENT, id_usuario INTEGER, slot INTEGER, modelo TEXT, patente TEXT)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS multas (id_multa INTEGER PRIMARY KEY AUTOINCREMENT, id_usuario INTEGER, motivo TEXT, monto INTEGER, oficial_id INTEGER, pagada BOOLEAN DEFAULT 0, fecha TEXT)''')
        
        # Actualizar tabla multas con nuevas columnas
        try:
            await self.db.execute("ALTER TABLE multas ADD COLUMN articulos TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass
        
        try:
            await self.db.execute("ALTER TABLE multas ADD COLUMN gravedad TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass
        
        try:
            await self.db.execute("ALTER TABLE multas ADD COLUMN slot INTEGER DEFAULT 1")
        except aiosqlite.OperationalError:
            pass
        
        # Agregar columna slot a tabla antecedentes
        try:
            await self.db.execute("ALTER TABLE antecedentes ADD COLUMN slot INTEGER DEFAULT 1")
        except aiosqlite.OperationalError:
            pass
        
        await self.db.execute('''CREATE TABLE IF NOT EXISTS antecedentes (id_antecedente INTEGER PRIMARY KEY AUTOINCREMENT, id_usuario INTEGER, delito TEXT, oficial_id INTEGER, fecha TEXT)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS ruleta_estado (guild_id INTEGER PRIMARY KEY, activa BOOLEAN DEFAULT 0)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS ruleta_apuestas (id_apuesta INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, id_usuario INTEGER, slot INTEGER, monto INTEGER, opcion TEXT)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS logs (id_log INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, usuario_nombre TEXT, comando TEXT, argumentos TEXT, fecha TEXT)''')
        await self.db.execute('''CREATE TABLE IF NOT EXISTS arrestos (id_usuario INTEGER PRIMARY KEY, id_guild INTEGER, fecha_liberacion REAL)''')

        # ==========================================
        #  NUEVAS TABLAS: SISTEMA POLICIAL COMPLETO
        # ==========================================
        
        # BÚSQUEDA Y CAPTURA
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS busqueda_captura (
                id_busqueda INTEGER PRIMARY KEY AUTOINCREMENT,
                id_usuario INTEGER NOT NULL,
                slot INTEGER NOT NULL,
                numero_orden TEXT UNIQUE NOT NULL,
                motivo TEXT NOT NULL,
                oficial_emisor_id INTEGER NOT NULL,
                oficial_emisor_nombre TEXT NOT NULL,
                fecha_emision TEXT NOT NULL,
                estado TEXT DEFAULT 'ACTIVA',
                fecha_captura TEXT,
                oficial_captura_id INTEGER,
                oficial_captura_nombre TEXT,
                UNIQUE(id_usuario, slot)
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS busqueda_avistamientos (
                id_avistamiento INTEGER PRIMARY KEY AUTOINCREMENT,
                id_busqueda INTEGER NOT NULL,
                oficial_id INTEGER NOT NULL,
                oficial_nombre TEXT NOT NULL,
                ubicacion TEXT NOT NULL,
                descripcion TEXT,
                fecha TEXT NOT NULL,
                FOREIGN KEY (id_busqueda) REFERENCES busqueda_captura(id_busqueda)
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS busqueda_intentos_captura (
                id_intento INTEGER PRIMARY KEY AUTOINCREMENT,
                id_busqueda INTEGER NOT NULL,
                oficial_id INTEGER NOT NULL,
                oficial_nombre TEXT NOT NULL,
                resultado TEXT NOT NULL,
                descripcion TEXT,
                fecha TEXT NOT NULL,
                FOREIGN KEY (id_busqueda) REFERENCES busqueda_captura(id_busqueda)
            )
        ''')

        # DENUNCIAS
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS denuncias (
                id_denuncia INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_denuncia TEXT UNIQUE NOT NULL,
                denunciante_id INTEGER NOT NULL,
                denunciante_nombre TEXT NOT NULL,
                denunciado_id INTEGER,
                denunciado_nombre TEXT,
                tipo_denuncia TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                ubicacion TEXT,
                fecha_hechos TEXT,
                fecha_denuncia TEXT NOT NULL,
                oficial_receptor_id INTEGER NOT NULL,
                oficial_receptor_nombre TEXT NOT NULL,
                estado TEXT DEFAULT 'PENDIENTE',
                prioridad TEXT DEFAULT 'MEDIA'
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS denuncias_seguimiento (
                id_seguimiento INTEGER PRIMARY KEY AUTOINCREMENT,
                id_denuncia INTEGER NOT NULL,
                oficial_id INTEGER NOT NULL,
                oficial_nombre TEXT NOT NULL,
                accion TEXT NOT NULL,
                descripcion TEXT,
                fecha TEXT NOT NULL,
                FOREIGN KEY (id_denuncia) REFERENCES denuncias(id_denuncia)
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS denuncias_evidencias (
                id_evidencia INTEGER PRIMARY KEY AUTOINCREMENT,
                id_denuncia INTEGER NOT NULL,
                tipo_evidencia TEXT NOT NULL,
                url_archivo TEXT,
                descripcion TEXT,
                fecha_agregada TEXT NOT NULL,
                FOREIGN KEY (id_denuncia) REFERENCES denuncias(id_denuncia)
            )
        ''')

        # VEHÍCULOS EXTENDIDO
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS vehiculos_antecedentes (
                id_antecedente INTEGER PRIMARY KEY AUTOINCREMENT,
                patente TEXT NOT NULL,
                tipo_incidente TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                oficial_id INTEGER NOT NULL,
                oficial_nombre TEXT NOT NULL,
                fecha TEXT NOT NULL
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS vehiculos_historial_propietarios (
                id_historial INTEGER PRIMARY KEY AUTOINCREMENT,
                patente TEXT NOT NULL,
                id_usuario_anterior INTEGER NOT NULL,
                nombre_anterior TEXT NOT NULL,
                id_usuario_nuevo INTEGER NOT NULL,
                nombre_nuevo TEXT NOT NULL,
                fecha_transferencia TEXT NOT NULL,
                precio_venta INTEGER DEFAULT 0
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS vehiculos_robados (
                id_robo INTEGER PRIMARY KEY AUTOINCREMENT,
                patente TEXT UNIQUE NOT NULL,
                modelo TEXT NOT NULL,
                propietario_id INTEGER NOT NULL,
                propietario_nombre TEXT NOT NULL,
                fecha_robo TEXT NOT NULL,
                descripcion TEXT,
                oficial_registro_id INTEGER,
                oficial_registro_nombre TEXT,
                estado TEXT DEFAULT 'ACTIVO',
                fecha_recuperacion TEXT,
                oficial_recuperacion_id INTEGER,
                oficial_recuperacion_nombre TEXT
            )
        ''')

        # ==========================================
        #  ACTUALIZACIÓN DE TABLA ARRESTOS
        # ==========================================
        
        # Agregar nuevas columnas a la tabla arrestos existente
        try:
            await self.db.execute("ALTER TABLE arrestos ADD COLUMN articulos TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass  # La columna ya existe
        
        try:
            await self.db.execute("ALTER TABLE arrestos ADD COLUMN multa_total INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass
        
        try:
            await self.db.execute("ALTER TABLE arrestos ADD COLUMN gravedad TEXT DEFAULT 'medio'")
        except aiosqlite.OperationalError:
            pass
        
        try:
            await self.db.execute("ALTER TABLE arrestos ADD COLUMN oficiales_a_cargo TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass
        
        try:
            await self.db.execute("ALTER TABLE arrestos ADD COLUMN numero_arresto TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass
        
        try:
            await self.db.execute("ALTER TABLE arrestos ADD COLUMN es_ck BOOLEAN DEFAULT 0")
        except aiosqlite.OperationalError:
            pass

        # Crear tabla de historial de arrestos
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS historial_arrestos (
                id_historial INTEGER PRIMARY KEY AUTOINCREMENT,
                id_usuario INTEGER NOT NULL,
                slot INTEGER NOT NULL,
                numero_arresto TEXT,
                fecha_arresto REAL NOT NULL,
                fecha_liberacion REAL NOT NULL,
                articulos TEXT,
                multa_total INTEGER DEFAULT 0,
                gravedad TEXT DEFAULT 'medio',
                oficiales_a_cargo TEXT,
                es_ck BOOLEAN DEFAULT 0,
                estado TEXT DEFAULT 'CUMPLIDO'
            )
        ''')

        try:
            await self.db.execute("UPDATE ruleta_estado SET activa = 0")
        except aiosqlite.OperationalError:
            pass

        await self.db.commit()
        print("✅ Base de datos verificada y lista.")

    async def setup_hook(self):
        self.db = await aiosqlite.connect('roleplay.db', timeout=15.0)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.db.execute("PRAGMA busy_timeout=15000;")
        self.sesiones_cache = {}
        await self.init_db()

        try:
            await self.load_extension("cogs.economia")
            await self.load_extension("cogs.casino")
            await self.load_extension("cogs.policia")
            await self.load_extension("cogs.roleplay")
            print("✅ Cogs cargados correctamente.")
        except Exception as e:
            logger.error(f"Error al cargar cogs: {e}")

        # Sincronización única y controlada durante el arranque
        try:
            await self.tree.sync()
            print("⚡ Árbol de comandos sincronizado exitosamente con Discord.")
        except discord.HTTPException as e:
            logger.error(f"Error al sincronizar comandos: {e}")

    async def registrar_log_ui(self, interaction: discord.Interaction, cog_name: str, accion: str, descripcion: str, thumbnail: str = None):
        usuario = interaction.user
        hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        tipo_embed = "principal"
        if cog_name == "Economia":
            tipo_embed = "economia"
        elif cog_name == "Policia":
            tipo_embed = "policial"
        elif cog_name == "Casino":
            tipo_embed = "casino"

        slot_activo = "Desconocido"
        if hasattr(utils, 'get_slot_activo') and self.db:
            slot_activo = await utils.get_slot_activo(usuario.id, self.db, self.sesiones_cache)

        try:
            if self.db:
                async with self.db.execute(
                    "INSERT INTO logs (usuario_id, usuario_nombre, comando, argumentos, fecha) VALUES (?, ?, ?, ?, ?)",
                    (usuario.id, f"{usuario.name}", f"UI:{accion}", descripcion[:1000], hora)
                ):
                    pass
                await self.db.commit()
        except Exception as e:
            logger.error(f"Error log UI SQL: {e}")

        canal_logs = self.get_channel(utils.ID_CANAL_LOGS)
        if canal_logs and isinstance(canal_logs, discord.TextChannel):
            desc = (
                f"**Detalles de Acción:**\n"
                f"• **Usuario:** {usuario.mention} (`{usuario.id}`)\n"
                f"• **Acción Ejecutada:** **{accion}**\n"
                f"• **Slot Afectado:** Slot {slot_activo}\n"
                f"• **Marca de Tiempo:** <t:{int(datetime.now().timestamp())}:f>\n\n"
                f"**Contexto:**\n{descripcion}"
            )
            embed = construir_embed(
                tipo=tipo_embed,
                titulo=f"📝 Log de Interfaz - Módulo {cog_name}",
                descripcion=desc,
                thumbnail=thumbnail or usuario.display_avatar.url
            )
            try:
                await canal_logs.send(view=discord.ui.LayoutView().add_item(embed), allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException as e:
                logger.error(f"Error al enviar log UI al canal: {e}")

    async def close(self):
        print("\n🛑 [SHUTDOWN] Iniciando apagado seguro del bot (Señal SIGTERM/SIGINT recibida)...")
        try:
            if self.db:
                print("💾 [SHUTDOWN] Guardando transacciones pendientes y cerrando Base de Datos SQLite...")
                await self.db.commit()
                await self.db.close()
                self.db = None
                print("✅ [SHUTDOWN] Base de Datos cerrada con éxito.")
        except Exception as e:
            logger.error(f"Error al cerrar la Base de Datos: {e}")

        print("👋 [SHUTDOWN] Desconectando de Discord...")
        await super().close()


bot = AmbaBot()


@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como: {bot.user}")
    print("----------------------------------------")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.CustomActivity(
            name="discord.gg/amba"
        )
    )


@bot.event
async def on_disconnect():
    print(f"⚠️ [WARN] El bot se ha desconectado del Gateway de Discord a las {datetime.now().strftime('%H:%M:%S')}")


@bot.event
async def on_resumed():
    print(f"🔄 [INFO] Sesión del Gateway de Discord reanudada exitosamente a las {datetime.now().strftime('%H:%M:%S')}")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    # Validar MODO_DESARROLLO antes de procesar el comando
    modo_desarrollo = os.getenv("MODO_DESARROLLO", "0")
    if modo_desarrollo == "1" and interaction.type == discord.InteractionType.application_command:
        is_dev = False
        if interaction.user.id == utils.ID_DUENO:
            is_dev = True
        elif isinstance(interaction.user, discord.Member):
            roles = [r.id for r in interaction.user.roles]
            if utils.ID_STAFF in roles:
                is_dev = True

        if not is_dev:
            desc = (
                f"El sistema se encuentra actualmente en **Mantenimiento / Desarrollo**.\n"
                f"**Detalles del Bloqueo:**\n"
                f"• **Motivo:** Restricción global de comandos activa.\n"
                f"• **Nivel de Acceso:** Limitado a personal **Staff**."
            )
            await interaction.response.send_message(
                view=discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc)),
                ephemeral=True
            )
            return


@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingAnyRole):
        roles_faltantes = [f"<@&{r}>" for r in error.missing_roles] if error.missing_roles else ["Roles Administrativos"]
        desc = (
            f"No posees los permisos suficientes en el sistema para ejecutar este comando.\n"
            f"**Detalles de la Restricción:**\n"
            f"• **Roles Requeridos:** {', '.join(roles_faltantes)}\n"
            f"• **Estado Actual:** Acceso Denegado por el Sistema de Seguridad."
        )
        return await enviar_alerta_seguridad(interaction, desc, "error")

    elif isinstance(error, app_commands.MissingPermissions):
        permisos_faltantes = [p.replace("_", " ").title() for p in error.missing_permissions]
        desc = (
            f"No posees los permisos suficientes en el sistema para ejecutar este comando.\n"
            f"**Detalles de la Restricción:**\n"
            f"• **Permisos Requeridos:** {', '.join(permisos_faltantes)}\n"
            f"• **Estado Actual:** Acceso Denegado por el Sistema de Seguridad."
        )
        return await enviar_alerta_seguridad(interaction, desc, "error")

    elif isinstance(error, app_commands.CommandOnCooldown):
        desc = (
            f"El comando se encuentra actualmente en estado de enfriamiento preventivo (Cooldown).\n"
            f"**Estado del Sistema:**\n"
            f"• **Tiempo Restante:** **{error.retry_after:.2f} segundos**."
        )
        view = discord.ui.LayoutView().add_item(construir_embed("advertencia", descripcion=desc))
        if interaction.response.is_done():
            return await interaction.followup.send(view=view, ephemeral=True)
        return await interaction.response.send_message(view=view, ephemeral=True)

    elif isinstance(error, app_commands.CheckFailure):
        desc = (
            f"Condiciones insuficientes para ejecutar el comando.\n"
            f"**Detalles de la Restricción:**\n"
            f"• **Estado Actual:** El sistema ha bloqueado la operación por falta de permisos o validaciones."
        )
        return await enviar_alerta_seguridad(interaction, desc, "error")

    else:
        logger.error(f"Error no manejado en comando: {error}", exc_info=True)

        canal_alertas = bot.get_channel(utils.ID_CANAL_ALERTAS)
        if canal_alertas and isinstance(canal_alertas, discord.TextChannel):
            cmd_name = interaction.command.name if interaction.command else "Desconocido"
            error_str = str(error)[:1000]
            desc_alerta = (
                f"**Usuario:** {interaction.user.mention} (`{interaction.user.id}`)\n"
                f"**Comando:** `/{cmd_name}`\n\n"
                f"**Traza de Error:**\n```py\n{error_str}\n```\n"
                f"Atención <@{utils.ID_DUENO}>!"
            )
            try:
                await canal_alertas.send(view=discord.ui.LayoutView().add_item(construir_embed("error", titulo="💥 Excepción Crítica Detectada", descripcion=desc_alerta)))
            except discord.HTTPException:
                pass

        desc_usuario = (
            f"Ocurrió un error inesperado de sintaxis o ejecución al procesar la solicitud.\n"
            f"**Reporte de Fallo Técnico:**\n"
            f"• **Estado:** Operación Abortada.\n"
            f"• **Acción Sugerida:** Contactar a las autoridades de desarrollo del servidor."
        )
        view_err = discord.ui.LayoutView().add_item(construir_embed("error", descripcion=desc_usuario))

        if not interaction.response.is_done():
            await interaction.response.send_message(view=view_err, ephemeral=True)
        else:
            await interaction.followup.send(view=view_err, ephemeral=True)


@bot.listen("on_app_command_completion")
async def log_command_completion(interaction: discord.Interaction, command: app_commands.Command):
    usuario = interaction.user
    nombre_cmd = command.qualified_name
    hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cog_name = getattr(command.binding.__class__, '__name__', 'Desconocido') if command.binding else 'General'
    tipo_embed = "principal"
    if cog_name == "Economia":
        tipo_embed = "economia"
    elif cog_name == "Policia":
        tipo_embed = "policial"
    elif cog_name == "Roleplay":
        tipo_embed = "principal"
    elif cog_name == "Casino":
        tipo_embed = "casino"

    ejecucion_ms = (discord.utils.utcnow() - interaction.created_at).total_seconds() * 1000

    slot_activo = "Desconocido"
    if hasattr(utils, 'get_slot_activo') and bot.db:
        slot_activo = await utils.get_slot_activo(usuario.id, bot.db, bot.sesiones_cache)

    args_txt = "N/A"
    try:
        if interaction.data and 'options' in interaction.data:
            opciones = interaction.data['options']
            lista = []
            for opt in opciones:
                if opt.get('type') == 1:
                    if 'options' in opt:
                        for sub_opt in opt['options']:
                            lista.append(f"{sub_opt.get('name')}: {sub_opt.get('value')}")
                else:
                    lista.append(f"{opt.get('name')}: {opt.get('value')}")

            if lista:
                args_txt = " | ".join(lista)
            else:
                args_txt = "(Sin argumentos)"
    except Exception:
        args_txt = "Error procesando args"

    try:
        if bot.db:
            async with bot.db.execute(
                "INSERT INTO logs (usuario_id, usuario_nombre, comando, argumentos, fecha) VALUES (?, ?, ?, ?, ?)",
                (usuario.id, f"{usuario.name}", nombre_cmd, args_txt, hora)
            ):
                pass
            await bot.db.commit()
    except Exception as e:
        logger.error(f"Error log SQL: {e}")

    canal_logs = bot.get_channel(utils.ID_CANAL_LOGS)
    if canal_logs and isinstance(canal_logs, discord.TextChannel):
        desc = (
            f"**Detalles de Ejecución:**\n"
            f"• **Usuario:** {usuario.mention} (`{usuario.id}`)\n"
            f"• **Comando Invocado:** **`/{nombre_cmd}`**\n"
            f"• **Argumentos:** `{args_txt}`\n"
            f"• **Slot Afectado:** Slot {slot_activo}\n"
            f"• **Tiempo de Ejecución:** **{ejecucion_ms:.2f}ms**\n"
            f"• **Marca de Tiempo:** <t:{int(datetime.now().timestamp())}:f>"
        )

        embed = construir_embed(
            tipo=tipo_embed,
            titulo=f"📝 Log - Módulo {cog_name}",
            descripcion=desc,
            thumbnail=usuario.display_avatar.url
        )

        try:
            await canal_logs.send(view=discord.ui.LayoutView().add_item(embed), allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException as e:
            logger.error(f"Error al enviar log al canal: {e}")


if __name__ == '__main__':
    bot.run(TOKEN)