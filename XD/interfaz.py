import customtkinter as ctk
from PIL import Image
from typing import List, Optional
import os


class MigrationApp(ctk.CTk):
    """Aplicación de migración de archivos con interfaz gráfica y barra de progreso."""
    
    # Constantes de configuración
    WINDOW_SIZE = "800x300"
    ICON_SIZE = (128, 128)
    BUTTON_SIZE = (150, 50)
    PROGRESS_BAR_SIZE = (300, 12)
    
    # Colores
    COLORS = {
        'primary': '#0078D7',
        'primary_hover': '#106EBE',
        'background': 'white',
        'text': '#333333',
        'progress_bg': '#E5E5E5'
    }
    
    # Configuración de animación
    ANIMATION = {
        'increment': 0.02,
        'interval': 100,
        'file_delay': 300,
        'completion_delay': 1000
    }

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._initialize_components()
        self._create_layout()
        self._reset_migration_state()

    def _setup_window(self) -> None:
        """Configura las propiedades básicas de la ventana."""
        ctk.set_appearance_mode("light")
        
        if os.path.exists("./Gui/icono.ico"):
            self.iconbitmap("./Gui/icono.ico")
        
        self.title("Migración")
        self.geometry(self.WINDOW_SIZE)
        self.resizable(False, False)
        self.configure(fg_color=self.COLORS['background'])

    def _initialize_components(self) -> None:
        """Inicializa los componentes de la interfaz."""
        # Cargar imágenes
        self.left_icon = self._load_image("./Gui/googledrive.png")
        self.right_icon = self._load_image("./Gui/onedrive.png")
        
        # Crear frame central
        self.center_frame = ctk.CTkFrame(self, fg_color=self.COLORS['background'])
        
        # Crear botón de migración
        self.migration_button = ctk.CTkButton(
            self.center_frame,
            text="Migración",
            fg_color=self.COLORS['primary'],
            hover_color=self.COLORS['primary_hover'],
            text_color="white",
            width=self.BUTTON_SIZE[0],
            height=self.BUTTON_SIZE[1],
            command=self.start_migration
        )
        
        # Crear barra de progreso
        self.progress_bar = ctk.CTkProgressBar(
            self.center_frame,
            width=self.PROGRESS_BAR_SIZE[0],
            height=self.PROGRESS_BAR_SIZE[1],
            fg_color=self.COLORS['progress_bg'],
            progress_color=self.COLORS['primary']
        )
        
        # Crear etiqueta de archivo actual
        self.file_label = ctk.CTkLabel(
            self.center_frame,
            text="",
            text_color=self.COLORS['text'],
            fg_color=self.COLORS['background']
        )

    def _load_image(self, path: str) -> Optional[ctk.CTkImage]:
        """Carga una imagen de forma segura."""
        try:
            if os.path.exists(path):
                return ctk.CTkImage(Image.open(path), size=self.ICON_SIZE)
        except Exception as e:
            print(f"Error cargando imagen {path}: {e}")
        return None

    def _create_layout(self) -> None:
        """Crea el diseño de la interfaz."""
        # Icono izquierdo
        if self.left_icon:
            ctk.CTkLabel(
                self,
                image=self.left_icon,
                text="",
                fg_color=self.COLORS['background']
            ).pack(side="left", padx=40, pady=40)

        # Frame central
        self.center_frame.pack(side="left", expand=True)
        
        # Botón de migración
        self.migration_button.pack(pady=(0, 10))

        # Icono derecho
        if self.right_icon:
            ctk.CTkLabel(
                self,
                image=self.right_icon,
                text="",
                fg_color=self.COLORS['background']
            ).pack(side="right", padx=40, pady=40)

    def _reset_migration_state(self) -> None:
        """Reinicia el estado de la migración."""
        self.files: List[str] = ["Formulario.docx", "Presentación.pptx", "Datos.xlsx"]
        self.current_file_index: int = 0
        self.progress_value: float = 0.0
        self.progress_bar.set(0)

    def start_migration(self) -> None:
        """Inicia el proceso de migración."""
        self._disable_migration_button()
        self._show_progress_components()
        self._reset_migration_state()
        self._process_next_file()

    def _disable_migration_button(self) -> None:
        """Deshabilita el botón de migración."""
        self.migration_button.configure(state="disabled")

    def _enable_migration_button(self) -> None:
        """Habilita el botón de migración."""
        self.migration_button.configure(state="normal")

    def _show_progress_components(self) -> None:
        """Muestra los componentes de progreso."""
        self.progress_bar.pack(pady=(0, 10))
        self.file_label.pack()

    def _hide_progress_components(self) -> None:
        """Oculta los componentes de progreso."""
        self.progress_bar.pack_forget()
        self.file_label.pack_forget()

    def _process_next_file(self) -> None:
        """Procesa el siguiente archivo en la lista."""
        if self.current_file_index >= len(self.files):
            self._complete_migration()
            return

        current_file = self.files[self.current_file_index]
        self.file_label.configure(text=f"Subiendo: {current_file}")
        self.progress_value = 0.0
        self._animate_progress_bar()

    def _animate_progress_bar(self) -> None:
        """Anima la barra de progreso para el archivo actual."""
        if self.progress_value < 1.0:
            self.progress_value += self.ANIMATION['increment']
            self.progress_bar.set(self.progress_value)
            self.after(self.ANIMATION['interval'], self._animate_progress_bar)
        else:
            self.current_file_index += 1
            self.after(self.ANIMATION['file_delay'], self._process_next_file)

    def _complete_migration(self) -> None:
        """Completa el proceso de migración."""
        self.file_label.configure(text="Migración completada")
        
        # Programar limpieza de la interfaz
        self.after(
            self.ANIMATION['completion_delay'],
            self._cleanup_after_completion
        )

    def _cleanup_after_completion(self) -> None:
        """Limpia la interfaz después de completar la migración."""
        self._hide_progress_components()
        self._enable_migration_button()
        self.progress_bar.set(0)

    def run(self) -> None:
        """Ejecuta la aplicación."""
        self.mainloop()


def main():
    """Función principal para ejecutar la aplicación."""
    app = MigrationApp()
    app.run()


if __name__ == "__main__":
    main()