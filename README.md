# LinkedIn Voice Bot v2.0
### Arquitectura: FastAPI + Redis Queue + Playwright Worker

Sistema de automatización de mensajes de LinkedIn diseñado para servidores con RAM limitada (6GB compartido con EasyPanel y n8n).

---

## 🏗️ Arquitectura

```
n8n / Frontend
      │
      ▼
[FastAPI - api.py]          <50MB RAM  — Valida y encola tareas
      │
      ▼
[Redis Queue]               <20MB RAM  — Cola de tareas y sesiones
      │
      ▼
[Playwright Worker]         ~250MB RAM base + ~50MB/contexto activo
      │
      ▼
[LinkedIn via Chromium]
```

### Componentes
| Archivo | Rol |
|---|---|
| `api.py` | Servidor FastAPI: recibe peticiones y las encola en Redis |
| `worker.py` | Worker Playwright: procesa tareas con un único Chromium |
| `session_manager.py` | Gestión de cookies de LinkedIn en Redis |
| `models.py` | Modelos Pydantic para validación de datos |
| `config.py` | Configuración centralizada (Redis, LinkedIn, Playwright) |

---

## 🚀 Despliegue en EasyPanel

```bash
# 1. Clonar el proyecto
git clone https://github.com/santiago96ml/envi-de-audios-.git

# 2. Levantar todos los servicios
docker-compose up --build -d

# 3. Verificar que todo funciona
curl http://TU_SERVIDOR:5000/health \
  -H "X-API-KEY: stark_secure_token_2024_linkedin_bot"
```

---

## 🍪 Importar Cookies de LinkedIn (Primer Uso)

**Automático (si ya tienes `session_data/linkedin_state.json`):**
El worker detecta el archivo al arrancar y migra las cookies automáticamente a Redis como la cuenta `linkedin_santi_01`.

**Manual (por API):**
```bash
curl -X POST http://TU_SERVIDOR:5000/sessions/import \
  -H "X-API-KEY: stark_secure_token_2024_linkedin_bot" \
  -H "Content-Type: application/json" \
  -d '{
    "cuenta_id": "linkedin_santi_01",
    "cookies": [...]
  }'
```

---

## 📡 Endpoints de la API

### Salud del sistema
```
GET /health
```

### Encolar tarea de edición de mensaje
```
POST /tasks/edit-message
Headers: X-API-KEY: <token>
Body:
{
  "cuenta_origen_id": "linkedin_santi_01",
  "contact": "https://linkedin.com/in/usuario-objetivo",
  "old_message": "Texto a reemplazar",
  "new_message": "Nuevo texto del mensaje"
}

Respuesta (202 Accepted):
{
  "task_id": "uuid-1234-...",
  "status": "queued",
  "message": "Tarea encolada exitosamente..."
}
```

### Consultar estado de una tarea
```
GET /tasks/{task_id}/status
Headers: X-API-KEY: <token>

Respuesta:
{
  "task_id": "uuid-1234-...",
  "status": "pendiente|procesando|completado|error",
  "resultado": "...",
  "fecha_creacion": "...",
  "fecha_actualizacion": "..."
}
```

### Estado de una sesión
```
GET /sessions/{cuenta_id}/status
Headers: X-API-KEY: <token>
```

---

## 🔗 Integración con n8n

**Nodo 1 — Encolar tarea:**
- Método: `POST`
- URL: `http://TU_SERVIDOR:5000/tasks/edit-message`
- Header: `X-API-KEY: stark_secure_token_2024_linkedin_bot`
- Body: JSON con `cuenta_origen_id`, `contact`, `old_message`, `new_message`

**Nodo 2 — Polling de estado (esperar resultado):**
- Usar nodo "Wait" + "HTTP Request" con `GET /tasks/{task_id}/status`
- Hacer loop hasta que `status === "completado"` o `"error"`

---

## 💾 Consumo de RAM Estimado

| Servicio | RAM Base | RAM por Tarea |
|---|---|---|
| Redis | ~15MB | +0MB |
| FastAPI (api) | ~45MB | +0MB |
| Playwright Worker | ~250MB | +~50MB por contexto activo |
| **Total** | **~310MB** | **+~50MB/tarea** |

Con límite de `mem_limit: 1g` en el worker, el sistema puede manejar ~15 tareas simultáneas antes de alcanzar el límite.

---

## 📁 Estructura del Proyecto

```
linkedin_voice_bot/
├── api.py                  # FastAPI: endpoint REST
├── worker.py               # Playwright Worker: procesa la cola
├── session_manager.py      # Gestión de sesiones en Redis
├── models.py               # Modelos Pydantic
├── config.py               # Configuración centralizada
├── web_message_editor.py   # DEPRECADO (referencia histórica)
├── docker-compose.yml      # Redis + API + Worker
├── Dockerfile
├── requirements.txt
└── session_data/
    └── linkedin_state.json # Cookies de sesión (migradas a Redis al arrancar)
```
