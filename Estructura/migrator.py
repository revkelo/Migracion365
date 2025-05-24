import time
import logging
from tqdm import tqdm
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
        self.stats = {
            'total_files': 0,
            'migrated': 0,
            'skipped': 0,
            'errors': 0,
            'total_size': 0,
            'migrated_size': 0,
            'start_time': None
        }
        self.logger = logging.getLogger('DirectMigrator')

    def migrate(self, skip_existing: bool = True):
        """Ejecuta la migración de todos los archivos."""
        self.logger.info("Iniciando migración directa Google Drive → OneDrive")
        folders, files, total = self.google.list_files_and_folders()
        self.stats['total_files'] = len(files)
        self.stats['total_size'] = total
        self.stats['start_time'] = time.time()

        with tqdm(total=len(files), desc="Migrando archivos", unit="archivo") as pbar:
            for fid, info in files.items():
                name = info['name']
                if skip_existing and fid in self.progress.get('migrated_files', set()):
                    self.stats['skipped'] += 1
                    pbar.update(1)
                    continue

                parents = info.get('parents')
                path = ''
                if parents:
                    path = '/'.join(self.google.get_folder_path(parents[0], folders))

                if path and not self.one.create_folder(f"{self.onedrive_folder}/{path}"):
                    self.stats['errors'] += 1
                    pbar.update(1)
                    continue

                for attempt in range(MAX_RETRIES):
                    fh, final_name = self.google.download_file(info)
                    if fh is None:
                        break
                    fh.seek(0, 2)
                    size = fh.tell()
                    fh.seek(0)
                    remote = f"{self.onedrive_folder}/{path}/{final_name}".replace('//', '/')
                    if self.one.upload(fh, remote, size):
                        self.stats['migrated'] += 1
                        self.stats['migrated_size'] += size
                        self.progress.setdefault('migrated_files', set()).add(fid)
                        break
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    self.stats['errors'] += 1
                    self.logger.error(f"Falló migración de {name}")

                pbar.update(1)
                if (self.stats['migrated'] + self.stats['errors']) % 5 == 0:
                    save_progress(PROGRESS_FILE, {'migrated_files': list(self.progress['migrated_files'])})

        save_progress(PROGRESS_FILE, {'migrated_files': list(self.progress['migrated_files'])})
        self.print_stats()

    def print_stats(self):
        duration = time.time() - self.stats['start_time']
        print(f"Total de archivos: {self.stats['total_files']}")
        print(f"Migrados exitosamente: {self.stats['migrated']}")
        print(f"Saltados: {self.stats['skipped']}")
        print(f"Errores: {self.stats['errors']}")
        print(f"Tamaño total: {format_size(self.stats['total_size'])}")
        print(f"Tamaño migrado: {format_size(self.stats['migrated_size'])}")
        print(f"Duración (s): {duration:.1f}")
