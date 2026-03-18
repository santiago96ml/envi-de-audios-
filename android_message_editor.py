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
        """Abre la conversación usando Intent Action VIEW (deep link) o búsqueda simple."""
        if not self.device:
            return
        
        if recipient_or_url.startswith("http"):
            print(f"🔗 Abriendo enlace directamente en Android: {recipient_or_url}")
            # Ejecutamos el intent de visualización manejado por LinkedIn
            self.device.shell(f"am start -a android.intent.action.VIEW -d '{recipient_or_url}' com.linkedin.android")
            time.sleep(6) # Darle tiempo a cargar la UI
            
            # Si estamos en un perfil en lugar de un chat directo, buscar el botón "Mensaje"
            msg_btn = self.device(textMatches="(?i)Mensaje|Message")
            if msg_btn.exists:
                print("   Clickeando botón 'Mensaje' en el perfil...")
                msg_btn.click()
                time.sleep(3)
        else:
            print(f"🔍 Buscando contacto por nombre '{recipient_or_url}' en Mensajes...")
            # Abrimos o traemos a frente LinkedIn
            self.device.app_start("com.linkedin.android")
            time.sleep(4)
            
            # Buscar la pestaña de mensajes
            msg_tab = self.device(contentDescriptionMatches="(?i).*Mensajes.*|.*Messaging.*")
            if msg_tab.exists:
                msg_tab.click()
                time.sleep(3)
            
            # Clicar en la barra de búsqueda superior
            search_box = self.device(textMatches="(?i)Buscar mensajes|Search messages")
            if search_box.exists:
                search_box.click()
                time.sleep(1)
                
                # Escribir el nombre
                search_input = self.device(className="android.widget.EditText")
                if search_input.exists:
                    search_input.set_text(recipient_or_url)
                    print("   Esperando resultados...")
                    time.sleep(3)
                    
                    # Clicar el primer resultado que contenga el nombre buscado
                    result = self.device(textContains=recipient_or_url)
                    if result.exists:
                        # Aseguramos de no clicar la propia barra de búsqueda
                        for match in result:
                            if match.info['className'] != "android.widget.EditText":
                                match.click()
                                time.sleep(3)
                                print(f"✅ Conversación con '{recipient_or_url}' abierta.")
                                return
                    else:
                        print(f"⚠️ No se encontró la conversación para: {recipient_or_url}")

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
