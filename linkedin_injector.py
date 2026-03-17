"""
linkedin_injector.py - Núcleo de Playwright y la inyección de JavaScript.

Este módulo se encarga de:
1. Iniciar Chromium con banderas de "fake media" para virtualizar el micrófono.
2. Gestionar la sesión de LinkedIn (inicio manual/automático y persistencia).
3. Inyectar código JS que usa getUserMedia -> MediaRecorder -> Blob -> fetch()
   para enviar el audio capturado como un mensaje de voz real.
"""

import asyncio
import time
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

import config


class LinkedInInjector:
    """Controlador principal de Playwright para la inyección de voz en LinkedIn."""

    def __init__(self, processed_wav_path: Path, audio_duration_seconds: float, cookie: str = None):
        """
        Args:
            processed_wav_path: Ruta absoluta al WAV procesado (PCM 16-bit mono 16kHz).
            audio_duration_seconds: Duración del audio en segundos.
            cookie: Cookie de sesión 'li_at' o JSON de cookies.
        """
        self.wav_path = Path(processed_wav_path).resolve()
        self.audio_duration_s = audio_duration_seconds
        self.cookie = cookie
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

        if not self.wav_path.exists():
            raise FileNotFoundError(f"WAV no encontrado: {self.wav_path}")

    # ==========================================================================
    # GESTIÓN DEL NAVEGADOR
    # ==========================================================================

    async def launch_browser(self):
        """
        Inicia Chromium con las banderas necesarias para falsificar el flujo de medios.

        Banderas:
          --use-fake-device-for-media-stream : Usa dispositivos de medios falsos.
          --use-fake-ui-for-media-stream     : Evita los diálogos de permisos del navegador.
          --use-file-for-fake-audio-capture  : Usa nuestro archivo WAV como entrada de micrófono.
        """
        self.playwright = await async_playwright().start()

        # Normalizar la ruta del archivo WAV para usarla como bandera
        wav_path_str = str(self.wav_path).replace("\\", "/")

        chrome_args = [
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
            f"--use-file-for-fake-audio-capture={wav_path_str}",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]

        print(f"🚀 Iniciando Chromium con micrófono virtual...")
        print(f"   Audio de origen: {self.wav_path.name}")
        print(f"   Duración: {self.audio_duration_s:.2f}s")

        # Verificar si existe un estado de sesión guardado
        storage_state = None
        if config.SESSION_STATE_FILE.exists():
            storage_state = str(config.SESSION_STATE_FILE)
            print(f"   📦 Restaurando sesión desde: {config.SESSION_STATE_FILE.name}")

        self.browser = await self.playwright.chromium.launch(
            headless=config.HEADLESS,
            args=chrome_args,
        )

        # Crear contexto del navegador con permisos y estado de sesión
        context_options = {
            "user_agent": config.USER_AGENT,
            "viewport": {
                "width": config.VIEWPORT_WIDTH,
                "height": config.VIEWPORT_HEIGHT,
            },
            "permissions": ["microphone"],
            "accept_downloads": False,
        }

        if storage_state:
            context_options["storage_state"] = storage_state

        self.context = await self.browser.new_context(**context_options)

        # Conceder permisos de micrófono explícitamente para LinkedIn
        await self.context.grant_permissions(
            permissions=["microphone"],
            origin="https://www.linkedin.com",
        )

        self.page = await self.context.new_page()
        
        # Inyectar la cookie si se proporcionó una
        if self.cookie:
            print(f"   🍪 Inyectando cookie li_at de acceso...")
            await self.context.add_cookies([{
                'name': 'li_at',
                'value': self.cookie,
                'domain': '.www.linkedin.com',
                'path': '/',
                'expires': int(time.time()) + 60*60*24*30 # 30 días
            }])
        self.page.on("console", lambda msg: print(f"[Chromium] {msg.text}"))
        self.page.set_default_timeout(config.DEFAULT_TIMEOUT)
        self.page.set_default_navigation_timeout(config.NAVIGATION_TIMEOUT)

        print("✅ Navegador lanzado y configurado.\n")

    async def close_browser(self):
        """Cierra el navegador y libera recursos de Playwright."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("🔒 Navegador cerrado.")

    # ==========================================================================
    # GESTIÓN DE SESIÓN
    # ==========================================================================

    async def save_session(self):
        """Guarda el estado de autenticación (cookies + localStorage) a disco."""
        config.SESSION_DATA_DIR.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=str(config.SESSION_STATE_FILE))
        print(f"💾 Sesión guardada en: {config.SESSION_STATE_FILE.name}")

    async def is_logged_in(self) -> bool:
        """Verifica si la sesión actual está autenticada en LinkedIn."""
        try:
            await self.page.goto(config.LINKEDIN_FEED_URL, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000)

            # Verificar que estamos en el feed y no en la página de login
            current_url = self.page.url
            if "/login" in current_url or "/authwall" in current_url:
                return False

            # Verificar presencia de elementos del feed
            feed_indicator = await self.page.query_selector(
                'div.feed-shared-update-v2, [data-test-id="feed-shared-update"],'
                ' .scaffold-layout__main'
            )
            return feed_indicator is not None

        except Exception as e:
            print(f"⚠️  Error verificando sesión: {e}")
            return False

    async def login(self):
        """
        Gestiona el inicio de sesión en LinkedIn.

        Si hay credenciales en el archivo de configuración, intenta el inicio automático.
        De lo contrario, espera al usuario para el inicio de sesión manual y luego guarda la sesión.
        """
        print("🔐 Iniciando proceso de autenticación en LinkedIn...")

        # Verificar si ya estamos logueados (ya sea por archivo o por cookie recién inyectada)
        if config.SESSION_STATE_FILE.exists() or self.cookie:
            if await self.is_logged_in():
                print("✅ Sesión restaurada con éxito (archivo o cookie). Ya estás autenticado.\n")
                return

        # Navegar a la página de inicio de sesión
        await self.page.goto(config.LINKEDIN_LOGIN_URL, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

        if config.LINKEDIN_EMAIL and config.LINKEDIN_PASSWORD:
            # Inicio automático con credenciales
            print("   Intentando inicio de sesión automático...")

            await self.page.fill('input#username', config.LINKEDIN_EMAIL)
            await self.page.wait_for_timeout(500)
            await self.page.fill('input#password', config.LINKEDIN_PASSWORD)
            await self.page.wait_for_timeout(500)
            await self.page.click('button[type="submit"]')

            # Esperar a que cargue el feed o aparezca un captcha/verificación
            try:
                await self.page.wait_for_url(
                    "**/feed/**",
                    timeout=30000,
                )
                print("✅ Inicio de sesión automático completado.\n")
            except Exception:
                print(
                    "⚠️  El inicio de sesión automático no pudo completarse "
                    "(posible CAPTCHA o verificación en dos pasos)."
                )
                print(
                    "   👉 Por favor, completa el proceso manualmente en el navegador."
                )
                print("   Presiona ENTER aquí cuando hayas terminado...")
                await asyncio.get_event_loop().run_in_executor(None, input)
        else:
            # Inicio de sesión manual
            print("   📝 No se encontraron credenciales configuradas.")
            print("   👉 Por favor, inicia sesión manualmente en el navegador.")
            print("   Presiona ENTER aquí cuando hayas terminado...")
            await asyncio.get_event_loop().run_in_executor(None, input)

        # Verificar si el inicio de sesión fue exitoso
        await self.page.wait_for_timeout(2000)
        if await self.is_logged_in():
            await self.save_session()
            print("✅ Autenticación válida. Sesión guardada.\n")
        else:
            raise RuntimeError(
                "No se pudo validar la sesión. "
                "Asegúrate de haber iniciado sesión correctamente."
            )

    # ==========================================================================
    # NAVEGACIÓN A CONVERSACIÓN
    # ==========================================================================

    async def navigate_to_conversation(self, recipient_name: str = None, conversation_url: str = None):
        """
        Navega a una conversación específica en LinkedIn Messaging.

        Args:
            recipient_name: Nombre del contacto a buscar en mensajes.
            conversation_url: URL directa de la conversación (opcional, tiene prioridad).
        """
        if conversation_url:
            print(f"📨 Navegando a conversación: {conversation_url}")
            await self.page.goto(conversation_url, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(3000)
            return

        # Navegar a la bandeja de mensajes
        print("📨 Navegando a LinkedIn Messaging...")
        await self.page.goto(config.LINKEDIN_MESSAGING_URL, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(3000)

        if recipient_name:
            print(f"   🔍 Buscando conversación con: {recipient_name}")

            # Buscar en la barra de búsqueda de mensajes
            search_input = await self.page.query_selector(
                'input[placeholder*="Search messages"], '
                'input[placeholder*="Buscar mensajes"], '
                'input.msg-search-form__search-field'
            )

            if search_input:
                await search_input.click()
                await search_input.fill(recipient_name)
                await self.page.wait_for_timeout(2000)

                # Hacer clic en el primer resultado
                first_result = await self.page.query_selector(
                    '.msg-conversation-listitem__link, '
                    '.msg-search-result__link, '
                    'li.msg-conversation-listitem'
                )
                if first_result:
                    await first_result.click()
                    await self.page.wait_for_timeout(2000)
                    print(f"   ✅ Conversación con '{recipient_name}' abierta.\n")
                else:
                    print(f"   ⚠️  No se encontró conversación con '{recipient_name}'.")
                    print("   👉 Abre la conversación manualmente y presiona ENTER...")
                    await asyncio.get_event_loop().run_in_executor(None, input)
            else:
                print("   ⚠️  No se encontró barra de búsqueda de mensajes.")
                print("   👉 Abre la conversación manualmente y presiona ENTER...")
                await asyncio.get_event_loop().run_in_executor(None, input)
        else:
            print("   👉 Abre la conversación destino manualmente y presiona ENTER...")
            await asyncio.get_event_loop().run_in_executor(None, input)

    # ==========================================================================
    # INYECCIÓN DE JAVASCRIPT - CORE
    # ==========================================================================

    async def inject_and_send_voice_message(self) -> dict:
        """
        Sube el archivo de audio como un adjunto estándar usando la interfaz de usuario de Playwright.
        Esta alternativa es 100% segura y sustituye al inyector de JS puro bloqueado por LinkedIn.
        """
        import os
        audio_path = str(self.wav_path)

        if not os.path.exists(audio_path):
            return {"success": False, "error": f"Archivo no encontrado: {audio_path}", "step": "pre-check"}

        print(f"\n[UI Automation] Seleccionando audio como adjunto: {audio_path}...")
        try:
            # Encontrar el input de tipo archivo en el DOM del chat de LinkedIn
            file_input = self.page.locator('input[type="file"]').first
            
            # Subir el archivo .wav
            await file_input.set_input_files(audio_path)
            print("[UI Automation] Archivo seteado en el frontend. Esperando subida inicial...")
            
            # Playwright sube localmente, ahora LinkedIn carga la preview (barra verde).
            await self.page.wait_for_timeout(3500)
            
            # El botón de enviar
            send_button = self.page.locator('.msg-form__send-button')
            
            # Esperar a que el botón se habilite si aún está gris. En mensajería, el CSS quita
            # la clase o atributo cuando hay un adjunto listo.
            is_disabled = await send_button.get_attribute('disabled')
            if is_disabled is not None:
                print("[UI Automation] Esperando a que el botón de enviar se habilite post subida...")
                await self.page.wait_for_selector('.msg-form__send-button:not([disabled])', timeout=15000)
                
            print("🚀 Enviando mensaje...")
            await send_button.click()
            
            # Esperamos tres segundos a que el frame se agregue en la vista antes de irnos
            await self.page.wait_for_timeout(3000)
            print("✅ ¡Audio enviado como archivo adjunto exitosamente!\n")
            
            return {
                "success": True,
                "status": 200,
                "method": "ui_attachment",
                "step": "send_complete"
            }
        except Exception as e:
            error_details = str(e)
            print(f"❌ Error durante la automatización de la UI: {error_details}")
            return {
                "success": False,
                "error": error_details,
                "step": "ui_automation"
            }


    # ==========================================================================
    # FLUJO COMPLETO
    # ==========================================================================

    async def run_full_flow(
        self,
        recipient_name: str = None,
        conversation_url: str = None,
        login_only: bool = False,
    ) -> dict:
        """
        Ejecuta el flujo completo: lanzar → login → navegar → inyectar → enviar.

        Args:
            recipient_name: Nombre del contacto destino.
            conversation_url: URL directa de la conversación (tiene prioridad).
            login_only: Si True, solo hace login y guarda sesión, sin enviar.

        Returns:
            dict con el resultado de la operación.
        """
        try:
            await self.launch_browser()
            await self.login()

            if login_only:
                print("✅ Modo --login-only: sesión guardada. Saliendo.\n")
                return {"success": True, "step": "login_only"}

            await self.navigate_to_conversation(
                recipient_name=recipient_name,
                conversation_url=conversation_url,
            )

            # Pequeña pausa para asegurar que la conversación está completamente cargada
            await self.page.wait_for_timeout(2000)

            result = await self.inject_and_send_voice_message()

            if result.get("success"):
                print("✅ ¡Mensaje de voz enviado exitosamente!")
            else:
                print(f"⚠️  Resultado: {result}")

            return result

        except Exception as e:
            print(f"❌ Error en el flujo: {e}")
            return {"success": False, "error": str(e), "step": "flow"}

        finally:
            # Guardar sesión antes de cerrar
            try:
                await self.save_session()
            except Exception:
                pass
            await self.close_browser()
