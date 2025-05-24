import io
import requests
import msal
import logging
from config import ONEDRIVE_CLIENT_ID, ONEDRIVE_AUTHORITY, ONEDRIVE_SCOPES, CHUNK_SIZE, LARGE_FILE_THRESHOLD
from utils import sanitize_filename

class OneDriveService:
    def __init__(self):
        """Inicializa la clase y autentica con OneDrive."""
        self.token = None
        self.logger = logging.getLogger('OneDriveService')
        self.authenticate()

    def authenticate(self):
        """Autentica con MSAL y obtiene un token de acceso a OneDrive."""
        app = msal.PublicClientApplication(
            client_id=ONEDRIVE_CLIENT_ID,
            authority=ONEDRIVE_AUTHORITY
        )
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
            error = result.get('error_description', str(result))
            raise Exception(f"Error obteniendo token de OneDrive: {error}")

    def create_folder(self, path: str) -> bool:
        """Crea recursivamente la estructura de carpetas en OneDrive."""
        if not path.strip():
            return True
        headers = {"Authorization": f"Bearer {self.token}"}
        parts = path.strip('/').split('/')
        for idx, part in enumerate(parts):
            subpath = '/'.join(parts[:idx+1]).strip('/')
            url_check = f"https://graph.microsoft.com/v1.0/me/drive/root:/{subpath}"
            response = requests.get(url_check, headers=headers)
            if response.status_code == 404:
                if idx > 0:
                    parent_path = '/'.join(parts[:idx]).strip('/')
                    url_create = f"https://graph.microsoft.com/v1.0/me/drive/root:/{parent_path}:/children"
                else:
                    url_create = "https://graph.microsoft.com/v1.0/me/drive/root/children"
                folder_data = {
                    "name": part,
                    "folder": {},
                    "@microsoft.graph.conflictBehavior": "rename"
                }
                create_resp = requests.post(url_create, headers=headers, json=folder_data)
                if create_resp.status_code not in (200, 201):
                    self.logger.error(f"Error creando carpeta '{part}': {create_resp.text}")
                    return False
        return True

    def upload(self, file_io: io.BytesIO, remote_path: str, size: int) -> bool:
        """Sube un archivo a OneDrive, eligiendo carga pequeña o fragmentada según el tamaño."""
        headers = {"Authorization": f"Bearer {self.token}"}
        if size > LARGE_FILE_THRESHOLD:
            return self._upload_large(file_io, remote_path, headers, size)
        return self._upload_small(file_io, remote_path, headers)

    def _upload_small(self, file_data: io.BytesIO, remote_path: str, headers: dict) -> bool:
        """Carga directa para archivos pequeños (< umbral)."""
        upload_headers = headers.copy()
        upload_headers["Content-Type"] = "application/octet-stream"
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{remote_path}:/content"
        response = requests.put(url, headers=upload_headers, data=file_data.read())
        return response.status_code in (200, 201)

    def _upload_large(self, file_data: io.BytesIO, remote_path: str, headers: dict, size: int) -> bool:
        """Carga fragmentada para archivos grandes usando Upload Session."""
        session_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{remote_path}:/createUploadSession"
        session_payload = {"item": {"@microsoft.graph.conflictBehavior": "replace"}}
        session_resp = requests.post(session_url, headers=headers, json=session_payload)
        if session_resp.status_code != 200:
            self.logger.error(f"Error creando sesión de upload: {session_resp.text}")
            return False
        upload_url = session_resp.json().get("uploadUrl")
        file_data.seek(0)
        start = 0
        while start < size:
            end = min(start + CHUNK_SIZE - 1, size - 1)
            chunk = file_data.read(end - start + 1)
            chunk_headers = {
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{size}"
            }
            chunk_resp = requests.put(upload_url, headers=chunk_headers, data=chunk)
            if chunk_resp.status_code not in (200, 201, 202):
                self.logger.error(f"Error subiendo fragmento: {chunk_resp.text}")
                return False
            start = end + 1
        return True