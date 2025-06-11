# ---------------------------------------------------------------
# Configuración de Migración
# Autor: Kevin Gonzalez
# Descripción:
#   Define las constantes y parámetros de configuración utilizados en el
#   proceso de migración de Google Drive a OneDrive.
#   Incluye scopes de OAuth, identificadores de cliente, tamaños de chunk,
#   rutas de archivos de progreso y log, así como formatos de exportación.
# ---------------------------------------------------------------


"""
Scopes de Google API (solo lectura):
- https://www.googleapis.com/auth/drive.readonly: leer archivos de Drive.
- https://www.googleapis.com/auth/forms.body.readonly: leer la estructura de Formularios.
"""
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/forms.body.readonly'
]


"""
Configuración de OAuth para OneDrive:
- ONEDRIVE_CLIENT_ID: Identificador de la aplicación registrada en Azure.
- ONEDRIVE_AUTHORITY: URL de autenticación de Microsoft.
- ONEDRIVE_SCOPES: permisos de archivos (lectura/escritura).
"""
ONEDRIVE_CLIENT_ID   = "d8227c52-3dde-4198-81a8-60f1347357ab"
ONEDRIVE_AUTHORITY   = "https://login.microsoftonline.com/common"
ONEDRIVE_SCOPES      = ["Files.ReadWrite.All", "User.Read"]

"""
Define tamaños para la transferencia de archivos:
- CHUNK_SIZE: tamaño de cada fragmento en bytes.
- LARGE_FILE_THRESHOLD: umbral para usar PUT simple en lugar de carga por fragmentos.
"""
CHUNK_SIZE = 100 * 1024 * 1024  
LARGE_FILE_THRESHOLD = 5 * 1024 * 1024 
MAX_FILE_SIZE_BYTES = 10 * 1024**3  # 10 GB
 
"""
Archivos de estado:
- PROGRESS_FILE: archivo JSON que guarda el estado de la migración.
- LOG_FILE: archivo de registro de eventos e incidencias.
"""
PROGRESS_FILE = 'migration_progress.json'
LOG_FILE = "migration.log"

"""
Mapeo de formatos de exportación de Google Drive:
- Clave: MIME type de Google.
- "mime": MIME destino.
- "ext": extensión de fichero resultante.
"""
GOOGLE_EXPORT_FORMATS = {
    'application/vnd.google-apps.document': {
        'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'ext' : 'docx'
    },
    'application/vnd.google-apps.spreadsheet': {
        'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'ext' : 'xlsx'
    },
    'application/vnd.google-apps.presentation': {
        'mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'ext' : 'pptx'
    },
    'application/vnd.google-apps.form': {
        'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'ext' : 'docx'
    }
}