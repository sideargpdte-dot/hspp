"""
╔══════════════════════════════════════════════════════════╗
║          TEMA BOT — Sistema Visual Centralizado         ║
║                                                          ║
║  Para ajustar los colores de tu servidor, editá los      ║
║  valores hexadecimales en la clase TemaBot más abajo.    ║
╚══════════════════════════════════════════════════════════╝
"""

import discord
import discord.ui


class TemaBot:
    """Paleta de colores centralizada del bot. Modificá los hex para personalizar."""
    PRINCIPAL   = 0x240000
    EXITO       = 0x22F9B9
    ERROR       = 0xA0323F
    ADVERTENCIA = 0xD4A373   
    ECONOMIA    = 0xF5AE7B  
    CASINO      = 0x5158FF  
    POLICIAL    = 0xAABFC6 
    GOBIERNO    = 0xAABFC6 
    LOG         = 0x151617
    GLOBAL_FOOTER_IMAGE = "https://media.discordapp.net/attachments/1437532141947715684/1516146711872143381/image_39.png?ex=6a32e6a8&is=6a319528&hm=cc04ead9638cd255ea1a52496a2df3d46f957f46dd02f722bada7e38e9d691e4&=&format=webp&quality=lossless&width=1860&height=104"
    THUMBNAIL_GOBIERNO = "https://media.discordapp.net/attachments/1491525836270993599/1540793152343117854/250px-Sello_Ministerio_de_Seguridad_Nacional_-_Argentina.png?ex=6a8b3ef2&is=6a89ed72&hm=891e3e4ccbb859858c8708b31c74c745ca96acc54d2f1a8441185548bc6c3c06&=&format=webp&quality=lossless"
    THUMBNAIL_POLICIAL = "https://media.discordapp.net/attachments/1491525836270993599/1540793152343117854/250px-Sello_Ministerio_de_Seguridad_Nacional_-_Argentina.png?ex=6a8b3ef2&is=6a89ed72&hm=891e3e4ccbb859858c8708b31c74c745ca96acc54d2f1a8441185548bc6c3c06&=&format=webp&quality=lossless"


# ==========================================
#  EMOJIS CONSISTENTES
# ==========================================

class Emojis:
    """Emojis unificados para todo el bot. Cambiá por custom emojis si lo deseás."""

    # Estado
    EXITO       = "<:Aprobado:1516817016181358702>"
    ERROR       = "<:error:1540774103991189535>"
    ADVERTENCIA = "<:warn:1540774105668649031>"
    DENEGADO    = "<:Denegado:1516817442968567939>"
    RELOJ       = "<a:loading:1540774102355419307>"
    INFO        = "<:info:1540774774303760584>"

    # Economía
    DINERO      = "<:peso:1517705795267989719>"
    EFECTIVO    = "<:billete:1540775220808257556>"
    BANCO       = "🏦"
    CAJERO      = "🏦"
    PAGO        = "💸"
    GRAFICO     = "<:stats:1540797358974173276>"
    BAJA        = "📉"

    # Policial
    POLICIA     = "<a:Sirena_Roja:1497293927592759478>"
    ARRESTO     = "<:esposas:1540795058843025428>"
    BUSCADO     = "<a:Sirena_Roja:1497293927592759478>"
    LIMPIO      = "<:Aprobado:1516817016181358702>"
    PRESO       = "<:esposas:1540795058843025428>"
    SIRENA      = "<a:Sirena_Roja:1497293927592759478>"

    # RP / Gobierno
    DOCUMENTO   = "📋"
    LICENCIA    = "💳"
    ARMA        = "<:escopeta:1540794824297422928>"
    MULTA       = "📝"
    USUARIO     = "👤"
    SLOT        = "📂"
    TRAMITE     = "💳"
    EDITAR      = "✏️"
    BORRAR      = "🗑️"
    PERSONAS    = "👥"

    # Casino
    CASINO      = "<a:casino:1540795611903688775>"
    RULETA      = "🎡"
    DADO        = "🎲"
    FUEGO       = "🔥"
    CORONA      = "👑"
    TROFEO      = "🏆"
    
    # Custom Emojis para Blackjack (52 cartas individuales + Carta Volteada)
    CARTAS_COMPLETAS = {
        'A♠️': '<:aP:1538947830465699931>', '2♠️': '<:2P:1538947857774547057>', '3♠️': '<:3P:1538947825633857577>', '4♠️': '<:4P:1538947865978601482>', '5♠️': '<:5P:1538947841429606440>', '6♠️': '<:6P:1538947833288458302>', '7♠️': '<:7P:1538947864242159617>', '8♠️': '<:8P:1538947845036707941>', '9♠️': '<:9P:1538947839881650226>', '10♠️': '<:10P:1538947861012807780>', 'J♠️': '<:jP:1538947851898331176>', 'Q♠️': '<:qP:1538947855098712064>', 'K♠️': '<:kP:1538947867224571935>',
        'A♥️': '<:aC:1538947805253603438>', '2♥️': '<:2C:1538947806851506406>', '3♥️': '<:3C:1538947819107520605>', '4♥️': '<:4C:1538947800908300439>', '5♥️': '<:5C:1538947817370816564>', '6♥️': '<:6C:1538947810186240000>', '7♥️': '<:7C:1538947802313392320>', '8♥️': '<:8C:1538947793111220314>', '9♥️': '<:9C:1538947799159144519>', '10♥️': '<:10C:1538947815865196564>', 'J♥️': '<:jC:1538948097739063326>', 'Q♥️': '<:qC:1538947796202299463>', 'K♥️': '<:kC:1538947814305038466>',
        'A♦️': '<:aD:1538947784877801473>', '2♦️': '<:2D:1538947808621498398>', '3♦️': '<:3D:1538947803764760606>', '4♦️': '<:4D:1538947786395877386>', '5♦️': '<:5D:1538947794684084334>', '6♦️': '<:6D:1538947782843310152>', '7♦️': '<:7D:1538947789197680720>', '8♦️': '<:8D:1538947822441726033>', '9♦️': '<:9D:1538947823897149490>', '10♦️': '<:10D:1538947791030845560>', 'J♦️': '<:jD:1538947820936237237>', 'Q♦️': '<:qC:1538947796202299463>', 'K♦️': '<:kD:1538947812115480666>',
        'A♣️': '<:aT:1538947828896759858>', '2♣️': '<:2T:1538947859561324614>', '3♣️': '<:3T:1538947835096072272>', '4♣️': '<:4T:1538947831887564850>', '5♣️': '<:5T:1538947843207864381>', '6♣️': '<:6T:1538947850082459709>', '7♣️': '<:7T:1538947869183185087>', '8♣️': '<:8T:1538947862774415482>', '9♣️': '<:9T:1538947827302928394>', '10♣️': '<:10T:1538947848165527613>', 'J♣️': '<:jT:1538947846697525310>', 'Q♣️': '<:qT:1538947837461668003>', 'K♣️': '<:kT:1538947870655381678>',
        'OCULTA': '<:bs:1538947853588766780>'
    }

    # Rankings
    ORO         = "<a:first:1540797753209258096>"
    PLATA       = "<a:second:1540797758070456433>"
    BRONCE      = "<a:third:1540797755323195413>"

    # Trabajo
    TRABAJO     = "🔨"
    CAMION      = "🛻"

    # Misc
    SWAP        = "<:swap:1540797268767150091>"
    NUCLEAR     = "<a:Sirena_Roja:1497293927592759478>"


# ==========================================
#  MAPEO DE TIPOS → COLORES
# ==========================================

_COLORES_TIPO = {
    "criminalidad":   TemaBot.PRINCIPAL, 
    "casino":         TemaBot.CASINO,
    "administracion": TemaBot.LOG,
    "economia":       TemaBot.ECONOMIA, 
    "advertencias":   TemaBot.ADVERTENCIA,
    "policial":       TemaBot.POLICIAL,
    "errores":        TemaBot.ERROR,
    "exito":          TemaBot.EXITO,
}

# ==========================================
#  MAPEO DE TIPOS → BANNERS INFERIORES V2
# ==========================================

_BANNERS_TIPO = {
    "criminalidad":   "https://media.discordapp.net/attachments/1531701803748425758/1539785295149535282/image324.png?ex=6a87944e&is=6a8642ce&hm=cdfb35b0e970f47370ccca99e365252eb01d7dd9a2f3d994e61626ab4f851ae4&=&format=webp&quality=lossless&width=1024&height=58",
    "casino":         "https://media.discordapp.net/attachments/1531701803748425758/1539785314837471423/image_47.png?ex=6a879452&is=6a8642d2&hm=28a01e1306df51409d962f5b3e9756ac1ead88c75640194f2b4fc8a12f33ce2b&=&format=webp&quality=lossless&width=1024&height=58",
    "administracion": "https://media.discordapp.net/attachments/1531701803748425758/1539785354461188188/image_49.png?ex=6a87945c&is=6a8642dc&hm=c2509b1b8b0762b05b3914cc905c460ee3a1a18fdfdba2a770caaeeb2923a736&=&format=webp&quality=lossless&width=1024&height=58",
    "economia":       "https://media.discordapp.net/attachments/1531701803748425758/1539785374497378334/image_50.png?ex=6a879461&is=6a8642e1&hm=da7fb34257fcf8dab0a8931cd96eae9a51f832d8372a744ef81e758688c99165&=&format=webp&quality=lossless&width=1024&height=58",
    "advertencias":   "https://media.discordapp.net/attachments/1531701803748425758/1539789048799821834/image_55.png?ex=6a8797cd&is=6a86464d&hm=127c9cfb804aa6bc528e233f0592f25a8c75337332a1dae52683a917ac2ea8ad&=&format=webp&quality=lossless&width=1024&height=58",
    "policial":       "https://media.discordapp.net/attachments/1531701803748425758/1539789987313229874/image.png?ex=6a8798ac&is=6a86472c&hm=49e18c5c2ec8b33c79de0cc485422a0a18c573e9d7833cd14c29ce3634b70ebf&=&format=webp&quality=lossless&width=1024&height=58",
    "errores":        "https://media.discordapp.net/attachments/1531701803748425758/1539790421964890184/image.png?ex=6a879914&is=6a864794&hm=1c42f3f7da890e4a461174ac3f04c19e06f21868cda94a2fff8174f8d9f8fad6&=&format=webp&quality=lossless&width=1024&height=58",
    "exito":          "https://media.discordapp.net/attachments/1531701803748425758/1539790638797815878/image.png?ex=6a879948&is=6a8647c8&hm=7b604e52792aedd384dec7f3f3dc1c1fd4d9505b1e4947827048a68c8b807269&=&format=webp&quality=lossless&width=1024&height=58",
}


# ==========================================
#  CONSTRUCTOR DE COMPONENTES V2 CENTRALIZADO
# ==========================================

def construir_embed(
    tipo: str = "principal",
    titulo: str = None,
    descripcion: str = None,
    campos: list = None,
    thumbnail: str = None,
    imagen: str | list = None,
    footer_texto: str = None,
    footer_icon: str = None,
    autor: dict = None,
    color_override: int = None,
):
    """
    Constructor centralizado para Component-Based Messages (V2).
    Reemplaza al antiguo discord.Embed.

    Retorna un discord.ui.Container que debe ser enviado dentro de una vista
    (ej: discord.ui.LayoutView().add_item(container)).
    """
    # -- MAPEO DE RETROCOMPATIBILIDAD --
    mapa_retrocompatibilidad = {
        "error": "errores",
        "advertencia": "advertencias",
        "ilegal": "criminalidad",
        "roleplay": "economia", 
        "principal": "administracion",
        "log": "administracion"
    }
    tipo_real = mapa_retrocompatibilidad.get(tipo, tipo)

    # 1. Determinar color
    color = color_override if color_override is not None else _COLORES_TIPO.get(tipo_real, TemaBot.PRINCIPAL)

    # 2. Crear Container
    container = discord.ui.Container(accent_color=discord.Color(color))

    # 3. Sección Principal (Texto y Accesorio)
    textos = []
    if titulo:
        textos.append(f"## {titulo}")
    if descripcion:
        textos.append(descripcion)
    if campos:
        textos.append("")
        for campo in campos:
            if isinstance(campo, (list, tuple)) and len(campo) >= 2:
                nombre, valor = campo[0], campo[1]
                textos.append(f"### {nombre}\n{valor}")

    # 4. Integrar footer_texto si se suministra (Soporte V2)
    if footer_texto:
        textos.append(f"\n*{footer_texto}*")

    # 5. Thumbnail como Accesorio
    final_thumbnail = thumbnail
    if not final_thumbnail:
        if tipo == "policial":
            final_thumbnail = TemaBot.THUMBNAIL_POLICIAL

    if final_thumbnail:
        acc = discord.ui.Thumbnail(media=final_thumbnail)
        section = discord.ui.Section(accessory=acc)
        if textos:
            section.add_item(discord.ui.TextDisplay("\n".join(textos)))
        container.add_item(section)
    else:
        if textos:
            container.add_item(discord.ui.TextDisplay("\n".join(textos)))

    # 6. Imagen adicional del embed anterior (se agrega como galería si se pasó `imagen`)
    if imagen:
        items_media = [img for img in imagen if img] if isinstance(imagen, list) else ([imagen] if imagen else [])
        if items_media:
            container.add_item(discord.ui.Separator())
            extra_gallery = discord.ui.MediaGallery()
            for img in items_media:
                extra_gallery.add_item(media=img)
            container.add_item(extra_gallery)

    # 7. Footer Dinámico por Tipo
    footer_url = _BANNERS_TIPO.get(tipo_real, _BANNERS_TIPO.get("administracion"))
    if footer_url:
        container.add_item(discord.ui.Separator())
        footer = discord.ui.MediaGallery()
        footer.add_item(media=footer_url)
        container.add_item(footer)

    return container


# ==========================================
#  FUNCIÓN HELPER PARA CREAR VISTAS
# ==========================================

def crear_vista_con_embed(tipo: str = "principal", **kwargs):
    """
    Helper para crear una LayoutView con un Container embed.
    
    Uso:
        view = crear_vista_con_embed("error", descripcion="Algo salió mal")
        await interaction.response.send_message(view=view)
    
    Args:
        tipo: Tipo de embed (error, exito, advertencia, etc.)
        **kwargs: Argumentos para construir_embed()
    
    Returns:
        discord.ui.LayoutView con el container embed agregado
    """
    embed_container = construir_embed(tipo, **kwargs)
    view = discord.ui.LayoutView()
    view.add_item(embed_container)
    return view
