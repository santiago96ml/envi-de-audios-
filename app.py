from flask import Flask, request, jsonify
import subprocess
import os
import sys

# Añadir el directorio actual al path para importar módulos locales si es necesario
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Usa siempre un token seguro en n8n (X-API-KEY)
API_TOKEN = os.getenv("API_TOKEN", "stark_secure_token_2024_linkedin_bot")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Bot API is running"}), 200

@app.route('/send-voice', methods=['POST'])
def send_voice():
    # 1. Validación de Seguridad (Token)
    client_token = request.headers.get('X-API-KEY')
    if not client_token or client_token != API_TOKEN:
        return jsonify({
            "status": "error", 
            "message": "No autorizado. Token API inválido o ausente."
        }), 401

    # 2. Obtención de parámetros del JSON (enviados por n8n)
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Cuerpo de la petición vacío o no es JSON"}), 400

    contact_name = data.get('contact')
    audio_file = data.get('audio') # Ejemplo: "audio_source/mensaje.wav"
    
    # Validaciones mínimas
    if not contact_name:
        return jsonify({"status": "error", "message": "Falta el campo 'contact'"}), 400
    if not audio_file:
        return jsonify({"status": "error", "message": "Falta el campo 'audio'"}), 400
    
    # Verificar si el archivo de audio existe
    if not os.path.exists(audio_file):
        return jsonify({"status": "error", "message": f"Archivo de audio no encontrado: {audio_file}"}), 404

    # 3. Ejecución del Bot
    try:
        # Ejecutamos el main.py con los argumentos dinámicos
        # Usamos --android para forzar el modo inyector nativo
        process_cmd = [
            "python", "main.py",
            "--audio", audio_file,
            "--android"
        ]
        
        result = subprocess.run(
            process_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return jsonify({
            "status": "success",
            "message": "Proceso de envío completado",
            "output": result.stdout
        }), 200

    except subprocess.CalledProcessError as e:
        return jsonify({
            "status": "error",
            "message": "Error al ejecutar el bot de voz",
            "error_log": e.stdout + e.stderr
        }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    # Escuchamos en todas las interfaces en el puerto 5000
    print(f"--- Servidor API del Bot Iniciado ---")
    print(f"Status: Protegido por Token")
    print(f"Puerto: 5000")
    app.run(host='0.0.0.0', port=5000)
