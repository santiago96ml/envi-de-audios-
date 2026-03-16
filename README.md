# 🎙️ LinkedIn Voice Bot - Inyector Nativo de Audio

Este proyecto automatiza el envío de **Notas de Voz Reales** a través de la aplicación de LinkedIn. Utiliza la emulación nativa de dispositivos Android para superar las restricciones de la API web de LinkedIn. Al inyectar el audio en tiempo real directamente al micrófono del emulador, genera mensajes de voz reales (con ondas de sonido y una duración de grabación genuina) ofreciendo una experiencia 100% auténtica que previene baneos y bloqueos de red.

## 🌟 Características Principales
- **Inyección Nativa de Audio:** No sube archivos como datos adjuntos (que el usuario vería como descargas), sino que transfiere el audio digitalmente al hardware de micrófono falso configurado en el emulador de Android.
- **Emulación Dispositivo Real:** Simula toques ("Hold to talk") y manipula la interfaz de la App de LinkedIn enviando eventos profundos ADB al sistema operativo de Android.
- **Multi Entorno:** Corre tanto en tu ordenador personal (BlueStacks) como en servicios de la nube desatendidos (Docker + Redroid).
- **Control de Tiempo Preciso:** Utiliza hilos simultáneos (threading) para mantener pulsada la pantalla con comandos nativos en perfecta sincronía hasta que el último milisegundo de tu audio haya sido introducido al móvil.

---

## 📦 Arquitecturas Soportadas

Tienes dos formas de utilizar y configurar este proyecto según tus necesidades:

1. **[Modo Local (Windows)]**: Utilizando tu PC de escritorio con BlueStacks y VB-Audio Virtual Cable (Recomendado para uso personal, pruebas, o envíos manuales agendados).
2. **[Modo Servidor (VPS / Docker)]**: Tecnología en jaula basada en Redroid y PulseAudio/ALSA. (Uso para agencias o automatizaciones 24/7 mediante plataformas como n8n).

---

## 💻 1. Guía de Instalación para Entorno Local (Windows)

Esta es la forma tradicional de ejecutarlo desde tu propia máquina.

### A. Pre-requisitos del Ordenador
1. **Python 3.9+** instalado en Windows (asegúrate de marcar "Add to PATH" al instalarlo).
2. **Git** (opcional para descargar el repositorio, o bien descárgalo directamente en formato `.zip`).
3. Software **FFmpeg** instalado (se emplea internamente si necesitas procesar la ganancia o volumen de audios que grabaste muy bajo).

### B. Configuración de Hardware Virtual y Emulador
Para engañar a Android haciéndole creer que nuestro script es una grabadora microfónica física encendida, necesitamos crear un "puente". Para esto usa estas dos herramientas:

**1. Instalar un Puente de Audio (VB-Audio Virtual Cable):**
- Descarga el driver gratuito de [VB-Cable (Virtual Audio Cable)](https://vb-audio.com/Cable/) e instálalo (ejecuta el Setup como Administrador).
- ¡Reinicia tu computadora para que se asienten los drivers!
- Abre Windows, busca `Panel de Control > Hardware y Sonido > Sonido`. 
- Repasa las pestañas de "Reproducción" y "Grabar"; es vital que localices las interfaces "CABLE Input" y "CABLE Output" y le des clic derecho -> **Habilitar**.

**2. Instalar y configurar BlueStacks:**
- Descarga [BlueStacks 5](https://www.bluestacks.com/) e instálalo normal.
- Abre la app accesoria **"BlueStacks Multi-Instance Manager"** (Administrador de instancias múltiples). 
- Crea una Instancia Nueva: Selecciona específicamente **Android 11** o **Pie 64-bit**. Las versiones obsoletas no cargan el LinkedIn moderno. Dale "Inicio".
- Ya dentro la nueva instancia de Android, ve al ícono del engranaje (Ajustes de BlueStacks abajo a la derecha):
  - En la sección **Avanzado**: Activa o enciende la opción **Configuración ADB** (o puentes de depuración).
  - En la sección **Audio / Dispositivos Auxiliares**: Abre la lista de opciones para Micrófono, y cámbialo a tu cable virtual recién instalado: **"CABLE Output (VB-Audio Virtual Cable)"**. Cierra y guarda.
- Finalmente, abre la app Google Play Store en él, busca LinkedIn, descarga la app e inicia tu sesión de usuario.

### C. Instalación del Código del Bot
Abre una terminal normal de Windows (CMD o PowerShell) o la terminal de VSCode y ejecuta esto paso a paso:

```bash
# 1. Clona o abre la carpeta del bot
git clone https://github.com/santiago96ml/envi-de-audios-.git
cd envi-de-audios-
cd linkedin_voice_bot

# 2. Descarga todas las dependencias para mover la matriz Android desde tu código
pip install -r requirements.txt
```

### D. Chequeo de Variables Críticas en Configuración
Revisa el código interno de configuración (abriendo el archivo `config.py`):

```python
# Habilitar Inyector Android en vez del API web obsoleto
USE_ANDROID = True

# IP DEL EMULADOR: BlueStacks típicamente abre el túnel ADB localmente en 127.0.0.1:5555. 
# Si tu dispositivo figura distinto, cambialo acá.
ADB_SERIAL = "127.0.0.1:5555" 

# NOMBRE EXACTO DEL CABLE
# Si estás configurando esto en Windows / Español, el sonido se lista en Python de esta forma:
VIRTUAL_CABLE_NAME = "Altavoces (VB-Audio Virtual Cable)"
```

### E. Uso General
- **Prepara a BlueStacks:** Dale Play, abre tu App de LinkedIn de Android, e ingresa al chat directo del individuo al que le quieres enviar el audio. Quédate mirando la bandeja de texto y el ícono de micrófono.
- **Prepara tu terminal, y dispara:**
```bash
python main.py --audio "audio_source/mi_mensaje_hola.wav" --android
```
En cuestión de segundos, la línea de comandos inyectará las señales motrices a BlueStacks y escucharás y verás a tu androide fantasma pulsando la app sostenidamente y pasándole el audio que dejaste como bandera.

---

## ☁️ 2. Guía de Despliegue Avanzado (Servidores VPS y Docker)

Si quieres dejar de usar tu ordenador personal y dejar que el bot opere 24/7 en segundo plano desde un servidor integrado con flujogramas de Workflows (ej. *n8n*, *Zapier*, o Make), esta es la sección.

### Dificultad Servidor y La Solución:
BlueStacks no funciona en servidores VPS bajo Linux en nube (ej. Hostinger) porque son entornos sin interfaz (pantalla negra "headless"). 
La solución es utilizar la rama de virtualización **"Redroid (Remote-Android)"** que ejecuta una emulación entera de Android enjaulada velozmente dentro de Linux, y reemplazar el VB-Cable de Windows con PulseAudio. Todo esto ya está construido y codificado usando Docker.

### Requisitos del VPS
- Una instancia de un **Servidor VPS (Virtual Private Server)** preferiblemente con Kernel "KVM" (Hostings compartidos de páginas webs no aplican porque Android exige mucha RAM).
- Sistema Operativo en el Servidor: **Ubuntu 20.04+ (o 22.04 LTS)**.
- **Docker** y **Docker-Compose** pre-instalados en tu servidor mediante SSH.
- Por lo menos 4 - 8 GB de RAM libres. Soporte de kernel habilitado para módulos Ashmem y Binder (requerimientos universales para correr Androids-virtuales).

### Lanzamiento Vía Docker de un Solo Clic
En el root del programa yacen dos recetas de automatización: un servidor de dependencias `Dockerfile` que contiene el cliente de sonido nativo Linux, y el archivo orquestador `docker-compose.yml`.

1. Arrastra tu proyecto entero hacia la estructura interna del disco de tu Servidor en Hostinger / AWS.
2. Ingresa vía consola SSH a la ruta de tu carpeta: `cd /home/proyectos/linkedin_voice_bot`
3. Dale orden a Docker de cobrar vida:
```bash
docker-compose up -d
```
Verás un reporte de ejecución. Automáticamente habrás inicializado en tu propio hosting 3 puertos de comunicación independientes y funcionales: `n8n` abierto en el puerto 5678, y una máquina silenciosa virtual llamada redroid en el 5555 aguardando la conexión de inyección local de ALSA. *Nota: Será obligatorio conectarte mediante un túnel o app gráfica remota a ese Redroid 1 vez para iniciar sesión en Linkedin app*.

---

## 🛠️ Utilidades Extras y Caja de Herramientas Incluida

Pensando en si alguna vez el proceso interno se daña y nadie sabe dónde: el robot provee pequeños códigos que se pueden lanzar en terminal individualmente para solucionar cualquier dolor de cabeza.

- **`python get_audio_devices.py`**: ¿Python arroja un error avisando que el Virtual Cable no existe? Este pequeño script generará un block de notas de volcado, rastreando los nombres binarios milimétricos bajo los que Windows registró tú Virtual Cable. Útil para copiar el index si tu OS lo cambió.
- **`python test_adb.py`**: Este script emite pings al emulador verificando que la puerta USB/Depuración local esté activa y te resume los datos del androide para detectar si fallaron los firewalls ADB locales.
- **`python dump_ui.py`**: El salvavidas principal. Las Apps como LinkedIn se actualizan comúnmente en la PlayStore. Un buen día cambian el botón "mandar voz" a un diseño ligeramente distinto y el bot falla cegado. Este plugin robará por rayos-x el código fuente entero de la visual de tu pantalla táctil App por App, escaneando para permitirte extraer mediante el buscador el ID exacto del botón que el desarrollador de LinkedIn haya renombrado ese día.
