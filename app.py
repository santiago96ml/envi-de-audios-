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

@app.route('/edit-message', methods=['POST'])
def edit_message():
    # 1. Validación de Seguridad (Token)
    client_token = request.headers.get('X-API-KEY')
    if not client_token or client_token != API_TOKEN:
        return jsonify({
            "status": "error", 
            "message": "No autorizado. Token API inválido o ausente."
        }), 401

    # 2. Obtención de parámetros del JSON
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Cuerpo de la petición vacío o no es JSON"}), 400

    contact_name_or_url = data.get('contact')
    old_message = data.get('old_message')
    new_message = data.get('new_message')
    
    # Validaciones mínimas
    if not contact_name_or_url or not old_message or not new_message:
        return jsonify({"status": "error", "message": "Faltan campos: 'contact', 'old_message' o 'new_message'"}), 400
    
    # 3. Ejecución del Editor Web
    try:
        # Llamamos al nuevo script independiente run_web_editor.py
        process_cmd = [
            "python", "run_web_editor.py",
            "--contact", contact_name_or_url,
            "--old", old_message,
            "--new", new_message
        ]
        
        result = subprocess.run(
            process_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return jsonify({
            "status": "success",
            "message": "Operación de edición web finalizada",
            "output": result.stdout
        }), 200

    except subprocess.CalledProcessError as e:
        return jsonify({
            "status": "error",
            "message": "Error al ejecutar el editor web Chromium",
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
