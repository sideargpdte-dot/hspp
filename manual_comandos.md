# Manual de Comandos - Sistema Policial y Roleplay

## Tabla de Contenidos
1. [Sistema de Arrestos](#sistema-de-arrestos)
2. [Sistema de Multas](#sistema-de-multas)
3. [Sistema Vehicular](#sistema-vehicular)
4. [Sistema de Denuncias](#sistema-de-denuncias)
5. [Sistema de Consultas](#sistema-de-consultas)
6. [Sistema de Personajes](#sistema-de-personajes)

---

## SISTEMA DE ARRESTOS

### /arrestar
**Descripción:** Registra un arresto oficial aplicando artículos del Código Penal de AMBA.

**Permisos:** Roles policiales (PERMISO_POLICIAL)

**Parámetros:**
- `dni_arrestado` (obligatorio): DNI del ciudadano a arrestar (ej: 12345678)
- `articulos` (obligatorio): Artículos separados por ' - ' (Ej: Art.1.1 - Art.2.3)
- `gravedad` (obligatorio): Nivel de gravedad del delito (leve/medio/grave)
- `dni_oficial_principal` (obligatorio): DNI del oficial principal a cargo
- `foto_prueba` (obligatorio): Evidencia fotográfica del arresto
- `dni_oficial_2` a `dni_oficial_10` (opcional): DNI de oficiales adicionales
- `link_imagen` (opcional): Link de imagen adicional como evidencia

**Funcionamiento:**
1. El sistema valida que todos los DNI existan en la base de datos
2. Procesa los artículos del Código Penal según la gravedad seleccionada
3. Calcula automáticamente multa total y tiempo de condena
4. Asigna el rol de "Preso" al arrestado (sin timeout de Discord)
5. Registra el arresto en la base de datos con número único
6. Crea una multa asociada al arresto
7. Registra antecedentes penales del ciudadano
8. Notifica al arrestado vía MD con detalles del arresto
9. Guarda el arresto en el historial para consultas futuras

**Notas importantes:**
- El sistema NO aplica timeout de Discord, solo asigna el rol de preso
- Si se incluye un artículo con condena "CK", se aplica cadena perpetua
- La multa debe ser pagada por el arrestado usando `/pay_multas`
- Los artículos deben existir en el Código Penal configurado

**Ejemplo de uso:**
```
/arrestar dni_arrestado:12345678 articulos:Art.1.1 - Art.2.3 gravedad:medio 
dni_oficial_principal:87654321 foto_prueba:[adjuntar imagen]
```

---

### /ver_arrestos
**Descripción:** Consulta el historial completo de arrestos de un ciudadano con paginación.

**Permisos:** Roles policiales (PERMISO_POLICIAL)

**Parámetros:**
- `dni_ciudadano` (obligatorio): DNI del ciudadano a consultar

**Funcionamiento:**
1. Busca al ciudadano por DNI en la base de datos
2. Obtiene TODOS los arrestos del historial (activos y cumplidos)
3. Muestra cada arresto en una página separada con:
   - Número de arresto
   - Fecha de arresto y liberación
   - Artículos aplicados con detalles del Código Penal
   - Multa total y gravedad
   - Oficiales a cargo
   - Estado (ACTIVO/CUMPLIDO)
4. Permite navegar entre arrestos con botones de paginación

**Notas importantes:**
- Muestra arrestos ordenados por fecha (más reciente primero)
- Los arrestos legacy (antiguos) aparecen con el número "LEGACY"
- Si un arresto es CK (Cadena Perpetua), se indica claramente
- Incluye botones: Anterior, Siguiente, Cerrar

---

## SISTEMA DE MULTAS

### /multar
**Descripción:** Emite una multa oficial usando artículos del Código Penal o monto manual.

**Permisos:** Roles policiales (PERMISO_POLICIAL)

**Parámetros:**
- `dni_infractor` (obligatorio): DNI del ciudadano infractor
- `dni_oficial` (obligatorio): DNI del oficial emisor
- `foto_prueba` (obligatorio): Evidencia fotográfica de la infracción
- `articulos` (opcional): Artículos del Código Penal separados por ' - '
- `gravedad` (opcional): Nivel de gravedad (leve/medio/grave) - solo si usas artículos
- `motivo_manual` (opcional): Motivo si no usas artículos del código penal
- `monto_manual` (opcional): Monto manual si no usas artículos (0 = usar código penal)
- `link_imagen` (opcional): Link adicional de evidencia

**Funcionamiento:**
1. Valida que se use ARTÍCULOS O MONTO MANUAL (no ambos)
2. Si usa artículos:
   - Procesa artículos del Código Penal según gravedad
   - Calcula multa total automáticamente
   - Registra detalles de cada artículo
3. Si usa monto manual:
   - Registra el monto y motivo proporcionados
4. Genera un folio de multa único
5. Registra la multa en estado "no pagada"
6. Notifica al infractor vía MD con detalles

**Notas importantes:**
- La evidencia fotográfica es OBLIGATORIA
- El oficial debe existir en la base de datos (tener DNI)
- Las multas se pagan con `/pay_multas`
- El monto manual debe ser mayor a $0

**Ejemplo con artículos:**
```
/multar dni_infractor:12345678 dni_oficial:87654321 foto_prueba:[imagen] 
articulos:Art.1.1 - Art.2.3 gravedad:medio
```

**Ejemplo con monto manual:**
```
/multar dni_infractor:12345678 dni_oficial:87654321 foto_prueba:[imagen] 
monto_manual:5000 motivo_manual:Estacionamiento indebido
```

---

### /ver_multas
**Descripción:** Consulta las multas pendientes de pago de un ciudadano.

**Permisos:** Ciudadanos (PERMISO_CIVIL) - puede ver sus propias multas o las de otros si es oficial

**Parámetros:**
- `dni_ciudadano` (opcional): DNI del ciudadano a consultar (si no se pone, ve las propias)
- `slot` (opcional): Slot del personaje (si no se pone, usa el activo)

**Funcionamiento:**
1. Si no se proporciona DNI, consulta las multas del usuario que ejecuta el comando
2. Si se proporciona DNI:
   - Busca al ciudadano en la base de datos
   - Verifica permisos (solo oficiales o el mismo ciudadano pueden ver)
3. Muestra todas las multas pendientes (no pagadas) del slot especificado
4. Lista cada multa con:
   - Folio/ID de multa
   - Motivo
   - Monto
   - Fecha de emisión
5. Calcula y muestra el total adeudado

**Notas importantes:**
- Solo muestra multas NO pagadas
- Si consultas multas ajenas necesitas ser oficial o admin
- Las multas están vinculadas al slot del personaje

---

### /pay_multas
**Descripción:** Paga multas pendientes usando un menú de selección interactivo.

**Permisos:** Ciudadanos (PERMISO_CIVIL)

**Parámetros:**
- `slot` (obligatorio): Slot del personaje (1 o 2)

**Funcionamiento:**
1. Verifica que el personaje existe en el slot especificado
2. Busca todas las multas pendientes del slot
3. Muestra un menú desplegable con hasta 25 multas
4. Al seleccionar una multa:
   - Verifica que tienes fondos suficientes EN EFECTIVO (dinero_mano)
   - Deduce el monto de tu efectivo
   - Marca la multa como pagada
   - Genera recibo de pago
5. Si no tienes efectivo suficiente, sugiere retirar del banco

**Notas importantes:**
- Solo se puede pagar con EFECTIVO (no desde el banco)
- El menú muestra: Folio, motivo, monto y fecha
- Cada multa se paga individualmente
- El sistema previene pagos duplicados

---

### /revocar_multa
**Descripción:** Revoca/cancela una multa sin realizar el cobro (uso administrativo).

**Permisos:** Administradores (PERMISO_ADMIN)

**Parámetros:**
- `id_multa` (obligatorio): ID/Folio de la multa a revocar

**Funcionamiento:**
1. Busca la multa por su ID
2. Marca la multa como "pagada" sin deducir fondos
3. Registra la acción administrativa
4. Genera confirmación de cancelación

**Notas importantes:**
- Esta acción NO devuelve dinero, solo cancela la deuda
- Útil para corregir errores o indultos
- La multa aparecerá como "pagada" en el sistema

---

## SISTEMA VEHICULAR

### /registrar_vehiculo
**Descripción:** Registra un nuevo vehículo en el Registro del Automotor a nombre de un ciudadano.

**Permisos:** Personal autorizado (PERMISO_MANEJO_LICENCIAS)

**Parámetros:**
- `dni_ciudadano` (obligatorio): DNI del propietario del vehículo
- `modelo` (obligatorio): Modelo del vehículo
- `patente` (obligatorio): Patente/Dominio del vehículo

**Funcionamiento:**
1. Busca al ciudadano por DNI
2. Convierte la patente a mayúsculas automáticamente
3. Verifica que la patente no esté registrada previamente
4. Registra el vehículo asociado al ID del ciudadano y su slot
5. Genera confirmación con datos del registro

**Notas importantes:**
- La patente debe ser única en todo el sistema
- El vehículo se vincula al slot activo del ciudadano
- Se puede usar para transferir registrando al nuevo propietario

---

### /retirar_vehiculo
**Descripción:** Da de baja un vehículo del Registro del Automotor.

**Permisos:** Personal autorizado (PERMISO_MANEJO_LICENCIAS)

**Parámetros:**
- `ciudadano` (obligatorio): Usuario de Discord del propietario
- `slot` (obligatorio): Slot del personaje (1 o 2)
- `patente` (obligatorio): Patente del vehículo a retirar

**Funcionamiento:**
1. Busca el vehículo por patente, usuario y slot
2. Verifica que el vehículo exista y pertenezca al ciudadano
3. Elimina el vehículo de la base de datos permanentemente
4. Genera confirmación de baja vehicular

**Notas importantes:**
- La acción es irreversible
- El vehículo debe pertenecer al ciudadano especificado en el slot correcto
- Útil para ventas, destrucciones o correcciones

---

### /buscar_dominio
**Descripción:** Busca información de registro de una patente vehicular en la base de datos nacional.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `patente` (obligatorio): Patente del vehículo a consultar

**Funcionamiento:**
1. Convierte la patente a mayúsculas automáticamente
2. Busca el vehículo en la base de datos
3. Obtiene información del propietario registrado
4. Muestra:
   - Patente
   - Modelo del vehículo
   - Nombre completo del propietario
   - Documento (DNI)
   - Contacto de Discord del propietario

**Notas importantes:**
- Útil para controles de tránsito
- Solo muestra el propietario ACTUAL registrado
- No muestra historial de transferencias

---

### /vehiculo_antecedente
**Descripción:** Registra un antecedente o incidente relacionado con un vehículo.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `patente` (obligatorio): Patente del vehículo
- `tipo_incidente` (obligatorio): Tipo de incidente a registrar (opciones predefinidas)
- `descripcion` (obligatorio): Descripción detallada del incidente

**Funcionamiento:**
1. Verifica que el vehículo existe en la base de datos
2. Obtiene datos del oficial que registra (nombre, ID)
3. Registra el antecedente con:
   - Patente del vehículo
   - Tipo de incidente
   - Descripción detallada
   - Oficial que registra
   - Fecha y hora
4. Genera un ID único de antecedente
5. Muestra confirmación con todos los detalles

**Tipos de incidente disponibles:**
- Infracción de tránsito
- Conducción temeraria
- Accidente
- Fuga
- Vehículo involucrado en delito
- Transporte ilegal
- Modificación ilegal
- Documentación falsa
- Otro

**Notas importantes:**
- Los antecedentes quedan vinculados a la PATENTE, no al propietario
- Si el vehículo cambia de dueño, los antecedentes se mantienen
- Útil para seguimiento policial de vehículos conflictivos

---

### /vehiculo_consultar
**Descripción:** Consulta el historial completo de un vehículo incluyendo antecedentes, robos y transferencias.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `patente` (obligatorio): Patente del vehículo a consultar

**Funcionamiento:**
1. Busca el vehículo en la base de datos
2. Obtiene datos del propietario actual
3. Consulta antecedentes (últimos 5)
4. Verifica estado de robo (activo/inactivo)
5. Obtiene historial de transferencias (últimas 3)
6. Muestra un informe completo con:
   - Datos básicos (patente, modelo, propietario)
   - Alerta de robo (si corresponde)
   - Antecedentes recientes con fechas y oficiales
   - Historial de propietarios con precios de venta

**Notas importantes:**
- Muestra información histórica del vehículo
- Si está reportado como robado, aparece una ALERTA prominente
- Los antecedentes incluyen: tipo, fecha y oficial que lo registró
- El historial de transferencias muestra: vendedor, comprador, fecha y precio

---

### /vehiculo_robo
**Descripción:** Reporta un vehículo como robado o lo marca como recuperado.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `patente` (obligatorio): Patente del vehículo
- `accion` (obligatorio): REPORTAR_ROBO o RECUPERAR
- `descripcion` (obligatorio): Descripción del robo o circunstancias de recuperación

**Funcionamiento:**

**Si se reporta como ROBADO:**
1. Verifica que el vehículo no esté ya reportado como robado
2. Obtiene datos del propietario legítimo
3. Registra el robo en la base de datos con:
   - Datos del vehículo y propietario
   - Fecha del robo
   - Descripción del incidente
   - Oficial que toma el reporte
4. Marca el vehículo como "ACTIVO" en búsqueda
5. Genera alerta policial

**Si se RECUPERA:**
1. Verifica que el vehículo esté reportado como robado activamente
2. Actualiza el estado a "RECUPERADO"
3. Registra fecha de recuperación y oficial
4. Levanta la alerta de búsqueda
5. Permite contactar al propietario para devolución

**Notas importantes:**
- Un vehículo robado aparecerá en las consultas con ALERTA
- La recuperación cierra el caso de robo
- El historial de robo se mantiene aunque se recupere

---

### /vehiculo_transferir
**Descripción:** Registra oficialmente una transferencia de propiedad vehicular (uso administrativo).

**Permisos:** Administradores (PERMISO_ADMIN)

**Parámetros:**
- `patente` (obligatorio): Patente del vehículo
- `nuevo_propietario` (obligatorio): Usuario de Discord del nuevo dueño
- `nuevo_slot` (obligatorio): Slot del nuevo propietario (1 o 2)
- `precio_venta` (opcional): Precio de la venta (0 = sin registro de precio)

**Funcionamiento:**
1. Verifica que el vehículo existe
2. Obtiene datos del propietario anterior
3. Verifica que el nuevo propietario tiene un personaje en el slot especificado
4. Registra la transferencia en el historial con:
   - Nombres de vendedor y comprador
   - Fecha de transferencia
   - Precio de venta (si se proporciona)
5. Actualiza el propietario del vehículo en el registro
6. Genera confirmación de transferencia

**Notas importantes:**
- Esta acción NO mueve dinero entre cuentas
- Es solo un registro administrativo de la transferencia
- El historial de transferencias queda guardado permanentemente
- Útil para documentar ventas entre jugadores

---

## SISTEMA DE DENUNCIAS

### /denuncia
**Descripción:** Registra una denuncia ciudadana oficial en el sistema policial.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `dni_denunciante` (obligatorio): DNI del ciudadano que denuncia
- `tipo_denuncia` (obligatorio): Tipo de denuncia (opciones predefinidas)
- `descripcion` (obligatorio): Descripción detallada de los hechos
- `prioridad` (obligatorio): BAJA, MEDIA, ALTA o URGENTE
- `dni_denunciado` (opcional): DNI del ciudadano denunciado (si se conoce)
- `ubicacion` (opcional): Ubicación donde ocurrieron los hechos
- `fecha_hechos` (opcional): Fecha en formato DD/MM/YYYY

**Funcionamiento:**
1. Valida que el denunciante existe por DNI
2. Si hay denunciado, valida su existencia
3. Obtiene datos del oficial receptor
4. Genera un número de denuncia único (DEN-YYYYMMDD-HHMMSS)
5. Registra la denuncia en estado "PENDIENTE"
6. Crea el primer seguimiento (apertura)
7. Notifica al denunciante vía MD con el número de denuncia

**Tipos de denuncia disponibles:**
- Robo
- Asalto
- Agresión
- Amenazas
- Extorsión
- Fraude
- Estafa
- Vandalismo
- Secuestro
- Homicidio
- Tráfico de drogas
- Tráfico de armas
- Corrupción
- Abuso de autoridad
- Violencia doméstica
- Otro

**Notas importantes:**
- La denuncia inicia en estado PENDIENTE
- El denunciado es opcional (puede ser desconocido)
- El número de denuncia se usa para hacer seguimiento

---

### /seguimiento
**Descripción:** Agrega una acción de seguimiento a una denuncia y/o actualiza su estado.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `numero_denuncia` (obligatorio): Número de la denuncia (Ej: DEN-20260909-143052)
- `accion` (obligatorio): Tipo de acción realizada (opciones predefinidas)
- `descripcion` (obligatorio): Descripción detallada de la acción
- `nuevo_estado` (opcional): Cambiar estado (PENDIENTE/EN_INVESTIGACION/RESUELTA/ARCHIVADA/DERIVADA)
- `foto_evidencia` (opcional): Adjuntar evidencia fotográfica

**Funcionamiento:**
1. Busca la denuncia por número
2. Obtiene datos del oficial que hace el seguimiento
3. Registra el seguimiento con:
   - Acción realizada
   - Descripción
   - Fecha y hora
   - Oficial responsable
4. Si hay foto, la registra como evidencia
5. Si se proporciona nuevo estado, actualiza la denuncia
6. Genera confirmación con todos los detalles

**Tipos de acción disponibles:**
- INVESTIGACIÓN
- DECLARACIÓN
- INSPECCIÓN
- CITACIÓN
- ARRESTO
- INCAUTACIÓN
- INFORME
- CIERRE
- DERIVACIÓN
- OTRO

**Estados de denuncia:**
- PENDIENTE: Recién registrada, sin atender
- EN_INVESTIGACION: Bajo investigación activa
- RESUELTA: Caso cerrado con resolución
- ARCHIVADA: Caso archivado sin resolución
- DERIVADA: Enviada a otra área/jurisdicción

**Notas importantes:**
- Cada seguimiento queda registrado con fecha y oficial
- Las evidencias fotográficas se vinculan a la denuncia
- El cambio de estado es opcional, puede solo agregar seguimiento

---

### /consultar_denuncia
**Descripción:** Consulta información completa de una denuncia con paginación de seguimientos.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `numero_denuncia` (obligatorio): Número de la denuncia a consultar

**Funcionamiento:**
1. Busca la denuncia por número
2. Obtiene información general:
   - Denunciante y denunciado
   - Tipo de denuncia
   - Estado y prioridad
   - Oficial receptor
   - Fecha de registro
   - Descripción de los hechos
3. Obtiene TODOS los seguimientos ordenados cronológicamente
4. Si hay evidencias fotográficas, las muestra
5. Presenta la información con paginación:
   - Primera página: Info general + primer seguimiento
   - Páginas siguientes: Un seguimiento por página
6. Permite navegar con botones: Anterior, Siguiente, Cerrar

**Notas importantes:**
- Muestra el historial completo de la investigación
- Cada seguimiento incluye: acción, oficial, fecha y descripción
- Las imágenes de evidencia se muestran en el embed
- Si solo hay un seguimiento, no muestra paginación

---

### /listar_denuncias
**Descripción:** Lista denuncias filtradas por estado y/o prioridad.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `estado` (opcional): Filtrar por estado (PENDIENTE/EN_INVESTIGACION/RESUELTA/ARCHIVADA/DERIVADA/TODAS)
- `prioridad` (opcional): Filtrar por prioridad (BAJA/MEDIA/ALTA/URGENTE/TODAS)

**Funcionamiento:**
1. Aplica los filtros seleccionados
2. Obtiene las últimas 10 denuncias que coincidan
3. Para cada denuncia muestra:
   - Número de denuncia
   - Tipo
   - Denunciante
   - Denunciado (si hay)
   - Fecha
   - Estado actual
   - Prioridad
4. Lista ordenada por fecha (más reciente primero)

**Notas importantes:**
- Por defecto filtra por PENDIENTE si no se especifica
- Muestra máximo 10 denuncias para no saturar
- Útil para ver casos por atender

---

## SISTEMA DE CONSULTAS

### /codigo-penal
**Descripción:** Consulta artículos del Código Penal de AMBA con tres modos de búsqueda.

**Permisos:** Ciudadanos (PERMISO_CIVIL)

**Parámetros:**
- `consulta_tipo` (obligatorio): articulo, capitulo o completo
- `codigo_articulo` (condicional): Código del artículo (Ej: Art.1.1) - solo para tipo "articulo"
- `numero_capitulo` (condicional): Número romano del capítulo (I-X) - solo para tipo "capitulo"

**Funcionamiento:**

**Modo ARTÍCULO:**
1. Busca el artículo específico por código
2. Muestra información detallada:
   - Capítulo al que pertenece
   - Infracción
   - Multa base
   - Sanción
   - Condena IC (In Character)
   - Tiempos OOC calculados por gravedad (Leve 33%, Medio 66%, Grave 100%)

**Modo CAPÍTULO:**
1. Obtiene todos los artículos del capítulo
2. Los divide en páginas de 8 artículos
3. Muestra con paginación cada artículo con:
   - Código y multa
   - Infracción
   - Tiempo medio (66%)
4. Permite navegar entre páginas

**Modo COMPLETO:**
1. Muestra índice de todos los capítulos del Código Penal
2. Lista cada capítulo con su nombre y cantidad de artículos
3. Proporciona instrucciones de uso

**Notas importantes:**
- Cualquier ciudadano puede consultar el código
- Los tiempos se calculan automáticamente por gravedad
- "CK" significa Cadena Perpetua (Character Kill)
- Útil antes de aplicar arrestos o multas

---

### /expediente
**Descripción:** Consulta el expediente policial completo de un ciudadano.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
- `ciudadano` (obligatorio): Usuario de Discord del ciudadano
- `slot` (obligatorio): Slot del personaje (1 o 2)

**Funcionamiento:**
1. Obtiene datos personales del ciudadano
2. Verifica estado legal actual:
   - Si está arrestado
   - Si tiene orden de búsqueda activa
3. Consulta registros:
   - Antecedentes penales (últimos 5)
   - Multas pendientes con monto total
   - Vehículos registrados
   - Licencias de conducir vigentes
   - Licencias de armas vigentes
4. Consulta datos económicos (dinero en mano y banco)
5. Presenta todo en un informe completo con:
   - DNI y datos personales
   - Estado legal con iconos (BUSCADO/PRESO/LIMPIO)
   - Todos los registros mencionados

**Notas importantes:**
- Es como una "ficha policial" completa
- Muestra alertas prominentes si está arrestado o buscado
- Incluye avatar del personaje
- Útil para controles policiales o investigaciones

---

### /listar_buscados
**Descripción:** Muestra lista de órdenes de búsqueda y captura activas.

**Permisos:** Personal policial (PERMISO_POLICIAL)

**Parámetros:**
Ninguno (sin parámetros)

**Funcionamiento:**
1. Obtiene todas las órdenes de búsqueda con estado "ACTIVA"
2. Ordena por fecha de emisión (más reciente primero)
3. Muestra últimas 10 órdenes activas
4. Para cada orden muestra:
   - Número de orden
   - Nombre del prófugo (con slot)
   - Motivo de la búsqueda
   - Oficial emisor
   - Fecha de emisión
   - Cantidad de avistamientos reportados
   - Mención de Discord del prófugo
5. Incluye instrucción de uso de `/avistar`

**Notas importantes:**
- Solo muestra órdenes ACTIVAS (no las canceladas)
- Máximo 10 para no saturar
- Útil para controles de rutina
- Los ciudadanos pueden reportar avistamientos

---

## SISTEMA DE PERSONAJES

### /mis_personajes
**Descripción:** Muestra tus personajes y permite cambiar entre ellos con un menú interactivo.

**Permisos:** Todos los usuarios

**Parámetros:**
Ninguno (sin parámetros)

**Funcionamiento:**
1. Obtiene todos los personajes del usuario (slots 1 y 2)
2. Identifica cuál está activo actualmente
3. Muestra lista con:
   - Número de slot
   - Nombre completo del personaje
   - Profesión/trabajo
   - Estado (ACTIVO o Inactivo)
4. Presenta un menú desplegable para cambiar de personaje
5. Al seleccionar un personaje:
   - Actualiza el slot activo en la base de datos
   - Actualiza la caché de sesiones
   - Confirma el cambio

**Notas importantes:**
- El personaje activo se usa en todos los comandos que no especifican slot
- Puedes tener hasta 2 personajes (Slot 1 y Slot 2)
- El Slot 2 requiere rol especial (Llave de 2do Personaje)

---

### /ciudadano
**Descripción:** Muestra el DNI gráfico y la ficha completa de un ciudadano.

**Permisos:** Ciudadanos (PERMISO_CIVIL)

**Parámetros:**
- `usuario` (opcional): Usuario de Discord a consultar (si no se pone, muestra el propio)
- `slot` (opcional): Slot del personaje (si no se pone, usa el activo)

**Funcionamiento:**
1. Si no se especifica usuario, usa el que ejecuta el comando
2. Si no se especifica slot, usa el slot activo
3. Obtiene datos completos del ciudadano
4. Genera imagen DNI gráfico con:
   - Foto del avatar de Roblox
   - Nombre y apellido
   - DNI
   - Fecha de nacimiento
   - Género
   - Nacionalidad
5. Consulta información adicional:
   - Estado legal (Buscado/Preso/Limpio)
   - Vehículos registrados
   - Licencias de conducir
   - Licencias de armas
   - Multas pendientes y monto
   - Antecedentes penales
   - Economía (dinero mano y banco)
6. Presenta todo en un embed con la imagen del DNI

**Notas importantes:**
- Cualquier ciudadano puede ver su propio DNI
- Ver el DNI de otros requiere permisos según contexto
- El DNI se genera dinámicamente cada vez
- Muestra información actualizada en tiempo real

---

## NOTAS GENERALES

### Permisos del Sistema

**PERMISO_CIVIL:**
- Todos los ciudadanos registrados
- Pueden usar comandos básicos de consulta

**PERMISO_POLICIAL:**
- Roles policiales del servidor
- Acceso a comandos de arresto, multas y consultas

**PERMISO_MANEJO_DNI:**
- Staff autorizado para aprobar/rechazar DNIs
- Pueden editar y eliminar ciudadanos

**PERMISO_MANEJO_LICENCIAS:**
- Personal autorizado para gestionar licencias
- Pueden registrar vehículos

**PERMISO_ADMIN:**
- Administradores del servidor
- Acceso total a comandos administrativos

### Sistema de DNI y Búsqueda por DNI

**Muchos comandos ahora funcionan con DNI en lugar de menciones de Discord:**
- `/arrestar`: Requiere DNI del arrestado y oficiales
- `/multar`: Requiere DNI del infractor y oficial
- `/registrar_vehiculo`: Requiere DNI del propietario
- `/denuncia`: Requiere DNI del denunciante (y opcionalmente denunciado)

**Ventajas del sistema por DNI:**
- No requiere que el usuario esté en el servidor
- Más realista para roleplay
- Evita errores con menciones
- Permite registros de NPCs o personajes inactivos

### Sistema de Slots

**Todos los datos están vinculados a slots:**
- Cada usuario puede tener hasta 2 personajes (Slot 1 y 2)
- Los arrestos, multas, vehículos y licencias se registran por slot
- Al cambiar de personaje, cambia toda la información asociada

### Base de Datos

**Tablas principales:**
- `usuarios`: Datos de personajes
- `arrestos`: Arrestos activos
- `historial_arrestos`: Historial completo de arrestos
- `multas`: Multas emitidas
- `antecedentes`: Antecedentes penales
- `vehiculos`: Vehículos registrados
- `vehiculos_antecedentes`: Antecedentes de vehículos
- `vehiculos_robados`: Vehículos reportados como robados
- `vehiculos_historial_propietarios`: Historial de transferencias
- `denuncias`: Denuncias registradas
- `denuncias_seguimiento`: Seguimientos de denuncias
- `denuncias_evidencias`: Evidencias fotográficas
- `busqueda_captura`: Órdenes de búsqueda

---

## FLUJOS DE TRABAJO COMUNES

### Flujo de Arresto Completo

1. Oficial detiene al ciudadano en roleplay
2. Oficial usa `/arrestar` con:
   - DNI del arrestado
   - Artículos del Código Penal aplicados
   - Gravedad del delito
   - DNI del oficial principal (y opcionales)
   - Foto de evidencia
3. Sistema procesa:
   - Asigna rol de preso
   - Calcula multa y tiempo
   - Registra en historial
   - Crea multa asociada
   - Notifica al arrestado
4. Arrestado cumple condena:
   - Sistema libera automáticamente al cumplir tiempo
   - Arrestado usa `/pay_multas` para pagar la deuda
5. Oficial puede consultar después con `/ver_arrestos` por DNI

### Flujo de Denuncia Completa

1. Ciudadano acude a comisaría
2. Oficial toma la denuncia con `/denuncia`:
   - DNI del denunciante
   - Tipo de denuncia
   - Descripción de hechos
   - Prioridad
   - Datos opcionales (denunciado, ubicación, fecha)
3. Sistema genera número de denuncia
4. Oficial investiga y va agregando seguimientos con `/seguimiento`:
   - Acciones realizadas (interrogatorios, inspecciones, etc.)
   - Evidencias fotográficas
   - Cambios de estado
5. Cualquier oficial puede consultar el caso con `/consultar_denuncia`
6. Al resolver el caso, oficial marca como RESUELTA
7. La denuncia queda en el sistema para futuras consultas

### Flujo de Multa

1. Oficial detecta infracción
2. Oficial usa `/multar`:
   - DNI del infractor y oficial
   - Artículos o monto manual
   - Foto de evidencia
3. Sistema registra multa y notifica
4. Infractor consulta sus multas con `/ver_multas`
5. Infractor va a cajero/comisaría y usa `/pay_multas`
6. Selecciona multa del menú y confirma pago
7. Sistema deduce dinero y marca multa como pagada

### Flujo de Registro Vehicular

1. Ciudadano compra vehículo
2. Staff usa `/registrar_vehiculo`:
   - DNI del nuevo propietario
   - Modelo del vehículo
   - Patente
3. Sistema registra vehículo
4. Durante uso del vehículo:
   - Oficiales pueden usar `/buscar_dominio` para verificar propietario
   - Si hay incidentes, usar `/vehiculo_antecedente`
   - Si es robado, usar `/vehiculo_robo` para reportar/recuperar
5. Al vender:
   - Admin usa `/vehiculo_transferir` para cambiar propietario
   - O Staff usa `/retirar_vehiculo` y `/registrar_vehiculo` al nuevo dueño

---

## RESOLUCIÓN DE PROBLEMAS COMUNES

### "No se encontró ciudadano con DNI X"
**Causa:** El DNI no existe en la base de datos o está mal escrito
**Solución:** 
- Verificar que el DNI esté correcto (8 dígitos)
- Usar `/ciudadano` para ver el DNI del personaje
- Asegurarse de que el personaje tiene DNI asignado

### "Solo el infractor o autoridades pueden ver multas ajenas"
**Causa:** Intentas ver multas de otro sin permisos
**Solución:**
- Si eres el ciudadano, no uses el parámetro `dni_ciudadano`
- Si eres oficial, asegúrate de tener rol policial

### "Fondos insuficientes en Efectivo"
**Causa:** Intentas pagar multa pero el dinero está en el banco
**Solución:**
- Usa comandos de economía para retirar del banco
- El pago de multas SOLO acepta efectivo (dinero_mano)

### "El vehículo ya está registrado"
**Causa:** La patente ya existe en el sistema
**Solución:**
- Verificar que la patente esté correcta
- Usar `/buscar_dominio` para ver quién tiene esa patente
- Si es un error, usar `/retirar_vehiculo` primero

### "Error procesando artículos del Código Penal"
**Causa:** Formato incorrecto de artículos o artículo no existe
**Solución:**
- Usar formato: Art.X.Y - Art.X.Z (con espacios antes y después del guión)
- Verificar que los artículos existan con `/codigo-penal`
- Ejemplos válidos: "Art.1.1 - Art.2.3" o "Art.5.2"

---

**Documento generado para AMBA Reborn 2**  
**Versión del sistema:** 2.0  
**Última actualización:** 2026
