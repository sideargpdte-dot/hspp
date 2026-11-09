# Análisis del Proyecto: AmbaReborn2

Este documento presenta un análisis completo de la estructura del bot de Discord **AmbaReborn2**, identificando su flujo de ejecución principal, la gestión de eventos y el mapeo de todos los comandos disponibles.

---

## 1. Estructura y Dependencias Principales
El proyecto es un bot de Discord programado en **Python** haciendo uso de la librería `discord.py` y enfocándose fuertemente en integraciones visuales, sistema de multislot de personajes y bases de datos locales.

**Archivos Principales:**
- **`main.py`**: El núcleo de la aplicación donde residen los eventos, comandos y la lógica principal del bot (~2200 líneas).
- **`tema.py`**: Archivo complementario para la creación y gestión visual de embeds y plantillas de diseño (`TemaBot`, `Emojis`).
- **`refactor.py`**: Aparentemente un script secundario o de mantenimiento.
- **`roleplay.db`**: Base de datos SQLite manejada a través de `aiosqlite`.
- **`.env`**: Archivo de configuración con tokens, IDs de canales (logs, revisión de DNI) e IDs de roles.
- **Plantillas Gráficas (`.png`) y Fuentes (`.ttf`)**: Usadas junto con `Pillow (PIL)` para generar credenciales/DNIs gráficos.

**Dependencias Críticas:**
- `discord.py`: Interfaz principal con Discord.
- `aiosqlite`: Manejo asíncrono de la base de datos local SQLite.
- `Pillow`: Generación dinámica de imágenes (DNI, licencias).
- `curl_cffi`: Utilizado para evadir restricciones de Cloudflare (TLS Fingerprinting) al hacer peticiones web, como obtener la imagen del avatar de Roblox.

---

## 2. Flujo Principal de Ejecución
1. **Inicialización y Configuración**:
   - Al arrancar, el bot carga las variables de entorno de `.env` (tokens, IDs de dueños, staff, roles, y canales).
   - Se instancian las herramientas principales de base de datos y diseño.
2. **Evento `on_ready` (Arranque del Sistema)**:
   - Se cargan los **Grupos de Comandos (Slash Commands)** en el árbol (tree) del bot.
   - Se verifican o crean automáticamente las tablas en `roleplay.db` (ej: tablas `arrestos` y `logs`).
   - Inicia el **Sistema de Vigilancia** (`check_presos` background task), que se encarga de revisar los tiempos de condena automáticamente.
   - Sincroniza todos los comandos con Discord para que aparezcan en la interfaz gráfica.
3. **Interacción Continua**:
   - El bot escucha las interacciones de los usuarios a través de comandos de barra (`/`).
   - Gran parte de la lógica central verifica **qué "Slot" de personaje** (1 o 2) tiene activo el usuario actual antes de operar sobre su economía o DNI.

---

## 3. Mapeo de Comandos (Slash Commands)
Los comandos están estructurados en tres grupos principales (Cogs/App Command Groups):

### 🎭 Grupo `/rp` (Roleplay, Identidad y Policial)
Gestión completa de los personajes de los jugadores, licencias y sistema de justicia.

| Comando | Descripción | Acceso |
|---------|-------------|--------|
| `/rp solicitar_dni` | Crea un personaje y DNI. Pasa por revisión del Staff. | Todos |
| `/rp mis_personajes` | Visualiza slots y permite cambiar de personaje. | Todos |
| `/rp cambiar_personaje` | Cambia entre el Slot 1 y el Slot 2. | Todos |
| `/rp forzar_cambio_pj` | Cambia forzosamente el slot activo de un usuario. | Staff / Admin |
| `/rp ciudadano` | Muestra el DNI gráfico y la Ficha Policial del PJ ACTIVO. | Todos |
| `/rp eliminar_ciudadano` | Borra un personaje permanentemente de la BD. | Staff |
| `/rp editar_ciudadano` | Modifica datos de un personaje. | Staff |
| `/rp licencia_conducir` | Gestiona licencias de tránsito del PJ ACTIVO. | Roles Autorizados |
| `/rp licencia_armas` | Gestiona credenciales ANMAC del PJ ACTIVO. | Roles Autorizados |
| `/rp multar` | Emite una multa económica al PJ ACTIVO de otro usuario. | Policía |
| `/rp ver_multas` | Permite visualizar multas pendientes. | Policía / Todos |
| `/rp busqueda` | Activa/Desactiva orden de búsqueda y captura. | Policía |

### 💰 Grupo `/eco` (Economía y Banco)
Manejo monetario, empleos básicos, y sistema de moderación económica.

| Comando | Descripción | Acceso |
|---------|-------------|--------|
| `/eco work` | Comando de trabajo legal (cooldown de 1h). | Todos |
| `/eco crime` | Comando de trabajo ilegal/crimen (cooldown de 2h). | Todos |
| `/eco deposit` | Depositar dinero en el banco (Acepta 'todo'). | Todos |
| `/eco withdraw` | Retirar dinero del banco (Acepta 'todo'). | Todos |
| `/eco pay` | Pagar a otro ciudadano (Acepta 'todo'). | Todos |
| `/eco balance` | Ver saldo (efectivo y banco) del PJ activo. | Todos |
| `/eco top` | Ranking global de la economía en el servidor. | Todos |
| `/eco add_money` | Añadir dinero a un usuario. | Admin |
| `/eco remove_money`| Quitar dinero a un usuario (Acepta 'todo'). | Admin |
| `/eco reseteo_personaje`| Resetear el dinero del personaje ACTIVO a $0. | Admin |
| `/eco reseteo_economia` | WIPE TOTAL: Resetea todos los slots de economía. | Admin |
| `/eco collect` | Recoger ingresos diarios / Impuesto automático. | Roles Específicos|

### 🎰 Grupo `/casino` (Juegos de Azar y Apuestas)
Sistemas para apostar dinero de forma aleatoria dentro del rol.

| Comando | Descripción | Acceso |
|---------|-------------|--------|
| `/casino bj` | Minijuego de Blackjack apostando saldo. | Todos |
| `/casino roulette` | Ruleta multijugador apostando saldo. | Todos |

---

## 4. Tareas en Segundo Plano (Tasks) y Eventos Notables
- **`@bot.event async def on_ready()`**: Se ejecuta en el primer arranque. Prepara DB y sincroniza comandos.
- **`check_presos` (Task)**: Un loop de fondo (`@tasks.loop()`) que revisa si el tiempo de condena policial de un personaje en la tabla de `arrestos` ha expirado, y si es así, levanta el rol de preso.
- **Peticiones a la API de Roblox**: Se incluye un bypass complejo (usando `curl_cffi` para suplantar a Chrome) para leer IDs y descargar las imágenes del Avatar de Roblox (para los DNI), evitando bloqueos anti-bot.
