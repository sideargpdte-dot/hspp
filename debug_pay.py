"""
Script de depuración para verificar problemas con el comando /pay
"""
import aiosqlite
import asyncio

async def debug_user_data(user_id: int, slot: int):
    """Verifica los datos de un usuario específico"""
    async with aiosqlite.connect('roleplay.db') as db:
        # Verificar datos del usuario
        async with db.execute(
            "SELECT id_usuario, nombres, apellidos, dinero_mano, dinero_banco, slot FROM usuarios WHERE id_usuario = ? AND slot = ?",
            (user_id, slot)
        ) as cur:
            user_data = await cur.fetchone()
        
        if user_data:
            print(f"\n{'='*60}")
            print(f"DATOS DEL USUARIO: {user_data[1]} {user_data[2]}")
            print(f"{'='*60}")
            print(f"ID Usuario: {user_data[0]}")
            print(f"Slot: {user_data[5]}")
            print(f"Dinero en Mano: ${user_data[3]:,}")
            print(f"Dinero en Banco: ${user_data[4]:,}")
            print(f"Total: ${(user_data[3] + user_data[4]):,}")
            print(f"{'='*60}\n")
        else:
            print(f"❌ No se encontró usuario con ID {user_id} en el slot {slot}")
        
        # Verificar sesión activa
        async with db.execute(
            "SELECT user_id, slot_activo FROM sesiones WHERE user_id = ?",
            (user_id,)
        ) as cur:
            sesion = await cur.fetchone()
        
        if sesion:
            print(f"📋 SESIÓN ACTIVA:")
            print(f"   Slot Activo: {sesion[1]}")
            if sesion[1] != slot:
                print(f"   ⚠️ ADVERTENCIA: El slot activo ({sesion[1]}) NO coincide con el consultado ({slot})")
        else:
            print(f"📋 No hay sesión activa registrada (usará slot 1 por defecto)")

async def main():
    print("\n🔍 SCRIPT DE DEPURACIÓN - COMANDO /PAY")
    print("="*60)
    
    # Solicitar ID del usuario problemático
    try:
        user_id = int(input("Ingresa el ID del usuario con problemas: "))
        slot = int(input("Ingresa el slot (1 o 2): "))
        
        await debug_user_data(user_id, slot)
        
    except ValueError:
        print("❌ Error: Debes ingresar valores numéricos válidos")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
