"""
dump_ui.py - Vuelca el árbol de UI de BlueStacks a un archivo XML
para identificar los selectores correctos de la App de LinkedIn.
"""
import uiautomator2 as u2
import config

d = u2.connect(config.ADB_SERIAL)
print("Tomando screenshot y volcando árbol de UI...")

# Guardar screenshot
d.screenshot("bluestacks_screen.png")
print("Screenshot: bluestacks_screen.png")

# Volcar jerarquía de UI
xml = d.dump_hierarchy()
with open("ui_dump.xml", "w", encoding="utf-8") as f:
    f.write(xml)
print("UI dump: ui_dump.xml")

# Buscar todos los elementos clicables en pantalla  
print("\n--- Elementos con 'voice' o 'audio' o 'mic' en sus atributos ---")
import re
matches = re.findall(r'<node[^>]*(?:voice|audio|mic|record)[^>]*>', xml, re.IGNORECASE)
for m in matches[:20]:
    print(m[:300])

print("\n--- Todos los elementos con contenido-desc ---")
descs = re.findall(r'content-desc="([^"]+)"', xml)
for d_val in descs[:30]:
    print(f"  content-desc: {d_val}")
