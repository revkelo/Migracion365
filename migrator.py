import time
import logging
from typing import Callable, Optional
from config import PROGRESS_FILE, LOG_FILE
from utils import load_progress, save_progress
from services.google_service import GoogleService
from services.onedrive_service import OneDriveService
import threading


class MigrationCancelled(Exception):
    """Excepción interna para indicar que la migración fue cancelada"""
    pass


class DirectMigrator:
    ERROR_LOG = 'migration_errors.txt'

    def __init__(
        self,
        onedrive_folder: str = '',
        cancel_event: Optional[threading.Event] = None
    ):
        # Carpeta base en OneDrive
        self.onedrive_folder = onedrive_folder.strip('/')
        # Flag de cancelación
        self.cancel_event = cancel_event

        # Servicios
        self.google = GoogleService()
        self.one = OneDriveService()

        # Progreso cargado
        self.progress = load_progress(PROGRESS_FILE)

        # Logger
        self.logger = logging.getLogger('DirectMigrator')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter(
                "%(asctime)s — %(levelname)s — %(message)s"
            ))
            self.logger.addHandler(ch)
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s — %(levelname)s — %(message)s"
            ))
            self.logger.addHandler(fh)

    def migrate(
        self,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        file_progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        self.logger.info("Iniciando migración...")
        folders, files, _ = self.google.list_files_and_folders()
        entries = list(files.values())
        total_files = len(entries)
        processed = 0

        for info in entries:
            # Comprobación de cancelación
            if self.cancel_event and self.cancel_event.is_set():
                self.logger.info("Migración cancelada por usuario")
                return

            fid = info['id']
            name = info['name']

            if progress_callback:
                progress_callback(processed + 1, total_files, name)

            parents = info.get('parents') or []
            path_parts = (
                self.google.get_folder_path(parents[0], folders)
                if parents else []
            )
            # Construir ruta remota antes de la descarga
            folder_path = '/'.join(path_parts)
            # Para registro de errores, usamos la ruta original + nombre de archivo
            drive_path = f"{folder_path}/{name}" if folder_path else name

            if skip_existing and fid in self.progress.get('migrated_files', set()):
                processed += 1
                continue

            try:
                # Descarga
                t0 = time.perf_counter()
                data, ext_name = self.google.download_file(info)
                t1 = time.perf_counter()
                self.logger.info(f"Descarga {name}: {t1-t0:.2f}s")

                if data is None:
                    raise RuntimeError("Descarga fallida")

                # Preparar datos para subida
                data.seek(0, 2)
                total_bytes = data.tell()
                data.seek(0)

                # Ruta final en OneDrive
                remote_path = f"{self.onedrive_folder}/{folder_path}/{ext_name}".lstrip('/')

                # Subida
                t2 = time.perf_counter()
                self.one.upload(
                    file_data=data,
                    remote_path=remote_path,
                    size=total_bytes,
                    progress_callback=lambda sent, tot, n=name: (
                        file_progress_callback(sent, tot, n)
                        if file_progress_callback else None
                    )
                )
                t3 = time.perf_counter()
                self.logger.info(f"Subida   {name}: {t3-t2:.2f}s")

                # Guardar progreso
                self.progress.setdefault('migrated_files', set()).add(fid)
                save_progress(PROGRESS_FILE, self.progress)

            except Exception as e:
                self._log_error(drive_path, str(e))

            processed += 1

        if progress_callback:
            progress_callback(total_files, total_files, '')

    def _log_error(self, drive_path: str, message: str) -> None:
        entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {drive_path} - {message}\n"
        try:
            with open(self.ERROR_LOG, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception:
            self.logger.error(f"Imposible escribir error en {self.ERROR_LOG}")