import io
import requests
import msal
import logging
import os
from config import ONEDRIVE_CLIENT_ID, ONEDRIVE_AUTHORITY, ONEDRIVE_SCOPES, CHUNK_SIZE, LARGE_FILE_THRESHOLD
from utils import sanitize_filename
from typing import Callable, Optional


class OneDriveService:
    def __init__(self):
        self.token = None
        self.logger = logging.getLogger('OneDriveService')
        self.authenticate()

    def authenticate(self):
        app = msal.PublicClientApplication(client_id=ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY)
        for acct in app.get_accounts():
            app.remove_account(acct)
        result = app.acquire_token_interactive(scopes=ONEDRIVE_SCOPES, prompt="select_account")
        if 'access_token' in result:
            self.token = result['access_token']
            self.logger.info("Token de OneDrive obtenido")
        else:
            raise Exception(f"Error obteniendo token: {result.get('error_description')}")

    def create_folder(self, path: str) -> bool:
        if not path.strip():
            return True
        headers = {"Authorization": f"Bearer {self.token}"}
        parts = path.strip('/').split('/')
        for idx, part in enumerate(parts):
            subpath = '/'.join(parts[:idx+1]).strip('/')
            check_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{subpath}"
            if requests.get(check_url, headers=headers).status_code == 404:
                parent = '/'.join(parts[:idx]).strip('/')
                create_url = (f"https://graph.microsoft.com/v1.0/me/drive/root:/{parent}:/children" if parent else
                              "https://graph.microsoft.com/v1.0/me/drive/root/children")
                data = {"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
                resp = requests.post(create_url, headers=headers, json=data)
                if resp.status_code not in (200, 201):
                    self.logger.error(f"Error creando carpeta {part}: {resp.text}")
                    return False
        return True

    def upload(
        self,
        file_data: io.BytesIO,
        remote_path: str,
        size: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> bool:
        headers = {"Authorization": f"Bearer {self.token}"}
        if size > LARGE_FILE_THRESHOLD:
            return self._upload_large(file_data, remote_path, headers, size, progress_callback)
        else:
            # pequeño: callback único al 100%
            if progress_callback:
                progress_callback(size, size, os.path.basename(remote_path))
            return self._upload_small(file_data, remote_path, headers)

    def _upload_small(self, file_data: io.BytesIO, remote_path: str, headers: dict) -> bool:
        headers = headers.copy()
        headers['Content-Type'] = 'application/octet-stream'
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
        session_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{remote_path}:/createUploadSession"
        session_resp = requests.post(session_url, headers=headers, json={"item":{"@microsoft.graph.conflictBehavior":"replace"}})
        if session_resp.status_code != 200:
            self.logger.error(f"Error creando sesión de upload: {session_resp.text}")
            return False
        upload_url = session_resp.json().get('uploadUrl')
        file_data.seek(0)
        start = 0
        while start < size:
            end = min(start + CHUNK_SIZE - 1, size - 1)
            chunk = file_data.read(end - start + 1)
            chunk_headers = {"Content-Length": str(len(chunk)), "Content-Range": f"bytes {start}-{end}/{size}"}
            resp = requests.put(upload_url, headers=chunk_headers, data=chunk)
            if resp.status_code not in (200, 201, 202):
                self.logger.error(f"Error subiendo fragmento: {resp.text}")
                return False
            start = end + 1
            if progress_callback:
                progress_callback(start, size, os.path.basename(remote_path))
        return True