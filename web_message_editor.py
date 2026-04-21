"""
web_message_editor.py - DEPRECADO / LEGACY

⚠️  ATENCIÓN: Este módulo ha sido refactorizado.
    La lógica de automatización de mensajes ahora vive en `worker.py`,
    como parte de la clase `LinkedInWorker._edit_message()`.

    Este archivo se conserva únicamente como referencia histórica y
    para compatibilidad con scripts externos que lo importen directamente.
    NO debe usarse en producción — usar la API REST vía `api.py`.

    Flujo recomendado:
        n8n → POST /tasks/edit-message → Redis Queue → worker.py (Playwright)

    Documentación completa: README.md
"""

import warnings
warnings.warn(
    "web_message_editor.py está deprecado. "
    "La lógica fue migrada a worker.py (clase LinkedInWorker). "
    "Usa la API REST en api.py para encolar tareas.",
    DeprecationWarning,
    stacklevel=2,
)

# ─────────────────────────────────────────────────────────────────
# Stub de compatibilidad: permite que código legacy siga importando
# WebMessageEditor sin crashear, pero lanza un error en runtime.
# ─────────────────────────────────────────────────────────────────

class WebMessageEditor:
    """
    STUB DE COMPATIBILIDAD — No usar en producción.
    Usar worker.py + api.py en su lugar.
    """

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "WebMessageEditor fue deprecado. "
            "Usa la API REST: POST /tasks/edit-message"
        )
