import os
import sys
import json
from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ---------------------------------------------------------------
# Configuración de cifrado y OAuth2
# ---------------------------------------------------------------
KEY = b"HG5GHGW3o9bMUMWUmz7khGjhELzFUJ9W-52s_ZnIC40="
ENC_CRED_FILE = 'credentials.json.enc'
TOKEN_FILE    = 'token.json'
SCOPES        = ['https://www.googleapis.com/auth/drive']

def _load_encrypted_blob(filename: str = ENC_CRED_FILE) -> bytes:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No encontré el archivo cifrado en {path}")
    with open(path, 'rb') as f:
        return f.read()

def _load_credentials(filename: str = ENC_CRED_FILE) -> dict:
    blob = _load_encrypted_blob(filename)
    f = Fernet(KEY)
    plaintext = f.decrypt(blob)
    return json.loads(plaintext)

def obtener_credenciales() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            config = _load_credentials(ENC_CRED_FILE)
            flow = InstalledAppFlow.from_client_config(config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
    return creds

# ---------------------------------------------------------------
# Funciones para listar unidades, permisos y contenido
# ---------------------------------------------------------------
def listar_unidades_compartidas(service):
    drives = []
    page_token = None
    while True:
        resp = service.drives().list(
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken, drives(id, name)"
        ).execute()
        drives.extend(resp.get('drives', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return drives

def listar_permisos(service, drive_id):
    perms = []
    page_token = None
    while True:
        resp = service.permissions().list(
            fileId=drive_id,
            supportsAllDrives=True,
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken, permissions(id, type, role, emailAddress, domain)"
        ).execute()
        perms.extend(resp.get('permissions', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return perms

def listar_contenido_drive(service, drive_id):
    items = []
    page_token = None
    while True:
        resp = service.files().list(
            corpora='drive',
            driveId=drive_id,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            q="trashed = false",
            pageSize=1000,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        items.extend(resp.get('files', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return items

# ---------------------------------------------------------------
# Ejecución principal
# ---------------------------------------------------------------
if __name__ == '__main__':
    creds   = obtener_credenciales()
    drive_svc = build('drive', 'v3', credentials=creds)

    unidades = listar_unidades_compartidas(drive_svc)
    if not unidades:
        print("No se encontraron Unidades compartidas.")
        sys.exit(0)

    for d in unidades:
        print(f"\n=== Unidad Compartida: {d['name']} (ID: {d['id']}) ===")

        # Listar quiénes tienen acceso
        permisos = listar_permisos(drive_svc, d['id'])
        print("Permisos de acceso:")
        for p in permisos:
            who = p.get('emailAddress') or p.get('domain') or p['type']
            print(f"  - {p['role']} ➜ {who} (type={p['type']})")

        # Listar contenido dentro de la unidad
        contenido = listar_contenido_drive(drive_svc, d['id'])
        print(f"\nContenido ({len(contenido)} items):")
        for item in contenido:
            print(f"  • {item['name']} [{item['mimeType']}] (ID: {item['id']})")
