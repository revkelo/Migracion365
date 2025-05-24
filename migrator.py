import time
import logging
from typing import Callable, Optional
from config import PROGRESS_FILE, MAX_RETRIES, RETRY_DELAY
from utils import load_progress, save_progress, format_size
from google_service import GoogleService
from onedrive_service import OneDriveService

class DirectMigrator:
    def __init__(self, onedrive_folder: str = ''):
        self.onedrive_folder = onedrive_folder.strip('/')
        self.google = GoogleService()
        self.one = OneDriveService()
        self.progress = load_progress(PROGRESS_FILE)
        self.logger = logging.getLogger('DirectMigrator')

    def migrate(self, skip_existing: bool = True, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        """
        Migra todos los archivos de Google Drive a OneDrive.
        Si se proporciona progress_callback, se llama así:
            progress_callback(procesados, total, nombre_archivo)
        """
        self.logger.info("Iniciando migración...")
        folders, files, _ = self.google.list_files_and_folders()
        files_list = list(files.values())
        total_files = len(files_list)
        processed = 0

        for info in files_list:
            file_id = info['id']
            filename = info['name']
            # Saltar ya migrados
            if skip_existing and file_id in self.progress.get('migrated_files', set()):
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_files, filename)
                continue

            # Crear carpeta remota
            parents = info.get('parents')
            path = '/'.join(self.google.get_folder_path(parents[0], folders)) if parents else ''
            self.one.create_folder(f"{self.onedrive_folder}/{path}")

            # Descargar y subir
            file_data, ext_name = self.google.download_file(info)
            if file_data is not None:
                file_data.seek(0, 2)
                size = file_data.tell()
                file_data.seek(0)
                remote_path = f"{self.onedrive_folder}/{path}/{ext_name}".replace('//', '/')
                success = self.one.upload(file_data, remote_path, size)
                if not success:
                    self.logger.error(f"Error subiendo {filename}")
            else:
                self.logger.error(f"No se pudo descargar {filename}")

            # Marcar como migrado
            self.progress.setdefault('migrated_files', set()).add(file_id)
            save_progress(PROGRESS_FILE, self.progress)

            processed += 1
            if progress_callback:
                progress_callback(processed, total_files, filename)

    def migrate_file_direct(self, file_info, path):
        # placeholder if needed
        pass
        pass