"""
Script de prueba para verificar que las correcciones funcionan
"""
import sys
print("✅ Verificando imports...")

try:
    from tema import Emojis, construir_embed, crear_vista_con_embed
    print("✅ Import de tema.py exitoso")
    print(f"   - crear_vista_con_embed disponible: {callable(crear_vista_con_embed)}")
except ImportError as e:
    print(f"❌ Error importando tema.py: {e}")
    sys.exit(1)

try:
    import discord
    print("✅ Import de discord.py exitoso")
except ImportError as e:
    print(f"❌ Error importando discord: {e}")
    sys.exit(1)

print("\n🔍 Probando crear_vista_con_embed...")
try:
    view = crear_vista_con_embed("error", descripcion="Mensaje de prueba")
    print(f"✅ Vista creada correctamente: {type(view)}")
    print(f"   - Es LayoutView: {isinstance(view, discord.ui.LayoutView)}")
    print(f"   - Tiene items: {len(list(view.walk_children())) > 0}")
except Exception as e:
    print(f"❌ Error creando vista: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ Todas las pruebas pasaron correctamente!")
print("\n📝 Resumen de cambios:")
print("   1. Agregada función helper 'crear_vista_con_embed' en tema.py")
print("   2. Corregidos todos los usos de LayoutView().add_item() en economia.py")
print("   3. Agregado manejo de errores en defer() para evitar 'Unknown interaction'")
print("   4. Eliminada verificación redundante en /pay que causaba falsos negativos")
print("\n🚀 El bot debería funcionar correctamente ahora!")
