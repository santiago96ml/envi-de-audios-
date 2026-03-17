FROM python:3.9-slim

# Instalar dependencias adicionales del sistema (ADB, FFmpeg, etc.)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    adb \
    pulseaudio \
    alsa-utils \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python (Añadimos Flask explícitamente)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt Flask

# Copiar el código del proyecto
COPY . .

# Exponer el puerto de la API (5000)
# Esto permite que n8n u otros servicios externos se comuniquen con el bot de forma segura.
EXPOSE 5000

# Crear script de inicio para PulseAudio (Puerto Virtual en Linux)
RUN echo '#!/bin/bash\n\
# Iniciar PulseAudio en modo daemon\n\
pulseaudio -D --exit-idle-time=-1\n\
# Crear el sumidero nulo de audio (el cable virtual)\n\
pactl load-module module-null-sink sink_name=VirtualMic sink_properties=device.description="VirtualMic"\n\
pactl set-default-sink VirtualMic\n\
# Intentar conectar automáticamente con el contenedor de Android antes de iniciar la API\n\
if [ -n "$ADB_SERIAL" ]; then\n\
  # Esperar un poco a que el contenedor de Android esté listo\n\
  sleep 5\n\
  # Conectar por ADB pasándole el serial definido en el entorno (ej. android:5555)\n\
  adb connect $ADB_SERIAL\n\
fi\n\
# Iniciar la API del Bot en Python (Flask)\n\
exec python app.py "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
