import os
import sys
import json
import re
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

# ---------------------------------------------------------------
# Equivalencias de roles en español
# ---------------------------------------------------------------
ROL_ES = {
    "organizer": "Administrador",
    "fileOrganizer": "Gestor de contenido",
    "writer": "Colaborador",
    "commenter": "Comentarista",
    "reader": "Lector"
}

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
# Funciones para Drive
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

def limpiar_nombre(nombre):
    return re.sub(r'[\\/*?:"<>|]', "", nombre)

# ---------------------------------------------------------------
# Ejecución principal
# ---------------------------------------------------------------
if __name__ == '__main__':
    creds = obtener_credenciales()
    drive_svc = build('drive', 'v3', credentials=creds)

    try:
        user_info = drive_svc.about().get(fields="user(emailAddress)").execute()
        usuario_actual = user_info['user']['emailAddress']
    except Exception as e:
        print("❌ No se pudo obtener el correo del usuario autenticado.")
        print(e)
        sys.exit(1)

    print(f"\n👤 Usuario autenticado: {usuario_actual}")

    unidades = listar_unidades_compartidas(drive_svc)
    if not unidades:
        print("No se encontraron Unidades compartidas.")
        sys.exit(0)

    for d in unidades:
        permisos = listar_permisos(drive_svc, d['id'])

        # Filtrar administradores
        admins = [
            p.get('emailAddress') or p.get('domain') or p['type']
            for p in permisos if p['role'] == 'organizer'
        ]

        # Solo continuar si el usuario actual es administrador
        if usuario_actual not in admins:
            continue

        nombre_unidad = limpiar_nombre(d['name'])
        carpeta = os.path.join(os.getcwd(), nombre_unidad)
        os.makedirs(carpeta, exist_ok=True)

        print(f"\n=== Unidad Compartida: {d['name']} (ID: {d['id']}) ===")
        print("Administradores:")
        for admin in admins:
            print(f"  - {admin}")

        # Generar archivo acceso.txt
        no_admins = [
            (p.get('emailAddress') or p.get('domain') or p['type'])
            for p in permisos if p['role'] != 'organizer'
        ]
        if no_admins:
            with open(os.path.join(carpeta, "acceso.txt"), 'w', encoding='utf-8') as f:
                f.write(",".join(no_admins))
            print("  → acceso.txt generado")

        # Generar archivo roles.txt simplificado
        with open(os.path.join(carpeta, "roles.txt"), 'w', encoding='utf-8') as f:
            f.write("Correo                          | Rol\n")
            f.write("-------------------------------|----------------------\n")
            for p in permisos:
                correo = p.get('emailAddress') or p.get('domain') or p['type']
                rol = ROL_ES.get(p['role'], "Desconocido")
                f.write(f"{correo:<31}| {rol}\n")
        print("  → roles.txt generado")

        # Mostrar contenido
        contenido = listar_contenido_drive(drive_svc, d['id'])
        print(f"\nContenido ({len(contenido)} items):")
        for item in contenido:
            print(f"  • {item['name']} [{item['mimeType']}] (ID: {item['id']})")
