FROM python:3.9-slim

# Instalar dependencias del sistema:
# - FFmpeg: para procesar el audio
# - ADB: para conectar con redroid
# - PulseAudio / ALSA: para crear cables virtuales de audio en Linux
RUN apt-get update && apt-get install -y \
    ffmpeg \
    adb \
    pulseaudio \
    alsa-utils \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

# Configurar directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
# Modificamos requirements si hace falta
RUN pip install --no-cache-dir -r requirements.txt Flask

# Copiar el código del proyecto
COPY . .

# Dar permisos al script de entrada (si lo usamos)
# RUN chmod +x entrypoint.sh

# Crear script de inicio para PulseAudio (Cable Virtual en Linux)
RUN echo '#!/bin/bash\n\
# Iniciar PulseAudio en modo demonio (system-wide o de usuario)\n\
pulseaudio -D --exit-idle-time=-1\n\
# Crear un modulo de sumidero virtual (nuestro "Virtual Cable")\n\
pactl load-module module-null-sink sink_name=VirtualMic sink_properties=device.description="VirtualMic"\n\
pactl set-default-sink VirtualMic\n\
# Iniciar la aplicación o mantener vivo\n\
exec "$@"' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
