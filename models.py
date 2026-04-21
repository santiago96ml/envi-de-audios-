"""
models.py - Modelos de datos (Pydantic) para la API y el Worker.

Define la estructura de los mensajes que viajan por la cola de Redis y
la estructura de las sesiones (cookies) de LinkedIn.
"""

from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field
import uuid


# ==============================================================================
# MODELOS DE TAREA (lo que viaja por la cola de Redis)
# ==============================================================================

class EditMessageRequest(BaseModel):
    """Cuerpo del request HTTP para editar un mensaje."""
    cuenta_origen_id: str = Field(
        default="linkedin_santi_01",
        description="ID de la cuenta de LinkedIn a usar (debe tener cookies guardadas)"
    )
    contact: str = Field(
        ...,
        description="URL del perfil de LinkedIn o nombre del contacto"
    )
    old_message: str = Field(
        ...,
        description="Texto del mensaje original a buscar en el chat"
    )
    new_message: str = Field(
        ...,
        description="Nuevo texto con el que se reemplazará el mensaje"
    )


class Task(BaseModel):
    """Estructura completa de una tarea que viaja por la cola de Redis."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cuenta_origen_id: str
    perfil_destino_url: str  # contact
    mensaje_viejo: str       # old_message
    mensaje_nuevo: str       # new_message
    estado: Literal["pendiente", "procesando", "completado", "error"] = "pendiente"
    resultado: Optional[str] = None
    fecha_creacion: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    fecha_actualizacion: Optional[str] = None


class TaskResponse(BaseModel):
    """Respuesta HTTP al encolar una tarea."""
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Respuesta HTTP al consultar el estado de una tarea."""
    task_id: str
    status: str
    resultado: Optional[str] = None
    fecha_creacion: Optional[str] = None
    fecha_actualizacion: Optional[str] = None


# ==============================================================================
# MODELOS DE SESIÓN (cookies de LinkedIn en Redis)
# ==============================================================================

class Cookie(BaseModel):
    """Una cookie individual de LinkedIn."""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: Optional[float] = None
    httpOnly: bool = False
    secure: bool = True
    sameSite: Optional[str] = None


class LinkedInSession(BaseModel):
    """Sesión de LinkedIn (conjunto de cookies guardadas en Redis)."""
    cuenta_origen_id: str
    cookies: list[Cookie]
    ultima_actualizacion: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    estado_sesion: Literal["activa", "expirada"] = "activa"


class ImportSessionRequest(BaseModel):
    """Request para importar cookies de una cuenta."""
    cuenta_id: str = Field(
        default="linkedin_santi_01",
        description="ID único para identificar esta cuenta de LinkedIn"
    )
    cookies: list[Cookie] = Field(
        ...,
        description="Lista de cookies exportadas desde el navegador"
    )
