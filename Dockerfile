FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Configurar directorio de trabajo
WORKDIR /app

# Variables de entorno del sistema
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1
# Necesario para que Playwright funcione correctamente en Docker
ENV DISPLAY=:99

# Instalar dependencias del sistema para Chromium headless en Docker
RUN apt-get update && apt-get install -y \
    # Para Chromium en Linux sin pantalla
    xvfb \
    # Para procesar audio si es necesario en el futuro
    libgbm-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python (en capa separada para mejor cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/session_data /app/chrome_profile /app/audio_processed

# Puerto de la API
EXPOSE 5000

# Por defecto lanza la API. El worker se lanza con el servicio específico en docker-compose.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "5000"]
