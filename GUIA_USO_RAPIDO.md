# ⚡ GUÍA DE USO RÁPIDO - Sistema CAD/MDT

## 🚀 Inicio Rápido (10 minutos)

### PASO 1: Configurar Backend (5 min)

```bash
# 1. Abrir terminal en la carpeta del proyecto
cd "C:\Users\AMD-TUF\OneDrive\BOT AMBA - DE SUPER\backend"

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env
notepad .env
```

**Editar `.env` con estos valores MÍNIMOS:**
```env
# Discord OAuth (desde Developer Portal)
DISCORD_CLIENT_ID=TU_CLIENT_ID
DISCORD_CLIENT_SECRET=TU_CLIENT_SECRET
DISCORD_REDIRECT_URI=http://localhost:3000/callback
DISCORD_GUILD_ID=TU_SERVER_ID

# Bot token (del .env del bot)
DISCORD_TOKEN=TU_BOT_TOKEN

# JWT (genera una clave aleatoria)
JWT_SECRET_KEY=clave_super_segura_y_larga_de_minimo_32_caracteres_12345

# Secret compartido
WEB_API_SECRET=clave_secreta_compartida

# IDs de roles (copiar del .env del bot)
ID_DUENO=tu_discord_id
ID_STAFF=id_rol_staff
ID_POLICIA=id_rol_policia
ID_CIVIL=id_rol_civil
# ... resto de IDs
```

```bash
# 5. Verificar configuración
python test_setup.py
# Debe mostrar: ✅ TODO LISTO

# 6. Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

**Servidor corriendo en:** http://localhost:8000

---

### PASO 2: Probar el Backend (2 min)

Abre tu navegador en: **http://localhost:8000/docs**

Verás la documentación interactiva (Swagger UI) con TODOS los endpoints:

#### **Probar Login:**
1. Ve a `GET /api/v1/auth/login`
2. Click en "Try it out" → "Execute"
3. Copia la `authorization_url` que aparece en la respuesta
4. Ábrela en una nueva pestaña
5. Autoriza en Discord
6. Recibirás un JWT (cópialo)

#### **Probar consulta de saldo:**
1. Ve a `GET /api/v1/economia/balance`
2. Click en "Try it out"
3. Click en el candado 🔒 → Pega tu JWT → "Authorize"
4. Click en "Execute"
5. ¡Verás tu saldo!

---

### PASO 3: Integrar con el Bot (3 min)

```bash
# 1. Copiar script de integración
copy integracion_bot_web.py ..\integracion_bot_web.py
```

```python
# 2. Editar main.py del BOT (agregar al final de setup_hook):
from integracion_bot_web import inicializar_integracion
inicializar_integracion()

# 3. Agregar al método close() del bot (ANTES de super().close()):
from integracion_bot_web import cerrar_integracion
await cerrar_integracion()

# 4. Agregar al .env del BOT:
WEB_API_URL=http://localhost:8000
WEB_API_SECRET=clave_secreta_compartida  # La misma del backend
```

```python
# 5. En cogs/economia.py, después de una transferencia exitosa:
from integracion_bot_web import emitir_evento_web

# Notificar al destinatario
await emitir_evento_web(
    'economia.transferencia',
    target_uid,
    {
        'tipo': 'recibida',
        'monto': monto_real,
        'remitente': f"{me[0]} {me[1]}",
        'nuevo_saldo': target[2] + monto_real
    }
)
```

---

## 📡 Endpoints Disponibles

### **Autenticación** (6 endpoints)
```
GET  /api/v1/auth/login          # Iniciar OAuth
GET  /api/v1/auth/callback       # Callback Discord
POST /api/v1/auth/logout         # Cerrar sesión
GET  /api/v1/auth/me             # Info usuario actual
GET  /api/v1/auth/verify         # Verificar token
POST /api/v1/auth/refresh        # Refrescar token
```

### **Ciudadanos / CAD** (6 endpoints)
```
GET  /api/v1/ciudadanos/me                   # Mi personaje
POST /api/v1/ciudadanos/cambiar-slot         # Cambiar slot
GET  /api/v1/ciudadanos/dni/{dni}            # ⭐ CAD: Buscar por DNI
GET  /api/v1/ciudadanos/buscar               # Búsqueda avanzada
GET  /api/v1/ciudadanos/{id}/{slot}          # Personaje específico
PUT  /api/v1/ciudadanos/{id}/{slot}          # Actualizar
```

### **Economía** (6 endpoints)
```
GET  /api/v1/economia/balance        # Consultar saldo
POST /api/v1/economia/transferir     # Transferir dinero
POST /api/v1/economia/depositar      # Depositar en banco
POST /api/v1/economia/retirar        # Retirar efectivo
GET  /api/v1/economia/leaderboard    # Top ricos
POST /api/v1/economia/ajustar        # Ajustar dinero (admin)
```

### **Multas** (5 endpoints)
```
GET    /api/v1/multas/mis-multas         # Mis multas
POST   /api/v1/multas/emitir             # Emitir multa (policía)
POST   /api/v1/multas/{folio}/pagar      # Pagar multa
DELETE /api/v1/multas/{folio}/revocar    # Revocar (admin)
```

### **WebSocket**
```
WS /ws?token=JWT                     # Conexión tiempo real
```

**Total: 24 endpoints REST + 1 WebSocket** ✅

---

## 🧪 Ejemplos de Uso

### Consultar ciudadano por DNI (CAD Policial)

```bash
curl -H "Authorization: Bearer TU_JWT" \
     http://localhost:8000/api/v1/ciudadanos/dni/12345678
```

**Respuesta:**
```json
{
  "id_usuario": 123456789,
  "slot": 1,
  "nombres": "Juan",
  "apellidos": "Pérez",
  "nro_doc": "12345678",
  "estado_legal": "LIBRE",
  "dinero_mano": 5000,
  "dinero_banco": 15000,
  "vehiculos": [
    {"id": 1, "modelo": "Chevrolet Cruze", "patente": "ABC123"}
  ],
  "multas": [
    {"id": 45, "monto": 2500, "motivo": "Exceso de velocidad", "pagada": false}
  ],
  "historial_arrestos": [],
  "orden_busqueda": null
}
```

### Transferir dinero

```bash
curl -X POST \
     -H "Authorization: Bearer TU_JWT" \
     -H "Content-Type: application/json" \
     -d '{"destinatario_discord_id": 987654321, "monto": 5000}' \
     http://localhost:8000/api/v1/economia/transferir
```

### Conectar WebSocket (JavaScript)

```javascript
const token = 'TU_JWT';
const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

ws.onopen = () => {
    console.log('✅ Conectado al servidor');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('📨 Evento recibido:', data);
    
    // data.type = 'economia.transferencia'
    // data.data = { monto: 5000, remitente: 'Juan Pérez', ... }
    
    // Actualizar UI automáticamente
    if (data.type === 'economia.transferencia') {
        alert(`💸 Recibiste $${data.data.monto} de ${data.data.remitente}`);
    }
};

// Mantener conexión viva
setInterval(() => {
    ws.send('ping');
}, 30000);
```

---

## 🔧 Troubleshooting

### Error: "Token inválido"
**Solución:** El JWT expiró (24h). Obtén uno nuevo en `/auth/login`

### Error: "Base de datos no encontrada"
**Solución:** Ejecuta primero el bot para que cree `roleplay.db`

### Error: "DISCORD_CLIENT_ID not configured"
**Solución:** Revisa tu archivo `.env`, falta configurar las variables

### WebSocket no conecta
**Solución:** Verifica que el token sea válido y esté en la URL: `ws://...?token=JWT`

### El bot no envía eventos a la web
**Solución:** 
1. Verifica que agregaste `inicializar_integracion()` en el bot
2. Verifica que `WEB_API_SECRET` sea el mismo en bot y backend
3. Revisa los logs del backend: `uvicorn app.main:app --reload --log-level debug`

---

## 📊 Monitoreo

### Ver logs del servidor
```bash
# El servidor imprime logs en la consola
# Formato: [timestamp] [LEVEL] module: message

✅ WebSocket conectado: Usuario 123456789
💸 Transferencia: Juan Pérez → María González ($5,000)
🚨 Multa #45 emitida a Juan Pérez por $2,500
```

### Health check
```bash
curl http://localhost:8000/health
```

### Usuarios conectados (agregar endpoint):
```python
# En main.py, agregar:
@app.get("/api/v1/stats/connected")
async def get_connected_users():
    from app.services.websocket_service import manager
    return {
        "total_users": len(manager.get_connected_users()),
        "total_connections": manager.get_total_connections(),
        "users": manager.get_connected_users()
    }
```

---

## 🎯 Casos de Uso Comunes

### 1. Usuario consulta su saldo desde la web
```
Usuario → Frontend → GET /api/v1/economia/balance → Backend → SQLite → Response
```

### 2. Policía busca ciudadano por DNI
```
Policía → Frontend → GET /api/v1/ciudadanos/dni/12345678 → Backend (verifica permisos) → SQLite → Response con antecedentes completos
```

### 3. Usuario transfiere dinero en Discord
```
Usuario → Bot (/eco pay) → SQLite (actualiza saldos) → emitir_evento_web() → Backend (/events/emit) → WebSocket → Frontend actualiza saldo automáticamente
```

### 4. Policía multa a ciudadano en Discord
```
Policía → Bot (/multar) → SQLite (crea multa) → emitir_evento_web() → Backend → WebSocket → Usuario recibe notificación en web
```

---

## ⚡ Tips de Performance

### 1. Usar Redis para caché (opcional)
```bash
pip install redis
```

```python
# En config.py
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Cachear roles de Discord por 5 minutos
import redis
r = redis.from_url(REDIS_URL)
cached_roles = r.get(f"roles:{user_id}")
```

### 2. Optimizar consultas
```python
# Mal ❌ (N+1 queries)
for ciudadano in ciudadanos:
    vehiculos = await db.execute("SELECT * FROM vehiculos WHERE id_usuario = ?", (ciudadano.id,))

# Bien ✅ (1 query)
vehiculos = await db.execute("SELECT * FROM vehiculos WHERE id_usuario IN (?)", (ids,))
```

### 3. Comprimir respuestas
```python
# En main.py
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

---

## 🎉 ¡TODO LISTO!

Tienes un sistema **100% funcional** con:

✅ **24 endpoints REST** listos para usar
✅ **WebSocket** para tiempo real
✅ **Sincronización** Bot ↔ Web
✅ **Documentación** interactiva en `/docs`

**Próximo paso:** Crear el frontend en Next.js para tener una interfaz visual.

**¿Dudas?** Revisa los logs del servidor o usa `/docs` para probar cada endpoint.
