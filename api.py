"""
api.py - API principal (FastAPI) del LinkedIn Voice Bot.

Este servidor es LIGERO (<50MB). Su única responsabilidad es:
  1. Validar el request y el token de seguridad.
  2. Serializar la tarea y meterla en la cola de Redis.
  3. Responder INMEDIATAMENTE con el task_id (no espera a Playwright).

El trabajo pesado lo hace el worker.py en segundo plano.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from models import (
    EditMessageRequest,
    ImportSessionRequest,
    Task,
    TaskResponse,
    TaskStatusResponse,
)
from session_manager import SessionManager

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("api")

API_TOKEN = os.getenv("API_TOKEN", "stark_secure_token_2024_linkedin_bot")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
TASK_QUEUE_KEY = "linkedin:tasks"
TASK_STATUS_PREFIX = "linkedin:task:"
TASK_TTL_SECONDS = 60 * 60 * 24 * 7  # Guardar resultados 7 días

# ==============================================================================
# ESTADO GLOBAL (conexión Redis)
# ==============================================================================

redis_client: redis.Redis | None = None
session_mgr: SessionManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejo del ciclo de vida de la app: conectar/desconectar Redis."""
    global redis_client, session_mgr
    logger.info(f"🔌 Conectando a Redis: {REDIS_URL}")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    try:
        redis_client.ping()
        logger.info("✅ Conexión a Redis establecida.")
    except redis.ConnectionError as e:
        logger.error(f"❌ No se pudo conectar a Redis: {e}")
        raise RuntimeError("Redis no disponible") from e

    session_mgr = SessionManager(redis_client)
    yield
    # Shutdown
    redis_client.close()
    logger.info("🔌 Conexión a Redis cerrada.")


# ==============================================================================
# APP FASTAPI
# ==============================================================================

app = FastAPI(
    title="LinkedIn Voice Bot API",
    description="API para encolar tareas de automatización de LinkedIn vía Playwright.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# DEPENDENCIAS
# ==============================================================================

def verify_api_key(x_api_key: str = Header(..., alias="X-API-KEY")):
    """Dependencia de seguridad: valida el token de la cabecera."""
    if x_api_key != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token API inválido o ausente."
        )


def get_redis() -> redis.Redis:
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis no disponible")
    return redis_client


def get_session_manager() -> SessionManager:
    if session_mgr is None:
        raise HTTPException(status_code=503, detail="SessionManager no disponible")
    return session_mgr


# ==============================================================================
# ENDPOINTS DE SALUD
# ==============================================================================

@app.get("/health", tags=["Health"])
def health(r: redis.Redis = Depends(get_redis)):
    """Verifica que la API y Redis estén operativos."""
    try:
        r.ping()
        queue_size = r.llen(TASK_QUEUE_KEY)
        return {
            "status": "ok",
            "message": "LinkedIn Bot API v2.0 is running",
            "redis": "connected",
            "queue_size": queue_size,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis error: {e}")


# ==============================================================================
# ENDPOINTS DE TAREAS
# ==============================================================================

@app.post(
    "/tasks/edit-message",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Tasks"],
    dependencies=[Depends(verify_api_key)],
)
def enqueue_edit_message(
    body: EditMessageRequest,
    r: redis.Redis = Depends(get_redis),
    mgr: SessionManager = Depends(get_session_manager),
):
    """
    Encola una tarea de edición de mensaje de LinkedIn.
    Responde inmediatamente con un task_id para hacer polling posterior.
    """
    # Verificar que la sesión de la cuenta existe
    if not mgr.session_exists(body.cuenta_origen_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontraron cookies para la cuenta '{body.cuenta_origen_id}'. "
                   f"Usa POST /sessions/import primero."
        )

    # Construir la tarea
    task = Task(
        cuenta_origen_id=body.cuenta_origen_id,
        perfil_destino_url=body.contact,
        mensaje_viejo=body.old_message,
        mensaje_nuevo=body.new_message,
        estado="pendiente",
    )

    # Serializar y pushear a la cola (LPUSH para que BLPOP en el worker la tome)
    task_json = task.model_dump_json()
    r.lpush(TASK_QUEUE_KEY, task_json)

    # Guardar estado inicial para polling
    r.set(
        f"{TASK_STATUS_PREFIX}{task.task_id}",
        task_json,
        ex=TASK_TTL_SECONDS,
    )

    logger.info(
        f"📥 Tarea encolada: {task.task_id} | "
        f"Cuenta: {body.cuenta_origen_id} | "
        f"Destino: {body.contact[:50]}..."
    )

    return TaskResponse(
        task_id=task.task_id,
        status="queued",
        message="Tarea encolada exitosamente. Usa GET /tasks/{task_id}/status para seguimiento.",
    )


@app.get(
    "/tasks/{task_id}/status",
    response_model=TaskStatusResponse,
    tags=["Tasks"],
    dependencies=[Depends(verify_api_key)],
)
def get_task_status(task_id: str, r: redis.Redis = Depends(get_redis)):
    """Consulta el estado actual de una tarea por su ID."""
    data = r.get(f"{TASK_STATUS_PREFIX}{task_id}")
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tarea '{task_id}' no encontrada o expirada."
        )

    task = Task.model_validate_json(data)
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.estado,
        resultado=task.resultado,
        fecha_creacion=task.fecha_creacion,
        fecha_actualizacion=task.fecha_actualizacion,
    )


# ==============================================================================
# ENDPOINTS DE SESIONES
# ==============================================================================

@app.post(
    "/sessions/import",
    tags=["Sessions"],
    dependencies=[Depends(verify_api_key)],
)
def import_session(
    body: ImportSessionRequest,
    mgr: SessionManager = Depends(get_session_manager),
):
    """
    Importa cookies de una sesión de LinkedIn a Redis.
    Úsalo para registrar nuevas cuentas o refrescar cookies expiradas.
    """
    cookies_list = [c.model_dump() for c in body.cookies]
    success = mgr.save_session(body.cuenta_id, cookies_list)

    if not success:
        raise HTTPException(status_code=500, detail="Error guardando la sesión en Redis.")

    return {
        "status": "ok",
        "message": f"Sesión importada para cuenta '{body.cuenta_id}'",
        "total_cookies": len(body.cookies),
    }


@app.get(
    "/sessions/{cuenta_id}/status",
    tags=["Sessions"],
    dependencies=[Depends(verify_api_key)],
)
def get_session_status(
    cuenta_id: str,
    mgr: SessionManager = Depends(get_session_manager),
):
    """Retorna el estado de la sesión de una cuenta (activa/expirada/no encontrada)."""
    return mgr.get_session_status(cuenta_id)


# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

if __name__ == "__main__":
    logger.info("🚀 Iniciando LinkedIn Bot API v2.0...")
    uvicorn.run("api:app", host="0.0.0.0", port=5000, reload=False)
