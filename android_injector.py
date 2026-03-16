"""
android_injector.py - Controlador de emulación Android para bot de LinkedIn.

Usa uiautomator2 para interactuar con la App oficial y sounddevice 
para inyectar audio a través de un Virtual Audio Cable.
"""

import time
import sys
import uiautomator2 as u2
import sounddevice as sd
import soundfile as sf
import numpy as np
import config

class AndroidVoiceInjector:
    def __init__(self, adb_serial=config.ADB_SERIAL):
        """
        Inicializa la conexión con el emulador.
        """
        self.serial = adb_serial
        self.device = None
        self.virtual_cable_index = None

    def connect(self):
        """
        Conecta con la instancia de Android vía ADB.
        """
        try:
            print(f"📱 Conectando a instancia Android ({self.serial})...")
            self.device = u2.connect(self.serial)
            info = self.device.info
            print(f"✅ Conectado a: {info.get('productName', 'Desconocido')} ({info.get('displayId', 'ID n/a')})")
            
            # Buscar el Virtual Cable
            self.virtual_cable_index = self.find_virtual_cable()
            if self.virtual_cable_index is None:
                print("⚠️  No se encontró 'CABLE Input'. Se usará el dispositivo por defecto.")
            else:
                print(f"🎙️  Audio bridge configurado en dispositivo índice: {self.virtual_cable_index}")
                
            return True
        except Exception as e:
            print(f"❌ Error al conectar con ADB: {e}")
            return False

    def find_virtual_cable(self):
        """
        Busca dinámicamente el índice del VB-Audio Virtual Cable.
        """
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if config.VIRTUAL_CABLE_NAME in dev['name'] and dev['max_output_channels'] > 0:
                return i
        return None

    def send_voice_message(self, audio_path):
        """
        Ejecuta la secuencia de envío de nota de voz nativa:
        1. Carga audio
        2. Detecta botón en App
        3. Presiona y mantiene (Hold)
        4. Reproduce audio
        5. Suelta
        """
        if not self.device:
            if not self.connect():
                return {"success": False, "error": "No conectado a Android"}

        try:
            # 1. Cargar archivo de audio
            print(f"📂 Cargando audio: {audio_path}")
            data, fs = sf.read(audio_path)

            # 2. Localizar botón de grabar en la App de LinkedIn
            # El selector puede variar según el idioma de la app. 
            # Intentamos selectores comunes de accesibilidad.
            voice_btn = self.device(descriptionContains="Grabar mensaje de voz")
            if not voice_btn.exists:
                voice_btn = self.device(descriptionContains="Graba un mensaje de voz") # Android 11+
            if not voice_btn.exists:
                voice_btn = self.device(descriptionContains="Record voice message")
            
            if not voice_btn.exists:
                # Fallback: buscar por ID de recurso si es posible
                voice_btn = self.device(resourceId="com.linkedin.android:id/messaging_keyboard_voice_button")
            if not voice_btn.exists:
                # Nuevo ID en Android 11
                voice_btn = self.device(resourceId="com.linkedin.android:id/messaging_keyboard_voice_dashboard_button")

            if not voice_btn.exists:
                return {
                    "success": False, 
                    "error": "No se encontró el botón de voz. ¿Está abierto el chat?",
                    "step": "detect_button"
                }

            print(f"🚀 Iniciando grabación nativa (manteniendo por {len(data)/fs:.1f}s)...")
            
            # Usar threading para ejecutar ADB swipe (touch hold) y el Audio simultáneamente
            import threading
            
            x, y = voice_btn.center()
            
            # Calcular duración total en milisegundos (audio + márgenes)
            total_duration_ms = int(((len(data) / fs) + config.PTT_DELAY + 0.5) * 1000)
            
            def adb_hold_thread():
                print(f"👉 Manteniendo presionado el botón ({total_duration_ms} ms)...")
                # El comando input swipe con las mismas coordenadas X e Y simula un toque prolongado real
                self.device.shell(f"input swipe {x} {y} {x} {y} {total_duration_ms}")

            def play_audio_thread():
                time.sleep(config.PTT_DELAY)
                print("🔊 Reproduciendo audio...")
                sd.play(data, fs, device=self.virtual_cable_index)
                sd.wait()

            hold_thread = threading.Thread(target=adb_hold_thread)
            audio_thread = threading.Thread(target=play_audio_thread)
            
            # Iniciar ambos procesos
            hold_thread.start()
            audio_thread.start()
            
            # Esperar a que terminen
            hold_thread.join()
            audio_thread.join()
            
            print("✅ Nota de voz terminada y enviada.")

            return {
                "success": True,
                "status": "sent",
                "method": "native_android_ptt"
            }

        except Exception as e:
            print(f"❌ Error en inyección Android: {e}")
            return {"success": False, "error": str(e), "step": "ptt_flow"}
