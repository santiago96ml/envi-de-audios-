import argparse
import asyncio
from web_message_editor import WebMessageEditor

async def main():
    parser = argparse.ArgumentParser(description="Edita un mensaje de LinkedIn en la web vía Playwright.")
    parser.add_argument("--contact", required=True, help="URL del chat o nombre del contacto")
    parser.add_argument("--old", required=True, help="Texto original a buscar")
    parser.add_argument("--new", required=True, help="Nuevo texto para reemplazar")
    args = parser.parse_args()

    editor = WebMessageEditor()
    success = await editor.run(
        contact=args.contact,
        old_msg=args.old,
        new_msg=args.new
    )
    
    if not success:
        print("\n❌ Error: La edición web falló.")
        exit(1)
        
    print("\n✅ Proceso de edición finalizado con éxito.")

if __name__ == "__main__":
    asyncio.run(main())
