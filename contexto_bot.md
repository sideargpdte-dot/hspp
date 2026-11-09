# 📖 AMBA Reborn 2 — Fuente de la Verdad (Source of Truth)

> **Última actualización:** 2026-08-29  
> **Propósito de este documento:** Servir como contexto definitivo para cualquier agente de IA o desarrollador que necesite entender, mantener o extender el bot de Discord "AMBA Reborn 2".

---

## 1. Visión General

**AMBA Reborn 2** es un bot de Discord diseñado para un servidor de **Roleplay Argentino** basado en Roblox. Proporciona un ecosistema completo de simulación civil que incluye: gestión de identidad ciudadana (DNI con imagen generada), economía con banco y efectivo, sistema policial y judicial (arrestos, multas, búsqueda y captura), casino (Blackjack y Ruleta multijugador) y administración de vehículos y licencias.

### Stack Tecnológico

| Componente | Tecnología | Versión |
|---|---|---|
| Runtime | Python 3.10+ | Type hints con `X | None` |
| Librería Discord | `discord.py` | **≥ 2.7.0** (usa `discord.ui.LayoutView`, `discord.ui.Container`, `discord.ui.Section`, Component-Based Messages V2) |
| Base de Datos | SQLite (asíncrona) | vía `aiosqlite ≥ 0.20.0` |
| HTTP Client | `aiohttp ≥ 3.9.0` + `curl_cffi ≥ 0.7.0` | curl_cffi para bypasear protecciones anti-bot de Roblox API |
| Procesamiento de Imagen | `Pillow ≥ 10.0.0` | Generación de DNI y carteles de búsqueda |
| Entorno | `python-dotenv ≥ 1.0.0` | Carga de `.env` |
| Event Loop (Linux) | `uvloop` (opcional) | Auto-detectado en `main.py` |

### Variables de Entorno Requeridas (`.env`)

| Variable | Tipo | Descripción |
|---|---|---|
| `DISCORD_TOKEN` | `str` | Token de autenticación del bot en Discord |
| `ID_DUENO` | `int` | ID del dueño del bot (bypass total de permisos) |
| `ID_STAFF` | `int` | ID del rol Staff |
| `ID_POLICIA` | `int` | ID del rol Policía |
| `ID_CIVIL` | `int` | ID del rol Civil |
| `ID_ROL_PRESO` | `int` | ID del rol que se asigna a usuarios arrestados |
| `ID_LLAVE_SLOT_2` | `int` | ID del rol que habilita un 2do personaje |
| `ID_ECONOMIA` | `int` | ID del rol con permisos de gestión económica |
| `ID_MANEJO_DNI` | `int` | ID del rol con permisos para aprobar/rechazar DNIs |
| `ID_MANEJO_LICENCIAS` | `int` | ID del rol con permisos para gestionar licencias |
| `ID_CANAL_LOGS` | `int` | ID del canal donde se envían los logs de ejecución de comandos |
| `ID_CANAL_ALERTAS` | `int` | ID del canal donde se envían alertas de seguridad y errores críticos |
| `ID_CANAL_REVISION_DNI` | `int` | ID del canal donde se revisan las solicitudes de DNI |
| `ID_CANAL_RECLAMOS` | `int` | ID del canal donde se revisan reclamos de robo |
| `ID_ROL_SUPERVISOR` | `int` | ID del rol supervisor (modera reclamos de robo) |
| `ROLES_CRIMINALES` | `int,int,...` | Lista de IDs de roles criminales (separados por coma) |
| `MODO_DESARROLLO` | `0 | 1` | Si es `1`, solo Staff y el dueño pueden usar comandos |

---

## 2. Arquitectura del Proyecto

```
AmbaReborn2/
├── main.py                    # 🟢 Entry Point — Clase AmbaBot, setup_hook, eventos globales, tree.error handler
├── utils.py                   # 🔧 Utilidades — Carga de .env, constantes globales, sistema de permisos, helpers de DB y cooldowns
├── tema.py                    # 🎨 Sistema Visual — Paleta de colores (TemaBot), emojis (Emojis), constructor centralizado de embeds V2 (construir_embed)
├── cogs/
│   ├── economia.py            # 💰 Cog de Economía — Trabajo, crimen, banco, transferencias, leaderboard, comandos admin de dinero
│   ├── casino.py              # 🎰 Cog de Casino — Blackjack interactivo, Ruleta multijugador con apuestas persistentes
│   ├── policia.py             # 🚔 Cog Policial — Arrestos con timeout, multas, búsqueda y captura, consulta de dominio vehicular
│   └── roleplay.py            # 🪪 Cog de Roleplay — Solicitud/aprobación de DNI, gestión de personajes, vehículos, licencias, reclamos de robo
├── .env                       # 🔐 Variables de entorno (NO versionar en producción)
├── roleplay.db                # 💾 Base de datos SQLite (generada automáticamente)
├── mensaje_modelo.json        # 📋 Template JSON de mensaje de bienvenida (Component-Based V2)
├── dni_template.png           # 🖼️ Plantilla gráfica para la generación de DNI
├── dni_template_fondo.png     # 🖼️ Fondo alternativo de DNI
├── profugo_template.png       # 🖼️ Plantilla gráfica para el cartel de búsqueda y captura
├── Helvetica-Bold.ttf         # 🔤 Fuente tipográfica para las imágenes generadas
├── requirements.txt           # 📦 Dependencias del proyecto
├── refactor.py                # 🛠️ Script one-shot de migración: sqlite3 sync → aiosqlite async (ya ejecutado, NO re-ejecutar)
└── refactor_db.py             # 🛠️ Script one-shot de refactorización: utils.db global → interaction.client.db (ya ejecutado, NO re-ejecutar)
```

### Flujo de Inicio (`setup_hook`)

1. Se conecta a `roleplay.db` con `aiosqlite` y configura pragmas de rendimiento (`WAL`, `NORMAL`, `busy_timeout`).
2. Ejecuta `init_db()` que crea o verifica todas las tablas y aplica migraciones de columnas (`ALTER TABLE ... ADD COLUMN`).
3. Carga los 4 cogs en orden: `economia` → `casino` → `policia` → `roleplay`.
4. Sincroniza el árbol de slash commands con Discord (`tree.sync()`).

### Patrón de Acceso a Base de Datos

La conexión a la DB **NO** es global. Reside en `bot.db` (atributo de la instancia `AmbaBot`). Dentro de los cogs, se accede a ella vía `interaction.client.db`. El caché de sesiones activas (`bot.sesiones_cache`) sigue el mismo patrón: `interaction.client.sesiones_cache`.

---

## 3. Manejo de Datos

### Motor de Base de Datos

- **Motor:** SQLite 3 (a través de `aiosqlite`)
- **Archivo:** `roleplay.db` (raíz del proyecto)
- **Modo Journal:** WAL (Write-Ahead Logging)
- **Conexión:** Única instancia almacenada en `AmbaBot.db`, abierta en `setup_hook()` y cerrada en `close()`
- **Timeout:** 15 segundos (`PRAGMA busy_timeout=15000`)

### Esquema de Tablas

#### `sesiones`
> Gestiona qué slot (personaje) tiene activo cada usuario. Cache en memoria en `bot.sesiones_cache`.

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `user_id` | `INTEGER` | `PRIMARY KEY` | ID de Discord del usuario |
| `slot_activo` | `INTEGER` | `DEFAULT 1` | Slot actualmente activo (1 o 2) |

#### `usuarios`
> Tabla principal de personajes. Cada usuario puede tener hasta 2 slots.

| Columna | Tipo | Default | Descripción |
|---|---|---|---|
| `id_usuario` | `INTEGER` | — | ID de Discord |
| `slot` | `INTEGER` | — | Número de slot (1 o 2) |
| `nombres` | `TEXT` | — | Nombre del personaje |
| `apellidos` | `TEXT` | — | Apellido del personaje |
| `fecha_nacimiento` | `TEXT` | — | Formato `DD/MM/AAAA` |
| `genero` | `TEXT` | — | `Masculino`, `Femenino`, `No Binario` |
| `nacionalidad` | `TEXT` | — | País de origen RP |
| `domicilio` | `TEXT` | — | Dirección RP |
| `dinero_mano` | `INTEGER` | `0` | Efectivo en mano |
| `dinero_banco` | `INTEGER` | `0` | Saldo bancario |
| `licencias_conducir` | `TEXT` | `''` | Lista CSV de licencias de conducir |
| `licencias_armas` | `TEXT` | `''` | Lista CSV de credenciales ANMAC |
| `trabajo` | `TEXT` | `'Desempleado'` | Profesión RP |
| `busqueda_captura` | `BOOLEAN` | `0` | Si está en búsqueda y captura |
| `arrestado` | `BOOLEAN` | `0` | Si está preso |
| `tiempo_carcel` | `TEXT` | `''` | Descripción textual de la condena |
| `last_work` | `TEXT` | `NULL` | Timestamp ISO del último `/eco work` |
| `last_crime` | `TEXT` | `NULL` | Timestamp ISO del último `/eco crime` |
| `last_collect` | `TEXT` | `NULL` | Timestamp ISO del último `/eco collect` |
| `imagen_url` | `TEXT` | `''` | URL del avatar de Roblox (para DNI) |
| `nro_doc` | `TEXT` | `''` | Número de documento (8 dígitos random) |
| `roblox_user` | `TEXT` | `''` | Username de Roblox vinculado |

**PK compuesta:** `(id_usuario, slot)`

#### `vehiculos`

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id_vehiculo` | `INTEGER` | `PK AUTOINCREMENT` | ID interno |
| `id_usuario` | `INTEGER` | — | Dueño (Discord ID) |
| `slot` | `INTEGER` | — | Slot del personaje dueño |
| `modelo` | `TEXT` | — | Modelo del vehículo |
| `patente` | `TEXT` | — | Dominio/patente única |

#### `multas`

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id_multa` | `INTEGER` | `PK AUTOINCREMENT` | Folio de la multa |
| `id_usuario` | `INTEGER` | — | Infractor (Discord ID) |
| `motivo` | `TEXT` | — | Razón de la multa |
| `monto` | `INTEGER` | — | Monto a pagar |
| `oficial_id` | `INTEGER` | — | ID del oficial que la emitió |
| `pagada` | `BOOLEAN` | `DEFAULT 0` | Estado de pago |
| `fecha` | `TEXT` | — | Fecha de emisión `DD/MM/AAAA` |

#### `antecedentes`

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id_antecedente` | `INTEGER` | `PK AUTOINCREMENT` | ID interno |
| `id_usuario` | `INTEGER` | — | Discord ID del acusado |
| `delito` | `TEXT` | — | Descripción del delito |
| `oficial_id` | `INTEGER` | — | ID del oficial que lo registró |
| `fecha` | `TEXT` | — | Fecha del registro |

#### `ruleta_estado`

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `guild_id` | `INTEGER` | `PRIMARY KEY` | ID del servidor |
| `activa` | `BOOLEAN` | `DEFAULT 0` | Si hay una ronda de ruleta en curso |

#### `ruleta_apuestas`

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id_apuesta` | `INTEGER` | `PK AUTOINCREMENT` | ID de la apuesta |
| `guild_id` | `INTEGER` | — | Servidor donde se realizó |
| `id_usuario` | `INTEGER` | — | Apostador (Discord ID) |
| `slot` | `INTEGER` | — | Slot del personaje apostador |
| `monto` | `INTEGER` | — | Monto apostado |
| `opcion` | `TEXT` | — | Opción elegida (número, color, paridad) |

#### `logs`

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id_log` | `INTEGER` | `PK AUTOINCREMENT` | ID del log |
| `usuario_id` | `INTEGER` | — | Discord ID |
| `usuario_nombre` | `TEXT` | — | Nombre de usuario de Discord |
| `comando` | `TEXT` | — | Nombre del comando ejecutado |
| `argumentos` | `TEXT` | — | Argumentos del comando |
| `fecha` | `TEXT` | — | Timestamp `YYYY-MM-DD HH:MM:SS` |

#### `arrestos`

| Columna | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id_usuario` | `INTEGER` | `PRIMARY KEY` | Discord ID del preso |
| `id_guild` | `INTEGER` | — | Servidor donde fue arrestado |
| `fecha_liberacion` | `REAL` | — | Timestamp Unix de liberación programada |

### Archivos Locales

| Archivo | Formato | Uso |
|---|---|---|
| `mensaje_modelo.json` | JSON | Template del mensaje de bienvenida usando Component-Based Messages V2 (tipo 17 = Container, tipo 12 = MediaGallery, tipo 9 = Section, tipo 10 = TextDisplay, tipo 14 = Separator) |
| `dni_template.png` | PNG | Plantilla visual para generar la imagen del DNI de un personaje |
| `dni_template_fondo.png` | PNG | Fondo alternativo de DNI |
| `profugo_template.png` | PNG | Plantilla visual para generar el cartel de búsqueda y captura |
| `Helvetica-Bold.ttf` | TTF | Fuente usada en la generación de imágenes |

---

## 4. Inventario de Comandos

### Cog: `Economia` (sin grupo, comandos top-level)

| Comando | Tipo | Descripción | Permisos |
|---|---|---|---|
| `/work` | Slash | Trabajar y ganar dinero (cooldown 1h por slot) | Ninguno (requiere personaje) |
| `/crime` | Slash | Cometer un crimen (cooldown 2h por slot) | Requiere rol de `ROLES_CRIMINALES` |
| `/deposit` | Slash | Depositar efectivo al banco (acepta `todo`) | Ninguno |
| `/withdraw` | Slash | Retirar dinero del banco (acepta `todo`) | Ninguno |
| `/pay` | Slash | Transferir dinero a otro ciudadano (acepta `todo`, con confirmación) | Ninguno |
| `/balance` | Slash | Ver saldo propio o de otro usuario (abre billetera interactiva si es propio) | Ninguno |
| `/top` | Slash | Leaderboard global de los más ricos (paginado, sin pings) | Ninguno |
| `/collect` | Slash | Cobrar ingresos de roles autorizados (cooldown 24h, impuesto de $50,000) | Requiere roles en `INGRESOS_ROLES` |
| `/add_money` | Slash | ADMIN: Añadir dinero a un ciudadano | `PERMISO_ECONOMIA` |
| `/remove_money` | Slash | ADMIN: Quitar dinero (acepta `todo`) | `PERMISO_ECONOMIA` |
| `/reseteo_personaje` | Slash | ADMIN: Resetear dinero de un personaje a $0 (requiere `CONFIRMO`) | `PERMISO_MANEJO_DNI` |
| `/reseteo_economia` | Slash | ADMIN: WIPE total de toda la economía (requiere `CONFIRMO`) | `PERMISO_ADMIN` |

> **Nota:** La billetera interactiva (`BilleteraView`) expone botones de **Transferir**, **Depositar** y **Retirar** que abren modales (`BankModal`, `TransferModal`) sin necesidad de comandos slash adicionales.

### Cog: `Casino` (sin grupo, comandos top-level)

| Comando | Tipo | Descripción | Permisos |
|---|---|---|---|
| `/blackjack` | Slash | Partida de Blackjack interactiva (6 mazos, botones Pedir/Plantarse/Doblar) | Ninguno (apuesta mín. $50) |
| `/roulette` | Slash | Ruleta multijugador (30s de espera, opciones: 0-36, rojo/negro/verde, par/impar, 1-18/19-36) | Ninguno (apuesta mín. $50) |

> **Nota:** La ruleta usa `secrets.randbelow(37)` para generación criptográficamente segura. Al reiniciar el bot, `cog_load()` reembolsa automáticamente apuestas pendientes.

### Cog: `Policia` (sin grupo, comandos top-level)

| Comando | Tipo | Descripción | Permisos |
|---|---|---|---|
| `/arrestar` | Slash | Arrestar a un usuario con timeout real de Discord + rol Preso (requiere foto de prueba) | `PERMISO_POLICIAL` |
| `/liberar` | Slash | OVERRIDE: Liberar a un preso inmediatamente | `administrator` (permiso nativo de Discord) |
| `/multar` | Slash | Emitir una multa con monto y motivo (requiere foto de prueba) | `PERMISO_POLICIAL` |
| `/ver_multas` | Slash | Ver multas pendientes (propias o de otros) | `PERMISO_CIVIL` (ver multas ajenas requiere `PERMISO_POLICIAL`) |
| `/pagar_multa` | Slash | Pagar una multa propia pendiente (descuenta del efectivo) | Ninguno |
| `/revocar_multa` | Slash | ADMIN: Revocar/cancelar una multa sin cobrar | `PERMISO_ADMIN` |
| `/buscar_dominio` | Slash | Consultar datos de registro de una patente vehicular | `PERMISO_POLICIAL` |
| `/busqueda` | Slash | Activar/Desactivar búsqueda y captura (genera cartel con Pillow) | `PERMISO_ADMIN` |

> **Nota:** El cog tiene un `tasks.loop(seconds=60)` llamado `check_presos` que automáticamente libera a los presos cuando se cumple su condena.

### Cog: `Roleplay` (sin grupo, comandos top-level)

| Comando | Tipo | Descripción | Permisos |
|---|---|---|---|
| `/solicitar_dni` | Slash | Crear personaje y generar DNI gráfico (pasa por revisión de Staff) | Ninguno (Slot 2 requiere `ID_LLAVE_SLOT_2`) |
| `/mis_personajes` | Slash | Ver tus slots y cambiar personaje activo vía select menu | Ninguno |
| `/cambiar_personaje` | Slash | Cambiar entre Slot 1 y 2 directamente | `PERMISO_2DO_PERSONAJE` |
| `/forzar_cambio_pj` | Slash | ADMIN: Cambiar forzosamente el slot activo de un usuario | `administrator` |
| `/ciudadano` | Slash | Mostrar DNI gráfico + ficha policial completa de un personaje | `PERMISO_CIVIL` |
| `/eliminar_ciudadano` | Slash | STAFF: Borrar permanentemente un personaje (requiere `CONFIRMO`) | `PERMISO_MANEJO_DNI` |
| `/editar_ciudadano` | Slash | STAFF: Modificar datos de un personaje (Nombres, Apellidos, Fecha, etc.) | `PERMISO_MANEJO_DNI` |
| `/registrar_vehiculo` | Slash | Registrar un vehículo a un ciudadano | `PERMISO_MANEJO_LICENCIAS` |
| `/retirar_vehiculo` | Slash | Dar de baja un vehículo | `PERMISO_MANEJO_LICENCIAS` |
| `/licencia_conducir` | Slash | Otorgar/Revocar/Suspender/Reactivar licencia de conducir | `PERMISO_MANEJO_LICENCIAS` |
| `/licencia_armas` | Slash | Otorgar/Revocar/Suspender/Reactivar credencial ANMAC | `PERMISO_MANEJO_LICENCIAS` |
| `/reclamar_robo` | Slash | Enviar reclamo de robo al canal de reclamos para revisión de Staff | Ninguno (requiere 2 fotos de prueba) |

### Sistema de Permisos

Los permisos se gestionan con el decorador `@utils.tiene_permiso()` que acepta una lista de IDs de roles. Las combinaciones predefinidas son:

| Constante | Roles Incluidos |
|---|---|
| `PERMISO_ADMIN` | Dueño, Staff |
| `PERMISO_POLICIAL` | Dueño, Staff, Policía |
| `PERMISO_CIVIL` | Dueño, Staff, Policía, Civil |
| `PERMISO_2DO_PERSONAJE` | Llave Slot 2, Dueño |
| `PERMISO_ECONOMIA` | Economía, Dueño |
| `PERMISO_MANEJO_DNI` | Manejo DNI, Dueño |
| `PERMISO_MANEJO_LICENCIAS` | Manejo Licencias, Dueño, Staff |

> **Regla especial:** `ID_DUENO` siempre bypasea cualquier check de permisos (hardcodeado en `tiene_permiso()`).

---

## 5. Eventos (Listeners)

| Evento | Archivo | Línea | Descripción |
|---|---|---|---|
| `on_ready` | `main.py` | L233 | Imprime confirmación y establece presencia con `discord.gg/amba` |
| `on_disconnect` | `main.py` | L245 | Loguea desconexión del Gateway |
| `on_resumed` | `main.py` | L250 | Loguea reconexión exitosa del Gateway |
| `on_interaction` | `main.py` | L255 | Intercepta todas las interacciones. Si `MODO_DESARROLLO=1`, bloquea comandos a usuarios no-Staff |
| `on_tree_error` (tree.error) | `main.py` | L282 | Handler global de errores de `app_commands`. Gestiona: `MissingAnyRole`, `MissingPermissions`, `CommandOnCooldown`, `CheckFailure` y errores genéricos con envío al canal de alertas |
| `on_app_command_completion` | `main.py` | L354 | Listener que registra cada ejecución exitosa de slash command: inserta en tabla `logs` y envía embed al canal de logs |
| `check_presos` (tasks.loop) | `cogs/policia.py` | L168 | Loop de 60 segundos que libera automáticamente a los presos cuando se cumple `fecha_liberacion` |
| `cog_load` (Casino) | `cogs/casino.py` | L281 | Al cargar el cog, reembolsa apuestas de ruleta pendientes que quedaron atrapadas en la DB (recovery por reinicio) |

### Shutdown Seguro

El método `AmbaBot.close()` (`main.py:213`) ejecuta un cierre limpio:
1. Commit de transacciones pendientes.
2. Cierre de la conexión `aiosqlite`.
3. Desconexión de Discord.

---

## 6. Reglas de Desarrollo (Directivas para IA)

> ⚠️ **OBLIGATORIO:** Cualquier agente de IA o desarrollador que modifique este código DEBE cumplir con las siguientes reglas sin excepción.

### 6.1. Reglas de Arquitectura

1. **Todo I/O DEBE ser asíncrono.** Nunca usar `sqlite3` síncrono, `requests`, `open()` bloqueante para imágenes, ni ninguna operación que bloquee el event loop. Usar `aiosqlite`, `aiohttp`, `asyncio.to_thread()` para CPU-bound (como generación de imágenes con Pillow).

2. **No modificar el event loop de asyncio.** Nunca llamar a `asyncio.run()`, `loop.run_until_complete()`, ni `asyncio.set_event_loop()` dentro del bot. El event loop es gestionado exclusivamente por `discord.py` y `bot.run()`.

3. **No crear conexiones globales a la DB.** La conexión a SQLite reside en `bot.db` (instancia de `AmbaBot`). Dentro de los cogs, accederla SIEMPRE via `interaction.client.db`. Nunca crear variables globales `db = ...`.

4. **Respetar el caché de sesiones.** El slot activo del usuario se obtiene con `utils.get_slot_activo(user_id, db, cache)`. Nunca consultar la tabla `sesiones` directamente sin pasar por la función de caché.

5. **Priorizar `app_commands` (Slash Commands).** Todo comando nuevo DEBE ser un Slash Command (`@app_commands.command`). No crear comandos de prefijo (`@bot.command`). El prefijo `am!` existe solo por compatibilidad y NO se usa activamente.

6. **Registrar comandos en un Cog `GroupCog` o `Cog` existente.** No crear comandos sueltos en `main.py`. Los nuevos comandos deben ir en el cog temáticamente correcto o en un nuevo cog dentro de `cogs/`.

### 6.2. Reglas de UI y Mensajería

7. **Usar el sistema de Component-Based Messages V2.** Este bot usa `discord.ui.LayoutView`, `discord.ui.Container`, `discord.ui.Section`, `discord.ui.TextDisplay`, `discord.ui.MediaGallery`, `discord.ui.Separator`, y `discord.ui.Thumbnail`. **NUNCA** enviar `discord.Embed` tradicionales directamente. Usar siempre `construir_embed()` de `tema.py` y enviar via `view=discord.ui.LayoutView().add_item(container)`.

8. **Enviar mensajes con `view=` y no con `embed=`.** Patrón correcto:
   ```python
   container = construir_embed(tipo="exito", descripcion="Mensaje")
   await interaction.response.send_message(view=discord.ui.LayoutView().add_item(container))
   ```

9. **Respetar la paleta de colores y emojis centralizados.** Usar `TemaBot` para colores y `Emojis` para iconos. No hardcodear emojis ni colores en los cogs.

10. **Mensajes de error deben ser descriptivos y formales.** Seguir el patrón existente: una línea de descripción general, seguida de `**Motivo:**` con bullets `•` para detalles.

### 6.3. Reglas de Base de Datos

11. **Usar `async with db.execute(...)` como context manager.** Patrón estándar:
    ```python
    async with interaction.client.db.execute("SELECT ...", (params,)) as cur:
        result = await cur.fetchone()
    ```

12. **Siempre llamar `await db.commit()` después de operaciones de escritura.** Los `INSERT`, `UPDATE`, y `DELETE` requieren commit explícito.

13. **Validar fondos con `WHERE ... AND dinero_mano >= ?` y verificar `rowcount`.** Para operaciones económicas atómicas, usar el patrón:
    ```python
    async with db.execute("UPDATE usuarios SET dinero_mano = dinero_mano - ? WHERE ... AND dinero_mano >= ?", (monto, ..., monto)) as cur:
        if cur.rowcount == 0:
            # Fondos insuficientes o condición de carrera
    ```

14. **No agregar columnas directamente. Usar el patrón de migración existente.** En `init_db()` se usa `ALTER TABLE ... ADD COLUMN` envuelto en `try/except aiosqlite.OperationalError: pass`. Seguir ese mismo patrón.

15. **Whitelist de columnas de cooldown.** Solo las columnas en `utils.COOLDOWN_COLUMNS` (`last_work`, `last_crime`, `last_collect`) son válidas para `check_cooldown_pro()` y `update_cooldown()`. Si se agrega un nuevo cooldown, incluirlo en ese set.

### 6.4. Reglas de Seguridad

16. **Nunca exponer tokens, IDs secretos ni datos sensibles en el código.** Toda configuración sensible va en `.env` y se accede vía `os.getenv()`.

17. **Validar tipo de archivo en attachments.** Antes de procesar un `discord.Attachment` como imagen, verificar que `attachment.content_type.startswith("image/")`.

18. **Respetar el sistema de permisos.** Usar `@utils.tiene_permiso()` con las constantes predefinidas. Nunca crear lógica de permisos ad-hoc sin pasar por el decorador.

19. **No eliminar ni modificar `refactor.py` ni `refactor_db.py`.** Son scripts de migración ya ejecutados. Se mantienen como referencia histórica.

### 6.5. Reglas de Rendimiento

20. **Procesamiento de imágenes en `asyncio.to_thread()`.** Toda operación de Pillow (generación de DNI, cartel de búsqueda) debe ejecutarse en un thread separado:
    ```python
    buffer = await asyncio.to_thread(generar_imagen_dni, ...)
    ```

21. **Cachear datos que se consultan frecuentemente.** El bot ya usa caché para sesiones activas y avatares de Roblox. Seguir este patrón para nuevas features.

22. **Limitar embeds a los límites de Discord.** Truncar textos largos con slicing (ej: `[:1000]`) antes de enviarlos en embeds.

### 6.6. Reglas de Estilo de Código

23. **Idioma del código: Español.** Variables, funciones, docstrings y mensajes al usuario están en español. Mantener esta convención.

24. **Logging con `logging.getLogger()`.** Cada módulo/cog debe crear su propio logger: `logger = logging.getLogger("cogs.nombre")`. No usar `print()` para errores o warnings en producción.

25. **Manejo de errores silencioso para DMs fallidos.** Al enviar DMs al usuario, siempre envolver en `try/except (discord.HTTPException, discord.Forbidden): pass` ya que el usuario puede tener DMs desactivados.

---

## Apéndice: Mapas de Configuración Adicionales

### `INGRESOS_ROLES` (recaudación diaria con `/eco collect`)

Diccionario en `utils.py` que mapea `ID_ROL → (monto, slot_requerido)`:
- `slot_requerido = 0` significa que aplica a cualquier slot activo.
- `slot_requerido = 1 o 2` significa que solo cobra si el slot activo coincide.

### `VALORES_ROBOS` (montos de reclamos de robo)

| Tipo de Robo | Monto |
|---|---|
| Auto Baja calidad | $250,000 |
| Auto Media calidad | $300,000 |
| Auto Alta calidad | $500,000 |
| Caja Registradora | $30,000 |
| Banco | $2,000,000 |
| ATM | $100,000 |
| Joyería | $1,250,000 |
| Tienda | $250,000 |
| Casas | $200,000 |
