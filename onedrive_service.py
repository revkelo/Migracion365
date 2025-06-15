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
from utils import limpiar_archivos

class OneDriveTokenExpired(Exception):
    """Excepción lanzada cuando el token de OneDrive ha expirado y requiere reautenticación."""
    pass


"""
Servicio para interactuar con OneDrive.

- Autenticación mediante MSAL (OAuth interactivo).
- Creación de carpetas de forma iterativa.
- Sesiones de subida resumable para archivos grandes.
- Subida de archivos pequeños y grandes, con callback de progreso.
- Registro de actividad en consola y archivo de log.
"""
class OneDriveService:
    
    def __init__(self):
        self.token = None
        self.logger = logging.getLogger("OneDriveService")
        self.usuario = None
        self.url = None 
        self.configurar_logger()
        self.autenticar()

    """
    Retorna la URL que se generó para el usuario, de modo que
    desde la GUI podamos reabrirla si fue cerrada.
    """

    def obtener_url(self) -> str:

        return self.url
    
    """
    Configura el logger para enviar mensajes a consola y a un archivo,
    evitando duplicar registros.
    """
    def configurar_logger(self):
  
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

    def autenticar(self):
        app = msal.PublicClientApplication(
            client_id=ONEDRIVE_CLIENT_ID,
            authority=ONEDRIVE_AUTHORITY
        )

        for acct in app.get_accounts():
            app.remove_account(acct)
            
        
        self.url = app.get_authorization_request_url(
            scopes=ONEDRIVE_SCOPES
        )
        print(self.url)

        result = app.acquire_token_interactive(
            scopes=ONEDRIVE_SCOPES,
            prompt="select_account"
        )
        
        if "access_token" in result:
            self.token = result["access_token"]
            self.logger.info("Token de OneDrive obtenido")

            try:
                headers = {"Authorization": f"Bearer {self.token}"}
                resp = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
                resp.raise_for_status()
                self.usuario = resp.json().get("userPrincipalName", None)

            except Exception as e:
                self.usuario = None
                self.logger.error("No se pudo obtener el usuario de OneDrive: %s", e)

        else:
            error = result.get("error_description", "desconocido")
            raise RuntimeError(f"Error obteniendo token de OneDrive: {error}")

    """
    Comprueba si la respuesta HTTP indica token expirado (401).

    Si el token expiró, vuelve a llamar a authenticate() para obtener uno nuevo.

    Args:
        response (requests.Response): Respuesta de la petición anterior.

    Returns:
        bool: True si se reautenticó correctamente; False si el token no estaba expirado.
    """
   
    def token_expirado(self, response) -> bool:
        if response.status_code == 401:
            self.logger.warning("Token expirado. Reintentando autenticación con OneDrive.")
            try:

                self.autenticar()
                return True
            except Exception as e:

                self.logger.error(f"Error reautenticando OneDrive: {e}")
                raise OneDriveTokenExpired(
                    "La sesión de OneDrive ha expirado. Por favor, vuelve a iniciar sesión."
                )
        return False

    """
    Crea de forma iterativa la estructura de carpetas en OneDrive.

    - Divide 'path' en segmentos por "/".
    - Para cada segmento:
        1. Comprueba si la carpeta ya existe (GET a root:/{subpath}).
        2. Si no existe (404), envía POST a /children de su carpeta padre.
            Usa "@microsoft.graph.conflictBehavior": "rename" para evitar conflictos.
    - Registro de errores en caso de fallo.

    Args:
        path (str): Ruta completa dentro de OneDrive (p.ej., "Carpeta/Subcarpeta").

    Returns:
        bool: True si todas las carpetas se crearon (o ya existían); False si hubo error.
    """
    def crear_carpeta(self, path: str) -> bool:

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
    Inicia una sesión de subida resumable para archivos grandes.

    - Envía POST a /me/drive/root:/{remote_path}:/createUploadSession.
    - Retorna la URL de subida (uploadUrl) para fragmentar la transferencia.

    Args:
        remote_path (str): Ruta completa en OneDrive donde se guardará el archivo.

    Returns:
        str: uploadUrl proporcionada por Microsoft Graph.
    """
    def crear_de_carga(self, remote_path: str) -> str:

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
    Selecciona método de subida según el tamaño del archivo.

    - Si size > LARGE_FILE_THRESHOLD, usa _upload_large (fragmentado).
    - Si size <= LARGE_FILE_THRESHOLD, usa _upload_small (PUT simple).
    - Notifica progreso completo de archivos pequeños, si se proporciona callback.

    Args:
        file_data (io.BytesIO): Buffer con el contenido del archivo a subir.
        remote_path (str): Ruta completa en OneDrive (por ej., "Carpeta/archivo.txt").
        size (int): Tamaño del archivo en bytes.
        progress_callback (callable | None): Función (bytes_sent, total_bytes, filename).

    Returns:
        bool: True si la subida fue exitosa; False si falló.
    """
    def subir(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        size: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        overwrite: bool = False 
    ) -> bool:
  
        headers = {"Authorization": f"Bearer {self.token}"}
        filename = limpiar_archivos(os.path.basename(remote_path))



        if not overwrite:
            check_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{remote_path}"
            check_resp = requests.get(check_url, headers=headers)
            if check_resp.status_code == 200:
                self.logger.info(f"Omitido: Ya existe → {remote_path}")
                return True
            elif check_resp.status_code != 404:
                self.logger.warning(f"Error al verificar existencia de {remote_path}: {check_resp.status_code}")
                return False
            
        if size > LARGE_FILE_THRESHOLD:
            return self.subir_grande(file_data, remote_path, headers, size, progress_callback)
        else:
            if progress_callback:
                progress_callback(size, size, filename)
            return self.subir_mini(file_data, remote_path, headers)
        
    """
    Sube archivos pequeños en una sola petición PUT.

    - Establece Content-Type como application/octet-stream.
    - Usa PUT a /me/drive/root:/{remote_path}:/content.
    - Si 401 (token expirado), reautentica y reintenta.

    Args:
        file_data (io.BytesIO): Buffer con contenido del archivo.
        remote_path (str): Ruta completa en OneDrive.
        headers (dict): Headers iniciales con Authorization.

    Returns:
        bool: True si status_code es 200 o 201; False en otro caso.
    """
    def subir_mini(
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

        if self.token_expirado(resp):

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
    def subir_grande(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        headers: dict,
        size: int,
        progress_callback: Optional[Callable[[int, int, str], None]]
    ) -> bool:
        upload_url = self.crear_de_carga(remote_path)

        file_data.seek(0)
        bytes_sent = 0
        filename = limpiar_archivos(os.path.basename(remote_path))

        while bytes_sent < size:
            end = min(bytes_sent + CHUNK_SIZE - 1, size - 1)
            chunk = file_data.read(end - bytes_sent + 1)

            chunk_headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {bytes_sent}-{end}/{size}",
                "Authorization": f"Bearer {self.token}"
            }

            resp = requests.put(upload_url, headers=chunk_headers, data=chunk)

            if resp.status_code == 401:
                self.logger.warning("Token expirado. Reautenticando y reintentando fragmento...")
                self.autenticar()
                upload_url = self.crear_de_carga(remote_path)  
                file_data.seek(bytes_sent)
                continue

            if resp.status_code not in (200, 201, 202):
                self.logger.error(f"Error subiendo fragmento: {resp.text}")
                return False

            bytes_sent = end + 1
            if progress_callback:
                progress_callback(bytes_sent, size, filename)

        return True

