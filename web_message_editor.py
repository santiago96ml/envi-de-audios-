"""
web_message_editor.py - Editor de mensajes de LinkedIn vía Chromium (Playwright).

Este script navega al chat de LinkedIn y utiliza cookies persistentes (para evitar
futuros inicios de sesión), busca un mensaje enviado previamente y lo edita de forma
humanizada para evadir la detección de bots.
"""

import asyncio
import time
from pathlib import Path
from playwright.async_api import async_playwright

# Directorio de datos de usuario para mantener sesión persistente y evitar baneos
USER_DATA_DIR = Path(__file__).resolve().parent / "chrome_profile"

class WebMessageEditor:
    def __init__(self):
        self.playwright = None
        self.browser_context = None
        self.page = None

    async def init_browser(self):
        print("🚀 Iniciando Chromium con sesión persistente...")
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        self.playwright = await async_playwright().start()
        
        # Usamos launch_persistent_context que guarda cookies como un navegador real
        self.browser_context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=True, # En producción correrá en background
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        self.page = await self.browser_context.new_page()
        self.page.set_default_timeout(60000)
        
    async def is_logged_in(self):
        try:
            await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            await self.page.wait_for_timeout(3000)
            if "login" in self.page.url or "authwall" in self.page.url:
                return False
            # Check for feed element
            return await self.page.query_selector('.scaffold-layout__main, .feed-shared-update-v2') is not None
        except Exception as e:
            print(f"Error verificando login: {e}")
            return False

    async def navigate_to_chat(self, chat_url_or_name: str):
        """Navega a la URL directa del chat o busca a la persona por nombre."""
        if chat_url_or_name.startswith("http"):
            print(f"🌐 Navegando a URL directa: {chat_url_or_name}")
            await self.page.goto(chat_url_or_name, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(3000)
            
            # Si era un perfil, hay que darle al botón de Enviar Mensaje
            if "/in/" in chat_url_or_name:
                print("   👤 Es un perfil. Buscando el botón de Mensaje...")
                msg_btn = await self.page.query_selector('button:has-text("Mensaje"), button:has-text("Message")')
                if msg_btn:
                    await msg_btn.click()
                    await self.page.wait_for_timeout(3000)
                else:
                    # Intentar en el menú "Más..."
                    more_btn = await self.page.query_selector('button[aria-label="Más acciones"], button[aria-label="More actions"]')
                    if more_btn:
                        await more_btn.click()
                        await self.page.wait_for_timeout(1000)
                        msg_btn_more = await self.page.query_selector('div.artdeco-dropdown__content >> text="Enviar mensaje"')
                        if msg_btn_more:
                            await msg_btn_more.click()
                            await self.page.wait_for_timeout(3000)
        else:
            print(f"🔍 Buscando chat por nombre: {chat_url_or_name}")
            await self.page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded")
            await self.page.wait_for_timeout(3000)
            search_input = await self.page.query_selector('input[placeholder*="Search messages"], input[placeholder*="Buscar mensajes"]')
            if search_input:
                await search_input.click()
                await search_input.fill(chat_url_or_name)
                await self.page.wait_for_timeout(2000)
                first_result = await self.page.query_selector('.msg-conversation-listitem__link')
                if first_result:
                    await first_result.click()
                    await self.page.wait_for_timeout(2000)
        
    async def edit_message(self, old_text: str, new_text: str) -> bool:
        """Busca el mensaje viejo, hace clic en el menú desplegable y lo edita."""
        print(f"✏️ Buscando el mensaje a editar: '{old_text}'")
        
        # Encontrar todos los mensajes en la vista actual
        messages = await self.page.query_selector_all('li.msg-s-message-list__event')
        target_message = None
        
        # Iterar de abajo hacia arriba (los más recientes)
        for msg in reversed(messages):
            text_content = await msg.inner_text()
            if old_text.strip().lower() in text_content.strip().lower():
                target_message = msg
                break
                
        if not target_message:
            print("❌ No se encontró el mensaje original en el chat.")
            return False
            
        print("✅ Mensaje encontrado. Procediendo a editar (espera humana)...")
        
        # Hover sobre el mensaje para que aparezcan las acciones (los 3 puntitos)
        await target_message.hover()
        await self.page.wait_for_timeout(1000) # Pausa humanizada
        
        # Clic en "Más opciones" (3 puntitos)
        more_options_btn = await target_message.query_selector('button[aria-label*="Opciones"], button[aria-label*="Options"]')
        if more_options_btn:
            await more_options_btn.click()
            await self.page.wait_for_timeout(1000)
        else:
            print("❌ No se encontró el botón de los 3 puntitos en el mensaje.")
            return False
            
        # Seleccionar "Editar"
        edit_btn = await self.page.query_selector('div.artdeco-dropdown__content >> text="Editar", div.artdeco-dropdown__content >> text="Edit"')
        if edit_btn:
            await edit_btn.click()
            await self.page.wait_for_timeout(1000)
        else:
            print("❌ No se encontró la opción de Editar en el menú desplegable.")
            return False
            
        # Ahora el editor de texto reemplazó al globo de mensaje.
        editor = await target_message.query_selector('div[role="textbox"]')
        if editor:
            # Borrar texto viejo con Ctrl+A / Backspace simula humano
            await editor.click()
            await self.page.keyboard.press("Control+A")
            await self.page.wait_for_timeout(500)
            await self.page.keyboard.press("Backspace")
            
            # Escribir el nuevo texto
            await editor.type(new_text, delay=50) # Teclado humano
            await self.page.wait_for_timeout(1000)
            
            # Guardar/Enviar edición (suele haber un botón "Guardar" o se envía con Enter)
            save_btn = await target_message.query_selector('button:has-text("Guardar"), button:has-text("Save")')
            if save_btn:
                await save_btn.click()
            else:
                await self.page.keyboard.press("Enter")
                
            print("✅ ¡Edición aplicada con éxito!")
            await self.page.wait_for_timeout(2000)
            return True
        else:
            print("❌ No se activó el campo de texto para editar el mensaje.")
            return False

    async def run(self, contact: str, old_msg: str, new_msg: str) -> bool:
        """Flujo orquestador"""
        try:
            await self.init_browser()
            
            if not await self.is_logged_in():
                print("❌ NO SE HA INICIADO SESIÓN. Tu volumen de cookies está vacío.")
                print("Por favor, levanta el contenedor sin headless una vez o usa --login para poner las credenciales.")
                return False
                
            await self.navigate_to_chat(contact)
            success = await self.edit_message(old_msg, new_msg)
            return success
        finally:
            if self.browser_context:
                await self.browser_context.close()
            if self.playwright:
                await self.playwright.stop()
