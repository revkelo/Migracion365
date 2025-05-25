import os
import io
import pickle
import logging
import sys
import json
from pathlib import Path
from cryptography.fernet import Fernet
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from docx import Document
from config import GOOGLE_SCOPES, GOOGLE_EXPORT_FORMATS
from utils import sanitize_filename

# —► Tu llave Fernet
KEY = b"HG5GHGW3o9bMUMWUmz7khGjhELzFUJ9W-52s_ZnIC40="


def _load_encrypted_blob(filename: str = 'credentials.json.enc') -> bytes:
    # Si estamos en un EXE creado con PyInstaller, los datos van a sys._MEIPASS
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_path, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No encontré el archivo cifrado en {path}")
    with open(path, 'rb') as f:
        return f.read()


def _load_credentials(filename: str = 'credentials.json.enc') -> dict:
    blob = _load_encrypted_blob(filename)
    f = Fernet(KEY)
    plaintext = f.decrypt(blob)
    return json.loads(plaintext)


class GoogleService:
    """
    Servicio para interactuar con Google Drive y Formularios,
    usando credenciales cifradas con Fernet.
    """
    def __init__(self,
                 encrypted_credentials: str = 'credentials.json.enc',
                 token_path: str = 'token.pickle'):
        self.encrypted_credentials = encrypted_credentials
        self.token_path = token_path
        self.drive = None
        self.forms = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_services()

    def _setup_services(self):
        creds = None
        # Carga token anterior si existe
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as token_file:
                    creds = pickle.load(token_file)
                    self.logger.info("Token cargado desde %s", self.token_path)
            except Exception:
                self.logger.warning("No se pudo cargar el token, se generará uno nuevo")
                creds = None

        # Refrescar o autenticar de cero
        if not creds or not getattr(creds, 'valid', False):
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.logger.info("Credenciales refrescadas automáticamente")
            else:
                # Carga credenciales cifradas
                config = _load_credentials(self.encrypted_credentials)
                flow = InstalledAppFlow.from_client_config(
                    {'installed': config['installed']},
                    scopes=GOOGLE_SCOPES
                )
                creds = flow.run_local_server(port=8089)
                self.logger.info("Autenticación completada con credenciales cifradas")
            # Guarda el token de acceso
            with open(self.token_path, 'wb') as token_file:
                pickle.dump(creds, token_file)
                self.logger.info("Token guardado en %s", self.token_path)

        # Inicializa APIs
        self.drive = build('drive', 'v3', credentials=creds)
        self.forms = build('forms', 'v1', credentials=creds)
        self.logger.info("APIs de Drive y Forms listas para usarse")

    def list_files_and_folders(self):
        """Lista carpetas, archivos y tamaño total en Drive."""
        folders, files = {}, {}
        page_token = None
        total_size = 0
        while True:
            res = self.drive.files().list(
                q="trashed = false",
                fields="nextPageToken, files(id, name, mimeType, parents, size, modifiedTime)",
                pageSize=1000,
                pageToken=page_token
            ).execute()
            for item in res.get('files', []):
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    folders[item['id']] = item
                else:
                    files[item['id']] = item
                    total_size += int(item.get('size', 0) or 0)
            page_token = res.get('nextPageToken')
            if not page_token:
                break
        return folders, files, total_size

    def get_folder_path(self, parent_id: str, folders: dict) -> list:
        """Reconstruye ruta de carpetas recursivamente."""
        path, current = [], parent_id
        while current in folders:
            folder = folders[current]
            path.append(sanitize_filename(folder['name']))
            parents = folder.get('parents') or []
            current = parents[0] if parents else None
        return list(reversed(path))

    def download_file(self, file_info: dict):
        """Descarga o exporta un archivo de Drive según su tipo."""
        file_id = file_info['id']
        mime = file_info['mimeType']
        name = file_info['name']
        try:
            if mime in GOOGLE_EXPORT_FORMATS:
                exp = GOOGLE_EXPORT_FORMATS[mime]
                if mime == 'application/vnd.google-apps.form':
                    form_data = self.forms.forms().get(formId=file_id).execute()
                    return self._create_word_from_form(form_data), f"{sanitize_filename(name)}_form.docx"
                req = self.drive.files().export_media(fileId=file_id, mimeType=exp['mime'])
            else:
                req = self.drive.files().get_media(fileId=file_id)

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, req)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            fh.seek(0)
            ext = exp['ext'] if mime in GOOGLE_EXPORT_FORMATS else None
            filename = f"{sanitize_filename(name)}.{ext}" if ext else sanitize_filename(name)
            return fh, filename

        except Exception as e:
            self.logger.error("Error al descargar %s: %s", name, e)
            return None, name

    def _create_word_from_form(self, form_data: dict) -> io.BytesIO:
        """Convierte un formulario de Google a un documento Word."""
        doc = Document()
        info = form_data.get('info', {})
        doc.add_heading(info.get('title', 'Formulario'), level=0)
        if info.get('description'):
            doc.add_paragraph(info['description'])
            doc.add_paragraph()

        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        for i, item in enumerate(form_data.get('items', []), start=1):
            q = item.get('title', f'Pregunta {i}')
            doc.add_paragraph(f"{i}. {q}", style='Heading 2')
            question = item.get('questionItem', {}).get('question', {})
            if 'choiceQuestion' in question:
                for j, opt in enumerate(question['choiceQuestion'].get('options', [])):
                    prefix = letters[j] if j < len(letters) else str(j+1)
                    doc.add_paragraph(f"    {prefix}. {opt.get('value', 'Opción')}")
            elif 'textQuestion' in question:
                para = question['textQuestion'].get('paragraph', False)
                placeholder = '[Respuesta de texto largo]' if para else '[Respuesta de texto corto]'
                doc.add_paragraph(f"    {placeholder}")
            doc.add_paragraph()

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf