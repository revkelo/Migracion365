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
KEY           = b"HG5GHGW3o9bMUMWUmz7khGjhELzFUJ9W-52s_ZnIC40="
ENC_CRED_FILE = 'credentials.json.enc'
TOKEN_FILE    = 'token.json'
SCOPES        = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.activity.readonly'
]

def _load_encrypted_blob(filename: str = ENC_CRED_FILE) -> bytes:
    """Carga el blob cifrado (compatible con PyInstaller)."""
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
    """Descifra el blob y retorna el JSON de credenciales OAuth2."""
    blob = _load_encrypted_blob(filename)
    f = Fernet(KEY)
    plaintext = f.decrypt(blob)
    return json.loads(plaintext)

def obtener_credenciales() -> Credentials:
    """Carga o genera credenciales OAuth2 y las guarda en TOKEN_FILE."""
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
# Funciones para Shared Drives, permisos, contenido y creador
# ---------------------------------------------------------------
def listar_unidades_compartidas(drive_svc):
    drives = []
    page_token = None
    while True:
        resp = drive_svc.drives().list(
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken, drives(id, name)"
        ).execute()
        drives.extend(resp.get('drives', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return drives

def listar_permisos(drive_svc, drive_id):
    perms = []
    page_token = None
    while True:
        resp = drive_svc.permissions().list(
            fileId=drive_id,
            supportsAllDrives=True,
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken, permissions(type, role, emailAddress, domain)"
        ).execute()
        perms.extend(resp.get('permissions', []))
        page_token = resp.get('nextPageToken')
        if not page_token:
            break
    return perms

def listar_contenido_drive(drive_svc, drive_id):
    items = []
    page_token = None
    while True:
        resp = drive_svc.files().list(
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

def obtener_creador_unidad(activity_svc, drive_id):
    """
    Usa la Drive Activity API para obtener el creador original
    de la Shared Drive especificada.
    """
    query_body = {
        "ancestorName": f"items/{drive_id}",
        "filter": "detail.action_detail_case:CREATE",
        "pageSize": 1
    }
    resp = activity_svc.activity().query(body=query_body).execute()
    activities = resp.get("activities", [])
    if not activities:
        return "Desconocido"
    actor = activities[0]["actors"][0].get("user", {})
    if "knownUser" in actor:
        return actor["knownUser"].get("knownUser", {}).get("personName", "Desconocido")
    elif "anonymous" in actor:
        return "Anónimo"
    else:
        return actor.get("system", {}).get("system", "Sistema")

# ---------------------------------------------------------------
# Ejecución principal
# ---------------------------------------------------------------
if __name__ == '__main__':
    # Borra token antiguo para renovar permisos si cambiaste scopes
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

    creds        = obtener_credenciales()
    drive_svc    = build('drive', 'v3', credentials=creds)
    activity_svc = build('driveactivity', 'v2', credentials=creds)

    unidades = listar_unidades_compartidas(drive_svc)
    if not unidades:
        print("No se encontraron Unidades compartidas.")
        sys.exit(0)

    for d in unidades:
        print(f"\n=== Unidad Compartida: {d['name']} (ID: {d['id']}) ===")
        print("Creada por:", obtener_creador_unidad(activity_svc, d['id']))

        permisos = listar_permisos(drive_svc, d['id'])
        print("Permisos de acceso:")
        for p in permisos:
            who = p.get('emailAddress') or p.get('domain') or p['type']
            print(f"  - {p['role']} ➜ {who}")

        contenido = listar_contenido_drive(drive_svc, d['id'])
        print(f"\nContenido ({len(contenido)} items):")
        for item in contenido:
            print(f"  • {item['name']} [{item['mimeType']}] (ID: {item['id']})")
