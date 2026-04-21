"""
session_manager.py - Gestión de sesiones (cookies) de LinkedIn en Redis.

Responsabilidades:
- Guardar y recuperar cookies de cuentas de LinkedIn en/desde Redis.
- Migrar automáticamente el archivo session_storage.json existente.
- Verificar el estado de expiración de las cookies.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import redis as redis_lib

from models import LinkedInSession, Cookie

logger = logging.getLogger(__name__)

# Prefijo de claves en Redis para sesiones
SESSION_KEY_PREFIX = "linkedin:sessions:"


class SessionManager:
    def __init__(self, redis_client: redis_lib.Redis):
        self.redis = redis_client

    def _make_key(self, cuenta_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}{cuenta_id}"

    # ------------------------------------------------------------------
    # CRUD de sesiones
    # ------------------------------------------------------------------

    def save_session(self, cuenta_id: str, cookies: list[dict]) -> bool:
        """Guarda/Actualiza las cookies de una cuenta en Redis."""
        try:
            session = LinkedInSession(
                cuenta_origen_id=cuenta_id,
                cookies=cookies,
                ultima_actualizacion=datetime.now(timezone.utc).isoformat(),
                estado_sesion="activa"
            )
            self.redis.set(
                self._make_key(cuenta_id),
                session.model_dump_json(),
                ex=60 * 60 * 24 * 60  # TTL: 60 días
            )
            logger.info(f"✅ Sesión guardada para cuenta '{cuenta_id}' ({len(cookies)} cookies)")
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando sesión para '{cuenta_id}': {e}")
            return False

    def get_session(self, cuenta_id: str) -> Optional[LinkedInSession]:
        """Recupera la sesión de una cuenta desde Redis."""
        data = self.redis.get(self._make_key(cuenta_id))
        if not data:
            logger.warning(f"⚠️ No se encontró sesión para cuenta '{cuenta_id}'")
            return None
        return LinkedInSession.model_validate_json(data)

    def get_cookies_for_playwright(self, cuenta_id: str) -> Optional[list[dict]]:
        """
        Retorna las cookies en el formato que Playwright espera para
        context.add_cookies(). Filtra cookies con dominio inválido.
        """
        session = self.get_session(cuenta_id)
        if not session:
            return None

        playwright_cookies = []
        for c in session.cookies:
            cookie_dict = {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "httpOnly": c.httpOnly,
                "secure": c.secure,
            }
            # Playwright sólo acepta sameSite: "Strict" | "Lax" | "None"
            if c.sameSite in ("Strict", "Lax", "None"):
                cookie_dict["sameSite"] = c.sameSite

            # Corregir expires: Playwright espera float o -1, no None
            if c.expires and c.expires > 0:
                cookie_dict["expires"] = c.expires

            playwright_cookies.append(cookie_dict)

        return playwright_cookies

    def mark_expired(self, cuenta_id: str):
        """Marca una sesión como expirada (ej. tras un error 401 en LinkedIn)."""
        session = self.get_session(cuenta_id)
        if session:
            session.estado_sesion = "expirada"
            self.redis.set(self._make_key(cuenta_id), session.model_dump_json())
            logger.warning(f"⚠️ Sesión '{cuenta_id}' marcada como expirada")

    def session_exists(self, cuenta_id: str) -> bool:
        return self.redis.exists(self._make_key(cuenta_id)) > 0

    def get_session_status(self, cuenta_id: str) -> dict:
        session = self.get_session(cuenta_id)
        if not session:
            return {"cuenta_id": cuenta_id, "estado": "no_encontrada"}
        return {
            "cuenta_id": cuenta_id,
            "estado": session.estado_sesion,
            "ultima_actualizacion": session.ultima_actualizacion,
            "total_cookies": len(session.cookies)
        }

    # ------------------------------------------------------------------
    # Migración desde archivo JSON local
    # ------------------------------------------------------------------

    def migrate_from_file(
        self,
        json_path: str | Path,
        cuenta_id: str = "linkedin_santi_01"
    ) -> bool:
        """
        Migra las cookies del archivo session_storage.json al redis.
        Se ejecuta automáticamente al iniciar el worker si la cuenta no existe.
        """
        path = Path(json_path)
        if not path.exists():
            logger.info(f"ℹ️ No existe {path.name}, nada que migrar.")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_cookies = data.get("cookies", [])
            if not raw_cookies:
                logger.warning(f"⚠️ {path.name} no contiene cookies.")
                return False

            # Filtrar cookies con dominio inválido para linkedin.com
            valid_cookies = []
            for c in raw_cookies:
                domain = c.get("domain", "")
                # Conservar sólo cookies relevantes de LinkedIn
                if "linkedin" in domain or "protechts" in domain:
                    valid_cookies.append(c)

            success = self.save_session(cuenta_id, valid_cookies)
            if success:
                logger.info(
                    f"🔄 Migración completada: {len(valid_cookies)} cookies de "
                    f"'{path.name}' → Redis como '{cuenta_id}'"
                )
            return success

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"❌ Error leyendo {path.name} para migración: {e}")
            return False
