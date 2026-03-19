# 🎙️ LinkedIn Message Editor - Playwright Web Edition

Este proyecto permite la edición automatizada de mensajes enviados en LinkedIn de forma humanizada, utilizando Playwright para el control del navegador y sesiones persistentes para evitar detecciones y bloqueos.

> [!IMPORTANT]
> Esta versión ha sido simplificada para eliminar la dependencia de emuladores Android y cables de audio virtuales. Ahora funciona directamente vía Web (Playwright), lo que reduce el consumo de recursos en un 90%.

## 🌟 Características Principales
- **Edición Web Directa**: Navega automáticamente a los chats de LinkedIn y edita mensajes existentes.
- **Sesiones Persistentes**: Utiliza un perfil de Chrome persistente (`chrome_profile`) para guardar cookies y evitar inicios de sesión constantes.
- **Escritura Humanizada**: Simula el tecleo humano (delay) y movimientos de ratón para evadir sistemas anti-bot.
- **Docker Ready**: Incluye un `Dockerfile` optimizado con las dependencias oficiales de Playwright.

---

## 🚀 Guía de Instalación Local (Windows)

### A. Pre-requisitos
1. **Python 3.9+** instalado.
2. **Git** para clonar el repositorio.

### B. Configuración
1. Clona el repositorio:
   ```bash
   git clone https://github.com/santiagomercadoluna26/envi-de-audios-.git
   cd envi-de-audios-/linkedin_voice_bot
   ```
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

### C. Primer Inicio de Sesión
Para que el bot funcione de forma desatendida, primero debes guardar tu sesión de LinkedIn:
1. (Opcional) Activa el modo con cabecera en `web_message_editor.py` cambiando `headless=True` a `False`.
2. Ejecuta un comando de prueba y logueate manualmente en la ventana que aparezca.
3. Las cookies se guardarán en la carpeta `chrome_profile`.

---

## ☁️ Despliegue en Servidor (Easypanel / Docker)

El proyecto está diseñado para desplegarse como una aplicación en Easypanel:
1. **Source**: GitHub Repository (`master`).
2. **Dockerfile**: El sistema detectará automáticamente el `Dockerfile`.
3. **Variables de Entorno**:
   - `API_TOKEN`: Tu clave secreta para el endpoint `/edit-message`.
4. **Volúmenes**: Es **VITAL** montar un volumen persistente en `/app/chrome_profile` para que el bot no pierda la sesión de LinkedIn cada vez que se reinicie el contenedor.

---

## 🛠️ API Endpoints

El bot expone una API Flask para integrarse con herramientas como **n8n**:

- **POST `/edit-message`**:
  - Headers: `X-API-KEY: <tu_token>`
  - Body (JSON):
    ```json
    {
      "contact": "URL_DEL_CHAT_O_NOMBRE",
      "old_message": "Texto que quieres cambiar",
      "new_message": "Nuevo texto corregido"
    }
    ```

---

## 🛠️ Herramientas Incluidas
- **`run_web_editor.py`**: Script de línea de comandos para realizar ediciones rápidas sin usar la API.
  ```bash
  python run_web_editor.py --contact "Juan Perez" --old "Hola" --new "Hola, ¿cómo estás?"
  ```
