GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/forms.body.readonly'
]

ONEDRIVE_CLIENT_ID   = "d8227c52-3dde-4198-81a8-60f1347357ab"
ONEDRIVE_AUTHORITY   = "https://login.microsoftonline.com/common"
ONEDRIVE_SCOPES      = ["Files.ReadWrite.All"]

CHUNK_SIZE = 60 * 1024 * 1024  # 60 MiB
LARGE_FILE_THRESHOLD = 5 * 1024 * 1024  # por debajo de eso sigue single PUT

PROGRESS_FILE = 'migration_progress.json'
# Nombre del fichero de log
LOG_FILE = "migration.log"


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