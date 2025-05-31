import os
import sys
import json
import re
import io
from cryptography.fernet import Fernet
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
import msal

# Configuración
KEY = b"HG5GHGW3o9bMUMWUmz7khGjhELzFUJ9W-52s_ZnIC40="
ENC_CRED_FILE = 'credentials.json.enc'
TOKEN_FILE = 'token.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
ONEDRIVE_CLIENT_ID = "d8227c52-3dde-4198-81a8-60f1347357ab"
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/common"
ONEDRIVE_SCOPES = ["Files.ReadWrite.All"]

ROL_ES = {
    "organizer": "Administrador",
    "fileOrganizer": "Gestor de contenido",
    "writer": "Colaborador",
    "commenter": "Comentarista",
    "reader": "Lector"
}

def _load_encrypted_blob(filename: str = ENC_CRED_FILE) -> bytes:
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
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
            config = _load_credentials()
            flow = InstalledAppFlow.from_client_config(config, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
    return creds

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

def limpiar_nombre(nombre):
    return re.sub(r'[\\/*?:"<>|]', "", nombre)

# ----------------------------- ONEDRIVE -----------------------------

def autenticar_onedrive():
    app = msal.PublicClientApplication(client_id=ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY)
    for acct in app.get_accounts():
        app.remove_account(acct)
    result = app.acquire_token_interactive(scopes=ONEDRIVE_SCOPES, prompt="select_account")
    if "access_token" in result:
        return result["access_token"]
    raise RuntimeError(f"Error autenticando con OneDrive: {result.get('error_description', 'desconocido')}")

def crear_carpeta_onedrive(token, ruta):
    partes = ruta.strip("/").split("/")
    ruta_actual = ""
    for parte in partes:
        ruta_actual = f"{ruta_actual}/{parte}" if ruta_actual else parte
        check_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{ruta_actual}"
        resp = requests.get(check_url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 404:
            parent = os.path.dirname(ruta_actual)
            create_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{parent}:/children" if parent else "https://graph.microsoft.com/v1.0/me/drive/root/children"
            requests.post(create_url, headers={"Authorization": f"Bearer {token}"}, json={
                "name": parte, "folder": {}, "@microsoft.graph.conflictBehavior": "replace"
            })

def subir_archivo(token, ruta, nombre, contenido):
    crear_carpeta_onedrive(token, ruta)
    full_path = f"{ruta}/{nombre}".strip("/")
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{full_path}:/content"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "text/plain"}
    requests.put(url, headers=headers, data=contenido.encode("utf-8"))

# ----------------------------- PRINCIPAL -----------------------------

if __name__ == '__main__':
    creds = obtener_credenciales()
    drive_svc = build('drive', 'v3', credentials=creds)
    token_onedrive = autenticar_onedrive()

    usuario = drive_svc.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]
    unidades = listar_unidades_compartidas(drive_svc)

    for unidad in unidades:
        permisos = listar_permisos(drive_svc, unidad['id'])
        admins = [
            p.get('emailAddress') or p.get('domain') or p['type']
            for p in permisos if p['role'] == 'organizer'
        ]
        if usuario not in admins:
            continue

        nombre = limpiar_nombre(unidad['name'])
        ruta_onedrive = f"Unidades Compartidas/{nombre}"

        roles_txt = "Correo                          | Rol\n"
        roles_txt += "-------------------------------|----------------------\n"
        for p in permisos:
            correo = p.get('emailAddress') or p.get('domain') or p['type']
            rol = ROL_ES.get(p['role'], "Desconocido")
            roles_txt += f"{correo:<31}| {rol}\n"

        no_admins = [
            p.get('emailAddress') or p.get('domain') or p['type']
            for p in permisos if p['role'] != 'organizer'
        ]
        acceso_txt = ",".join(no_admins)

        print(f"🟢 Subiendo: {nombre}")
        subir_archivo(token_onedrive, ruta_onedrive, "roles.txt", roles_txt)
        subir_archivo(token_onedrive, ruta_onedrive, "acceso.txt", acceso_txt)
        print(f"✅ Carpeta '{ruta_onedrive}' completada\n")
