# ---------------------------------------------------------------
# Script para Descargar Google Drive Localmente con Estructura
# Autor: Kevin Gonzalez
# ---------------------------------------------------------------

import os, io, pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
CARPETA_DESTINO_LOCAL = "Descarga_GoogleDrive"

# Autenticación
def obtener_credenciales():
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as f:
            cred = pickle.load(f)
    else:
        cred = None
    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            cred = flow.run_local_server(port=8089)
        with open('token.pickle', 'wb') as f:
            pickle.dump(cred, f)
    return cred

# Construir mapa de carpetas para preservar estructura
def construir_mapa_carpetas(service):
    carpetas = {}
    page_token = None
    while True:
        respuesta = service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            fields="nextPageToken, files(id, name, parents)",
            pageToken=page_token
        ).execute()
        for carpeta in respuesta.get('files', []):
            carpetas[carpeta['id']] = {
                'name': carpeta['name'],
                'parents': carpeta.get('parents', [])
            }
        page_token = respuesta.get('nextPageToken')
        if not page_token:
            break
    return carpetas

# Obtener ruta local basada en el árbol de carpetas
def obtener_ruta_local(carpeta_id, carpetas):
    path = []
    while carpeta_id in carpetas:
        carpeta = carpetas[carpeta_id]
        path.insert(0, carpeta['name'])
        padres = carpeta.get('parents')
        if not padres:
            break
        carpeta_id = padres[0]
    return os.path.join(CARPETA_DESTINO_LOCAL, *path)

# Descargar archivos
def descargar_archivos(service):
    carpetas = construir_mapa_carpetas(service)
    page_token = None
    total = 0

    while True:
        respuesta = service.files().list(
            q="mimeType != 'application/vnd.google-apps.folder'",
            fields="nextPageToken, files(id, name, parents, mimeType)",
            pageToken=page_token
        ).execute()

        for archivo in respuesta.get('files', []):
            nombre = archivo['name']
            archivo_id = archivo['id']
            carpeta_padre = archivo.get('parents', ['root'])[0]
            ruta_local = obtener_ruta_local(carpeta_padre, carpetas)

            os.makedirs(ruta_local, exist_ok=True)
            ruta_archivo = os.path.join(ruta_local, nombre)

            print(f"⬇️ Descargando: {ruta_archivo}")

            try:
                request = service.files().get_media(fileId=archivo_id)
                fh = io.FileIO(ruta_archivo, 'wb')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            except Exception as e:
                print(f"⚠️ Error al descargar {nombre}: {e}")
                continue

            total += 1

        page_token = respuesta.get('nextPageToken')
        if not page_token:
            break

    print(f"\n✅ Descarga completa. Total archivos descargados: {total}")

# Ejecución
if __name__ == "__main__":
    servicio = build('drive', 'v3', credentials=obtener_credenciales())
    descargar_archivos(servicio)
