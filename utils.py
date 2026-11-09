import os
import sys
import pathlib
from datetime import datetime as dt, timedelta
import re
from dotenv import load_dotenv
import discord
from discord import app_commands

# ==========================================
#  1. CARGA DE ENTORNO
# ==========================================
ruta_actual = pathlib.Path(__file__).parent.absolute()
ruta_env = ruta_actual / ".env"

if not os.path.exists(ruta_env):
    print("❌ CRÍTICO: No se encuentra el archivo .env")
    sys.exit(1)

load_dotenv(dotenv_path=ruta_env)


def get_env_int(key: str) -> int:
    val = os.getenv(key)
    if not val:
        print(f"❌ CRÍTICO: Falta la variable de entorno {key} en el archivo .env")
        sys.exit(1)
    try:
        return int(val.strip())
    except ValueError:
        print(f"❌ CRÍTICO: La variable de entorno {key} debe ser un número entero válido.")
        sys.exit(1)


def get_env_int_list(key: str) -> list[int]:
    val = os.getenv(key)
    if not val:
        print(f"❌ CRÍTICO: Falta la variable de entorno {key} en el archivo .env")
        sys.exit(1)
    try:
        return [int(x.strip()) for x in val.split(",") if x.strip()]
    except ValueError:
        print(f"❌ CRÍTICO: La variable de entorno {key} debe ser una lista de números separados por coma.")
        sys.exit(1)


# ==========================================
#  2. VARIABLES GLOBALES DE CONFIGURACIÓN
# ==========================================
ID_DUENO = get_env_int("ID_DUENO")
ID_STAFF = get_env_int("ID_STAFF")
ID_POLICIA = get_env_int("ID_POLICIA")
ID_CIVIL = get_env_int("ID_CIVIL")
ID_ROL_PRESO = get_env_int("ID_ROL_PRESO")
ID_LLAVE_SLOT_2 = get_env_int("ID_LLAVE_SLOT_2")
ID_ECONOMIA = get_env_int("ID_ECONOMIA")
ID_MANEJO_DNI = get_env_int("ID_MANEJO_DNI")
ID_MANEJO_LICENCIAS = get_env_int("ID_MANEJO_LICENCIAS")
ID_CANAL_LOGS = get_env_int("ID_CANAL_LOGS")
ID_CANAL_ALERTAS = get_env_int("ID_CANAL_ALERTAS")
ID_CANAL_REVISION_DNI = get_env_int("ID_CANAL_REVISION_DNI")
ID_CANAL_RECLAMOS = get_env_int("ID_CANAL_RECLAMOS")
ID_ROL_SUPERVISOR = get_env_int("ID_ROL_SUPERVISOR")

VALORES_ROBOS = {
    "Auto Baja calidad": 250000,
    "Auto Media calidad": 300000,
    "Auto Alta calidad": 500000,
    "Caja Registradora": 30000,
    "Banco": 2000000,
    "ATM": 100000,
    "Joyería": 1250000,
    "Tienda": 250000,
    "Casas": 200000
}

ROLES_CRIMINALES = get_env_int_list("ROLES_CRIMINALES")

INGRESOS_ROLES = {
    1443306067697209445: (-50000, 0),    # Aplica a cualquier slot activo
    1516535737951060019: (200000, 1),
    1516535738504581140: (200000, 2),
    1516535739091914882: (450000, 1),
    1516535739746226318: (450000, 2),
    1516535740513779883: (750000, 1),
    1516535740853391442: (750000, 2),
    1516535741495382126: (950000, 1),
    1516535742195564614: (950000, 2),
    1516535743076368465: (1000000, 1),
    1516535743546265700: (1000000, 2),
    1516535743965696110: (1250000, 1),
    1516537683877564546: (1250000, 2)
}

PERMISO_ADMIN = [ID_DUENO, ID_STAFF]
PERMISO_POLICIAL = [ID_DUENO, ID_STAFF, ID_POLICIA]
PERMISO_CIVIL = [ID_DUENO, ID_STAFF, ID_POLICIA, ID_CIVIL]
PERMISO_2DO_PERSONAJE = [ID_LLAVE_SLOT_2, ID_DUENO]
PERMISO_ECONOMIA = [ID_ECONOMIA, ID_DUENO]
PERMISO_MANEJO_DNI = [ID_MANEJO_DNI, ID_DUENO]
PERMISO_MANEJO_LICENCIAS = [ID_MANEJO_LICENCIAS, ID_DUENO, ID_STAFF]

COOLDOWN_COLUMNS = {"last_work", "last_crime", "last_collect"}


def tiene_permiso(*roles):
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id == ID_DUENO:
            return True
        if isinstance(interaction.user, discord.Member):
            if any(role.id in roles for role in interaction.user.roles):
                return True
        roles_requeridos = [r for r in roles if r != ID_DUENO]
        raise app_commands.MissingAnyRole(roles_requeridos)
    return app_commands.check(predicate)


# ==========================================
#  3. CONEXIÓN A BASE DE DATOS Y CACHÉ
# ==========================================

async def get_slot_activo(user_id: int, db, cache: dict) -> int:
    """Devuelve el slot activo usando la caché en memoria para no saturar SQLite."""
    if user_id in cache:
        return cache[user_id]

    async with db.execute("SELECT slot_activo FROM sesiones WHERE user_id = ?", (user_id,)) as cur:
        sesion = await cur.fetchone()

    slot = sesion[0] if sesion else 1
    cache[user_id] = slot
    return slot


async def update_slot_activo_cache(user_id: int, slot: int, db, cache: dict):
    """Actualiza la sesión activa en BD y Caché."""
    cache[user_id] = slot
    async with db.execute("INSERT OR REPLACE INTO sesiones (user_id, slot_activo) VALUES (?, ?)", (user_id, slot)):
        pass
    await db.commit()


async def get_active_char(user_id: int, db, cache: dict):
    """Obtiene el personaje del slot seleccionado actualmente utilizando Caché en Sesión."""
    slot = await get_slot_activo(user_id, db, cache)

    async with db.execute("""
        SELECT nombres, apellidos, dinero_mano, dinero_banco, slot 
        FROM usuarios 
        WHERE id_usuario = ? AND slot = ?
    """, (user_id, slot)) as cur:
        personaje = await cur.fetchone()

    return personaje


async def check_cooldown_pro(user_id: int, col_name: str, seconds: int, slot: int, db):
    """Verifica cooldown específico para el personaje (Slot)."""
    if col_name not in COOLDOWN_COLUMNS:
        raise ValueError(f"Columna de cooldown no autorizada: {col_name}")

    async with db.execute(f"SELECT {col_name} FROM usuarios WHERE id_usuario = ? AND slot = ?", (user_id, slot)) as cur:
        res = await cur.fetchone()

    if not res or not res[0]:
        return True, None

    try:
        last = dt.fromisoformat(res[0])
    except (ValueError, TypeError):
        return True, None

    fin = last + timedelta(seconds=seconds)
    if dt.now() > fin:
        return True, None
    return False, int(fin.timestamp())


async def update_cooldown(user_id: int, col_name: str, slot: int, db):
    """Actualiza la marca de tiempo para el personaje (Slot)."""
    if col_name not in COOLDOWN_COLUMNS:
        raise ValueError(f"Columna de cooldown no autorizada: {col_name}")

    async with db.execute(f"UPDATE usuarios SET {col_name} = ? WHERE id_usuario = ? AND slot = ?", (dt.now().isoformat(), user_id, slot)):
        pass
    await db.commit()


# ==========================================
#  4. UTILIDADES GENERALES
# ==========================================
def format_money(amount: int | float) -> str:
    return f"${int(amount):,}"


def calcular_edad(fecha_nacimiento: str) -> int | str:
    try:
        nacimiento = dt.strptime(fecha_nacimiento, "%d/%m/%Y")
        hoy = dt.now()
        edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
        return edad if edad >= 0 else "??"
    except ValueError:
        return "??"


def gestionar_estado_licencia(actual_str: str, item: str, accion: str) -> str:
    lista = [x.strip() for x in actual_str.split(',')] if actual_str and actual_str != "" else []
    item_normal = item
    item_suspendido = f"{item} (SUSPENDIDA)"

    if accion == "Otorgar":
        if item_normal not in lista and item_suspendido not in lista:
            lista.append(item_normal)
    elif accion == "Revocar":
        if item_normal in lista:
            lista.remove(item_normal)
        if item_suspendido in lista:
            lista.remove(item_suspendido)
    elif accion == "Suspender":
        if item_normal in lista:
            index = lista.index(item_normal)
            lista[index] = item_suspendido
    elif accion == "Reactivar":
        if item_suspendido in lista:
            index = lista.index(item_suspendido)
            lista[index] = item_normal

    return ", ".join(lista)


def parsear_tiempo(tiempo_str: str):
    patron = r"(\d+)([smhd])"
    coincidencias = re.findall(patron, tiempo_str.lower().replace(" ", ""))

    if not coincidencias:
        return None, None

    total_segundos = 0
    partes_texto = []
    valores = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    nombres = {'s': 'seg', 'm': 'min', 'h': 'hs', 'd': 'días'}

    for cantidad, unidad in coincidencias:
        valor = int(cantidad)
        total_segundos += valor * valores[unidad]
        partes_texto.append(f"{valor} {nombres[unidad]}")

    if total_segundos <= 0:
        return None, None

    tiempo_delta = timedelta(seconds=total_segundos)
    texto_legible = ", ".join(partes_texto)

    return tiempo_delta, texto_legible


# ==========================================
#  5. GENERADORES DE NÚMEROS ÚNICOS
# ==========================================

def generar_numero_orden_busqueda() -> str:
    """
    Genera un número único para Orden de Búsqueda y Captura.
    Formato: OBC-YYYYMMDD-HHMMSS
    Ejemplo: OBC-20260909-143052
    """
    ahora = dt.now()
    return f"OBC-{ahora.strftime('%Y%m%d-%H%M%S')}"


def generar_numero_denuncia() -> str:
    """
    Genera un número único para Denuncia.
    Formato: DEN-YYYYMMDD-HHMMSS
    Ejemplo: DEN-20260909-143052
    """
    ahora = dt.now()
    return f"DEN-{ahora.strftime('%Y%m%d-%H%M%S')}"


def generar_numero_arresto() -> str:
    """
    Genera un número único para Arresto.
    Formato: ARR-YYYYMMDD-HHMMSS
    Ejemplo: ARR-20260909-143052
    """
    ahora = dt.now()
    return f"ARR-{ahora.strftime('%Y%m%d-%H%M%S')}"
