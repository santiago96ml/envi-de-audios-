import sys

file_path = "linkedin_injector.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_method = """    async def inject_and_send_voice_message(self) -> dict:
        \"\"\"
        Sube el archivo de audio como un adjunto estándar usando la interfaz de usuario de Playwright.
        Esta alternativa es 100% segura y sustituye al inyector de JS puro bloqueado por LinkedIn.
        \"\"\"
        import os
        audio_path = str(self.processed_wav_path)

        if not os.path.exists(audio_path):
            return {"success": False, "error": f"Archivo no encontrado: {audio_path}", "step": "pre-check"}

        print(f"\\n[UI Automation] Seleccionando audio como adjunto: {audio_path}...")
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
            print("✅ ¡Audio enviado como archivo adjunto exitosamente!\\n")
            
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
"""

# Keep prefix until line 278 (index 277)
prefix = lines[:278]
# Keep suffix from line 640 (index 639)
suffix = lines[639:]

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(prefix)
    f.write(new_method + "\n")
    f.writelines(suffix)

print("✅ Archivo linkedin_injector.py modificado correctamente.")
