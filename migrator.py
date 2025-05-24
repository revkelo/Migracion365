import time
import logging
from typing import Callable, Optional
from config import PROGRESS_FILE
from utils import load_progress, save_progress
from google_service import GoogleService
from onedrive_service import OneDriveService

class DirectMigrator:
    ERROR_LOG = 'migration_errors.txt'

    def __init__(self, onedrive_folder: str = ''):
        self.onedrive_folder = onedrive_folder.strip('/')
        self.google = GoogleService()
        self.one = OneDriveService()
        self.progress = load_progress(PROGRESS_FILE)
        self.logger = logging.getLogger('DirectMigrator')

    def migrate(
        self,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        file_progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        """
        Migra archivos de Google Drive a OneDrive.
        - progress_callback(procesados, total_archivos, nombre_archivo)
        - file_progress_callback(bytes_subidos, bytes_totales, nombre_archivo)
        Registra fallos en migration_errors.txt
        """
        self.logger.info("Iniciando migración...")
        folders, files, _ = self.google.list_files_and_folders()
        entries = list(files.values())
        total_files = len(entries)
        processed = 0

        for info in entries:
            fid = info['id']
            name = info['name']
            # Notificar inicio de este archivo
            if progress_callback:
                progress_callback(processed + 1, total_files, name)

            # Ruta en Drive
            parents = info.get('parents') or []
            path_parts = self.google.get_folder_path(parents[0], folders) if parents else []
            drive_path = '/'.join(path_parts + [name])

            # Saltar ya migrados
            if skip_existing and fid in self.progress.get('migrated_files', set()):
                processed += 1
                continue

            # Crear carpeta remota
            remote_folder = '/'.join(path_parts)
            try:
                self.one.create_folder(f"{self.onedrive_folder}/{remote_folder}")
            except Exception as e:
                self._log_error(drive_path, f"Error creando carpeta: {e}")

            # Descargar y subir
            try:
                data, ext_name = self.google.download_file(info)
                if data is None:
                    raise RuntimeError("Descarga fallida")
                data.seek(0, 2)
                total_bytes = data.tell()
                data.seek(0)
                remote_path = f"{self.onedrive_folder}/{remote_folder}/{ext_name}".replace('//', '/')
                # Subida con callback de archivo
                self.one.upload(
                    file_data=data,
                    remote_path=remote_path,
                    size=total_bytes,
                    progress_callback=lambda sent, tot, n=name: file_progress_callback(sent, tot, n) if file_progress_callback else None
                )
            except Exception as e:
                self._log_error(drive_path, str(e))
            else:
                # Marcar como migrado
                self.progress.setdefault('migrated_files', set()).add(fid)
                save_progress(PROGRESS_FILE, self.progress)

            processed += 1

        # Al terminar, opcional: llamar progress_callback al 100%
        if progress_callback:
            progress_callback(total_files, total_files, '')

    def _log_error(self, drive_path: str, message: str) -> None:
        entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {drive_path} - {message}\n"
        try:
            with open(self.ERROR_LOG, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception:
            self.logger.error(f"Imposible escribir error en {self.ERROR_LOG}")