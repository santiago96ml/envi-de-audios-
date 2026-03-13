"""
main.py - Orquestador principal del bot de voz para LinkedIn.

Ejemplos de uso:
    # Inicio de sesión para guardar cookies
    python main.py --login-only

    # Enviar audio a un contacto (por nombre)
    python main.py --audio audio_source/mensaje.mp3 --recipient "Nombre del Contacto"

    # Enviar audio a una conversación directa
    python main.py --audio audio_source/mensaje.mp3 --conversation-url "https://www.linkedin.com/messaging/thread/..."

    # Solo convertir audios (sin enviar)
    python main.py --process-only
"""

import argparse
import asyncio
import sys
from pathlib import Path

import config
from audio_processor import (
    check_ffmpeg_installed,
    convert_audio_for_chromium,
    get_audio_duration_seconds,
    process_all_audio_files,
)
from linkedin_injector import LinkedInInjector


def print_banner():
    """Muestra el banner informativo en la consola."""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║           🎙️  LinkedIn Voice Bot v1.0                    ║
    ║     Playwright + WebRTC Media Stream Virtualization      ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def parse_args():
    """Define y procesa los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(
        description="LinkedIn Voice Bot - Automatización de mensajes de voz.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--audio",
        type=str,
        help="Ruta del archivo de audio (mp3, wav, ogg, etc.).",
    )

    parser.add_argument(
        "--recipient",
        type=str,
        help="Nombre del contacto de destino.",
    )

    parser.add_argument(
        "--conversation-url",
        type=str,
        help="URL directa del hilo de mensajes.",
    )

    parser.add_argument(
        "--login-only",
        action="store_true",
        help="Solo inicia sesión y guarda la sesión (cookies).",
    )

    parser.add_argument(
        "--process-only",
        action="store_true",
        help="Solo procesa y convierte los audios de la carpeta de origen.",
    )

    return parser.parse_args()


def check_prerequisites():
    """Verifica los requisitos necesarios para la ejecución."""
    print("🔍 Comprobando requisitos previos...\n")

    # Validar FFmpeg
    if not check_ffmpeg_installed():
        print("❌ FFmpeg no está instalado o no se encuentra en el PATH.")
        print("   Instálalo con:")
        print("   Windows: choco install ffmpeg")
        sys.exit(1)
    print("   ✅ FFmpeg detectado.")

    # Asegurar carpetas
    config.ensure_directories_exist()
    print("   ✅ Directorios verificados.")

    # Validar configuración básica
    config.validate_config()
    print()


async def run_login_only():
    """Ejecuta únicamente el flujo de autenticación."""
    print("🔐 Modo: Solo Autenticación\n")

    # Necesitamos un archivo WAV dummy para que el navegador inicie con los parámetros de audio
    dummy_wav = config.AUDIO_PROCESSED_DIR / "_dummy_login.wav"

    if not dummy_wav.exists():
        import subprocess
        # Intentar con la ruta configurada primero
        ffmpeg_exe = config.FFMPEG_PATH if config.FFMPEG_PATH else "ffmpeg"
        try:
            subprocess.run(
                [
                    ffmpeg_exe, "-y",
                    "-f", "lavfi",
                    "-i", "anullsrc=r=16000:cl=mono",
                    "-t", "1",
                    "-acodec", "pcm_s16le",
                    "-ac", "1",
                    "-ar", "16000",
                    str(dummy_wav),
                ],
                capture_output=True,
                timeout=10,
            )
        except Exception:
            # Crear manualmente un WAV vacío si falla ffmpeg
            import struct
            sample_rate = 16000
            num_samples = sample_rate
            data_size = num_samples * 2
            with open(dummy_wav, "wb") as f:
                f.write(b"RIFF")
                f.write(struct.pack("<I", 36 + data_size))
                f.write(b"WAVE")
                f.write(b"fmt ")
                f.write(struct.pack("<I", 16))
                f.write(struct.pack("<H", 1))
                f.write(struct.pack("<H", 1))
                f.write(struct.pack("<I", sample_rate))
                f.write(struct.pack("<I", sample_rate * 2))
                f.write(struct.pack("<H", 2))
                f.write(struct.pack("<H", 16))
                f.write(b"data")
                f.write(struct.pack("<I", data_size))
                f.write(b"\x00" * data_size)

    injector = LinkedInInjector(
        processed_wav_path=dummy_wav,
        audio_duration_seconds=1.0,
    )

    result = await injector.run_full_flow(login_only=True)
    return result


async def run_send_voice(audio_path: str, recipient: str = None, conversation_url: str = None):
    """
    Flujo de envío: conversión -> autenticación -> navegación -> envío.
    """
    audio_file = Path(audio_path).resolve()

    if not audio_file.exists():
        print(f"❌ No se encontró el audio: {audio_file}")
        sys.exit(1)

    print(f"📁 Audio original: {audio_file.name}\n")

    print("-" * 60)
    print("PASO 1: Procesamiento de Audio")
    print("-" * 60)

    processed_wav = convert_audio_for_chromium(audio_file)
    duration = get_audio_duration_seconds(processed_wav)

    print("-" * 60)
    print("PASO 2: Navegador y Envío")
    print("-" * 60)

    injector = LinkedInInjector(
        processed_wav_path=processed_wav,
        audio_duration_seconds=duration,
    )

    result = await injector.run_full_flow(
        recipient_name=recipient,
        conversation_url=conversation_url,
    )

    print("-" * 60)
    print("RESUMEN FINAL")
    print("-" * 60)

    if result.get("success"):
        print("✅ ¡Mensaje de voz enviado!")
        print(f"   ID de Conversación: {result.get('conversationId', 'N/A')}")
    else:
        print("❌ Fallo en el envío.")
        print(f"   Error: {result.get('error', 'Desconocido')}")
        print(f"   Paso: {result.get('step', 'N/A')}")
        print(f"   Detalles guardados en error_details.json")
        import json
        with open("error_details.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)

    return result


def main():
    print_banner()
    args = parse_args()
    check_prerequisites()

    if args.process_only:
        process_all_audio_files()
        return

    if args.login_only:
        asyncio.run(run_login_only())
        return

    if not args.audio:
        print("❌ Usa --audio para indicar qué archivo enviar.")
        sys.exit(1)

    asyncio.run(
        run_send_voice(
            audio_path=args.audio,
            recipient=args.recipient,
            conversation_url=args.conversation_url,
        )
    )


if __name__ == "__main__":
    main()
