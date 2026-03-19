import argparse
import asyncio
import sys
from web_message_editor import WebMessageEditor

async def main():
    parser = argparse.ArgumentParser(description="Edita un mensaje de LinkedIn en la web vía Playwright.")
    parser.add_argument("--contact", required=True, help="URL del chat o nombre del contacto")
    parser.add_argument("--old", required=True, help="Texto original a buscar")
    parser.add_argument("--new", required=True, help="Nuevo texto para reemplazar")
    parser.add_argument("--visual", action="store_true", help="Abrir el navegador físicamente (no headless)")
    args = parser.parse_args()

    # Si se pasa --visual, headless es False
    editor = WebMessageEditor(headless=not args.visual)
    
    success = await editor.run(
        contact=args.contact,
        old_msg=args.old,
        new_msg=args.new
    )
    
    if not success:
        print("\n❌ Error: La edición web falló.")
        sys.exit(1)
        
    print("\n✅ Proceso de edición finalizado con éxito.")

if __name__ == "__main__":
    asyncio.run(main())
