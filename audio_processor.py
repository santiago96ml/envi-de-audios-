"""
audio_processor.py - Procesamiento de audio para compatibilidad con Chromium.

Convierte cualquier archivo de audio al formato exacto requerido por
--use-file-for-fake-audio-capture de Chromium:
  WAV PCM signed 16-bit little-endian, mono, 16000 Hz.

Requiere FFmpeg instalado y accesible desde PATH.
"""

import subprocess
import sys
import json
from pathlib import Path

import config


def check_ffmpeg_installed() -> bool:
    """Verifica si FFmpeg está instalado y disponible."""
    # Intentar con la ruta configurada primero
    ffmpeg_exe = config.FFMPEG_PATH if config.FFMPEG_PATH else "ffmpeg"
    try:
        result = subprocess.run(
            [ffmpeg_exe, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except FileNotFoundError:
        # Si la ruta configurada falla, intentar con la global
        if ffmpeg_exe != "ffmpeg":
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return result.returncode == 0
            except FileNotFoundError:
                return False
        return False
    except subprocess.TimeoutExpired:
        return False


def get_audio_duration_seconds(audio_path: Path) -> float:
    """
    Obtiene la duración de un archivo de audio en segundos usando ffprobe.
    """
    ffprobe_exe = config.FFPROBE_PATH if config.FFPROBE_PATH else "ffprobe"
    cmd = [
        ffprobe_exe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(audio_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffprobe falló para '{audio_path}':\n{result.stderr}"
            )

        probe_data = json.loads(result.stdout)
        duration = float(probe_data["format"]["duration"])
        return duration

    except (KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"No se pudo extraer la duración de '{audio_path}': {e}"
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffprobe no encontrado. Instala FFmpeg y asegúrate de que esté en PATH."
        )


def convert_audio_for_chromium(input_path: Path, output_path: Path = None) -> Path:
    """
    Convierte un archivo de audio al formato WAV requerido por Chromium.

    Formato de salida: WAV PCM signed 16-bit little-endian, mono, 16000 Hz.

    Equivale al comando:
        ffmpeg -i input.mp3 -acodec pcm_s16le -ac 1 -ar 16000 -vn output.wav

    Args:
        input_path: Ruta al archivo de audio fuente.
        output_path: Ruta de salida (opcional). Si no se especifica, se genera
                     automáticamente en AUDIO_PROCESSED_DIR con extensión .wav.

    Returns:
        Path al archivo WAV convertido.

    Raises:
        FileNotFoundError: Si el archivo de entrada no existe.
        RuntimeError: Si FFmpeg falla en la conversión.
    """
    input_path = Path(input_path).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Archivo de audio no encontrado: {input_path}")

    # Generar ruta de salida si no se proporcionó
    if output_path is None:
        output_path = config.AUDIO_PROCESSED_DIR / f"{input_path.stem}_processed.wav"
    else:
        output_path = Path(output_path).resolve()

    # Asegurar que el directorio de salida exista
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Comando FFmpeg para conversión
    ffmpeg_exe = config.FFMPEG_PATH if config.FFMPEG_PATH else "ffmpeg"
    cmd = [
        ffmpeg_exe,
        "-y",                           # Sobrescribir sin preguntar
        "-i", str(input_path),          # Archivo de entrada
        "-acodec", config.AUDIO_CODEC,  # pcm_s16le
        "-ac", str(config.AUDIO_CHANNELS),  # 1 (mono)
        "-ar", str(config.AUDIO_SAMPLE_RATE),  # 16000 Hz
        "-vn",                          # Sin video
        str(output_path),               # Archivo de salida
    ]

    print(f"🔄 Convirtiendo audio: {input_path.name}")
    print(f"   Comando: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg falló con código {result.returncode}:\n{result.stderr}"
            )

        # Verificar que el archivo de salida se creó
        if not output_path.exists():
            raise RuntimeError(
                f"FFmpeg terminó exitosamente pero no se creó el archivo: {output_path}"
            )

        # Verificar tamaño mínimo (un WAV válido tiene al menos 44 bytes de header)
        file_size = output_path.stat().st_size
        if file_size < 44:
            raise RuntimeError(
                f"Archivo de salida demasiado pequeño ({file_size} bytes). "
                "Posible error de conversión."
            )

        duration = get_audio_duration_seconds(output_path)
        print(f"✅ Audio convertido exitosamente: {output_path.name}")
        print(f"   Formato: WAV PCM 16-bit mono @ {config.AUDIO_SAMPLE_RATE}Hz")
        print(f"   Duración: {duration:.2f} segundos")
        print(f"   Tamaño: {file_size / 1024:.1f} KB")

        return output_path

    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg no encontrado. Instala FFmpeg y asegúrate de que esté en PATH.\n"
            "  Windows: choco install ffmpeg  o  winget install ffmpeg\n"
            "  macOS:   brew install ffmpeg\n"
            "  Linux:   sudo apt install ffmpeg"
        )


def process_all_audio_files() -> list[dict]:
    """
    Procesa todos los archivos de audio en AUDIO_SOURCE_DIR.

    Returns:
        Lista de diccionarios con info de cada archivo procesado:
        [{"input": Path, "output": Path, "duration": float}, ...]
    """
    config.ensure_directories_exist()

    supported_extensions = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma", ".opus"}
    source_files = [
        f for f in config.AUDIO_SOURCE_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]

    if not source_files:
        print(f"⚠️  No se encontraron archivos de audio en: {config.AUDIO_SOURCE_DIR}")
        return []

    print(f"📂 Encontrados {len(source_files)} archivo(s) de audio para procesar.\n")

    results = []
    for audio_file in sorted(source_files):
        try:
            output_path = convert_audio_for_chromium(audio_file)
            duration = get_audio_duration_seconds(output_path)
            results.append({
                "input": audio_file,
                "output": output_path,
                "duration": duration,
            })
        except Exception as e:
            print(f"❌ Error procesando '{audio_file.name}': {e}")

        print()  # Línea en blanco entre archivos

    return results


# ==============================================================================
# EJECUCIÓN DIRECTA (para pruebas)
# ==============================================================================

if __name__ == "__main__":
    if not check_ffmpeg_installed():
        print("❌ FFmpeg no está instalado o no se encuentra en el PATH.")
        print("   Por favor, instálalo antes de continuar:")
        print("   Windows: choco install ffmpeg o winget install ffmpeg")
        sys.exit(1)

    print("✅ FFmpeg detectado correctamente.\n")

    if len(sys.argv) > 1:
        # Procesar un archivo específico pasado por argumento
        input_file = Path(sys.argv[1])
        result = convert_audio_for_chromium(input_file)
        duration = get_audio_duration_seconds(result)
        print(f"\n📊 Resultado: {result} ({duration:.2f}s)")
    else:
        # Procesar todos los archivos en la carpeta audio_source/
        results = process_all_audio_files()
        if results:
            print(f"\n📊 Resumen: {len(results)} archivo(s) procesado(s) con éxito.")
