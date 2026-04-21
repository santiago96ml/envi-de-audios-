"""
worker.py - Playwright Worker del LinkedIn Voice Bot.

ARQUITECTURA:
  - Inicia UN SOLO proceso de Chromium al arrancar (~200MB RAM base).
  - Escucha la cola de Redis con BLPOP (blocking, sin polling activo).
  - Por cada tarea: crea un Context aislado → inyecta cookies → ejecuta tarea → cierra Context.
  - El cierre del Context libera la RAM usada por esa tarea inmediatamente.
  - Si Chromium crashea, el worker se reinicia y Redis conserva las tareas pendientes.

CONSUMO ESTIMADO: ~250MB base + ~50MB por contexto activo simultáneo.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import redis as redis_lib
from playwright.async_api import BrowserType, PlaywrightContextManager, async_playwright

from models import Task
from session_manager import SessionManager

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("worker")

REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379")
TASK_QUEUE_KEY  = "linkedin:tasks"
TASK_STATUS_PREFIX = "linkedin:task:"
TASK_TTL        = 60 * 60 * 24 * 7   # 7 días
SESSION_FILE    = Path(__file__).resolve().parent / "session_data" / "linkedin_state.json"

# Recursos a bloquear para ahorrar RAM/ancho de banda
BLOCKED_RESOURCES = {"image", "stylesheet", "media", "font"}

# ==============================================================================
# WORKER PRINCIPAL
# ==============================================================================

class LinkedInWorker:
    def __init__(self):
        self.redis: redis_lib.Redis | None = None
        self.session_mgr: SessionManager | None = None
        self.playwright: PlaywrightContextManager | None = None
        self.browser = None
        self._running = True

    # ------------------------------------------------------------------
    # INICIALIZACIÓN
    # ------------------------------------------------------------------

    async def init(self):
        """Conecta a Redis e inicia el navegador base."""
        logger.info(f"🔌 Conectando a Redis: {REDIS_URL}")
        self.redis = redis_lib.from_url(REDIS_URL, decode_responses=True)
        self.redis.ping()
        logger.info("✅ Redis conectado.")

        self.session_mgr = SessionManager(self.redis)

        # Migración automática de cookies desde archivo JSON (si aplica)
        self._auto_migrate_session()

        # Iniciar Chromium (un solo proceso para toda la vida del worker)
        await self._start_browser()

    def _auto_migrate_session(self):
        """Migra session_storage.json → Redis si la cuenta default no existe."""
        default_cuenta = "linkedin_santi_01"
        if not self.session_mgr.session_exists(default_cuenta):
            logger.info(
                f"🔄 Cuenta '{default_cuenta}' no encontrada en Redis. "
                f"Intentando migrar desde {SESSION_FILE.name}..."
            )
            self.session_mgr.migrate_from_file(SESSION_FILE, default_cuenta)
        else:
            logger.info(f"✅ Sesión '{default_cuenta}' ya está en Redis.")

    async def _start_browser(self):
        """Lanza Chromium con las flags de optimización para servidor Linux/Docker."""
        logger.info("🚀 Iniciando Chromium base...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",   # OBLIGATORIO en Docker
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-extensions",
                "--disable-infobars",
                "--mute-audio",
            ]
        )
        logger.info("✅ Chromium iniciado (~200MB RAM base).")

    # ------------------------------------------------------------------
    # BUCLE PRINCIPAL
    # ------------------------------------------------------------------

    async def run(self):
        """Bucle infinito: lee tareas de Redis y las ejecuta secuencialmente."""
        logger.info(f"👂 Escuchando cola '{TASK_QUEUE_KEY}' en Redis...")
        logger.info("   (Usando BLPOP — consume 0% CPU cuando no hay tareas)")

        while self._running:
            try:
                # BLPOP bloquea hasta que llegue una tarea (timeout=5s para poder chequear _running)
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.redis.brpop(TASK_QUEUE_KEY, timeout=5)
                )

                if result is None:
                    # Timeout, no hay tareas — continuar el bucle
                    continue

                _, task_json = result
                task = Task.model_validate_json(task_json)

                logger.info(f"📋 Tarea recibida: {task.task_id} | Cuenta: {task.cuenta_origen_id}")
                await self._process_task(task)

            except redis_lib.ConnectionError as e:
                logger.error(f"❌ Redis desconectado: {e}. Reintentando en 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ Error inesperado en el bucle principal: {e}", exc_info=True)
                await asyncio.sleep(2)

    # ------------------------------------------------------------------
    # PROCESAMIENTO DE UNA TAREA
    # ------------------------------------------------------------------

    async def _process_task(self, task: Task):
        """Procesa una tarea en un Context aislado. El Context se cierra al finalizar."""
        context = None
        try:
            # 1. Marcar como "procesando"
            self._update_task_status(task, "procesando")

            # 2. Obtener cookies de la cuenta
            cookies = self.session_mgr.get_cookies_for_playwright(task.cuenta_origen_id)
            if not cookies:
                raise ValueError(
                    f"No hay cookies disponibles para la cuenta '{task.cuenta_origen_id}'"
                )

            # 3. Crear un CONTEXTO AISLADO (como una ventana de incógnito nueva)
            context = await self.browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )

            # 4. Inyectar cookies (evita login manual y captchas)
            await context.add_cookies(cookies)
            logger.info(f"🍪 {len(cookies)} cookies inyectadas para '{task.cuenta_origen_id}'")

            # 5. Bloquear recursos innecesarios (ahorrar RAM y tiempo)
            async def block_resources(route):
                if route.request.resource_type in BLOCKED_RESOURCES:
                    await route.abort()
                else:
                    await route.continue_()

            await context.route("**/*", block_resources)

            # 6. Criar página y ejecutar la tarea de edición
            page = await context.new_page()
            page.set_default_timeout(60000)

            success = await self._execute_edit_message(
                page=page,
                contact=task.perfil_destino_url,
                old_msg=task.mensaje_viejo,
                new_msg=task.mensaje_nuevo,
            )

            if success:
                self._update_task_status(task, "completado", "Mensaje editado exitosamente.")
                logger.info(f"✅ Tarea {task.task_id} completada.")
            else:
                self._update_task_status(
                    task, "error",
                    "El worker no pudo editar el mensaje. Revisar logs del worker."
                )

        except ValueError as e:
            logger.error(f"❌ Error de datos en tarea {task.task_id}: {e}")
            self._update_task_status(task, "error", str(e))
        except Exception as e:
            logger.error(f"❌ Error ejecutando tarea {task.task_id}: {e}", exc_info=True)
            # Si LinkedIn devolvió un error de sesión, marcar como expirada
            if "login" in str(e).lower() or "authwall" in str(e).lower():
                self.session_mgr.mark_expired(task.cuenta_origen_id)
            self._update_task_status(task, "error", str(e))
        finally:
            # CRÍTICO: Cerrar el contexto libera la RAM inmediatamente
            if context:
                await context.close()
                logger.info(f"🧹 Contexto del task {task.task_id} cerrado (RAM liberada).")

    # ------------------------------------------------------------------
    # LÓGICA DE PLAYWRIGHT (editar mensaje en LinkedIn)
    # ------------------------------------------------------------------

    async def _check_logged_in(self, page) -> bool:
        """Verifica que las cookies son válidas y estamos logueados."""
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        url = page.url
        return "login" not in url and "authwall" not in url

    async def _execute_edit_message(
        self, page, contact: str, old_msg: str, new_msg: str
    ) -> bool:
        """Navega al chat, busca el mensaje y lo edita. Retorna True si tuvo éxito."""
        # Verificar sesión activa
        if not await self._check_logged_in(page):
            raise ValueError("Sesión expirada o cookies inválidas. Requiere re-importar cookies.")

        # Navegar al contacto
        await self._navigate_to_chat(page, contact)

        # Editar el mensaje
        return await self._edit_message(page, old_msg, new_msg)

    async def _navigate_to_chat(self, page, contact: str):
        """Navega a la URL de perfil o busca en mensajería por nombre."""
        if contact.startswith("http"):
            logger.info(f"🌐 Navegando a: {contact[:60]}...")
            await page.goto(contact, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)

            # Si es un perfil (/in/...), buscar el botón de Mensaje
            if "/in/" in contact:
                logger.info("👤 Perfil detectado. Buscando botón de Mensaje...")
                msg_btn = await page.query_selector(
                    'button:has-text("Mensaje"), button:has-text("Message")'
                )
                if msg_btn:
                    await msg_btn.click()
                    await page.wait_for_timeout(2500)
                else:
                    # Intentar en el menú "Más..."
                    more = await page.query_selector(
                        'button[aria-label*="Más acciones"], button[aria-label*="More actions"]'
                    )
                    if more:
                        await more.click()
                        await page.wait_for_timeout(800)
                        send = await page.query_selector(
                            '.artdeco-dropdown__content >> text="Enviar mensaje"'
                        )
                        if send:
                            await send.click()
                            await page.wait_for_timeout(2500)
        else:
            logger.info(f"🔍 Buscando por nombre: {contact}")
            await page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            search = await page.query_selector(
                'input[placeholder*="Search messages"], input[placeholder*="Buscar mensajes"]'
            )
            if search:
                await search.click()
                await search.fill(contact)
                await page.wait_for_timeout(1500)
                first = await page.query_selector(".msg-conversation-listitem__link")
                if first:
                    await first.click()
                    await page.wait_for_timeout(1500)

    async def _edit_message(self, page, old_text: str, new_text: str) -> bool:
        """Busca el mensaje en el chat y lo edita con simulación humana de teclado."""
        logger.info(f"✏️ Buscando mensaje: '{old_text[:40]}...'")

        messages = await page.query_selector_all("li.msg-s-message-list__event")
        target = None

        for msg in reversed(messages):
            content = await msg.inner_text()
            if old_text.strip().lower() in content.strip().lower():
                target = msg
                break

        if not target:
            logger.error("❌ Mensaje original no encontrado en el chat.")
            return False

        # Hover para hacer aparecer las opciones
        bubble = await target.query_selector(".msg-s-event-listitem__message-bubble")
        await (bubble or target).hover()
        await page.wait_for_timeout(1500)

        # Clic en los 3 puntitos
        options_btn = await target.query_selector(
            ".msg-s-event-listitem__options-trigger, "
            'button[aria-label*="Opciones"], button[aria-label*="Options"]'
        )
        if not options_btn:
            options_btn = await target.query_selector(
                "li.msg-s-message-options__option-item button, .msg-s-message-options button"
            )
        if not options_btn:
            logger.error("❌ No se encontró el botón de opciones (3 puntitos).")
            await page.screenshot(path="/tmp/debug_no_options.png")
            return False

        await options_btn.click()
        await page.wait_for_timeout(800)

        # Buscar opción "Editar"
        edit_btn = await page.query_selector(
            'text="Editar", text="Edit", '
            '[role="menuitem"] >> text="Editar", '
            '[role="menuitem"] >> text="Edit"'
        )
        if not edit_btn:
            edit_btn = await page.query_selector(
                '.artdeco-dropdown__item:has-text("Edit"), '
                '.artdeco-dropdown__item:has-text("Editar")'
            )
        if not edit_btn:
            logger.error("❌ Opción 'Editar' no encontrada en el menú.")
            await page.screenshot(path="/tmp/debug_no_edit.png")
            return False

        await edit_btn.click()
        await page.wait_for_timeout(1500)

        # Localizar el campo de edición activado
        editor = await target.query_selector(
            'div[role="textbox"], .msg-form__contenteditable, [contenteditable="true"]'
        )
        if not editor:
            editor = await page.query_selector(
                '.msg-form__contenteditable[contenteditable="true"]'
            )
        if not editor:
            logger.error("❌ Campo de edición no encontrado.")
            return False

        # Simulación humana: seleccionar todo y reemplazar con delay de teclado
        await editor.click()
        await page.keyboard.press("Control+A")
        await page.wait_for_timeout(400)
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(200)
        await editor.type(new_text, delay=65)  # ~65ms por tecla = ritmo humano
        await page.wait_for_timeout(800)

        # Guardar edición
        save_btn = await target.query_selector('button:has-text("Guardar"), button:has-text("Save")')
        if not save_btn:
            save_btn = await page.query_selector(
                '.msg-form__send-button, button:has-text("Guardar"), button:has-text("Save")'
            )

        if save_btn:
            await save_btn.click()
        else:
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(2000)
        logger.info("✅ Mensaje editado exitosamente.")
        return True

    # ------------------------------------------------------------------
    # GESTIÓN DE ESTADO
    # ------------------------------------------------------------------

    def _update_task_status(self, task: Task, estado: str, resultado: str | None = None):
        """Actualiza el estado de la tarea en Redis para que la API lo devuelva al cliente."""
        task.estado = estado
        task.resultado = resultado
        task.fecha_actualizacion = datetime.now(timezone.utc).isoformat()
        self.redis.set(
            f"{TASK_STATUS_PREFIX}{task.task_id}",
            task.model_dump_json(),
            ex=TASK_TTL,
        )
        logger.info(f"📊 Tarea {task.task_id[:8]}... → estado: {estado}")

    # ------------------------------------------------------------------
    # SHUTDOWN GRACEFUL
    # ------------------------------------------------------------------

    async def shutdown(self):
        """Cierra el navegador y la conexión a Redis limpiamente."""
        logger.info("🛑 Iniciando shutdown graceful...")
        self._running = False
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.redis:
            self.redis.close()
        logger.info("👋 Worker detenido limpiamente.")


# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

async def main():
    worker = LinkedInWorker()

    # Manejo de señales SIGINT/SIGTERM para shutdown graceful en Docker
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(worker.shutdown())
        )

    await worker.init()
    await worker.run()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  LinkedIn Voice Bot — Playwright Worker v2.0")
    logger.info("=" * 60)
    asyncio.run(main())
