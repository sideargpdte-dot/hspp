"""
Script de depuración para el problema de cambio de slot en /pay
"""
import aiosqlite
import asyncio

async def debug_slot_issue(user_id: int):
    """Verifica el estado del slot de un usuario"""
    async with aiosqlite.connect('roleplay.db') as db:
        print(f"\n{'='*60}")
        print(f"DIAGNÓSTICO DE SLOT PARA USER_ID: {user_id}")
        print(f"{'='*60}\n")
        
        # 1. Verificar sesión activa
        async with db.execute(
            "SELECT user_id, slot_activo FROM sesiones WHERE user_id = ?",
            (user_id,)
        ) as cur:
            sesion = await cur.fetchone()
        
        if sesion:
            print(f"✅ SESIÓN REGISTRADA:")
            print(f"   Slot Activo: {sesion[1]}")
        else:
            print(f"⚠️  NO HAY SESIÓN REGISTRADA")
            print(f"   Comportamiento: El sistema usará Slot 1 por defecto")
            print(f"   ESTO PUEDE CAUSAR EL CAMBIO DE SLOT!")
        
        # 2. Verificar personajes registrados
        async with db.execute(
            "SELECT id_usuario, slot, nombres, apellidos, dinero_mano, dinero_banco FROM usuarios WHERE id_usuario = ?",
            (user_id,)
        ) as cur:
            personajes = await cur.fetchall()
        
        print(f"\n📋 PERSONAJES REGISTRADOS: {len(personajes)}")
        for pj in personajes:
            print(f"   Slot {pj[1]}: {pj[2]} {pj[3]} | Mano: ${pj[4]:,} | Banco: ${pj[5]:,}")
        
        # 3. Diagnóstico y recomendación
        print(f"\n{'='*60}")
        print("DIAGNÓSTICO:")
        print(f"{'='*60}")
        
        if not sesion and len(personajes) > 0:
            print("⚠️  PROBLEMA DETECTADO:")
            print("   - El usuario tiene personajes pero NO tiene sesión registrada")
            print("   - Cada vez que use get_active_char, se creará una sesión en Slot 1")
            print("   - Esto puede cambiar su slot activo sin querer")
            print(f"\n💡 SOLUCIÓN: Crear sesión manualmente con:")
            print(f"   INSERT INTO sesiones (user_id, slot_activo) VALUES ({user_id}, 1);")
        elif sesion and len(personajes) == 0:
            print("⚠️  INCONSISTENCIA:")
            print("   - Hay sesión registrada pero NO hay personajes")
        elif not sesion and len(personajes) == 0:
            print("ℹ️  Usuario nuevo o sin personajes registrados")
        else:
            print("✅ Estado normal - Sesión y personajes coinciden")

async def fix_missing_sessions():
    """Crea sesiones para usuarios que no las tienen"""
    async with aiosqlite.connect('roleplay.db') as db:
        print("\n🔧 REPARACIÓN AUTOMÁTICA: Creando sesiones faltantes...")
        
        # Encontrar usuarios sin sesión
        async with db.execute("""
            SELECT DISTINCT u.id_usuario, MIN(u.slot) as primer_slot
            FROM usuarios u
            LEFT JOIN sesiones s ON u.id_usuario = s.user_id
            WHERE s.user_id IS NULL
            GROUP BY u.id_usuario
        """) as cur:
            usuarios_sin_sesion = await cur.fetchall()
        
        if not usuarios_sin_sesion:
            print("✅ Todos los usuarios tienen sesión registrada")
            return
        
        print(f"Encontrados {len(usuarios_sin_sesion)} usuarios sin sesión")
        
        for user_id, primer_slot in usuarios_sin_sesion:
            await db.execute(
                "INSERT INTO sesiones (user_id, slot_activo) VALUES (?, ?)",
                (user_id, primer_slot)
            )
            print(f"   ✅ Creada sesión para user {user_id} en slot {primer_slot}")
        
        await db.commit()
        print("\n✅ Reparación completada!")

async def main():
    print("\n🔍 SCRIPT DE DIAGNÓSTICO - CAMBIO DE SLOT EN /PAY")
    print("="*60)
    
    print("\n1️⃣  Diagnóstico Individual")
    print("2️⃣  Reparación Automática (crear sesiones faltantes)")
    print("3️⃣  Salir")
    
    opcion = input("\nSelecciona una opción (1-3): ").strip()
    
    if opcion == "1":
        try:
            user_id = int(input("Ingresa el ID del usuario: "))
            await debug_slot_issue(user_id)
        except ValueError:
            print("❌ Error: ID inválido")
    elif opcion == "2":
        confirmar = input("⚠️  Esto modificará la base de datos. ¿Continuar? (SI/NO): ").strip().upper()
        if confirmar == "SI":
            await fix_missing_sessions()
        else:
            print("❌ Operación cancelada")
    elif opcion == "3":
        print("👋 Saliendo...")
    else:
        print("❌ Opción inválida")

if __name__ == "__main__":
    asyncio.run(main())
