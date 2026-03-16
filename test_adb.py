import uiautomator2 as u2
import sounddevice as sd
import config

def test_connection():
    print(f"I Intentando conectar a: {config.ADB_SERIAL}...")
    try:
        d = u2.connect(config.ADB_SERIAL)
        print("OK Conectado con exito!")
        print(f"   Info del dispositivo: {d.info}")
    except Exception as e:
        print(f"ERR Error de conexion: {e}")
        print("   Asegurate de que BlueStacks este abierto y el ADB habilitado.")

def list_audio_devices():
    print("\nI Dispositivos de Audio Detectados:")
    print("-" * 40)
    devices = sd.query_devices()
    found = False
    for i, dev in enumerate(devices):
        marker = "* [VIRTUAL CABLE]" if config.VIRTUAL_CABLE_NAME in dev['name'] else "  "
        print(f"{marker} [{i}] {dev['name']} (Canales: {dev['max_output_channels']} out / {dev['max_input_channels']} in)")
        if config.VIRTUAL_CABLE_NAME in dev['name']:
            found = True
    
    if not found:
        print("\nWARN ADVERTENCIA: No se detecto 'CABLE Input'.")
        print("   Instala VB-Audio Virtual Cable para que la inyeccion funcione.")

if __name__ == "__main__":
    test_connection()
    list_audio_devices()
