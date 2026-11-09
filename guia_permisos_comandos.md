# Guía de Permisos de Comandos - AMBA Reborn 2

## Índice
1. [Resumen de Comandos y Permisos](#resumen-de-comandos-y-permisos)
2. [Sistema de Permisos Explicado](#sistema-de-permisos-explicado)
3. [Cómo Cambiar Permisos](#cómo-cambiar-permisos)
4. [Variables de Entorno (.env)](#variables-de-entorno-env)

---

## RESUMEN DE COMANDOS Y PERMISOS

### Comandos de policia.py (20 comandos)

| Comando | Permiso Actual | Origen del Permiso | Ubicación en Código |
|---------|---------------|-------------------|-------------------|
| `/arrestar` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 442 |
| `/codigo-penal` | PERMISO_CIVIL | utils.py línea 98 | policia.py línea 580 |
| `/liberar` | Administrator | Discord nativo | policia.py línea 664 |
| `/multar` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 698 |
| `/ver_multas` | PERMISO_CIVIL | utils.py línea 98 | policia.py línea 859 |
| `/revocar_multa` | PERMISO_ADMIN | utils.py línea 95 | policia.py línea 938 |
| `/buscar_dominio` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 963 |
| `/busqueda` | PERMISO_ADMIN | utils.py línea 95 | policia.py línea 1017 |
| `/vehiculo_antecedente` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1128 |
| `/vehiculo_consultar` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1205 |
| `/vehiculo_robo` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1299 |
| `/vehiculo_transferir` | PERMISO_ADMIN | utils.py línea 95 | policia.py línea 1427 |
| `/ver_arrestos` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1514 |
| `/listar_denuncias` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1659 |
| `/listar_buscados` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1724 |
| `/expediente` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1795 |
| `/pay_multas` | PERMISO_CIVIL | utils.py línea 98 | policia.py línea 1921 |
| `/denuncia` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 1963 |
| `/seguimiento` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 2108 |
| `/consultar_denuncia` | PERMISO_POLICIAL | utils.py línea 96 | policia.py línea 2236 |

### Comandos de roleplay.py (12 comandos)

| Comando | Permiso Actual | Origen del Permiso | Ubicación en Código |
|---------|---------------|-------------------|-------------------|
| `/solicitar_dni` | Ninguno (público) | Sin decorador | roleplay.py línea 461 |
| `/mis_personajes` | Ninguno (público) | Sin decorador | roleplay.py línea 588 |
| `/cambiar_personaje` | PERMISO_2DO_PERSONAJE | utils.py línea 99 | roleplay.py línea 648 |
| `/forzar_cambio_pj` | Administrator | Discord nativo | roleplay.py línea 673 |
| `/ciudadano` | PERMISO_CIVIL | utils.py línea 98 | roleplay.py línea 694 |
| `/eliminar_ciudadano` | PERMISO_MANEJO_DNI | utils.py línea 101 | roleplay.py línea 794 |
| `/editar_ciudadano` | PERMISO_MANEJO_DNI | utils.py línea 101 | roleplay.py línea 841 |
| `/registrar_vehiculo` | PERMISO_MANEJO_LICENCIAS | utils.py línea 102 | roleplay.py línea 914 |
| `/retirar_vehiculo` | PERMISO_MANEJO_LICENCIAS | utils.py línea 102 | roleplay.py línea 971 |
| `/licencia_conducir` | PERMISO_MANEJO_LICENCIAS | utils.py línea 102 | roleplay.py línea 993 |
| `/licencia_armas` | PERMISO_MANEJO_LICENCIAS | utils.py línea 102 | roleplay.py línea 1041 |
| `/reclamar_robo` | Ninguno (público) | Sin decorador | roleplay.py línea 1089 |

---

## SISTEMA DE PERMISOS EXPLICADO

### Permisos Definidos en utils.py

Los permisos se definen en el archivo `utils.py` a partir de la línea 95:

```python
PERMISO_ADMIN = [ID_DUENO, ID_STAFF]
PERMISO_POLICIAL = [ID_DUENO, ID_STAFF, ID_POLICIA]
PERMISO_CIVIL = [ID_DUENO, ID_STAFF, ID_POLICIA, ID_CIVIL]
PERMISO_2DO_PERSONAJE = [ID_LLAVE_SLOT_2, ID_DUENO]
PERMISO_ECONOMIA = [ID_ECONOMIA, ID_DUENO]
PERMISO_MANEJO_DNI = [ID_MANEJO_DNI, ID_DUENO]
PERMISO_MANEJO_LICENCIAS = [ID_MANEJO_LICENCIAS, ID_DUENO, ID_STAFF]
```

### Jerarquía de Permisos (de mayor a menor)

1. **ID_DUENO**: Propietario del bot (tiene TODOS los permisos)
2. **PERMISO_ADMIN**: Staff administrativo (ID_DUENO + ID_STAFF)
3. **PERMISO_POLICIAL**: Personal policial (ID_DUENO + ID_STAFF + ID_POLICIA)
4. **PERMISO_CIVIL**: Todos los ciudadanos registrados (incluye policía y staff)
5. **PERMISO_MANEJO_LICENCIAS**: Personal autorizado para licencias/vehículos
6. **PERMISO_MANEJO_DNI**: Personal autorizado para gestionar DNIs
7. **PERMISO_2DO_PERSONAJE**: Usuarios con llave de segundo slot
8. **PERMISO_ECONOMIA**: Personal autorizado para comandos económicos

### Decorador @tiene_permiso()

El decorador `@utils.tiene_permiso()` se encuentra en utils.py línea 106:

```python
def tiene_permiso(*roles):
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id == ID_DUENO:
            return True  # El dueño siempre tiene acceso
        if isinstance(interaction.user, discord.Member):
            if any(role.id in roles for role in interaction.user.roles):
                return True  # Si tiene alguno de los roles requeridos
        roles_requeridos = [r for r in roles if r != ID_DUENO]
        raise app_commands.MissingAnyRole(roles_requeridos)
    return app_commands.check(predicate)
```

**Cómo funciona:**
1. Siempre permite al ID_DUENO
2. Verifica si el usuario tiene ALGUNO de los roles especificados
3. Si no tiene ninguno, lanza un error de "roles faltantes"

---

## CÓMO CAMBIAR PERMISOS

### Método 1: Cambiar IDs de Roles en .env (Recomendado)

Este método cambia qué rol de Discord tiene cada permiso, pero mantiene la estructura.

**Pasos:**
1. Abre el archivo `.env` en la raíz del proyecto
2. Modifica los IDs de los roles:

```env
# PERMISOS PRINCIPALES
ID_DUENO=123456789012345678          # Tu ID de usuario de Discord
ID_STAFF=987654321098765432          # ID del rol de Staff
ID_POLICIA=111111111111111111        # ID del rol de Policía
ID_CIVIL=222222222222222222          # ID del rol de Ciudadano

# PERMISOS ESPECÍFICOS
ID_MANEJO_DNI=333333333333333333     # ID del rol que gestiona DNIs
ID_MANEJO_LICENCIAS=444444444444444  # ID del rol que gestiona licencias
ID_LLAVE_SLOT_2=555555555555555555   # ID del rol de segundo personaje
ID_ECONOMIA=666666666666666666       # ID del rol de economía
```

3. Guarda el archivo
4. Reinicia el bot

**Cómo obtener IDs de roles:**
1. Activa el "Modo Desarrollador" en Discord (Configuración > Avanzado)
2. Click derecho en el rol > Copiar ID

---

### Método 2: Modificar Listas de Permisos en utils.py

Este método permite combinar múltiples roles para un permiso.

**Ubicación:** `utils.py` líneas 95-102

**Ejemplo - Agregar un rol adicional a comandos policiales:**

```python
# ANTES
PERMISO_POLICIAL = [ID_DUENO, ID_STAFF, ID_POLICIA]

# DESPUÉS (agregar rol de detective)
ID_DETECTIVE = get_env_int("ID_DETECTIVE")  # Agregar en línea 51
PERMISO_POLICIAL = [ID_DUENO, ID_STAFF, ID_POLICIA, ID_DETECTIVE]
```

No olvides agregar `ID_DETECTIVE` en el archivo `.env`:
```env
ID_DETECTIVE=777777777777777777
```

**Ejemplo - Crear un nuevo nivel de permiso:**

```python
# En utils.py después de la línea 102, agregar:
PERMISO_JEFE_POLICIA = [ID_DUENO, ID_JEFE_POLICIA]

# Luego usar en comandos:
@utils.tiene_permiso(*utils.PERMISO_JEFE_POLICIA)
async def comando_especial(self, interaction):
    ...
```

---

### Método 3: Cambiar Permisos Individuales de Comandos

Este método cambia el permiso de un comando específico sin afectar a otros.

**Ubicación:** Archivo del cog (policia.py o roleplay.py)

**Ejemplo - Cambiar permiso de /arrestar:**

**Opción A - Usar otro permiso existente:**
```python
# ANTES (policia.py línea 442)
@utils.tiene_permiso(*utils.PERMISO_POLICIAL)
async def arrestar(self, interaction, ...):

# DESPUÉS - Solo admins pueden arrestar
@utils.tiene_permiso(*utils.PERMISO_ADMIN)
async def arrestar(self, interaction, ...):
```

**Opción B - Usar permiso nativo de Discord:**
```python
# ANTES
@utils.tiene_permiso(*utils.PERMISO_POLICIAL)
async def arrestar(self, interaction, ...):

# DESPUÉS - Requiere permiso de "Administrator" de Discord
@app_commands.checks.has_permissions(administrator=True)
async def arrestar(self, interaction, ...):
```

**Opción C - Combinar múltiples permisos:**
```python
# Requiere ser STAFF O POLICÍA (cualquiera de los dos)
@utils.tiene_permiso(*utils.PERMISO_ADMIN, *utils.PERMISO_POLICIAL)
async def arrestar(self, interaction, ...):
```

**Opción D - Hacer un comando público (sin permisos):**
```python
# ANTES
@utils.tiene_permiso(*utils.PERMISO_CIVIL)
async def ciudadano(self, interaction, ...):

# DESPUÉS - Cualquiera puede usar el comando
# (simplemente eliminar el decorador @utils.tiene_permiso)
async def ciudadano(self, interaction, ...):
```

---

### Método 4: Crear Permisos Personalizados por Comando

Para casos especiales donde necesitas una combinación única de roles.

**Ejemplo - Solo jefes de policía pueden usar /arrestar:**

1. En utils.py, agregar:
```python
# Después de línea 102
ID_JEFE_POLICIA = get_env_int("ID_JEFE_POLICIA")
PERMISO_ARRESTO = [ID_DUENO, ID_JEFE_POLICIA]
```

2. En .env, agregar:
```env
ID_JEFE_POLICIA=888888888888888888
```

3. En policia.py línea 442, cambiar:
```python
# ANTES
@utils.tiene_permiso(*utils.PERMISO_POLICIAL)

# DESPUÉS
@utils.tiene_permiso(*utils.PERMISO_ARRESTO)
```

---

## VARIABLES DE ENTORNO (.env)

### IDs Requeridos en .env

Estas variables DEBEN existir en tu archivo .env:

```env
# === PERMISOS PRINCIPALES ===
ID_DUENO=123456789012345678
ID_STAFF=123456789012345678
ID_POLICIA=123456789012345678
ID_CIVIL=123456789012345678

# === PERMISOS ESPECÍFICOS ===
ID_MANEJO_DNI=123456789012345678
ID_MANEJO_LICENCIAS=123456789012345678
ID_LLAVE_SLOT_2=123456789012345678
ID_ECONOMIA=123456789012345678

# === ROLES FUNCIONALES ===
ID_ROL_PRESO=123456789012345678
ID_ROL_SUPERVISOR=123456789012345678

# === CANALES ===
ID_CANAL_LOGS=123456789012345678
ID_CANAL_ALERTAS=123456789012345678
ID_CANAL_REVISION_DNI=123456789012345678
ID_CANAL_RECLAMOS=123456789012345678

# === ROLES CRIMINALES (lista separada por comas) ===
ROLES_CRIMINALES=111111111111,222222222222,333333333333
```

### Cómo Funciona el Sistema

1. **Al iniciar el bot**, el archivo `utils.py` carga las variables del `.env`
2. Si falta alguna variable obligatoria, **el bot NO arrancará** y mostrará un error
3. Las variables se convierten en constantes Python que se usan en todo el bot
4. Los cambios en `.env` **requieren reiniciar el bot** para aplicarse

---

## EJEMPLOS PRÁCTICOS DE CAMBIOS

### Ejemplo 1: Hacer que solo Staff pueda multar

**Archivo:** policia.py línea 698

**Cambio:**
```python
# ANTES
@utils.tiene_permiso(*utils.PERMISO_POLICIAL)
async def multar(self, interaction, ...):

# DESPUÉS
@utils.tiene_permiso(*utils.PERMISO_ADMIN)
async def multar(self, interaction, ...):
```

---

### Ejemplo 2: Permitir que cualquier ciudadano vea arrestos

**Archivo:** policia.py línea 1514

**Cambio:**
```python
# ANTES
@utils.tiene_permiso(*utils.PERMISO_POLICIAL)
async def ver_arrestos(self, interaction, ...):

# DESPUÉS
@utils.tiene_permiso(*utils.PERMISO_CIVIL)
async def ver_arrestos(self, interaction, ...):
```

---

### Ejemplo 3: Crear rol "Detective" con permisos especiales

**1. En .env, agregar:**
```env
ID_DETECTIVE=999999999999999999
```

**2. En utils.py línea 51, agregar:**
```python
ID_DETECTIVE = get_env_int("ID_DETECTIVE")
```

**3. En utils.py línea 102, agregar:**
```python
PERMISO_DETECTIVE = [ID_DUENO, ID_STAFF, ID_DETECTIVE]
```

**4. En policia.py, cambiar comandos específicos:**
```python
# Para /consultar_denuncia (línea 2236)
@utils.tiene_permiso(*utils.PERMISO_DETECTIVE)
async def consultar_denuncia(self, interaction, ...):
```

---

### Ejemplo 4: Hacer público el comando /ciudadano

**Archivo:** roleplay.py línea 694

**Cambio:**
```python
# ANTES
@app_commands.command(name="ciudadano", description="...")
@utils.tiene_permiso(*utils.PERMISO_CIVIL)
async def ciudadano(self, interaction, ...):

# DESPUÉS (eliminar decorador de permisos)
@app_commands.command(name="ciudadano", description="...")
async def ciudadano(self, interaction, ...):
```

---

### Ejemplo 5: Solo el dueño puede liberar presos

**Archivo:** policia.py línea 664

**Cambio:**
```python
# ANTES
@app_commands.checks.has_permissions(administrator=True)
async def liberar(self, interaction, ...):

# DESPUÉS (solo el dueño del bot)
@app_commands.check(lambda interaction: interaction.user.id == utils.ID_DUENO)
async def liberar(self, interaction, ...):
```

---

## TABLA DE REFERENCIA RÁPIDA

### Permisos de Mayor a Menor Restricción

| Decorador | Descripción | Uso Recomendado |
|-----------|-------------|-----------------|
| `lambda: interaction.user.id == utils.ID_DUENO` | Solo el dueño | Comandos críticos del sistema |
| `@utils.tiene_permiso(*utils.PERMISO_ADMIN)` | Staff/Admins | Comandos administrativos |
| `@app_commands.checks.has_permissions(administrator=True)` | Admin de Discord | Alternativa a PERMISO_ADMIN |
| `@utils.tiene_permiso(*utils.PERMISO_MANEJO_DNI)` | Gestores de DNI | Aprobar/rechazar DNIs |
| `@utils.tiene_permiso(*utils.PERMISO_MANEJO_LICENCIAS)` | Gestores de licencias | Licencias y vehículos |
| `@utils.tiene_permiso(*utils.PERMISO_POLICIAL)` | Policía | Arrestos, multas, consultas |
| `@utils.tiene_permiso(*utils.PERMISO_CIVIL)` | Todos los ciudadanos | Comandos básicos |
| Sin decorador | Público | Comandos de acceso libre |

---

## TROUBLESHOOTING

### Error: "Falta la variable de entorno X en el archivo .env"

**Solución:** Agregar la variable faltante en el archivo `.env` con el formato:
```env
NOMBRE_VARIABLE=123456789012345678
```

### Error: "MissingAnyRole"

**Causa:** El usuario no tiene ninguno de los roles requeridos

**Solución:** 
- Verificar que el rol esté configurado correctamente en Discord
- Verificar que el ID del rol en `.env` sea correcto
- Asignar el rol al usuario en Discord

### Los cambios no se aplican

**Solución:** 
1. Guardar todos los archivos modificados
2. Reiniciar completamente el bot
3. Si editaste `.env`, verificar que no haya espacios extras

### Error: "NotFound" al obtener rol

**Causa:** El ID del rol no existe en el servidor

**Solución:**
- Verificar que el ID sea correcto (copiar desde Discord con Modo Desarrollador)
- Asegurarse de que el rol exista en el servidor

---

## RECOMENDACIONES DE SEGURIDAD

1. **Nunca compartas tu archivo .env** - Contiene IDs sensibles
2. **Backup antes de cambiar** - Haz copia de `utils.py` antes de modificarlo
3. **Prueba en servidor de desarrollo** - No hagas cambios directos en producción
4. **Documenta tus cambios** - Comenta qué cambios hiciste y por qué
5. **Jerarquía clara** - Mantén el ID_DUENO siempre con acceso total

---

## PLANTILLA DE PERMISOS PERSONALIZADOS

Si quieres crear tu propia estructura de permisos, usa esta plantilla:

**1. En .env:**
```env
# TUS ROLES PERSONALIZADOS
ID_TU_ROL_1=111111111111111111
ID_TU_ROL_2=222222222222222222
```

**2. En utils.py (después de línea 102):**
```python
# Cargar IDs
ID_TU_ROL_1 = get_env_int("ID_TU_ROL_1")
ID_TU_ROL_2 = get_env_int("ID_TU_ROL_2")

# Crear permisos personalizados
PERMISO_TU_CATEGORIA = [ID_DUENO, ID_TU_ROL_1, ID_TU_ROL_2]
```

**3. En el archivo del cog (policia.py o roleplay.py):**
```python
@utils.tiene_permiso(*utils.PERMISO_TU_CATEGORIA)
async def tu_comando(self, interaction, ...):
    # Tu código aquí
```

---

**Documento creado para AMBA Reborn 2**  
**Sistema de Permisos Modular v2.0**  
**Última actualización: 2026**
