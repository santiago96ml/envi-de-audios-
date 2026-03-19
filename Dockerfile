FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Configurar directorio de trabajo
WORKDIR /app

# Variable de entorno para que Playwright use los navegadores preinstalados en la imagen
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY . .

# Comando por defecto definido en docker-compose
CMD ["python", "app.py"]
