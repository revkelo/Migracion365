GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/forms.body.readonly'
]

ONEDRIVE_CLIENT_ID   = "d8227c52-3dde-4198-81a8-60f1347357ab"
ONEDRIVE_AUTHORITY   = "https://login.microsoftonline.com/common"
ONEDRIVE_SCOPES      = ["Files.ReadWrite.All"]

CHUNK_SIZE           = 10 * 1024 * 1024  # 10MB
LARGE_FILE_THRESHOLD = 4  * 1024 * 1024  # 4MB
MAX_RETRIES          = 3
RETRY_DELAY          = 2  # segundos

LOG_FILE      = 'migration_log.txt'
PROGRESS_FILE = 'migration_progress.json'

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