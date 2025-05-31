# ---------------------------------------------------------------
# Servicio Google Drive y Forms
# Autor: Kevin Gonzalez
# Descripción:
#   Gestiona la autenticación usando credenciales cifradas y permite
#   listar, descargar y exportar archivos de Google Drive y Formularios.
# ---------------------------------------------------------------

import os
import io
import pickle
import logging
import sys
import json
from pathlib import Path
import time
from cryptography.fernet import Fernet
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from docx import Document
from config import GOOGLE_SCOPES, GOOGLE_EXPORT_FORMATS
from utils import sanitize_filename

KEY = b"HG5GHGW3o9bMUMWUmz7khGjhELzFUJ9W-52s_ZnIC40="





"""
Carga el blob cifrado desde archivo.

- Si el script está congelado con PyInstaller, busca en sys._MEIPASS.
- Lanza FileNotFoundError si no existe.
- Devuelve los bytes cifrados.
"""

def _load_encrypted_blob(filename: str = 'credentials.json.enc') -> bytes:

    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_path, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No encontré el archivo cifrado en {path}")
    with open(path, 'rb') as f:
        return f.read()

"""
Descifra y carga las credenciales JSON.

- Usa Fernet con la clave KEY para descifrar.
- Parsea JSON y retorna el dict.
"""
def _load_credentials(filename: str = 'credentials.json.enc') -> dict:
    blob = _load_encrypted_blob(filename)
    f = Fernet(KEY)
    plaintext = f.decrypt(blob)
    return json.loads(plaintext)

"""
    Servicio para interactuar con Google Drive y Google Forms.

    - Autenticación y token almacenado en pickle.
    - Listado de archivos y carpetas.
    - Descarga y exportación de documentos, hojas y slides.
    - Conversión de formularios a Word.
"""
class GoogleService:

    def __init__(self,
                 encrypted_credentials: str = 'credentials.json.enc',
                 token_path: str = 'token.pickle'):
        self.encrypted_credentials = encrypted_credentials
        self.token_path = token_path
        self.drive = None
        self.usuario = None
        self.forms = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_services()

    """
    Configura credenciales y construye los clientes de API.

    - Carga o refresca token en pickle.
    - Usa credenciales cifradas si no existe token.
    - Inicializa client libraries de Drive y Forms.
    """
    def _setup_services(self):
        creds = None

        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as token_file:
                    creds = pickle.load(token_file)
                    self.logger.info("Token cargado desde %s", self.token_path)
            except Exception:
                self.logger.warning("No se pudo cargar el token, se generará uno nuevo")
                creds = None

    
        if not creds or not getattr(creds, 'valid', False):
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.logger.info("Credenciales refrescadas automáticamente")
            else:
               
                config = _load_credentials(self.encrypted_credentials)
                flow = InstalledAppFlow.from_client_config(
                    {'installed': config['installed']},
                    scopes=GOOGLE_SCOPES
                )
                creds = flow.run_local_server(port=8089)
                self.logger.info("Autenticación completada con credenciales cifradas")
          
            with open(self.token_path, 'wb') as token_file:
                pickle.dump(creds, token_file)
                self.logger.info("Token guardado en %s", self.token_path)

        self.drive = build('drive', 'v3', credentials=creds)
        self.forms = build('forms', 'v1', credentials=creds)
        self.logger.info("APIs de Drive y Forms listas para usarse")
        
        # Obtener y guardar el correo del usuario autenticado
        try:
            about = self.drive.about().get(fields="user").execute()
            self.usuario = about['user']['emailAddress']
            self.logger.info("Usuario autenticado: %s", self.usuario)
        except Exception as e:
            self.usuario = None
            self.logger.error("No se pudo obtener el usuario autenticado: %s", e)



    def rol_espanol(self, rol: str) -> str:
        equivalencias = {
            "organizer": "Administrador",
            "fileOrganizer": "Gestor de contenido",
            "writer": "Colaborador",
            "commenter": "Comentarista",
            "reader": "Lector"
        }
        return equivalencias.get(rol, "Desconocido")



    def listar_unidades_compartidas(self):
        unidades = []
        page_token = None
        while True:
            res = self.drive.drives().list(
                pageSize=100,
                pageToken=page_token,
                fields="nextPageToken, drives(id, name)"
            ).execute()
            unidades.extend(res.get("drives", []))
            page_token = res.get("nextPageToken")
            if not page_token:
                break
        return unidades



    def listar_permisos(self, file_id: str):
        permisos = []
        page_token = None
        while True:
            res = self.drive.permissions().list(
                fileId=file_id,
                supportsAllDrives=True,
                pageSize=100,
                pageToken=page_token,
                fields="nextPageToken, permissions(id, type, role, emailAddress, domain)"
            ).execute()
            permisos.extend(res.get("permissions", []))
            page_token = res.get("nextPageToken")
            if not page_token:
                break
        return permisos


    def listar_contenido_drive(self, drive_id: str):
        archivos = []
        page_token = None
        while True:
            res = self.drive.files().list(
                corpora='drive',
                driveId=drive_id,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                q="trashed = false",
                pageSize=1000,
                pageToken=page_token,
                fields="nextPageToken, files(id, name, mimeType, parents)"
            ).execute()
            archivos.extend(res.get("files", []))
            page_token = res.get("nextPageToken")
            if not page_token:
                break
        return archivos


    def obtener_usuario(self) -> str:
        """
        Obtiene el correo electrónico del usuario autenticado en Google Drive.
        """
        try:
            about = self.drive.about().get(fields="user").execute()
            return about['user']['emailAddress']
        except Exception as e:
            self.logger.error("No se pudo obtener el usuario: %s", e)
            return ""


    """
    Lista todos los archivos y carpetas en Drive.

    - Omite elementos en la papelera.
    - Retorna dicts de carpetas, archivos y tamaño total.
    """
    def list_files_and_folders(self):

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


    """
    Reconstruye el path de carpetas dado un parent_id.

    - Usa recursión basada en el dict de carpetas.
    - Sanitiza nombres para uso en archivos locales.
    """
    def get_folder_path(self, parent_id: str, folders: dict) -> list:

        path, current = [], parent_id
        while current in folders:
            folder = folders[current]
            path.append(sanitize_filename(folder['name']))
            parents = folder.get('parents') or []
            current = parents[0] if parents else None
        return list(reversed(path))
    
    """
    Descarga o exporta un archivo según su MIME.

    - Para archivos de Google Apps, exporta a formatos Office.
    - Para otros, descarga el contenido directamente.
    - Convierte Formularios a Word.
    - Devuelve un BytesIO y nombre de fichero.
    """
    def download_file(self, file_info: dict):
        file_id   = file_info['id']
        mime      = file_info['mimeType']
        name      = file_info['name']
        
        # 1) Chequear tamaño si es un Google Doc/Sheet/Slide
        if mime in GOOGLE_EXPORT_FORMATS:
            try:
                meta = self.drive.files().get(fileId=file_id, fields="size").execute()
                size_bytes = int(meta.get('size', 0) or 0)
                # Ejemplo: si supera 100MB, ya sabemos que fallará
                if size_bytes > 100 * 1024 * 1024:
                    self.last_error = Exception("exportSizeLimitExceeded")
                    return None, name
            except Exception:
                # Si no pudimos obtener size (quizá no existe), seguimos al código normal
                pass

        max_retries = 3
        attempt = 0
        while attempt < max_retries:
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
                raw = str(e).lower()
                # Si es un timeout o error 500 o SSL, reintenta
                if any(keyword in raw for keyword in ("timed out", "timeout", "500", "ssl")):
                    attempt += 1
                    backoff = 2 ** attempt
                    self.logger.warning("Reintentando descarga de '%s' (intento %d/%d) tras error: %s", name, attempt, max_retries, e)
                    time.sleep(backoff)
                    continue
                # Si es exportSizeLimitExceeded o permiso insuficiente, no reintenta
                self.logger.error("Error irreparable al descargar '%s': %s", name, e)
                self.last_error = e
                return None, name

        # Si agotó reintentos
        self.last_error = Exception("Tiempo de espera agotado tras varios intentos.")
        return None, name


        
    """
    Convierte datos de formulario a un documento Word.

    - Añade título y descripción.
    - Incluye opciones de elección o marcado de texto.
    - Guarda en un BytesIO.
    """
    def _create_word_from_form(self, form_data: dict) -> io.BytesIO:

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