# Mini CRM de Leads (Flask + Google Sheets)

Una aplicación web ultraligera y responsive para registrar y gestionar leads de ventas en tiempo real, utilizando **Google Sheets** como base de datos única y persistente.

## Características clave

- **Estructura limpia:** Sin frameworks CSS o JS, construido con HTML5 y CSS vanilla con un diseño oscuro premium.
- **Base de datos en vivo:** Integración directa con Google Sheets (`gspread`).
- **CRUD completo:** Registrar, leer, buscar, editar y eliminar leads.
- **Validaciones robustas:** Comprobación de duplicados por número de celular, campos obligatorios e interés de mínimo 2 caracteres.
- **Configuración rápida:** Estados modificables a través de un array en `app.py`.

---

## Requisitos de Instalación

1. **Clonar/Descargar** los archivos en una carpeta de trabajo.
2. Asegurarse de tener instalado **Python 3.8+**.
3. Instalar las dependencias especificadas en `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuración de Google Sheets API

Para que la aplicación funcione, debes conectar tu aplicación Flask con un Google Sheet usando una cuenta de servicio de Google Cloud:

### Paso 1: Obtener las Credenciales de Google Cloud
1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un nuevo proyecto.
3. Habilita las API de **Google Sheets API** y **Google Drive API** desde el menú "APIs y servicios" > "Biblioteca".
4. Dirígete a "APIs y servicios" > "Credenciales".
5. Haz clic en **Crear credenciales** y selecciona **Cuenta de servicio**.
6. Completa el asistente. Luego entra en los detalles de la cuenta de servicio recién creada, ve a la pestaña **Claves**, haz clic en **Agregar clave** > **Crear clave nueva** en formato **JSON**.
7. Se descargará un archivo `.json`. Cámbiale el nombre a `credentials.json` y colócalo en la raíz de este proyecto.

### Paso 2: Configurar tu Google Sheet
1. Crea una nueva hoja de cálculo en tu cuenta personal de Google Drive.
2. Comparte la hoja de cálculo dándole permisos de **Editor** al correo de la cuenta de servicio (puedes encontrar este correo en el archivo `credentials.json` en el campo `"client_email"`).
3. Copia el **ID de tu Google Sheet** desde la URL de la hoja:
   `https://docs.google.com/spreadsheets/d/TU_ID_DE_GOOGLE_SHEET/edit#gid=0`

### Paso 3: Configurar el archivo `.env`
Crea un archivo llamado `.env` en la raíz de tu proyecto y define tu ID de hoja de cálculo:
```env
GOOGLE_SHEET_ID=TU_ID_DE_GOOGLE_SHEET
SECRET_KEY=clave-secreta-para-sesiones-flask
```

---

## Ejecución del CRM

Inicia la aplicación ejecutando en la consola:
```bash
python app.py
```
La aplicación estará disponible en tu navegador en la dirección:
[http://127.0.0.1:5000](http://127.0.0.1:5000)
