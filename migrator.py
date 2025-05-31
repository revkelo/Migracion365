# ---------------------------------------------------------------
# Migrador Directo de Google Drive a OneDrive (Incluye Unidades Compartidas)
# Autor: Kevin Gonzalez
# Descripción:
#   Orquesta el proceso de migración de archivos desde Google Drive 
#   (tanto "Mi unidad" como Unidades Compartidas donde el usuario 
#   es organizador) hacia OneDrive.
#   - Gestiona autenticación y servicios de Google y OneDrive.
#   - Descarga, exporta y sube archivos, preservando estructura de carpetas.
#   - Control de progreso y capacidad de reanudar.
#   - Registro de errores y soporte para cancelar la operación.
#   - Genera roles.txt y acceso.txt para cada Unidad Compartida.
# ---------------------------------------------------------------

import time
import logging
from typing import Callable, Optional
import threading
import re
import io

from config import PROGRESS_FILE, LOG_FILE, GOOGLE_EXPORT_FORMATS
from utils import load_progress, save_progress, sanitize_filename
from google_service import GoogleService
from onedrive_service import OneDriveService


class MigrationCancelled(Exception):
    """Señaliza que el usuario ha cancelado el proceso de migración."""
    pass


class ConnectionLost(Exception):
    """Señaliza que se perdió la conexión a Internet durante la migración."""
    pass


class DirectMigrator:
    ERROR_LOG = 'migration_errors.txt'

    def __init__(
        self,
        onedrive_folder: str = '',
        cancel_event: Optional[threading.Event] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ):
        # Callbacks y configuraciones iniciales
        self.status_callback = status_callback
        self.onedrive_folder = onedrive_folder.strip('/')
        self.cancel_event = cancel_event

        # Autenticación con Google Drive
        self._update_status("Autenticando con Google Drive...")
        self.google = GoogleService()

        # Autenticación con OneDrive
        self._update_status("Autenticando con OneDrive...")
        self.one = OneDriveService()

        self._update_status("Autenticación completa. Preparando migración...")
        self.progress = load_progress(PROGRESS_FILE)

        # Verificación de que el correo de Google y OneDrive coincidan
        correo_google = self.google.usuario
        correo_onedrive = self.one.usuario
        if correo_google != correo_onedrive:
            # Inicializar el logger antes de arrojar la excepción
            self._init_logger()
            self.logger.error("Los correos de Google y OneDrive no coinciden. Cancelando migración.")
            raise MigrationCancelled("Los correos de autenticación no coinciden.")

        # Inicializar logger (si no se inicializó aún)
        self._init_logger()
        self.logger.info("DirectMigrator inicializado correctamente.")

    def _init_logger(self):
        """Configura el logger de la clase si no existe aún."""
        if hasattr(self, 'logger') and self.logger.handlers:
            return  # Ya está inicializado

        self.logger = logging.getLogger('DirectMigrator')
        self.logger.setLevel(logging.INFO)

        # Handler de consola
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
        self.logger.addHandler(ch)

        # FileHandler para guardar en LOG_FILE
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s — %(levelname)s — %(message)s"))
        self.logger.addHandler(fh)

    def _update_status(self, msg: str):
        """Llama al callback de estado si fue provisto."""
        if self.status_callback:
            self.status_callback(msg)

    def migrate(
        self,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        file_progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        """
        Método principal que migra archivos de 'Mi unidad' y luego lanza 
        la migración de Unidades Compartidas si corresponde. 
        Ahora calcula el total de archivos exportables en ambos ámbitos
        antes de comenzar, para que la barra de progreso refleje todo el proceso.
        """

        # 1) Obtener lista de archivos exportables de "Mi unidad"
        self.logger.info("Obteniendo archivos exportables de 'Mi unidad'...")
        self._update_status("Obteniendo archivos de 'Mi unidad'...")
        folders, files, _ = self.google.list_files_and_folders()
        mi_entries = [
            f for f in files.values()
            if f['mimeType'] in GOOGLE_EXPORT_FORMATS
        ]
        mi_total = len(mi_entries)

        # 2) Obtener lista de archivos exportables en Unidades Compartidas donde el usuario es organizer
        self.logger.info("Contando archivos exportables en Unidades Compartidas...")
        self._update_status("Contando archivos en Unidades Compartidas...")
        # Inicializar contador de archivos compartidos
        shared_total = 0

        # Primero listamos todas las Unidades Compartidas
        unidades = self.google.listar_unidades_compartidas()
        for unidad in unidades:
            permisos = self.google.listar_permisos(unidad['id'])
            # Filtrar solo si el usuario es organizer en esa unidad
            admins = [
                p.get('emailAddress') or p.get('domain') or p['type']
                for p in permisos
                if p['role'] == 'organizer'
            ]
            if self.google.usuario not in admins:
                continue

            # Listar todo el contenido (archivos y carpetas) de esa unidad
            archivos = self.google.listar_contenido_drive(unidad['id'])
            # Contar únicamente aquellos exportables
            for a in archivos:
                if a['mimeType'] in GOOGLE_EXPORT_FORMATS:
                    shared_total += 1

        # 3) Sumar totales para saber cuántos archivos en total vamos a migrar
        total_tasks = mi_total + shared_total
        self.logger.info(f"Total de archivos a migrar: {total_tasks} (Mi unidad: {mi_total}, Unidades Compartidas: {shared_total})")
        self._update_status(f"Total de archivos a migrar: {total_tasks} (Mi unidad: {mi_total}, Unidades Compartidas: {shared_total})")

        # 4) Inicializar contador de archivos procesados
        processed = 0

        # 5) Empezar migración de "Mi unidad"
        self.logger.info("Iniciando migración de 'Mi unidad'...")
        self._update_status("Obteniendo archivos de Google Drive...")

        for info in mi_entries:
            # 5.1) Verificar cancelación
            if self.cancel_event and self.cancel_event.is_set():
                self.logger.info("Migración cancelada por usuario")
                return

            fid = info['id']
            raw_name = info['name']
            name = raw_name.replace('\r', '').replace('\n', ' ').strip()

            # 5.2) Saltar si ya está migrado
            if skip_existing and fid in self.progress.get('migrated_files', set()):
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_tasks, name)
                continue

            # 5.3) Reconstruir ruta en Mi unidad
            parents = info.get('parents') or []
            if parents:
                path_parts = self.google.get_folder_path(parents[0], folders)
            else:
                path_parts = []
            folder_path = '/'.join(path_parts)
            drive_path = f"{folder_path}/{name}" if folder_path else name

            try:
                # 5.4) Descargar/Exportar
                t0 = time.perf_counter()
                data, ext_name = self.google.download_file(info)
                t1 = time.perf_counter()
                self.logger.info(f"Descarga '{name}': {t1 - t0:.2f}s")

                if data is None:
                    raw_msg = getattr(self.google, 'last_error', None)
                    mensaje = self._format_error(raw_msg) if raw_msg else "Descarga fallida (error desconocido)"
                    print(f"[ERROR] {drive_path} -> {mensaje}")
                    self._log_error(drive_path, mensaje)
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_tasks, name)
                    continue

                # 5.5) Preparar bytes para callback de progreso
                data.seek(0, 2)
                total_bytes = data.tell()
                data.seek(0)

                # 5.6) Subir a OneDrive
                remote_path = f"{self.onedrive_folder}/{folder_path}/{ext_name}".lstrip('/')
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
                self.logger.info(f"Subida '{name}': {t3 - t2:.2f}s")

                # 5.7) Marcar como migrado y guardar
                self.progress.setdefault('migrated_files', set()).add(fid)
                save_progress(PROGRESS_FILE, self.progress)

            except Exception as e:
                raw_msg = str(e)
                mensaje = self._format_error(raw_msg)
                self._log_error(drive_path, mensaje)
                if mensaje in (
                    "Tiempo de espera agotado al leer los datos.",
                    "No se pudo conectar al servidor de Google APIs."
                ):
                    raise ConnectionLost(mensaje)

            # 5.8) Incrementar y notificar progreso
            processed += 1
            if progress_callback:
                progress_callback(processed, total_tasks, name)

        self.logger.info("Migración de 'Mi unidad' completada.")

        # 6) Migración de Unidades Compartidas
        try:
            self.logger.info("Iniciando migración de Unidades Compartidas...")
            self._migrar_unidades_compartidas(processed, total_tasks, progress_callback)
            self.logger.info("Migración de Unidades Compartidas completada.")
        except Exception as e:
            self.logger.error(f"Error al migrar Unidades Compartidas: {str(e)}")
            
        

    def _migrar_unidades_compartidas(
        self,
        processed: int,
        total_tasks: int,
        progress_callback: Optional[Callable[[int, int, str], None]]
    ):
        """
        Método privado que:
        - Lista Unidades Compartidas, filtra por organizer.
        - Por cada archivo exportable dentro de cada unidad:
            * Si ya está migrado (en self.progress), lo omite SIN imprimir nada.
            * De lo contrario, descarga/exporta y sube a OneDrive.
            * Incrementa `processed` y llama a progress_callback.
            * Registra el ID en el JSON de progreso para evitar duplicados.
        """

        usuario_actual = self.google.usuario
        unidades = self.google.listar_unidades_compartidas()

        for unidad in unidades:
            permisos = self.google.listar_permisos(unidad['id'])
            admins = [
                p.get('emailAddress') or p.get('domain') or p['type']
                for p in permisos
                if p['role'] == 'organizer'
            ]

            # Solo migrar si el usuario es organizer de esta unidad
            if usuario_actual not in admins:
                continue

            nombre_unidad  = sanitize_filename(unidad['name'])
            ruta_onedrive  = f"Unidades Compartidas/{nombre_unidad}"
            self.one.create_folder(ruta_onedrive)

            # Aquí podrías crear roles.txt y acceso.txt si lo deseas…

            # Obtener todo el contenido (archivos + carpetas) de la unidad
            archivos = self.google.listar_contenido_drive(unidad['id'])

            # Separar carpetas y archivos exportables
            folders_dict   = {
                a['id']: a for a in archivos
                if a['mimeType'] == 'application/vnd.google-apps.folder'
            }
            archivos_dict  = {
                a['id']: a for a in archivos
                if a['mimeType'] in GOOGLE_EXPORT_FORMATS
            }

            for archivo in archivos_dict.values():
                file_id   = archivo['id']
                file_name = archivo['name']
                parents   = archivo.get('parents') or []

                # --- CHEQUEO PARA OMITIR SI YA ESTÁ MIGRADO ---
                if file_id in self.progress.get('migrated_files', set()):
                    # Ya no imprimimos nada aquí; simplemente avanzamos el contador:
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_tasks, file_name)
                    continue
                # --- FIN DEL CHEQUEO ---

                # 1) Reconstruir ruta interna dentro de la unidad compartida
                if parents:
                    path_parts   = self.google.get_folder_path(parents[0], folders_dict)
                else:
                    path_parts   = []
                ruta_interna = "/".join(path_parts)
                ruta_completa = f"{ruta_onedrive}/{ruta_interna}".strip("/")

                # Asegurarse de que la carpeta exista en OneDrive
                if ruta_completa:
                    self.one.create_folder(ruta_completa)

                try:
                    # 2) Descargar/Exportar desde Google Drive
                    data, final_name = self.google.download_file(archivo)
                    if data:
                        # 3) Preparar el buffer para medir tamaño
                        data.seek(0, 2)
                        total_bytes = data.tell()
                        data.seek(0)

                        # 4) Definir ruta remota en OneDrive
                        remote_path = f"{ruta_completa}/{final_name}".strip("/")

                        # 5) Subir a OneDrive
                        self.one.upload(
                            file_data=data,
                            remote_path=remote_path,
                            size=total_bytes
                        )
                        self.logger.info(f"Compartido - Subida '{file_name}' en '{ruta_completa}'")

                        # 6) Registrar el ID del archivo como migrado
                        self.progress.setdefault('migrated_files', set()).add(file_id)
                        save_progress(PROGRESS_FILE, self.progress)

                except Exception as e:
                    mensaje = str(e)
                    self.logger.error(f"Error al migrar archivo '{file_name}' en '{ruta_completa}': {mensaje}")

                # 7) Incrementar contador y notificar callback
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_tasks, file_name)





    def _log_error(self, drive_path: str, message: str) -> None:
        """
        Añade una entrada en el log de errores (una sola línea).
        Formato: 'YYYY-MM-DD HH:MM:SS - ruta - mensaje'
        """
        clean_path = drive_path.replace('\r', '').replace('\n', '')
        entry = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {clean_path} - {message}\n"
        try:
            with open(self.ERROR_LOG, 'a', encoding='utf-8') as f:
                f.write(entry)
        except Exception:
            self.logger.error(f"Imposible escribir error en {self.ERROR_LOG}")

    def _format_error(self, raw_msg: str) -> str:
        """
        Traduce mensajes de error crudos en algo legible para el usuario.
        """
        msg = str(raw_msg)

        if 'exportSizeLimitExceeded' in msg:
            return "Este archivo es demasiado grande para ser exportado desde Google Docs."
        if 'cannotExportFile' in msg or 'This file cannot be exported by the user.' in msg:
            return "No tienes permiso para exportar este archivo desde Google Docs."
        if '403' in msg and 'export' in msg:
            return "No tienes permiso para exportar este archivo desde Google Docs."
        if '404' in msg:
            return "Archivo no encontrado."
        if 'timed out' in msg.lower():
            return "Tiempo de espera agotado al leer los datos."
        if 'unable to find the server' in msg.lower():
            return "No se pudo conectar al servidor de Google APIs."
        if 'ConnectionError' in msg or 'Failed to establish a new connection' in msg:
            return "Error de red. Verifica tu conexión a Internet."
        if 'invalid_grant' in msg or 'Token has been expired or revoked' in msg:
            return "Tu sesión ha expirado. Inicia sesión nuevamente."
        if 'rateLimitExceeded' in msg:
            return "Se excedió el límite de la API. Intenta más tarde."
        if 'Backend Error' in msg:
            return "Error temporal de Google Drive."

        # Si no coincide con ningún patrón conocido, retorna el mensaje original
        return msg
