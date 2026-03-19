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
    def __init__(self, headless: bool = True):
        self.playwright = None
        self.browser_context = None
        self.page = None
        self.headless = headless

    async def init_browser(self):
        print(f"🚀 Iniciando Chromium (Headless={self.headless}) con sesión persistente...")
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        self.playwright = await async_playwright().start()
        
        # Usamos launch_persistent_context que guarda cookies como un navegador real
        self.browser_context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=self.headless, 
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
            
        # Hover sobre la burbuja del mensaje para que aparezcan las acciones (los 3 puntitos)
        bubble = await target_message.query_selector('.msg-s-event-listitem__message-bubble')
        if bubble:
            await bubble.hover()
        else:
            await target_message.hover()
            
        await self.page.wait_for_timeout(2000) # Pausa humanizada un poco más larga
        
        # Clic en "Más opciones" (3 puntitos) - Selector específico encontrado en debug
        more_options_btn = await target_message.query_selector('.msg-s-event-listitem__options-trigger, button[aria-label*="Opciones"], button[aria-label*="Options"]')
        
        if not more_options_btn:
            # Plan B: Buscar por el icono dentro del botón
            more_options_btn = await target_message.query_selector('li.msg-s-message-options__option-item button, .msg-s-message-options button')

        if not more_options_btn:
            print("❌ No se encontró el botón de los 3 puntitos. Guardando debug info...")
            # DEBUG: Guardar HTML del mensaje y captura de pantalla
            html_msg = await target_message.inner_html()
            with open("debug_msg_fail.html", "w", encoding="utf-8") as f:
                f.write(html_msg)
            await self.page.screenshot(path="debug_msg_fail.png")
            return False

        if more_options_btn:
            await more_options_btn.click()
            await self.page.wait_for_timeout(1000)
        else:
            print("❌ No se encontró el botón de los 3 puntitos en el mensaje.")
            return False
            
        # Seleccionar "Editar" - Probamos varios selectores de texto y roles
        edit_btn = await self.page.query_selector('text="Editar", text="Edit", [role="menuitem"] >> text="Editar", [role="menuitem"] >> text="Edit"')
        if not edit_btn:
            # Plan B: Buscar por icono o clases comunes
            edit_btn = await self.page.query_selector('.msg-s-message-option-bar__edit-btn, .artdeco-dropdown__item:has-text("Edit"), .artdeco-dropdown__item:has-text("Editar")')

        if not edit_btn:
            print("❌ No se encontró la opción de Editar en el menú desplegable. Guardando debug...")
            # DEBUG: Guardar HTML del dropdown (está en una capa superior usualmente)
            menu_content = await self.page.query_selector('.artdeco-dropdown__content--is-open')
            if menu_content:
                html_menu = await menu_content.inner_html()
                with open("debug_menu_fail.html", "w", encoding="utf-8") as f:
                    f.write(html_menu)
            await self.page.screenshot(path="debug_menu_fail.png")
            return False

        if edit_btn:
            await edit_btn.click()
            await self.page.wait_for_timeout(1000)
            
        # Ahora el editor de texto reemplazó al globo de mensaje, o apareció en la conversación.
        # Esperamos un poco a que el DOM cambie
        await self.page.wait_for_timeout(2000)
        
        editor = await target_message.query_selector('div[role="textbox"], .msg-form__contenteditable, [contenteditable="true"]')
        if not editor:
            # Plan B: Buscar en toda la página el editor activo
            editor = await self.page.query_selector('.msg-form__contenteditable[contenteditable="true"]')

        if editor:
            print("⌨️ Campo de texto encontrado. Editando...")
            # Borrar texto viejo con Ctrl+A / Backspace simula humano
            await editor.click()
            await self.page.keyboard.press("Control+A")
            await self.page.wait_for_timeout(500)
            await self.page.keyboard.press("Backspace")
            
            # Escribir el nuevo texto
            await editor.type(new_text, delay=70) # Teclado humano
            await self.page.wait_for_timeout(1000)
            
            # Guardar/Enviar edición
            # A veces el botón GUARDAR está dentro del li, a veces es global en el form
            save_btn = await target_message.query_selector('button:has-text("Guardar"), button:has-text("Save")')
            if not save_btn:
                save_btn = await self.page.query_selector('.msg-form__send-button, button:has-text("Guardar"), button:has-text("Save")')

            if save_btn:
                await save_btn.click()
            else:
                await self.page.keyboard.press("Enter")
                
            print("✅ ¡Edición aplicada con éxito!")
            await self.page.wait_for_timeout(3000)
            return True
        else:
            print("❌ No se activó el campo de texto para editar el mensaje.")
            return False

    async def run(self, contact: str, old_msg: str, new_msg: str) -> bool:
        """Flujo orquestador"""
        try:
            await self.init_browser()
            
            if not await self.is_logged_in():
                if self.headless:
                    print("❌ NO SE HA INICIADO SESIÓN. Tu volumen de cookies está vacío.")
                    print("Por favor, ejecuta el script con --visual una vez para poner las credenciales.")
                    return False
                else:
                    print("⚠️ No se detectó sesión activa. POR FAVOR INICIA SESIÓN EN LA VENTANA ABIERTA.")
                    print("El script esperará a que estés en el Feed o Mensajería para continuar...")
                    # Esperar hasta que estemos en LinkedIn logueados (buscando el feed o mensajería)
                    while not await self.is_logged_in():
                        await asyncio.sleep(5)
                    print("✅ Sesión detectada. Continuando...")
                
            await self.navigate_to_chat(contact)
            success = await self.edit_message(old_msg, new_msg)
            return success
        finally:
            if self.browser_context:
                await self.browser_context.close()
            if self.playwright:
                await self.playwright.stop()
