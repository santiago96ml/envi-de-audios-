"""
config.py - Configuración centralizada para el bot de voz de LinkedIn.

Gestiona rutas, credenciales y parámetros del sistema.
"""

import os
from pathlib import Path

# ==============================================================================
# RUTAS DEL PROYECTO
# ==============================================================================

# Directorio raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent

# Carpeta de audios originales (mp3, wav, etc.)
AUDIO_SOURCE_DIR = PROJECT_ROOT / "audio_source"

# Carpeta de audios procesados (WAV PCM 16-bit mono 16kHz)
AUDIO_PROCESSED_DIR = PROJECT_ROOT / "audio_processed"

# Carpeta de datos de sesión de Playwright
SESSION_DATA_DIR = PROJECT_ROOT / "session_data"

# Archivo de estado de sesión (cookies y localStorage)
SESSION_STATE_FILE = SESSION_DATA_DIR / "linkedin_state.json"

# ==============================================================================
# CREDENCIALES DE LINKEDIN
# ==============================================================================
# Se recomienda establecerlas como variables de entorno:
#   set LINKEDIN_EMAIL=tu_email@example.com
#   set LINKEDIN_PASSWORD=tu_contraseña
#
# Si no están definidas, se usarán los valores por defecto (vacíos).

LINKEDIN_EMAIL = os.environ.get("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "")

# ==============================================================================
# URLs DE LINKEDIN
# ==============================================================================

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"
LINKEDIN_MESSAGING_URL = "https://www.linkedin.com/messaging/"

# ==============================================================================
# CONFIGURACIÓN DE PLAYWRIGHT / CHROMIUM
# ==============================================================================

# headless=False es OBLIGATORIO para que WebRTC funcione correctamente
HEADLESS = False

# Tiempo de espera global para operaciones de Playwright (ms)
DEFAULT_TIMEOUT = 30000

# Tiempo de espera para la carga de páginas (ms)
NAVIGATION_TIMEOUT = 60000

# User-Agent personalizado (simular un navegador real)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

# Viewport del navegador
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800

# ==============================================================================
# CONFIGURACIÓN DE AUDIO (FFmpeg)
# ==============================================================================

# Ruta al ejecutable de FFmpeg (especificar si no está en el PATH)
# Ejemplo: "C:/FFmpeg/bin/ffmpeg.exe"
FFMPEG_PATH = r"C:\Users\merca\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\Users\merca\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffprobe.exe"

# Formato requerido por Chromium para --use-file-for-fake-audio-capture
AUDIO_SAMPLE_RATE = 16000   # Hz
AUDIO_CHANNELS = 1          # Mono
AUDIO_CODEC = "pcm_s16le"   # PCM signed 16-bit little-endian
AUDIO_FORMAT = "wav"

# ==============================================================================
# CONFIGURACIÓN DE ANDROID / BLUESTACKS
# ==============================================================================

# Serial ADB para conectar con BlueStacks (usualmente 5555 o 5565)
ADB_SERIAL = "127.0.0.1:5555"

# Nombre del dispositivo de audio virtual (VB-Audio Virtual Cable)
# Se usará para buscar el índice dinámicamente en sounddevice
# Nombre que aparece en sounddevice para el OUTPUT del cable virtual
# (el PC reproduce aquí, BlueStacks graba de aquí como input)
VIRTUAL_CABLE_NAME = "Altavoces (VB-Audio Virtual Cable)"

# Retraso (s) tras presionar el botón de micro antes de empezar el audio
# Evita cortes al inicio de la grabación en la App móvil
PTT_DELAY = 0.5

# ==============================================================================
# CONFIGURACIÓN DEL MENSAJE DE VOZ
# ==============================================================================

# Margen extra (en ms) que se le da al MediaRecorder después de la duración
# real del audio, para asegurar que la grabación se complete sin cortes
RECORDING_MARGIN_MS = 500

# Modo de ejecución (inyectado por main.py)
USE_ANDROID = False

# ==============================================================================
# VALIDACIONES DE INICIO
# ==============================================================================

def ensure_directories_exist():
    """Crea los directorios necesarios si no existen."""
    AUDIO_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_DATA_DIR.mkdir(parents=True, exist_ok=True)


def validate_config():
    """Valida que la configuración mínima esté presente."""
    warnings = []

    if not LINKEDIN_EMAIL:
        warnings.append(
            "⚠️  LINKEDIN_EMAIL no definido. "
            "Deberás iniciar sesión manualmente en el navegador."
        )
    if not LINKEDIN_PASSWORD:
        warnings.append(
            "⚠️  LINKEDIN_PASSWORD no definido. "
            "Deberás iniciar sesión manualmente en el navegador."
        )

    for w in warnings:
        print(w)

    return len(warnings) == 0
