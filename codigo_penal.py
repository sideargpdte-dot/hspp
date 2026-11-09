"""
╔══════════════════════════════════════════════════════════╗
║        CÓDIGO PENAL COMPLETO - AMBA Reborn 2            ║
║                                                          ║
║  Base de datos completa del Código Penal con            ║
║  10 capítulos y 250+ artículos.                         ║
║                                                          ║
║  Incluye conversión automática de tiempo IC → OOC       ║
║  y sistema de gravedad de delitos.                      ║
╚══════════════════════════════════════════════════════════╝
"""

import re
from typing import Literal

# ==========================================
#  ⚙️ CONFIGURACIÓN FÁCIL DE PRECIOS
# ==========================================
#
#  🎯 MULTIPLICADORES GLOBALES (fácil de cambiar)
#
#  Cambia estos valores para ajustar TODAS las multas de un capítulo:
#  - 1.0 = Precio normal (100%)
#  - 0.5 = Mitad de precio (50%)
#  - 2.0 = Doble de precio (200%)
#  - 1.5 = 50% más caro
#  - 0.75 = 25% más barato
#
#  📝 EJEMPLOS DE USO:
#
#  1. Hacer TODAS las multas de tráfico 50% más baratas:
#     'I': 0.5,
#
#  2. Duplicar TODAS las multas de robos:
#     'III': 2.0,
#
#  3. Hacer las multas de drogas un 25% más caras:
#     'X': 1.25,
#
#  4. Subir todas las multas un 10%:
#     Cambia MULTIPLICADOR_GENERAL a 1.1
#

MULTIPLICADORES_CAPITULOS = {
    'I':    1.0,  # Delitos de Tráfico (37 artículos)
    'II':   1.0,  # Agresiones, Disturbios y Conductas Erróneas (30 artículos)
    'III':  1.0,  # Robos y Asaltos (23 artículos)
    'IV':   1.0,  # Tenencia de Armas y Objetos (15 artículos)
    'V':    1.0,  # Posesión y Tráfico de Divisas (11 artículos)
    'VI':   1.0,  # Delitos contra la Administración Pública (18 artículos)
    'VII':  1.0,  # Bandas y Organizaciones Criminales (16 artículos)
    'VIII': 1.0,  # Homicidio y Agresiones (10 artículos)
    'IX':   1.0,  # Falsificación y Suplantación de Identidad (19 artículos)
    'X':    1.0,  # Delitos de Drogas y Tóxicos (10 artículos)
}

# 🔧 MULTIPLICADOR GENERAL (afecta TODAS las multas de TODOS los capítulos)
#    Ejemplo: 1.2 = Todas las multas suben un 20%
MULTIPLICADOR_GENERAL = 1.0

# ⚠️ NOTA IMPORTANTE:
# Los multiplicadores se aplican automáticamente cuando inicias el bot.
# Después de cambiar los valores, REINICIA EL BOT para aplicar los cambios.

# ==========================================

# ==========================================
#  CÓDIGO PENAL COMPLETO (BASE)
# ==========================================
# Los precios aquí son los ORIGINALES.
# Los multiplicadores se aplican automáticamente al consultar.

CODIGO_PENAL_BASE = {
    # CAPÍTULO I: DELITOS DE TRÁFICO (37 artículos)
    'Art.1.1': {'cap': 'I', 'infraccion': 'Uso excesivo del claxon', 'multa': 15000, 'sancion': 'Sanción económica', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.2': {'cap': 'I', 'infraccion': 'Invadir / circular en sentido contrario', 'multa': 25000, 'sancion': 'Sanción económica', 'condena': 'Hasta 30 días de cárcel'},
    'Art.1.3': {'cap': 'I', 'infraccion': 'Giro indebido', 'multa': 10000, 'sancion': 'Sanción económica', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.4': {'cap': 'I', 'infraccion': 'Conducir fuera de la carretera sin justificación', 'multa': 30000, 'sancion': 'Sanción económica', 'condena': 'Hasta 3 días de cárcel'},
    'Art.1.5': {'cap': 'I', 'infraccion': 'Negarse a la inspección del vehículo / no facilitar registro-seguro', 'multa': 50000, 'sancion': 'Sanción económica', 'condena': 'Hasta 7 días de cárcel'},
    'Art.1.6': {'cap': 'I', 'infraccion': 'No hacer caso a la señal / orden de un agente', 'multa': 100000, 'sancion': 'Sanción económica', 'condena': 'Hasta 30 días de cárcel'},
    'Art.1.7': {'cap': 'I', 'infraccion': 'Conducir con un vehículo en mal estado / no apto', 'multa': 150000, 'sancion': 'Sanción económica + incautación del vehículo', 'condena': 'Hasta 15 días de cárcel'},
    'Art.1.8': {'cap': 'I', 'infraccion': 'Estacionar en un lugar no permitido / zonas no habilitadas', 'multa': 40000, 'sancion': 'Sanción económica + incautación del vehículo (si no está el dueño presente)', 'condena': 'Hasta 2 días de cárcel'},
    'Art.1.9': {'cap': 'I', 'infraccion': 'Estacionar un vehículo no eléctrico en plaza para eléctricos', 'multa': 25000, 'sancion': 'Sanción económica + incautación del vehículo (si no está el dueño presente)', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.10': {'cap': 'I', 'infraccion': 'Obstruir la circulación', 'multa': 30000, 'sancion': 'Sanción económica', 'condena': 'Hasta 2 días de cárcel'},
    'Art.1.11': {'cap': 'I', 'infraccion': 'Conducir sin papeles / documentación del vehículo (incluye registro/seguro/ITV)', 'multa': 75000, 'sancion': 'Sanción económica + incautación del vehículo', 'condena': 'Hasta 7 días de cárcel'},
    'Art.1.12': {'cap': 'I', 'infraccion': 'Conducir sin carnet / licencia válida', 'multa': 250000, 'sancion': 'Sanción económica', 'condena': 'Hasta 90 días de cárcel'},
    'Art.1.13': {'cap': 'I', 'infraccion': 'Saltarse un stop', 'multa': 15000, 'sancion': 'Sanción económica', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.14': {'cap': 'I', 'infraccion': 'Saltarse un ceda el paso', 'multa': 15000, 'sancion': 'Sanción económica', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.15': {'cap': 'I', 'infraccion': 'Obstaculizar un paso de cebra', 'multa': 25000, 'sancion': 'Sanción económica + incautación del vehículo (si no está el dueño presente)', 'condena': 'Hasta 2 días de cárcel'},
    'Art.1.16': {'cap': 'I', 'infraccion': 'Saltarse un semáforo', 'multa': 30000, 'sancion': 'Sanción económica (hasta 3 acumulables)', 'condena': 'Hasta 3 días de cárcel'},
    'Art.1.17': {'cap': 'I', 'infraccion': 'Conducción temeraria', 'multa': 150000, 'sancion': 'Sanción económica + calabozo + puntos', 'condena': 'Hasta 6 meses de cárcel'},
    'Art.1.18': {'cap': 'I', 'infraccion': 'Circular por zona no autorizada (parking comisaría, zonas privadas, etc.)', 'multa': 50000, 'sancion': 'Sanción económica', 'condena': 'Hasta 7 días de cárcel'},
    'Art.1.19': {'cap': 'I', 'infraccion': 'Circular sin cinturón de seguridad', 'multa': 20000, 'sancion': 'Sanción económica', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.20': {'cap': 'I', 'infraccion': 'Saltarse un control policial / evadir control', 'multa': 200000, 'sancion': 'Sanción económica + prisión', 'condena': 'Hasta 1 año de cárcel'},
    'Art.1.21': {'cap': 'I', 'infraccion': 'Falsificar documentos del vehículo / matrículas', 'multa': 250000, 'sancion': 'Sanción económica + calabozo', 'condena': 'Hasta 2 años de prisión'},
    'Art.1.22': {'cap': 'I', 'infraccion': 'Superar el límite de velocidad en zona residencial', 'multa': 37500, 'sancion': 'Sanción económica + puntos', 'condena': 'Hasta 7 días de cárcel'},
    'Art.1.23': {'cap': 'I', 'infraccion': 'Superar el límite de velocidad en zona urbana', 'multa': 57500, 'sancion': 'Sanción económica + puntos', 'condena': 'Hasta 15 días de cárcel'},
    'Art.1.24': {'cap': 'I', 'infraccion': 'Superar el límite de velocidad en autovía / autopista', 'multa': 95000, 'sancion': 'Sanción económica + puntos', 'condena': 'Hasta 30 días de cárcel'},
    'Art.1.25': {'cap': 'I', 'infraccion': 'Superar el límite de velocidad en vías secundarias', 'multa': 65000, 'sancion': 'Sanción económica + puntos', 'condena': 'Hasta 15 días de cárcel'},
    'Art.1.26': {'cap': 'I', 'infraccion': 'Circular con un vehículo no apto para la vía', 'multa': 50000, 'sancion': 'Sanción económica', 'condena': 'Hasta 7 días de cárcel'},
    'Art.1.27': {'cap': 'I', 'infraccion': 'Adelantar en línea continua', 'multa': 25000, 'sancion': 'Sanción económica', 'condena': 'Hasta 2 días de cárcel'},
    'Art.1.28': {'cap': 'I', 'infraccion': 'Conducir bajo los efectos del alcohol (DUI)', 'multa': 200000, 'sancion': 'Multa + retirada/suspensión de licencia + prisión', 'condena': 'Hasta 1 año de cárcel'},
    'Art.1.29': {'cap': 'I', 'infraccion': 'Conducir bajo los efectos de las drogas (DUI)', 'multa': 250000, 'sancion': 'Multa + retirada/suspensión de licencia + prisión', 'condena': 'Hasta 1 año de cárcel'},
    'Art.1.30': {'cap': 'I', 'infraccion': 'Hacer uso del teléfono móvil mientras conduce', 'multa': 25000, 'sancion': 'Sanción económica', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.31': {'cap': 'I', 'infraccion': 'No hacer uso de las luces correspondientes en vía pública', 'multa': 15000, 'sancion': 'Sanción económica', 'condena': 'Hasta 1 día de cárcel'},
    'Art.1.32': {'cap': 'I', 'infraccion': 'No ceder el paso a un vehículo de emergencias', 'multa': 50000, 'sancion': 'Sanción económica + puntos', 'condena': 'Hasta 30 días de cárcel'},
    'Art.1.33': {'cap': 'I', 'infraccion': 'Obstaculizar salidas de vehículos de emergencia', 'multa': 75000, 'sancion': 'Sanción económica + incautación del vehículo (si no está el dueño presente)', 'condena': 'Hasta 30 días de cárcel'},
    'Art.1.34': {'cap': 'I', 'infraccion': 'Obstaculizar una intersección', 'multa': 30000, 'sancion': 'Sanción económica', 'condena': 'Hasta 2 días de cárcel'},
    'Art.1.35': {'cap': 'I', 'infraccion': 'Distracción al volante', 'multa': 30000, 'sancion': 'Sanción económica + puntos', 'condena': 'Hasta 2 días de cárcel'},
    'Art.1.36': {'cap': 'I', 'infraccion': 'Provocar un accidente con fuga (Hit & Run)', 'multa': 250000, 'sancion': 'Sanción económica + prisión', 'condena': 'Hasta 1 año de cárcel'},
    'Art.1.37': {'cap': 'I', 'infraccion': 'Circular sin matrícula / matrícula falsa o no registrada', 'multa': 75000, 'sancion': 'Sanción económica', 'condena': 'Hasta 30 días de cárcel'},

    # CAPÍTULO II: AGRESIONES, DISTURBIOS Y CONDUCTAS ERRÓNEAS (30 artículos)
    'Art.2.1': {'cap': 'II', 'infraccion': 'Alteración / disturbios del orden público', 'multa': 60000, 'sancion': 'Sanción económica + prisión', 'condena': 'Hasta 3 meses'},
    'Art.2.2': {'cap': 'II', 'infraccion': 'Racismo / Xenofobia', 'multa': 80000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.3': {'cap': 'II', 'infraccion': 'Faltas de respeto a otro civil o funcionario', 'multa': 50000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.4': {'cap': 'II', 'infraccion': 'Dañar mobiliario urbano (farolas, semáforos, etc.)', 'multa': 35000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.5': {'cap': 'II', 'infraccion': 'Insultos o amenazas graves', 'multa': 150000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.6': {'cap': 'II', 'infraccion': 'Provocar peleas en vía pública', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': '1 mes'},
    'Art.2.7': {'cap': 'II', 'infraccion': 'Amenaza de muerte a un civil', 'multa': 400000, 'sancion': 'Sanción económica + psicólogo', 'condena': '12 meses'},
    'Art.2.8': {'cap': 'II', 'infraccion': 'Acoso sexual (verbal o físico)', 'multa': 550000, 'sancion': 'Sanción económica + orden de alejamiento', 'condena': '—'},
    'Art.2.9': {'cap': 'II', 'infraccion': 'Uso indebido de máscara sin justificación / rostro tapado', 'multa': 150000, 'sancion': 'Sanción económica + retirada inmediata', 'condena': '—'},
    'Art.2.10': {'cap': 'II', 'infraccion': 'Circular desnudo o semidesnudo en vía pública', 'multa': 85000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.11': {'cap': 'II', 'infraccion': 'Acoso psicológico', 'multa': 60000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.12': {'cap': 'II', 'infraccion': 'Negarse a identificarse ante autoridades', 'multa': 150000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.13': {'cap': 'II', 'infraccion': 'Obstrucción a la autoridad / justicia', 'multa': 250000, 'sancion': 'Sanción económica + prisión', 'condena': '1 mes'},
    'Art.2.14': {'cap': 'II', 'infraccion': 'Falsas denuncias o acusaciones', 'multa': 200000, 'sancion': 'Sanción económica + prisión', 'condena': '1 mes'},
    'Art.2.15': {'cap': 'II', 'infraccion': 'Suplantación de identidad', 'multa': 300000, 'sancion': 'Sanción económica + prisión', 'condena': '2 meses'},
    'Art.2.16': {'cap': 'II', 'infraccion': 'Actos obscenos en público', 'multa': 120000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.17': {'cap': 'II', 'infraccion': 'Escándalo público', 'multa': 80000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.18': {'cap': 'II', 'infraccion': 'Lenguaje ofensivo en espacios públicos', 'multa': 40000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.19': {'cap': 'II', 'infraccion': 'Obstaculizar el tráfico sin motivo', 'multa': 100000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.20': {'cap': 'II', 'infraccion': 'Intento de soborno a funcionario', 'multa': 500000, 'sancion': 'Sanción económica + prisión', 'condena': '3 meses'},
    'Art.2.21': {'cap': 'II', 'infraccion': 'Reuniones clandestinas con fines delictivos', 'multa': 400000, 'sancion': 'Sanción económica + prisión', 'condena': '2 meses'},
    'Art.2.22': {'cap': 'II', 'infraccion': 'Uso de disfraces para delinquir o confundir', 'multa': 250000, 'sancion': 'Sanción económica + retirada del disfraz', 'condena': '—'},
    'Art.2.23': {'cap': 'II', 'infraccion': 'Fotografiar o grabar sin consentimiento', 'multa': 75000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.2.24': {'cap': 'II', 'infraccion': 'Negarse a pagar servicios prestados', 'multa': 500000, 'sancion': 'Sanción económica + obligación de pago', 'condena': '—'},
    'Art.2.25': {'cap': 'II', 'infraccion': 'Manifestación ilegal', 'multa': 150000, 'sancion': 'Sanción económica + prisión', 'condena': 'Hasta 2 meses'},
    'Art.2.26': {'cap': 'II', 'infraccion': 'Violar un perímetro o cordón policial', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': 'Hasta 2 meses'},
    'Art.2.27': {'cap': 'II', 'infraccion': 'Venta ambulante sin autorización', 'multa': 45000, 'sancion': 'Sanción económica + precintación del local', 'condena': '—'},
    'Art.2.28': {'cap': 'II', 'infraccion': 'Allanamiento de morada', 'multa': 50000, 'sancion': 'Sanción económica + prisión', 'condena': 'Hasta 6 meses'},
    'Art.2.29': {'cap': 'II', 'infraccion': 'Violar el derecho de privacidad de un ciudadano', 'multa': 50000, 'sancion': 'Sanción económica + prisión', 'condena': 'Hasta 6 meses'},
    'Art.2.30': {'cap': 'II', 'infraccion': 'Organizar peleas callejeras', 'multa': 40000, 'sancion': 'Sanción económica', 'condena': '—'},

    # CAPÍTULO III: ROBOS Y ASALTOS (23 artículos)
    'Art.3.1': {'cap': 'III', 'infraccion': 'Robo de vehículo', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.2': {'cap': 'III', 'infraccion': 'Robo de vehículo de importación', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.3': {'cap': 'III', 'infraccion': 'Robo de establecimiento (tienda, restaurante, cafetería, etc.)', 'multa': 150000, 'sancion': 'Sanción económica + prisión', 'condena': '15 meses'},
    'Art.3.4': {'cap': 'III', 'infraccion': 'Robo a gasolinera', 'multa': 155000, 'sancion': 'Sanción económica + prisión', 'condena': '15 meses'},
    'Art.3.5': {'cap': 'III', 'infraccion': 'Robo de joyería', 'multa': 250000, 'sancion': 'Sanción económica + prisión', 'condena': '20 meses'},
    'Art.3.6': {'cap': 'III', 'infraccion': 'Robo de banco', 'multa': 500000, 'sancion': 'Sanción económica + prisión', 'condena': '24 meses (Cadena perpetua (CK) si hay agravantes graves)'},
    'Art.3.7': {'cap': 'III', 'infraccion': 'Robo de propiedad', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.8': {'cap': 'III', 'infraccion': 'Robo a armería', 'multa': 147000, 'sancion': 'Sanción económica + prisión + incautación del arma', 'condena': '24 meses'},
    'Art.3.9': {'cap': 'III', 'infraccion': 'Asalto a un civil con arma blanca', 'multa': 120000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.10': {'cap': 'III', 'infraccion': 'Asalto a un civil con arma de fuego', 'multa': 120000, 'sancion': 'Sanción económica + prisión', 'condena': '15 meses'},
    'Art.3.11': {'cap': 'III', 'infraccion': 'Hurto en vía pública', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': '6 meses'},
    'Art.3.12': {'cap': 'III', 'infraccion': 'Intento de robo a un establecimiento', 'multa': 140000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.13': {'cap': 'III', 'infraccion': 'Intento de robo a una gasolinera', 'multa': 145000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.14': {'cap': 'III', 'infraccion': 'Intento de robo a joyería', 'multa': 200000, 'sancion': 'Sanción económica + prisión', 'condena': '15 meses'},
    'Art.3.15': {'cap': 'III', 'infraccion': 'Intento de robo al banco', 'multa': 250000, 'sancion': 'Sanción económica + prisión', 'condena': '20 meses (Cadena perpetua (CK) si hay toma de rehenes / explosivos)'},
    'Art.3.16': {'cap': 'III', 'infraccion': 'Intento de robo a una propiedad', 'multa': 90000, 'sancion': 'Sanción económica + prisión', 'condena': '9 meses'},
    'Art.3.17': {'cap': 'III', 'infraccion': 'Intento de robo a armería', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.18': {'cap': 'III', 'infraccion': 'Cómplice de robo', 'multa': 100000, 'sancion': 'Sanción económica + prisión', 'condena': '12 meses'},
    'Art.3.19': {'cap': 'III', 'infraccion': 'Asalto a un funcionario público (con el uso de la fuerza)', 'multa': 140000, 'sancion': 'Sanción económica + prisión', 'condena': '18 meses'},
    'Art.3.20': {'cap': 'III', 'infraccion': 'Intento de asalto a un funcionario público', 'multa': 120000, 'sancion': 'Sanción económica + prisión', 'condena': '15 meses'},
    'Art.3.21': {'cap': 'III', 'infraccion': 'Impago de multas', 'multa': 140000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.3.22': {'cap': 'III', 'infraccion': 'Impago de deudas', 'multa': 140000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.3.23': {'cap': 'III', 'infraccion': 'Robo a un ciudadano (con el uso de la fuerza)', 'multa': 140000, 'sancion': 'Sanción económica', 'condena': '12 meses'},

    # CAPÍTULO IV: TENENCIA DE ARMAS Y OBJETOS (15 artículos)
    'Art.4.1': {'cap': 'IV', 'infraccion': 'Posesión de un arma blanca ilegal en vía pública', 'multa': 30000, 'sancion': 'Sanción económica + incautación del arma', 'condena': '—'},
    'Art.4.2': {'cap': 'IV', 'infraccion': 'Exhibición de un arma blanca ilegal en vía pública', 'multa': 50000, 'sancion': 'Sanción económica + incautación del arma + prisión', 'condena': 'Hasta 1 mes'},
    'Art.4.3': {'cap': 'IV', 'infraccion': 'Posesión de un arma de fuego de calibre bajo sin licencia (pistolas)', 'multa': 70000, 'sancion': 'Sanción económica + incautación del arma', 'condena': '—'},
    'Art.4.4': {'cap': 'IV', 'infraccion': 'Posesión de un arma de fuego de calibre medio sin licencia (subfusiles, escopetas…)', 'multa': 160000, 'sancion': 'Sanción económica + incautación del arma', 'condena': '—'},
    'Art.4.5': {'cap': 'IV', 'infraccion': 'Posesión de un arma de fuego de calibre alto sin licencia (fusiles, automáticas…)', 'multa': 200000, 'sancion': 'Sanción económica + incautación del arma', 'condena': '—'},
    'Art.4.6': {'cap': 'IV', 'infraccion': 'Exhibición de un arma de fuego de calibre bajo', 'multa': 80000, 'sancion': 'Sanción económica + incautación del arma + prisión', 'condena': 'Hasta 1 mes'},
    'Art.4.7': {'cap': 'IV', 'infraccion': 'Exhibición de un arma de fuego de calibre medio', 'multa': 170000, 'sancion': 'Sanción económica + incautación del arma + prisión', 'condena': 'Hasta 2 meses'},
    'Art.4.8': {'cap': 'IV', 'infraccion': 'Exhibición de un arma de fuego de calibre alto', 'multa': 210000, 'sancion': 'Sanción económica + incautación del arma + prisión', 'condena': 'Hasta 2 meses'},
    'Art.4.9': {'cap': 'IV', 'infraccion': 'Hacer mal uso de un arma', 'multa': 50000, 'sancion': 'Sanción económica + incautación del arma', 'condena': '—'},
    'Art.4.10': {'cap': 'IV', 'infraccion': 'Posesión de herramientas de robo', 'multa': 30000, 'sancion': 'Sanción económica + incautación del objeto', 'condena': '—'},
    'Art.4.11': {'cap': 'IV', 'infraccion': 'Posesión de artefactos explosivos', 'multa': 1500000, 'sancion': 'Sanción económica + incautación del explosivo + prisión', 'condena': 'Hasta 2 meses'},
    'Art.4.12': {'cap': 'IV', 'infraccion': 'Posesión de munición', 'multa': 30000, 'sancion': 'Sanción económica + incautación de la munición', 'condena': '—'},
    'Art.4.13': {'cap': 'IV', 'infraccion': 'Posesión de equipamiento táctico (cascos, chalecos balísticos, pistoleras…)', 'multa': 30000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.4.14': {'cap': 'IV', 'infraccion': 'Venta ilegal de armas', 'multa': 10000000, 'sancion': 'Sanción económica + incautación del arma + prisión', 'condena': 'Hasta 3 meses'},
    'Art.4.15': {'cap': 'IV', 'infraccion': 'Tráfico de armas', 'multa': 5000000, 'sancion': 'Sanción económica + incautación del arma + prisión', 'condena': 'Hasta 6 meses'},

    # CAPÍTULO V: POSESIÓN Y TRÁFICO DE DIVISAS (11 artículos)
    'Art.5.1': {'cap': 'V', 'infraccion': 'Posesión de dinero negro 1–5.000€', 'multa': 500000, 'sancion': 'Sanción económica + incautación del dinero + prisión', 'condena': 'Hasta 1 mes'},
    'Art.5.2': {'cap': 'V', 'infraccion': 'Posesión de dinero negro 5.001–10.000€', 'multa': 1000000, 'sancion': 'Sanción económica + incautación del dinero + prisión', 'condena': 'Hasta 1 mes'},
    'Art.5.3': {'cap': 'V', 'infraccion': 'Posesión de dinero negro 10.001–30.000€', 'multa': 4050000, 'sancion': 'Sanción económica + incautación del dinero + prisión', 'condena': 'Hasta 2 meses'},
    'Art.5.4': {'cap': 'V', 'infraccion': 'Posesión de dinero negro +30.000€', 'multa': 7400000, 'sancion': 'Sanción económica + incautación del dinero + prisión', 'condena': 'Hasta 2 meses'},
    'Art.5.5': {'cap': 'V', 'infraccion': 'Blanqueo de capitales', 'multa': 450000, 'sancion': 'Sanción económica + incautación del dinero + prisión', 'condena': 'Hasta 3 meses'},
    'Art.5.6': {'cap': 'V', 'infraccion': 'Creación de dinero ilegal', 'multa': 400000, 'sancion': 'Sanción económica + incautación del dinero + prisión', 'condena': 'Hasta 2 meses'},
    'Art.5.7': {'cap': 'V', 'infraccion': 'Tráfico de capitales', 'multa': 450000, 'sancion': 'Sanción económica + incautación del dinero + prisión', 'condena': 'Hasta 3 meses'},
    'Art.5.8': {'cap': 'V', 'infraccion': 'Posesión de objetos robados', 'multa': 150000, 'sancion': 'Sanción económica + incautación del objeto + prisión', 'condena': 'Hasta 1 mes'},
    'Art.5.9': {'cap': 'V', 'infraccion': 'Posesión de joyas ilegales', 'multa': 250000, 'sancion': 'Sanción económica + incautación del objeto + prisión', 'condena': 'Hasta 2 meses'},
    'Art.5.10': {'cap': 'V', 'infraccion': 'Venta de joyas ilegales', 'multa': 260000, 'sancion': 'Sanción económica + incautación del objeto + prisión', 'condena': 'Hasta 2 meses'},
    'Art.5.11': {'cap': 'V', 'infraccion': 'Venta de objetos robados', 'multa': 160000, 'sancion': 'Sanción económica + incautación del objeto + prisión', 'condena': 'Hasta 1 mes'},

    # CAPÍTULO VI: DELITOS CONTRA LA ADMINISTRACIÓN PÚBLICA (18 artículos)
    'Art.6.1': {'cap': 'VI', 'infraccion': 'Violación de una orden judicial', 'multa': 100000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 30 meses'},
    'Art.6.2': {'cap': 'VI', 'infraccion': 'Obstrucción a la justicia', 'multa': 250000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 9 meses'},
    'Art.6.3': {'cap': 'VI', 'infraccion': 'Resistencia a la autoridad', 'multa': 250000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 6 meses'},
    'Art.6.4': {'cap': 'VI', 'infraccion': 'Negación a identificarse ante un funcionario', 'multa': 100000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 9 meses'},
    'Art.6.5': {'cap': 'VI', 'infraccion': 'Negación a presentar licencias a un funcionario', 'multa': 75000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 6 meses'},
    'Art.6.6': {'cap': 'VI', 'infraccion': 'Distribución de material confidencial del Estado', 'multa': 600000000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 12 meses'},
    'Art.6.7': {'cap': 'VI', 'infraccion': 'Soborno a funcionario público', 'multa': 500000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 24 meses'},
    'Art.6.8': {'cap': 'VI', 'infraccion': 'Desacato a la autoridad', 'multa': 250000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 12 meses'},
    'Art.6.9': {'cap': 'VI', 'infraccion': 'Malversación de fondos estatales', 'multa': 2500000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 24 meses'},
    'Art.6.10': {'cap': 'VI', 'infraccion': 'Detención ilegal por parte de un funcionario', 'multa': 400000, 'sancion': 'Sanción económica', 'condena': 'Pena interna'},
    'Art.6.11': {'cap': 'VI', 'infraccion': 'Amenaza a funcionario público', 'multa': 300000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 12 meses'},
    'Art.6.12': {'cap': 'VI', 'infraccion': 'Agresión a funcionario público', 'multa': 500000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 18 meses'},
    'Art.6.13': {'cap': 'VI', 'infraccion': 'Secuestro de funcionario público', 'multa': 1000000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 36 meses'},
    'Art.6.14': {'cap': 'VI', 'infraccion': 'Tentativa de homicidio a funcionario público', 'multa': 1500000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 40 meses'},
    'Art.6.15': {'cap': 'VI', 'infraccion': 'Homicidio de funcionario público', 'multa': 2500000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 35 años'},
    'Art.6.16': {'cap': 'VI', 'infraccion': 'Asesinato de funcionario público', 'multa': 8900000, 'sancion': 'Sanción económica', 'condena': 'Cadena perpetua'},
    'Art.6.17': {'cap': 'VI', 'infraccion': 'Falsificación de documentación oficial', 'multa': 200000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 12 meses'},
    'Art.6.18': {'cap': 'VI', 'infraccion': 'Uso indebido de bienes o fondos públicos', 'multa': 150000, 'sancion': 'Sanción económica + Arresto', 'condena': 'Hasta 6 meses'},

    # CAPÍTULO VII: BANDAS Y ORGANIZACIONES CRIMINALES (16 artículos)
    'Art.7.1': {'cap': 'VII', 'infraccion': 'Pertenencia a una banda criminal', 'multa': 750000, 'sancion': 'Multa + Arresto (48 meses de prisión)', 'condena': '48 meses (si hay suficiente información de la banda y de la persona, puede ser Cadena Perpetua)'},
    'Art.7.2': {'cap': 'VII', 'infraccion': 'Creación de una banda criminal (ser jefe de una)', 'multa': 0, 'sancion': 'Cadena Perpetua', 'condena': 'Cadena Perpetua'},
    'Art.7.3': {'cap': 'VII', 'infraccion': 'Financiamiento de una organización criminal', 'multa': 1250000, 'sancion': 'Multa + Arresto (60 meses de prisión)', 'condena': '60 meses'},
    'Art.7.4': {'cap': 'VII', 'infraccion': 'Colaboración con banda criminal', 'multa': 500000, 'sancion': 'Multa + Arresto (36 meses de prisión)', 'condena': '36 meses'},
    'Art.7.5': {'cap': 'VII', 'infraccion': 'Asociación para delinquir (pandilla)', 'multa': 600000, 'sancion': 'Multa + Arresto (24 meses de prisión)', 'condena': '24 meses'},
    'Art.7.6': {'cap': 'VII', 'infraccion': 'Uso de violencia para control territorial', 'multa': 900000, 'sancion': 'Multa + Arresto (60 meses de prisión)', 'condena': '60 meses'},
    'Art.7.7': {'cap': 'VII', 'infraccion': 'Extorsión organizada', 'multa': 1000000, 'sancion': 'Multa + Arresto (60 meses de prisión)', 'condena': '60 meses'},
    'Art.7.8': {'cap': 'VII', 'infraccion': 'Atentado contra entidad pública o policial', 'multa': 1500000, 'sancion': 'Multa + Arresto (96 meses de prisión)', 'condena': '96 meses'},
    'Art.7.9': {'cap': 'VII', 'infraccion': 'Secuestro organizado', 'multa': 2000000, 'sancion': 'Multa + Arresto (120 meses de prisión)', 'condena': '120 meses'},
    'Art.7.10': {'cap': 'VII', 'infraccion': 'Tráfico de armas organizado', 'multa': 1800000, 'sancion': 'Multa + Arresto (72 meses de prisión)', 'condena': '72 meses'},
    'Art.7.11': {'cap': 'VII', 'infraccion': 'Tráfico de drogas organizado', 'multa': 2000000, 'sancion': 'Multa + Arresto (144 meses de prisión)', 'condena': '144 meses'},
    'Art.7.12': {'cap': 'VII', 'infraccion': 'Lavado de dinero para una organización criminal', 'multa': 2500000, 'sancion': 'Multa + Arresto (72 meses de prisión)', 'condena': '72 meses'},
    'Art.7.13': {'cap': 'VII', 'infraccion': 'Conspiración criminal transnacional', 'multa': 2200000, 'sancion': 'Multa + Arresto (72 meses de prisión)', 'condena': '72 meses'},
    'Art.7.14': {'cap': 'VII', 'infraccion': 'Tráfico de seres humanos organizado', 'multa': 3000000, 'sancion': 'Multa + Arresto (180 meses de prisión)', 'condena': '180 meses'},
    'Art.7.15': {'cap': 'VII', 'infraccion': 'Corrupción de funcionario público en beneficio de organización criminal', 'multa': 1400000, 'sancion': 'Multa + Arresto (36 meses de prisión)', 'condena': '36 meses'},
    'Art.7.16': {'cap': 'VII', 'infraccion': 'Fraude informático organizado (cibercrimen)', 'multa': 1200000, 'sancion': 'Multa + Arresto (24 meses de prisión)', 'condena': '24 meses'},

    # CAPÍTULO VIII: HOMICIDIO Y AGRESIONES (10 artículos)
    'Art.8.1': {'cap': 'VIII', 'infraccion': 'Agresión a civil', 'multa': 200000, 'sancion': 'Multa + Arresto', 'condena': '12 meses de prisión'},
    'Art.8.2': {'cap': 'VIII', 'infraccion': 'Secuestro', 'multa': 500000, 'sancion': 'Multa + Arresto', 'condena': '24 meses de prisión'},
    'Art.8.3': {'cap': 'VIII', 'infraccion': 'Tentativa de secuestro', 'multa': 250000, 'sancion': 'Multa + Arresto', 'condena': '12 meses de prisión'},
    'Art.8.4': {'cap': 'VIII', 'infraccion': 'Homicidio en grado de tentativa', 'multa': 700000, 'sancion': 'Multa + Arresto', 'condena': '24 meses de prisión'},
    'Art.8.5': {'cap': 'VIII', 'infraccion': 'Homicidio', 'multa': 1800000, 'sancion': 'Multa + Arresto', 'condena': '30 meses de prisión'},
    'Art.8.6': {'cap': 'VIII', 'infraccion': 'Homicidio imprudente', 'multa': 1250000, 'sancion': 'Multa + Arresto', 'condena': '24 meses de prisión'},
    'Art.8.7': {'cap': 'VIII', 'infraccion': 'Asesinato', 'multa': 10000000, 'sancion': 'Multa + Arresto', 'condena': '124 meses de prisión (Hasta Cadena Perpetua (CK) en casos agravados)'},
    'Art.8.8': {'cap': 'VIII', 'infraccion': 'Trata de personas', 'multa': 3750000, 'sancion': 'Multa + Arresto', 'condena': '30 meses de prisión (Hasta Cadena Perpetua (CK) si hay menores/red organizada)'},
    'Art.8.9': {'cap': 'VIII', 'infraccion': 'Amenaza a un civil', 'multa': 250000, 'sancion': 'Multa', 'condena': '—'},
    'Art.8.10': {'cap': 'VIII', 'infraccion': 'Amenaza a un civil con arma blanca', 'multa': 200000, 'sancion': 'Multa + Arresto', 'condena': '2 meses de prisión'},

    # CAPÍTULO IX: FALSIFICACIÓN Y SUPLANTACIÓN DE IDENTIDAD (19 artículos)
    'Art.9.1': {'cap': 'IX', 'infraccion': 'Falsificación de documento público', 'multa': 750000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 24 meses de prisión'},
    'Art.9.2': {'cap': 'IX', 'infraccion': 'Falsificación de documento privado', 'multa': 500000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 18 meses de prisión'},
    'Art.9.3': {'cap': 'IX', 'infraccion': 'Uso de documento falso', 'multa': 400000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 12 meses de prisión'},
    'Art.9.4': {'cap': 'IX', 'infraccion': 'Alteración de información en documentos oficiales', 'multa': 600000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 24 meses de prisión'},
    'Art.9.5': {'cap': 'IX', 'infraccion': 'Falsificación de firmas', 'multa': 550000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 18 meses de prisión'},
    'Art.9.6': {'cap': 'IX', 'infraccion': 'Uso de identidad falsa o eliminar la tuya', 'multa': 1000000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 100 meses de prisión'},
    'Art.9.7': {'cap': 'IX', 'infraccion': 'Suplantación de identidad de un ciudadano', 'multa': 800000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 36 meses de prisión'},
    'Art.9.8': {'cap': 'IX', 'infraccion': 'Suplantación de identidad de un funcionario público', 'multa': 1000000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 42 meses de prisión'},
    'Art.9.9': {'cap': 'IX', 'infraccion': 'Falsificación de licencias o permisos oficiales', 'multa': 850000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 36 meses de prisión'},
    'Art.9.10': {'cap': 'IX', 'infraccion': 'Producción o distribución de documentos falsos', 'multa': 1200000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 48 meses de prisión'},
    'Art.9.11': {'cap': 'IX', 'infraccion': 'Suplantación de identidad de ciudadano común', 'multa': 700000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 24 meses de prisión'},
    'Art.9.12': {'cap': 'IX', 'infraccion': 'Suplantación de identidad de funcionario público', 'multa': 1000000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 36 meses de prisión'},
    'Art.9.13': {'cap': 'IX', 'infraccion': 'Suplantación de identidad de fuerzas de seguridad (policía/militar)', 'multa': 1200000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 42 meses de prisión'},
    'Art.9.14': {'cap': 'IX', 'infraccion': 'Suplantación de identidad para cometer fraude financiero', 'multa': 1500000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 48 meses de prisión'},
    'Art.9.15': {'cap': 'IX', 'infraccion': 'Uso de identidad robada para acceder a sistemas restringidos', 'multa': 1300000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 42 meses de prisión'},
    'Art.9.16': {'cap': 'IX', 'infraccion': 'Venta o transferencia de identidades falsas', 'multa': 1400000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 48 meses de prisión'},
    'Art.9.17': {'cap': 'IX', 'infraccion': 'Suplantación de identidad en redes sociales con fines delictivos', 'multa': 600000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 18 meses de prisión'},
    'Art.9.18': {'cap': 'IX', 'infraccion': 'Creación y uso de múltiples identidades falsas', 'multa': 1600000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 54 meses de prisión'},
    'Art.9.19': {'cap': 'IX', 'infraccion': 'Suplantación de identidad de figura pública o celebridad para cometer delitos', 'multa': 1100000, 'sancion': 'Multa + Arresto', 'condena': 'Hasta 36 meses de prisión'},

    # CAPÍTULO X: ESTUPEFACIENTES (10 artículos)
    'Art.10.1': {'cap': 'X', 'infraccion': 'Consumo de drogas en vía pública', 'multa': 50000, 'sancion': 'Sanción económica', 'condena': '—'},
    'Art.10.2': {'cap': 'X', 'infraccion': 'Posesión de drogas (cantidad baja)', 'multa': 100000, 'sancion': 'Sanción económica + incautación', 'condena': 'Hasta 3 meses'},
    'Art.10.3': {'cap': 'X', 'infraccion': 'Posesión de drogas (cantidad media)', 'multa': 200000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 6 meses'},
    'Art.10.4': {'cap': 'X', 'infraccion': 'Posesión de drogas (cantidad alta)', 'multa': 400000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 12 meses'},
    'Art.10.5': {'cap': 'X', 'infraccion': 'Distribución / venta de drogas', 'multa': 600000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 18 meses'},
    'Art.10.6': {'cap': 'X', 'infraccion': 'Tráfico de drogas (gran escala)', 'multa': 1000000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 24 meses'},
    'Art.10.7': {'cap': 'X', 'infraccion': 'Tráfico de drogas organizado (banda/red)', 'multa': 1500000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 36 meses'},
    'Art.10.8': {'cap': 'X', 'infraccion': 'Cultivo / producción de drogas', 'multa': 800000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 24 meses'},
    'Art.10.9': {'cap': 'X', 'infraccion': 'Transporte de drogas', 'multa': 750000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 18 meses'},
    'Art.10.10': {'cap': 'X', 'infraccion': 'Blanqueo de dinero procedente de drogas', 'multa': 1200000, 'sancion': 'Sanción económica + incautación + Arresto', 'condena': 'Hasta 30 meses'}
}

# ==========================================
#  🎯 APLICAR MULTIPLICADORES AUTOMÁTICAMENTE
# ==========================================

def _aplicar_multiplicadores():
    """
    Aplica los multiplicadores configurados a las multas del código penal.
    Se ejecuta automáticamente al importar el módulo.
    """
    CODIGO_PENAL = {}
    for codigo, datos in CODIGO_PENAL_BASE.items():
        # Copiar datos del artículo
        articulo = datos.copy()
        
        # Obtener capítulo
        capitulo = articulo['cap']
        
        # Aplicar multiplicadores
        multa_base = articulo['multa']
        mult_capitulo = MULTIPLICADORES_CAPITULOS.get(capitulo, 1.0)
        multa_final = int(multa_base * mult_capitulo * MULTIPLICADOR_GENERAL)
        
        # Actualizar multa
        articulo['multa'] = multa_final
        CODIGO_PENAL[codigo] = articulo
    
    return CODIGO_PENAL

# Generar el código penal con multiplicadores aplicados
CODIGO_PENAL = _aplicar_multiplicadores()

# ==========================================
#  CONVERSIÓN DE TIEMPO IC → OOC
# ==========================================

def convertir_tiempo_a_minutos(condena_texto: str, gravedad: Literal['leve', 'medio', 'grave'] = 'medio') -> int | str:
    """
    Convierte una condena de texto a minutos OOC.
    
    Fórmula de conversión:
    - 1 mes IC = 7.5 minutos OOC
    - 1 año IC = 90 minutos OOC
    - 1 día IC = 0.25 minutos OOC
    
    Modificadores de gravedad:
    - leve: 33% del tiempo (mínimo)
    - medio: 66% del tiempo (intermedio)
    - grave: 100% del tiempo (máximo)
    
    Args:
        condena_texto: Texto de la condena (ej: "Hasta 36 meses")
        gravedad: Nivel de gravedad del delito
    
    Returns:
        Minutos OOC (int) o 'CK' para cadena perpetua
    """
    if not condena_texto or condena_texto in ('—', 'Pena interna'):
        return 0
    
    # Cadena perpetua
    if 'Cadena perpetua' in condena_texto or 'Cadena Perpetua' in condena_texto:
        return 'CK'
    
    # Extraer números y unidades
    meses_match = re.search(r'(\d+)\s*mes(?:es)?', condena_texto, re.IGNORECASE)
    años_match = re.search(r'(\d+)\s*años?', condena_texto, re.IGNORECASE)
    dias_match = re.search(r'(\d+)\s*días?', condena_texto, re.IGNORECASE)
    
    total_minutos = 0
    
    # 1 mes IC = 7.5 minutos OOC
    if meses_match:
        meses = int(meses_match.group(1))
        total_minutos += meses * 7.5
    
    # 1 año IC = 90 minutos OOC
    if años_match:
        años = int(años_match.group(1))
        total_minutos += años * 90
    
    # 1 día IC ≈ 0.25 minutos OOC
    if dias_match:
        dias = int(dias_match.group(1))
        total_minutos += round(dias * 0.25)
    
    # Aplicar modificador de gravedad si la condena tiene "Hasta"
    if 'Hasta' in condena_texto:
        modificadores = {
            'leve': 0.33,   # 33% del tiempo
            'medio': 0.66,  # 66% del tiempo
            'grave': 1.0    # 100% del tiempo
        }
        total_minutos = round(total_minutos * modificadores.get(gravedad, 0.66))
    
    # Mínimo de 1 minuto si hay condena
    if total_minutos > 0 and total_minutos < 1:
        total_minutos = 1
    
    return int(total_minutos)

# ==========================================
#  PROCESAMIENTO DE ARTÍCULOS
# ==========================================

def procesar_articulos(articulos_string: str, gravedad: Literal['leve', 'medio', 'grave'] = 'medio') -> dict:
    """
    Procesa múltiples artículos del Código Penal.
    
    Args:
        articulos_string: Artículos separados por " - " (ej: "Art.1.1 - Art.2.3")
        gravedad: Nivel de gravedad
    
    Returns:
        dict con:
        - multa_total: int
        - tiempo_total: int (minutos OOC)
        - es_ck: bool
        - detalles: list[dict]
        - sanciones: list[str]
        - gravedad: str
    """
    articulos = [a.strip() for a in articulos_string.split('-')]
    multa_total = 0
    tiempo_total = 0
    es_ck = False
    detalles = []
    sanciones = set()

    for codigo in articulos:
        articulo = CODIGO_PENAL.get(codigo)
        if not articulo:
            return {'error': f'Artículo {codigo} no encontrado en el Código Penal'}

        multa_total += articulo['multa']
        tiempo = convertir_tiempo_a_minutos(articulo['condena'], gravedad)
        
        if tiempo == 'CK':
            es_ck = True
        else:
            tiempo_total += tiempo

        detalles.append({
            'codigo': codigo,
            'infraccion': articulo['infraccion'],
            'multa': articulo['multa'],
            'sancion': articulo['sancion'],
            'condena': articulo['condena'],
            'tiempo_minutos': tiempo
        })

        # Recopilar sanciones especiales
        if 'incautación' in articulo['sancion']:
            sanciones.add('incautación')
        if 'calabozo' in articulo['sancion']:
            sanciones.add('calabozo')
        if 'psicólogo' in articulo['sancion']:
            sanciones.add('psicólogo')
        if 'orden de alejamiento' in articulo['sancion']:
            sanciones.add('orden de alejamiento')
        if 'retirada' in articulo['sancion']:
            sanciones.add('retirada')

    return {
        'multa_total': multa_total,
        'tiempo_total': tiempo_total,
        'es_ck': es_ck,
        'detalles': detalles,
        'sanciones': list(sanciones),
        'gravedad': gravedad
    }

# ==========================================
#  CONSULTAS
# ==========================================

def obtener_articulo(codigo: str) -> dict | None:
    """Obtiene información de un artículo específico."""
    return CODIGO_PENAL.get(codigo)

def obtener_capitulo(numero_capitulo: str) -> dict:
    """Obtiene todos los artículos de un capítulo."""
    capitulos_nombres = {
        'I': 'DELITOS DE TRÁFICO',
        'II': 'AGRESIONES, DISTURBIOS Y CONDUCTAS ERRÓNEAS',
        'III': 'ROBOS Y ASALTOS',
        'IV': 'TENENCIA DE ARMAS Y OBJETOS',
        'V': 'POSESIÓN Y TRÁFICO DE DIVISAS',
        'VI': 'DELITOS CONTRA LA ADMINISTRACIÓN PÚBLICA',
        'VII': 'BANDAS Y ORGANIZACIONES CRIMINALES',
        'VIII': 'HOMICIDIO Y AGRESIONES',
        'IX': 'FALSIFICACIÓN Y SUPLANTACIÓN DE IDENTIDAD',
        'X': 'ESTUPEFACIENTES'
    }

    articulos = [
        {'codigo': codigo, **data}
        for codigo, data in CODIGO_PENAL.items()
        if data['cap'] == numero_capitulo
    ]

    return {
        'numero': numero_capitulo,
        'nombre': capitulos_nombres.get(numero_capitulo, 'DESCONOCIDO'),
        'articulos': articulos
    }

def obtener_codigo_penal_completo() -> dict:
    """Obtiene el código penal completo organizado por capítulos."""
    capitulos_nombres = {
        'I': 'DELITOS DE TRÁFICO',
        'II': 'AGRESIONES, DISTURBIOS Y CONDUCTAS ERRÓNEAS',
        'III': 'ROBOS Y ASALTOS',
        'IV': 'TENENCIA DE ARMAS Y OBJETOS',
        'V': 'POSESIÓN Y TRÁFICO DE DIVISAS',
        'VI': 'DELITOS CONTRA LA ADMINISTRACIÓN PÚBLICA',
        'VII': 'BANDAS Y ORGANIZACIONES CRIMINALES',
        'VIII': 'HOMICIDIO Y AGRESIONES',
        'IX': 'FALSIFICACIÓN Y SUPLANTACIÓN DE IDENTIDAD',
        'X': 'ESTUPEFACIENTES'
    }

    resultado = {}
    
    for numero, nombre in capitulos_nombres.items():
        articulos = [
            {'codigo': codigo, **data}
            for codigo, data in CODIGO_PENAL.items()
            if data['cap'] == numero
        ]
        
        resultado[numero] = {
            'numero': numero,
            'nombre': nombre,
            'articulos': articulos
        }
    
    return resultado
