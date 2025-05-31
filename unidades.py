from google_service import GoogleService
from onedrive_service import OneDriveService
from utils import sanitize_filename
from config import GOOGLE_EXPORT_FORMATS
import io

class SharedDriveMigrator:
    def __init__(self, google_service: GoogleService, onedrive_service: OneDriveService):
        self.google = google_service
        self.onedrive = onedrive_service
        self.usuario = self.google.obtener_usuario()

    def migrar_unidades(self):
        unidades = self.google.listar_unidades_compartidas()

        for unidad in unidades:
            permisos = self.google.listar_permisos(unidad['id'])
            admins = [p.get('emailAddress') or p.get('domain') or p['type']
                      for p in permisos if p['role'] == 'organizer']

            if self.usuario not in admins:
                continue

            nombre_unidad = sanitize_filename(unidad['name'])
            ruta_onedrive = f"Unidades Compartidas/{nombre_unidad}"
            self.onedrive.create_folder(ruta_onedrive)

            # roles.txt
            roles_txt = "Correo                          | Rol\n"
            roles_txt += "-------------------------------|----------------------\n"
            for p in permisos:
                correo = p.get('emailAddress') or p.get('domain') or p['type']
                rol = self.google.rol_espanol(p['role'])
                roles_txt += f"{correo:<31}| {rol}\n"
            self.onedrive.upload(
                file_data=io.BytesIO(roles_txt.encode("utf-8")),
                remote_path=f"{ruta_onedrive}/roles.txt",
                size=len(roles_txt.encode("utf-8"))
            )

            # acceso.txt
            no_admins = [p.get('emailAddress') or p.get('domain') or p['type']
                         for p in permisos if p['role'] != 'organizer']
            acceso_txt = ",".join(no_admins)
            self.onedrive.upload(
                file_data=io.BytesIO(acceso_txt.encode("utf-8")),
                remote_path=f"{ruta_onedrive}/acceso.txt",
                size=len(acceso_txt.encode("utf-8"))
            )

            # Archivos reales (filtrados por tipo compatible)
            archivos = self.google.listar_contenido_drive(unidad['id'])
            archivos_filtrados = [
                a for a in archivos
                if a['mimeType'] in GOOGLE_EXPORT_FORMATS
            ]

            for archivo in archivos_filtrados:
                nombre_archivo = archivo['name']
                mime_type = archivo['mimeType']
                file_id = archivo['id']

                info = {
                    'id': file_id,
                    'name': nombre_archivo,
                    'mimeType': mime_type
                }

                try:
                    data, nombre_final = self.google.download_file(info)

                    if data:
                        data.seek(0, 2)
                        total_bytes = data.tell()
                        data.seek(0)
                        self.onedrive.upload(
                            file_data=data,
                            remote_path=f"{ruta_onedrive}/{nombre_final}",
                            size=total_bytes
                        )
                except Exception as e:
                    print(f"Error al migrar archivo {nombre_archivo}: {str(e)}")
