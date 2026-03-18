import argparse
import sys
from android_message_editor import AndroidMessageEditor

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Android Bot - Editor de Mensajes")
    parser.add_argument("--contact", type=str, required=True, help="Nombre del contacto o URL directa del chat/perfil")
    parser.add_argument("--old", type=str, required=True, help="Texto original del mensaje a buscar")
    parser.add_argument("--new", type=str, required=True, help="Nuevo texto para reemplazar")

    args = parser.parse_args()

    print("═══════════════════════════════════════════════════════════")
    print("      ✏️ LinkedIn Android Bot - Editor de Mensajes")
    print("═══════════════════════════════════════════════════════════")

    editor = AndroidMessageEditor()
    
    if not editor.connect():
        sys.exit(1)

    # Opcional: intentamos navegar al chat si se provee
    editor.navigate_to_chat(args.contact)

    # Intentamos editar el mensaje
    result = editor.edit_message(args.old, args.new)

    if result.get("success"):
        print("✅ Operación completada con éxito.")
    else:
        print(f"❌ Falló la operación: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
