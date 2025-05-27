# ---------------------------------------------------------------
# Servicio OneDrive
# Autor: Kevin Gonzalez
# Descripción:
#   Gestiona la autenticación y operaciones de carga en OneDrive
#   mediante la API de Microsoft Graph.
# ---------------------------------------------------------------

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

class OneDriveTokenExpired(Exception):
    """Excepción lanzada cuando el token de OneDrive ha expirado y requiere reautenticación."""
    pass


class OneDriveService:
    
    """
    Servicio para interactuar con OneDrive.

    - Autenticación mediante MSAL (OAuth interactivo).
    - Creación de carpetas de forma iterativa.
    - Sesiones de subida resumable para archivos grandes.
    - Subida de archivos pequeños y grandes, con callback de progreso.
    - Registro de actividad en consola y archivo de log.
    """
    
    def __init__(self):
        self.token = None
        self.logger = logging.getLogger("OneDriveService")
        self._configure_logger()
        self.authenticate()

    """
    Configura el logger para enviar mensajes a consola y a un archivo,
    evitando duplicar registros.
    """
    def _configure_logger(self):
  
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

    """
    Realiza la autenticación interactiva con MSAL, forzando
    un inicio de sesión limpio y obteniendo el token de acceso.

    - Elimina cuentas existentes para evitar cache limpio.
    - Utiliza `acquire_token_interactive` con `prompt="select_account"`.
    - Guarda el token o lanza error en caso de fallo.
    """

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

    """
        Crea de forma iterativa la estructura de carpetas en OneDrive.

        - Recorre cada parte de la ruta y comprueba existencia.
        - Si no existe, envía POST para crear la carpeta.
        - Renombra en caso de conflicto.
        - Registra errores y retorna False si falla.
     """
   
   
   
    def _handle_token_expired(self, response) -> bool:
        if response.status_code == 401:
            self.logger.warning("Token expirado. Reintentando autenticación con OneDrive.")
            try:
                # Intentamos renovar el token automáticamente
                self.authenticate()
                return True
            except Exception as e:
                # Si falla la reautenticación, informamos y propagamos la excepción específica
                self.logger.error(f"Error reautenticando OneDrive: {e}")
                raise OneDriveTokenExpired(
                    "La sesión de OneDrive ha expirado. Por favor, vuelve a iniciar sesión."
                )
        return False

   


    def create_folder(self, path: str) -> bool:

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

    """
        Inicia una sesión de subida resumable y devuelve la URL.

        - Envía POST a la ruta `/createUploadSession`.
        - Devuelve `uploadUrl` del JSON de respuesta.
    """

    def create_upload_session(self, remote_path: str) -> str:

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

    """
        Selecciona método de subida según el tamaño:

        - < LARGE_FILE_THRESHOLD: `_upload_small`.
        - >= LARGE_FILE_THRESHOLD: `_upload_large` con progreso.
    """
    def upload(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        size: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
  
        headers = {"Authorization": f"Bearer {self.token}"}
        filename = sanitize_filename(os.path.basename(remote_path))

        if size > LARGE_FILE_THRESHOLD:
            return self._upload_large(file_data, remote_path, headers, size, progress_callback)
        else:
            if progress_callback:
                progress_callback(size, size, filename)
            return self._upload_small(file_data, remote_path, headers)
        
    """
        Sube archivos pequeños en una sola petición PUT.

        - Establece `Content-Type` como `application/octet-stream`.
        - Envía todo el contenido de `file_data`.
        - Retorna True si el estado es 200 o 201.
    """
    def _upload_small(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        headers: dict
    ) -> bool:
        headers = headers.copy()
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Content-Type"] = "application/octet-stream"
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{remote_path}:/content"
        resp = requests.put(url, headers=headers, data=file_data.read())

        if self._handle_token_expired(resp):
            # Retry after reauth
            headers["Authorization"] = f"Bearer {self.token}"
            file_data.seek(0)
            resp = requests.put(url, headers=headers, data=file_data.read())

        return resp.status_code in (200, 201)



    """
        Sube archivos grandes por fragmentos usando una sesión resumable.

        - Crea sesión con `create_upload_session`.
        - Lee y sube fragmentos de tamaño CHUNK_SIZE.
        - Envía encabezados `Content-Range` con cada fragmento.
        - Invoca `progress_callback` tras cada trozo subido.
        - Retorna False y registra error si algún fragmento falla.
    """
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
                "Content-Range": f"bytes {bytes_sent}-{end}/{size}",
                "Authorization": f"Bearer {self.token}"
            }

            resp = requests.put(upload_url, headers=chunk_headers, data=chunk)

            # 🔁 Manejo de token expirado (401)
            if resp.status_code == 401:
                self.logger.warning("Token expirado. Reautenticando y reintentando fragmento...")
                self.authenticate()
                upload_url = self.create_upload_session(remote_path)  # ⚠️ necesario nuevo URL
                file_data.seek(bytes_sent)
                continue

            if resp.status_code not in (200, 201, 202):
                self.logger.error(f"Error subiendo fragmento: {resp.text}")
                return False

            bytes_sent = end + 1
            if progress_callback:
                progress_callback(bytes_sent, size, filename)

        return True

