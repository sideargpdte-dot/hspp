import os
import re

cogs = ['cogs/roleplay.py', 'cogs/economia.py', 'cogs/policia.py', 'cogs/casino.py']

def process_file(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    new_content = content.replace('utils.db', 'interaction.client.db')
    
    new_content = re.sub(
        r'await utils\.get_slot_activo\(([^,)]+)\)', 
        r'await utils.get_slot_activo(\1, interaction.client.db, interaction.client.sesiones_cache)', 
        new_content
    )
    
    new_content = re.sub(
        r'await utils\.update_slot_activo_cache\(([^,]+),\s*([^)]+)\)', 
        r'await utils.update_slot_activo_cache(\1, \2, interaction.client.db, interaction.client.sesiones_cache)', 
        new_content
    )

    new_content = re.sub(
        r'await utils\.get_active_char\(([^,)]+)\)', 
        r'await utils.get_active_char(\1, interaction.client.db, interaction.client.sesiones_cache)', 
        new_content
    )
    
    new_content = re.sub(
        r'await utils\.check_cooldown_pro\(([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', 
        r'await utils.check_cooldown_pro(\1, \2, \3, \4, interaction.client.db)', 
        new_content
    )

    new_content = re.sub(
        r'await utils\.update_cooldown\(([^,]+),\s*([^,]+),\s*([^)]+)\)', 
        r'await utils.update_cooldown(\1, \2, \3, interaction.client.db)', 
        new_content
    )
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")
    else:
        print(f"No changes in {filepath}")

for cog in cogs:
    process_file(cog)

