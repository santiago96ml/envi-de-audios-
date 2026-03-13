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

    def __init__(self, processed_wav_path: Path, audio_duration_seconds: float):
        """
        Args:
            processed_wav_path: Ruta absoluta al WAV procesado (PCM 16-bit mono 16kHz).
            audio_duration_seconds: Duración del audio en segundos.
        """
        self.wav_path = Path(processed_wav_path).resolve()
        self.audio_duration_s = audio_duration_seconds
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
        self.page.on("console", lambda msg: print(f"[Chromium] {msg.text}"))
        self.page.set_default_timeout(config.DEFAULT_TIMEOUT)
        self.page.set_default_navigation_timeout(config.NAVIGATION_TIMEOUT)

        # Falsificando dispositivo móvil solo para los endpoints de voz (interceptación local)
        async def mock_mobile_api_route(route):
            headers = route.request.headers.copy()
            headers["user-agent"] = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            headers["sec-ch-ua-mobile"] = "?1"
            headers["sec-ch-ua-platform"] = '"Android"'
            headers["x-li-user-agent"] = "LIAuthLibrary:3.2.4 com.linkedin.android:4.1.881 x86_64:android-33"
            await route.continue_(headers=headers)

        await self.page.route("**/voyager/api/voyagerMediaUploadMetadata*", mock_mobile_api_route)
        await self.page.route("**/voyager/api/messaging/conversations/*/events*", mock_mobile_api_route)

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

        # Verificar si ya estamos logueados con la sesión restaurada
        if config.SESSION_STATE_FILE.exists():
            if await self.is_logged_in():
                print("✅ Sesión restaurada con éxito. Ya estás autenticado.\n")
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
        Inyecta JavaScript en la página para:
        1. Capturar el stream del micrófono virtual (getUserMedia)
        2. Grabar con MediaRecorder
        3. Esperar la duración del audio
        4. Crear un Blob con la grabación
        5. Extraer CSRF token de las cookies de sesión
        6. Enviar via fetch() multipart al endpoint de LinkedIn

        Returns:
            dict con el resultado de la operación.
        """
        duration_ms = int(self.audio_duration_s * 1000) + config.RECORDING_MARGIN_MS

        print(f"💉 Inyectando script de captura y envío de voz...")
        print(f"   Duración de grabación: {duration_ms}ms")

        # JavaScript que se inyecta en la página autenticada de LinkedIn
        js_code = """
        async (durationMs) => {
            // ============================================================
            // PASO 1: Capturar el stream del micrófono virtual
            // ============================================================
            console.log('[VoiceBot] Solicitando acceso al micrófono virtual...');

            let stream;
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                console.log('[VoiceBot] Stream de audio obtenido:', stream.id);
            } catch (err) {
                return {
                    success: false,
                    error: `getUserMedia falló: ${err.message}`,
                    step: 'getUserMedia'
                };
            }

            // ============================================================
            // PASO 2: Inicializar MediaRecorder
            // ============================================================
            let mimeType = 'audio/webm;codecs=opus';
            if (!MediaRecorder.isTypeSupported(mimeType)) {
                mimeType = 'audio/webm';
                if (!MediaRecorder.isTypeSupported(mimeType)) {
                    mimeType = 'audio/ogg;codecs=opus';
                    if (!MediaRecorder.isTypeSupported(mimeType)) {
                        mimeType = '';  // Fallback al default del navegador
                    }
                }
            }

            console.log('[VoiceBot] MIME type seleccionado:', mimeType || 'default');

            const recorderOptions = mimeType ? { mimeType } : {};
            const mediaRecorder = new MediaRecorder(stream, recorderOptions);
            const audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                    console.log('[VoiceBot] Chunk recibido:', event.data.size, 'bytes');
                }
            };

            // ============================================================
            // PASO 3: Grabar y esperar la duración del audio
            // ============================================================
            return new Promise((resolve) => {
                mediaRecorder.onstop = async () => {
                    console.log('[VoiceBot] Grabación detenida. Chunks:', audioChunks.length);

                    // Detener todas las pistas del stream
                    stream.getTracks().forEach(track => track.stop());

                    // Crear Blob con los chunks grabados
                    const actualMime = mediaRecorder.mimeType || 'audio/webm';
                    const audioBlob = new Blob(audioChunks, { type: actualMime });
                    console.log('[VoiceBot] Blob creado:', audioBlob.size, 'bytes,', actualMime);

                    if (audioBlob.size === 0) {
                        resolve({
                            success: false,
                            error: 'El Blob de audio está vacío. El micrófono virtual no proporcionó datos.',
                            step: 'blob_creation'
                        });
                        return;
                    }

                    // ============================================================
                    // PASO 4: Extraer CSRF token (JSESSIONID) de las cookies
                    // ============================================================
                    let csrfToken = '';
                    try {
                        const cookies = document.cookie.split(';');
                        for (const cookie of cookies) {
                            const [name, value] = cookie.trim().split('=');
                            if (name === 'JSESSIONID') {
                                csrfToken = value.replace(/"/g, '');
                                break;
                            }
                        }
                    } catch (e) {
                        console.warn('[VoiceBot] No se pudo extraer JSESSIONID:', e);
                    }

                    console.log('[VoiceBot] CSRF token:', csrfToken ? '✅ encontrado' : '❌ no encontrado');

                    // ============================================================
                    // PASO 5: Extraer el ID de la conversación activa
                    // ============================================================
                    let conversationId = '';
                    try {
                        // Intentar extraer del URL actual
                        const urlMatch = window.location.href.match(/messaging\\/thread\\/([^/\\?]+)/);
                        if (urlMatch) {
                            conversationId = urlMatch[1];
                        }

                        // Fallback: intentar desde la UI
                        if (!conversationId) {
                            const threadEl = document.querySelector(
                                '[data-thread-urn], .msg-thread, [id*="thread"]'
                            );
                            if (threadEl) {
                                const urn = threadEl.getAttribute('data-thread-urn') || '';
                                const urnMatch = urn.match(/thread:([^)]+)/);
                                if (urnMatch) conversationId = urnMatch[1];
                            }
                        }
                    } catch (e) {
                        console.warn('[VoiceBot] No se pudo extraer conversation ID:', e);
                    }

                    console.log('[VoiceBot] Conversation ID:', conversationId || 'no detectado');

                    // ============================================================
                    // PASO 6: Subir el audio al endpoint de LinkedIn
                    // ============================================================
                    try {
                        // --- PASO 6a: Registrar el upload de media ---
                        const registerPayload = {
                            "recipe": "urn:li:digitalmediaRecipe:messenger-audio",
                            "mediaUploadType": "AUDIO",
                            "fileSize": audioBlob.size,
                        };

                        const registerHeaders = {
                            'Content-Type': 'application/json',
                            'x-restli-protocol-version': '2.0.0',
                        };
                        if (csrfToken) {
                            registerHeaders['csrf-token'] = csrfToken;
                        }

                        console.log('[VoiceBot] Registrando upload de media...');
                        const registerResp = await fetch(
                            'https://www.linkedin.com/voyager/api/voyagerMediaUploadMetadata?action=upload',
                            {
                                method: 'POST',
                                headers: registerHeaders,
                                body: JSON.stringify(registerPayload),
                                credentials: 'include',
                            }
                        );

                        if (!registerResp.ok) {
                            const regErrText = await registerResp.text().catch(() => '');
                            console.warn('[VoiceBot] Register response:', registerResp.status, regErrText);

                            // Si el endpoint de registro no funciona, intentamos un POST directo
                            // con FormData como mecanismo alternativo
                            console.log('[VoiceBot] Intentando envío directo con FormData...');

                            const formData = new FormData();
                            const audioFile = new File(
                                [audioBlob],
                                'voice_message.webm',
                                { type: actualMime }
                            );
                            formData.append('file', audioFile);

                            const directHeaders = {};
                            if (csrfToken) {
                                directHeaders['csrf-token'] = csrfToken;
                            }

                            // Intentar envío al endpoint de mensajería
                            if (conversationId) {
                                const msgEndpoint = `https://www.linkedin.com/voyager/api/messaging/conversations/${conversationId}/messages`;
                                const msgResp = await fetch(msgEndpoint, {
                                    method: 'POST',
                                    headers: directHeaders,
                                    body: formData,
                                    credentials: 'include',
                                });

                                resolve({
                                    success: msgResp.ok,
                                    status: msgResp.status,
                                    blobSize: audioBlob.size,
                                    mimeType: actualMime,
                                    conversationId: conversationId,
                                    method: 'direct_formdata',
                                    regStatus: registerResp.status,
                                    regError: regErrText,
                                    step: 'send_complete'
                                });
                                return;
                            }

                            // Sin conversation ID, retornar el blob info para envío manual
                            resolve({
                                success: false,
                                error: 'No se pudo registrar el upload ni detectar conversation ID',
                                blobSize: audioBlob.size,
                                mimeType: actualMime,
                                regStatus: registerResp.status,
                                regError: regErrText,
                                step: 'upload_register'
                            });
                            return;
                        }

                        const registerData = await registerResp.json();
                        console.log('[VoiceBot] Upload registrado:', JSON.stringify(registerData));

                        const uploadUrl = registerData?.value?.singleUploadUrl
                            || registerData?.data?.value?.singleUploadUrl
                            || '';
                        const mediaUrn = registerData?.value?.urn
                            || registerData?.data?.value?.urn
                            || '';

                        // --- PASO 6b: Subir el archivo de audio ---
                        if (uploadUrl) {
                            console.log('[VoiceBot] Subiendo audio a:', uploadUrl);
                            const uploadResp = await fetch(uploadUrl, {
                                method: 'PUT',
                                headers: {
                                    'Content-Type': actualMime,
                                    ...(csrfToken ? {'csrf-token': csrfToken} : {}),
                                },
                                body: audioBlob,
                                credentials: 'include',
                            });

                            if (!uploadResp.ok) {
                                resolve({
                                    success: false,
                                    error: `Upload falló: ${uploadResp.status}`,
                                    step: 'upload_audio'
                                });
                                return;
                            }
                            console.log('[VoiceBot] Audio subido exitosamente.');
                        }

                        // --- PASO 6c: Enviar el mensaje con el media URN ---
                        if (conversationId && mediaUrn) {
                            console.log('[VoiceBot] Enviando mensaje de voz con URN:', mediaUrn);

                            const messagePayload = {
                                "eventCreate": {
                                    "value": {
                                        "com.linkedin.voyager.messaging.create.MessageCreate": {
                                            "attributedBody": {
                                                "text": "",
                                                "attributes": []
                                            },
                                            "attachments": [
                                                mediaUrn
                                            ]
                                        }
                                    }
                                }
                            };

                            const msgResp = await fetch(
                                `https://www.linkedin.com/voyager/api/messaging/conversations/${conversationId}/events?action=create`,
                                {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                        'x-restli-protocol-version': '2.0.0',
                                        'csrf-token': csrfToken,
                                        'accept': 'application/vnd.linkedin.normalized+json+2.1'
                                    },
                                    body: JSON.stringify(messagePayload),
                                    credentials: 'include',
                                }
                            );

                            const resultData = msgResp.ok ? await msgResp.json().catch(() => ({})) : {};
                            
                            if (!msgResp.ok) {
                                const errTextMsg = await msgResp.text().catch(() => '');
                                console.log('[VoiceBot] Error enviando mensaje final:', errTextMsg);
                            }

                            resolve({
                                success: msgResp.ok,
                                status: msgResp.status,
                                blobSize: audioBlob.size,
                                mimeType: actualMime,
                                conversationId: conversationId,
                                mediaUrn: mediaUrn,
                                method: 'voyager_api',
                                responseData: resultData,
                                step: 'send_complete'
                            });
                            return;
                        }

                        // Retornar éxito parcial si no hay conversation ID
                        resolve({
                            success: false,
                            blobSize: audioBlob.size,
                            mimeType: actualMime,
                            mediaUrn: mediaUrn,
                            uploadUrl: uploadUrl ? '✅' : '❌',
                            conversationId: conversationId || 'no detectado',
                            error: 'Audio subido pero no se pudo enviar: falta conversationId o mediaUrn',
                            step: 'send_message'
                        });

                    } catch (fetchError) {
                        resolve({
                            success: false,
                            error: `Error en fetch: ${fetchError.message}`,
                            blobSize: audioBlob.size,
                            mimeType: actualMime,
                            step: 'fetch'
                        });
                    }
                };

                // Iniciar la grabación
                console.log('[VoiceBot] Iniciando grabación por', durationMs, 'ms...');
                mediaRecorder.start(1000);  // Chunks cada 1 segundo

                // Detener la grabación después de la duración del audio
                setTimeout(() => {
                    if (mediaRecorder.state === 'recording') {
                        console.log('[VoiceBot] Deteniendo grabación...');
                        mediaRecorder.stop();
                    }
                }, durationMs);
            });
        }
        """

        try:
            result = await self.page.evaluate(js_code, duration_ms)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error al ejecutar JavaScript: {str(e)}",
                "step": "page_evaluate",
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
