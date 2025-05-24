import io
import os
import requests
import msal
import logging
from typing import Callable, Optional

from config import (
    ONEDRIVE_CLIENT_ID,
    ONEDRIVE_AUTHORITY,
    ONEDRIVE_SCOPES,
    CHUNK_SIZE,
    LARGE_FILE_THRESHOLD,
    LOG_FILE
)
from utils import sanitize_filename

class OneDriveService:
    def __init__(self):
        self.token = None
        self.logger = logging.getLogger("OneDriveService")
        self._configure_logger()
        self.authenticate()

    def _configure_logger(self):
        # Configura logger para consola y archivo sin duplicar mensajes
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            fmt = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")
            ch = logging.StreamHandler()
            ch.setFormatter(fmt)
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setFormatter(fmt)
            self.logger.addHandler(ch)
            self.logger.addHandler(fh)

    def authenticate(self):
        app = msal.PublicClientApplication(
            client_id=ONEDRIVE_CLIENT_ID,
            authority=ONEDRIVE_AUTHORITY
        )
        # Forzar siempre login limpio
        for acct in app.get_accounts():
            app.remove_account(acct)

        result = app.acquire_token_interactive(
            scopes=ONEDRIVE_SCOPES,
            prompt="select_account"
        )
        if "access_token" in result:
            self.token = result["access_token"]
            self.logger.info("Token de OneDrive obtenido")
        else:
            error = result.get("error_description", "desconocido")
            raise RuntimeError(f"Error obteniendo token de OneDrive: {error}")

    def create_folder(self, path: str) -> bool:
        """
        Crea de forma iterativa la estructura de carpetas en OneDrive.
        """
        if not path.strip():
            return True

        headers = {"Authorization": f"Bearer {self.token}"}
        parts = path.strip("/").split("/")
        for idx, part in enumerate(parts):
            subpath = "/".join(parts[: idx + 1]).strip("/")
            check_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{subpath}"
            if requests.get(check_url, headers=headers).status_code == 404:
                parent = "/".join(parts[:idx]).strip("/")
                create_url = (
                    f"https://graph.microsoft.com/v1.0/me/drive/root:/{parent}:/children"
                    if parent
                    else "https://graph.microsoft.com/v1.0/me/drive/root/children"
                )
                data = {
                    "name": part,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "rename"
                }
                resp = requests.post(create_url, headers=headers, json=data)
                if resp.status_code not in (200, 201):
                    self.logger.error(f"Error creando carpeta “{part}”: {resp.text}")
                    return False
        return True

    def create_upload_session(self, remote_path: str) -> str:
        """
        Inicia una sesión de subida resumable.
        Devuelve la URL temporal para cargar los trozos.
        """
        url = (
            f"https://graph.microsoft.com/v1.0/me/drive/root:/{remote_path}"
            ":/createUploadSession"
        )
        headers = {"Authorization": f"Bearer {self.token}"}
        body = {"item": {"@microsoft.graph.conflictBehavior": "replace"}}
        resp = requests.post(url, json=body, headers=headers)
        resp.raise_for_status()
        session = resp.json()
        return session["uploadUrl"]

    def upload(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        size: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        """
        Elige entre upload pequeño o grande según el umbral.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        filename = sanitize_filename(os.path.basename(remote_path))

        if size > LARGE_FILE_THRESHOLD:
            return self._upload_large(file_data, remote_path, headers, size, progress_callback)
        else:
            if progress_callback:
                progress_callback(size, size, filename)
            return self._upload_small(file_data, remote_path, headers)

    def _upload_small(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        headers: dict
    ) -> bool:
        headers = headers.copy()
        headers["Content-Type"] = "application/octet-stream"
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{remote_path}:/content"
        resp = requests.put(url, headers=headers, data=file_data.read())
        return resp.status_code in (200, 201)

    def _upload_large(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        headers: dict,
        size: int,
        progress_callback: Optional[Callable[[int, int, str], None]]
    ) -> bool:
        upload_url = self.create_upload_session(remote_path)

        file_data.seek(0)
        bytes_sent = 0
        filename = sanitize_filename(os.path.basename(remote_path))

        while bytes_sent < size:
            end = min(bytes_sent + CHUNK_SIZE - 1, size - 1)
            chunk = file_data.read(end - bytes_sent + 1)

            chunk_headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {bytes_sent}-{end}/{size}"
            }
            resp = requests.put(upload_url, headers=chunk_headers, data=chunk)
            if resp.status_code not in (200, 201, 202):
                self.logger.error(f"Error subiendo fragmento: {resp.text}")
                return False

            bytes_sent = end + 1
            if progress_callback:
                progress_callback(bytes_sent, size, filename)

        return True
