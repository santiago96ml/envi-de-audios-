import time
import uiautomator2 as u2
import config

class AndroidMessageEditor:
    """Clase para editar mensajes de texto en la app de LinkedIn en Android."""
    
    def __init__(self, adb_serial=config.ADB_SERIAL):
        self.serial = adb_serial
        self.device = None

    def connect(self):
        """Conecta a la instancia de Android vía ADB y usa uiautomator2."""
        try:
            print(f"📱 Conectando a instancia Android ({self.serial})...")
            self.device = u2.connect(self.serial)
            info = self.device.info
            print(f"✅ Conectado a: {info.get('productName', 'Desconocido')} ({info.get('displayId', 'ID n/a')})")
            return True
        except Exception as e:
            print(f"❌ Error al conectar con ADB: {e}")
            return False

    def navigate_to_chat(self, recipient_or_url):
        """
        Navega al chat de manera inteligente manteniendo el modo 'suspenso' de la app.
        Verifica si ya estamos en un chat y no reinicia la aplicación innecesariamente.
        """
        if not self.device:
            self.connect()
        
        url = None
        search_name = recipient_or_url
        
        if recipient_or_url.startswith("http"):
            url = recipient_or_url
            try:
                # Extraer nombre del URL (heurística)
                # ej: linkedin.com/in/santiago-meneguzzi-123/ -> "Santiago Meneguzzi"
                parts = url.split("/in/")[1].strip("/").split("-")
                parts = [p.capitalize() for p in parts if not p.isdigit() and len(p) > 1]
                search_name = " ".join(parts)
            except:
                pass

        print(f"🧠 Deducido nombre para búsqueda en chat: '{search_name}'")

        # Asegurar que la app está abierta y al frente (esto NO la reinicia si ya está abierta)
        self.device.app_start("com.linkedin.android")
        time.sleep(2)

        # 1. ¿Estamos en un chat actualmente?
        chat_title = self.device(resourceId="com.linkedin.android:id/messaging_thread_title")
        if chat_title.exists:
            current_chat = chat_title.get_text()
            # Si estamos en el chat correcto, ¡no hacemos nada más!
            if search_name and search_name.lower() in current_chat.lower():
                print(f"✅ Ya estamos en el chat correcto: {current_chat}. Modo suspenso efectivo.")
                return True
            else:
                print(f"🔙 Estamos en un chat distinto ({current_chat}). Volviendo a la lista de mensajes...")
                self.device.press("back")
                time.sleep(1)

        # 2. Buscar en la barra de mensajes
        search_box = self.device(textMatches="(?i)Buscar mensajes|Search messages")
        if not search_box.exists:
            # Ir a la pestaña de mensajes desde el home
            msg_tab = self.device(contentDescriptionMatches="(?i).*Mensajes.*|.*Messaging.*")
            if msg_tab.exists:
                msg_tab.click()
                time.sleep(2)
                search_box = self.device(textMatches="(?i)Buscar mensajes|Search messages")

        # 3. Intentar búsqueda si encontramos la barra
        if search_box.exists and search_name:
            search_box.click()
            time.sleep(1)
            search_input = self.device(className="android.widget.EditText")
            if search_input.exists:
                search_input.set_text(search_name)
                print(f"🔍 Buscando '{search_name}' en el historial de chats...")
                time.sleep(3)
                
                # Clicar el primer resultado que coincida
                result = self.device(textContains=search_name)
                if result.exists:
                    for match in result:
                        if match.info['className'] != "android.widget.EditText":
                            match.click()
                            time.sleep(3)
                            if self.device(resourceId="com.linkedin.android:id/messaging_thread_title").exists:
                                print(f"✅ Chat encontrado en la lista rápida.")
                                return True

        # 4. Fallback: Si no lo encuentra en el chat por heurística, usa el Deep Link completo
        if url:
            print(f"🌐 Fallback: Abriendo la URL directamente en el perfil nativo de LinkedIn -> {url}")
            self.device.shell(f"am start -a android.intent.action.VIEW -d '{url}' com.linkedin.android")
            time.sleep(6)
            
            # Buscar el botón de Mensaje principal
            msg_btn = self.device(textMatches="(?i)Mensaje|Message", className="android.widget.Button")
            
            if msg_btn.exists:
                msg_btn.click()
                time.sleep(3)
                print("✅ Entrando al chat desde el botón del perfil.")
                return True
            else:
                # A veces el botón está bajo el menú "Más" o "More"
                print("⚠️ Botón 'Mensaje' oculto. Buscando en el menú 'Más...'")
                more_btn = self.device(textMatches="(?i)Más|More", className="android.widget.Button")
                if more_btn.exists:
                    more_btn.click()
                    time.sleep(1.5)
                    # En el menú desplegable suele decir "Enviar mensaje" en lugar de solo "Mensaje"
                    msg_menu_btn = self.device(textMatches="(?i).*Mensaje.*|.*Message.*")
                    if msg_menu_btn.exists:
                        msg_menu_btn.click()
                        time.sleep(3)
                        print("✅ Entrando al chat desde el menú secundario.")
                        return True
                
                print("❌ No se pudo encontrar una forma de enviarle mensaje desde su perfil.")
                return False

        print("⚠️ No se pudo asegurar la navegación al chat. El sistema intentará interactuar de todos modos.")
        return False


    def edit_message(self, old_text, new_text):
        """
        Busca el mensaje 'old_text', lo mantiene presionado, 
        selecciona "Editar", elimina todo y escribe 'new_text'.
        """
        if not self.device:
            if not self.connect():
                return {"success": False, "error": "No conectado a Android"}

        try:
            print(f"🔍 Buscando burbuja de mensaje original con texto temporal: '{old_text}'...")
            
            # Scroll pequeño por si no se ve en primera pantalla
            self.device.swipe_ext("down", scale=0.3)
            time.sleep(1)

            # Buscar el mensaje en pantalla
            msg_bubble = self.device(textContains=old_text)
            if not msg_bubble.exists:
                # Tratar de hacer scroll hacia arriba (mensajes más antiguos)
                self.device.swipe_ext("down", scale=0.6)
                time.sleep(1)
                msg_bubble = self.device(textContains=old_text)
                
            if not msg_bubble.exists:
                return {"success": False, "error": f"No se encontró el mensaje original en la pantalla ('{old_text}')."}

            print("👉 Manteniendo presionado el mensaje hallado...")
            # Usar long_click en vez de click
            msg_bubble.long_click(duration=1.5)
            time.sleep(1)

            print("✏️ Buscando opción 'Editar' o 'Edit' en el menú principal...")
            edit_btn = self.device(textMatches="(?i)Editar|Edit")
            if not edit_btn.exists:
                return {"success": False, "error": "No apareció la opción de Editar. ¿Estás sobre tu propio mensaje enviado?"}
            
            edit_btn.click()
            time.sleep(2)

            print("🗑️ En modo edición: Seleccionando y limpiando texto original...")
            # En LinkedIn editar abre un cuadro de texto en la misma base o modal.
            input_box = self.device(className="android.widget.EditText")
            if not input_box.exists:
                return {"success": False, "error": "No se encontró el campo de texto (""EditText"")."}

            # uiautomator2 clear_text method sends action clear selection
            input_box.clear_text()
            # En caso de que queden residuos en algunas apps, enviamos unos retrocesos extras (borrado)
            self.device.press("del")
            self.device.press("del")
            time.sleep(0.5)

            print(f"✍️ Escribiendo nuevo texto: '{new_text}'...")
            input_box.set_text(new_text)
            time.sleep(1.5)

            print("🚀 Buscando botón de confirmación de edición...")
            # Algunas veces es un ícono de tilde (Save). A veces es un botón de Enviar "Send" o "Guardar".
            save_btn = self.device(descriptionMatches="(?i)Guardar|Save|Enviar|Send")
            if not save_btn.exists:
                save_btn = self.device(textMatches="(?i)Guardar|Save|Enviar|Send")

            if save_btn.exists:
                save_btn.click()
                print("✅ Cambios de texto guardados por botón visible.")
            else:
                print("   No vi botón Guardar, simulando 'Enter' para enviar edición...")
                self.device.press("enter")
                # Intentar pulsar 'Tab' y 'Enter' si el enter principal no envía
                self.device.press("tab")
                self.device.press("enter")

            print("✅ Edición en Android completada correctamente.")
            return {
                "success": True,
                "status": "edited",
                "method": "android_ui_automation"
            }

        except Exception as e:
            print(f"❌ Excepción durante la macro de UI: {e}")
            return {"success": False, "error": str(e)}
