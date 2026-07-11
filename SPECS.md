# Mini CRM de Captación de Leads

## Objetivo

Desarrollar una aplicación web ligera para registrar manualmente los leads recibidos desde WhatsApp, escribiendo directamente en Google Sheets para eliminar el proceso de registro doble (borrador → limpio) y permitir que los agentes de ventas accedan a los leads en tiempo real.

La prioridad del sistema es reducir el tiempo de registro de cada lead de 10–15 minutos a menos de 15 segundos y centralizar toda la información en Google Sheets como única fuente de verdad.

## Stack tecnológico

### Backend

- Python 3.8+ con Flask
- gspread + oauth2client para la integración con Google Sheets API
- Flask-Login para gestión de sesiones y autenticación
- SQLite local para usuarios, contraseñas y datos de autenticación
- Google Sheets como base de datos principal de leads

### Frontend

- HTML5 + CSS3 puro
- JavaScript vanilla para validaciones y mejoras de UX
- Templates Jinja2 para renderizado en servidor (con template base `base.html`)

### Infraestructura

- Google Sheets como base de datos principal de leads
- SQLite local (`crm.db`) para usuarios y autenticación
- Cuenta de servicio de Google para autenticación API
- Servidor local en localhost:5000
- Sin despliegue en la nube

## Dependencias

```text
flask
gspread
oauth2client
python-dotenv
flask-login
```

## Estructura de archivos

```text
mini-crm-leads/
├── app.py                 # Aplicación Flask principal (rutas y lógica)
├── auth.py                # Blueprint de autenticación (login/logout/decoradores)
├── models.py              # Modelo User y acceso a SQLite
├── crm.db                 # Base de datos SQLite local (se crea al primer arranque)
├── credentials.json       # Credenciales de Google (descargadas)
├── requirements.txt       # Dependencias del proyecto
├── templates/
│   ├── base.html          # Layout base (header, flash, footer)
│   ├── login.html         # Página de inicio de sesión
│   ├── index.html         # Lista de leads
│   ├── add.html           # Formulario de registro
│   ├── edit.html          # Formulario de edición
│   └── setup_error.html   # Pantalla de error de configuración
└── static/
    └── style.css          # Estilos CSS
```

## Autenticación y roles

La aplicación requiere inicio de sesión. Los datos de usuarios se almacenan en SQLite local (las contraseñas **nunca** van a Google Sheets, se hashean con `werkzeug.security`).

### Roles disponibles

- **agente**: usuario regular de ventas. Solo ve y edita sus propios leads. Al registrar un lead, se le asigna automáticamente.
- **marketing** (responsable de marketing): ve y edita todos los leads. Puede reasignar agentes. Puede eliminar leads. Acceso a estadísticas (Fase 4).
- **admin**: mismas capacidades que marketing, más la gestión de usuarios (futuro).

### Permisos por ruta

| Ruta | Agente | Marketing | Admin |
| --- | --- | --- | --- |
| `/login`, `/logout` | sí | sí | sí |
| `GET /` (ver leads) | solo propios | todos | todos |
| `GET/POST /add` | sí (autoasignado) | sí (puede asignar) | sí (puede asignar) |
| `GET/POST /edit/<celular>` | solo sus leads | todos | todos |
| `POST /delete/<celular>` | no | sí | sí |

### Primer arranque

Si no existe ningún usuario en la base de datos local, se crea automáticamente uno con rol **admin**:

- Usuario: `admin`
- Contraseña: `admin123`

Se imprime una advertencia en la consola al crearlo. **Cambia esta contraseña después del primer login** (gestión de contraseñas se implementará en una fase posterior).

### Coincidencia Agente ↔ Usuario

El campo `agente` del sheet (columna H) almacena el **email** del usuario (no el nombre). Esto evita colisiones entre agentes con el mismo nombre y hace el identificador único y estable.

**Importante:** Los agentes deben llenar el campo `agente` con su email personal (ej. `maria.lopez@gmail.com`). La normalización (sin acentos, minúsculas) se aplica para hacer el matching robusto.

En la UI, el sistema resuelve el email al nombre del agente para mostrarlo de forma legible. Si el email no corresponde a ningún usuario activo (ej. un agente dado de baja), se muestra el email tal cual con tooltip.

## Round Robin (Fase 3)

Cada nuevo lead se asigna automáticamente al **siguiente agente activo** de la lista, distribuyendo equitativamente el trabajo entre el equipo.

### Funcionamiento

- Al crear un lead, si no se especifica un agente (o si lo crea un agente), el sistema toma el siguiente de la lista usando el algoritmo Round Robin.
- El contador persiste en la tabla `config` de SQLite (`round_robin_index`).
- Solo los usuarios con rol `agente` y `activo = 1` participan del ciclo.
- Marketing puede **override manual**: al crear un lead, puede elegir un agente específico del select o dejarlo "Sin asignar".

### Valores del selector (formulario de creación)

- `""` (default) → Asignación automática (Round Robin)
- `"__none__"` → Sin asignar
- `<email>` → Agente específico

### Página de configuración

- `GET /config/round-robin` (admin + marketing) — Muestra el próximo agente, el orden del ciclo y un botón para reiniciar.
- `POST /config/round-robin/reset` — Reinicia el contador al primer agente de la lista.

### Cambios de comportamiento

- **Antes**: El agente que creaba el lead quedaba asignado automáticamente a sí mismo.
- **Ahora**: Cualquier lead nuevo se asigna al siguiente del ciclo (puede no ser quien lo creó). Esto balancea la carga y permite que el operador o marketing cree leads sin monopolizar la asignación.

## Estadísticas e informes (Fase 4)

Dashboard de métricas para el responsable de marketing y admin. Permite hacer seguimiento del equipo y del funnel de conversión.

### Ruta

- `GET /stats` (admin + marketing) — Dashboard con KPIs, gráficos y filtros.

### Filtros

- **Periodo**: 7 días / 30 días / 90 días / Todo el tiempo
- **Agente**: selector con todos los agentes activos (default: todos)

### KPIs (tarjetas superiores)

- **Total leads** (en el periodo y filtro seleccionado)
- **Inscritos** (leads con estado `Inscrito`)
- **En seguimiento** (todos los que no son estados terminales: Inscrito, No interesado, No responde, Número incorrecto)
- **Conversión** = `Inscritos / Total × 100`

### Gráficos (Chart.js vía CDN)

- **Doughnut**: Distribución por estado (colores consistentes con los badges de la tabla principal)
- **Bar horizontal**: Top 10 agentes por cantidad de leads
- **Línea**: Leads por día en los últimos 30 días (rellena días sin leads con 0)

### Tabla resumen

- Top 10 intereses/carreras con barra de porcentaje

### Formato de fecha

El parser intenta estos formatos al leer `Fecha Registro` del sheet:
- `%d/%m/%Y` (10/07/2026)
- `%Y-%m-%d` (2026-07-10)
- `%d-%m-%Y`, `%Y/%m/%d`, `%d/%m/%y`, `%Y-%m-%d %H:%M:%S`

Si una fecha no se puede parsear, el lead se incluye en los totales pero se excluye de los filtros por fecha.

## Backup automático (Fase 5)

Copia completa del Google Sheet principal al sheet configurado en `GOOGLE_SHEET_ID_BACKUP`. El objetivo es tener un snapshot del estado en caso de pérdida de datos.

### Rutas

- `GET /backup` (admin) — Historial de backups + estado del último + botón para ejecutar uno manual.
- `POST /backup/run` (admin) — Ejecuta un backup en el momento.

### Funcionamiento

- El backup copia **todas las filas** del sheet principal al sheet de backup.
- El sheet de backup se **sobrescribe** en cada ejecución (es un snapshot del estado actual, no un historial).
- El resultado se registra en la tabla `backups` de SQLite con: timestamp, row_count, status (success/error), error_message.
- Se pueden ver los últimos 20 backups en `/backup`.

### Scheduler

- Usa `APScheduler` (BackgroundScheduler).
- Corre automáticamente **cada día a las 00:00** hora local del servidor.
- Solo se inicializa una vez (evita duplicación con el reloader de Flask en debug).
- Si el job falla, el error queda registrado en la tabla `backups` y se muestra en la UI.

### Configuración

- Variable de entorno requerida: `GOOGLE_SHEET_ID_BACKUP` (Sheet ID del backup).
- El sheet de backup debe existir y la cuenta de servicio debe tener permisos de editor sobre él.
- Si el backup está vacío o no configurado, se muestra un error claro en la UI al intentar ejecutarlo.

## Alcance

### Incluye

- Registrar nuevos leads directamente en Google Sheets.
- Consultar leads registrados desde Google Sheets.
- Editar la información de un lead en Google Sheets.
- Evitar registros duplicados por número de celular.
- Actualizar el estado de un lead.
- Registrar observaciones.
- Buscar rápidamente cualquier lead.
- Eliminar el paso intermedio del "borrador" al escribir directamente en el sheet compartido.

### No incluye

- Automatizaciones avanzadas.
- Integración con WhatsApp (entrada manual).
- Reportes complejos.
- Roles o permisos.
- Embudos de ventas.
- Campañas.
- Recordatorios.
- Migración de datos históricos.

## Integración con Google Sheets

### Configuración requerida

- Proyecto en Google Cloud Console.
- API de Google Sheets habilitada.
- Cuenta de servicio con credenciales JSON.
- Google Sheet compartido con la cuenta de servicio como editor.
- Estructura de columnas definida en la primera fila.

### Estructura del Google Sheets

| Columna | Encabezado | Campo correspondiente |
| --- | --- | --- |
| A | Numero | Identificador secuencial auto-incremental |
| B | Celular | Identificador único del lead |
| C | Nombre | Nombre del lead |
| D | Interés | Carrera/curso/interés |
| E | Estado | Estado actual |
| F | Observaciones | Notas adicionales |
| G | Fecha Registro | Fecha de creación |
| H | Agente | Agente de ventas asignado |
| I | Último contacto | Fecha del último contacto con el lead |
| J | Nota interna | Comentarios privados del equipo |

### Flujo de datos

```text
WhatsApp → [Usuario] → App Flask → Google Sheets API → Google Sheets (en vivo)
   ↓           ↓           ↓              ↓                    ↓
Manual     < 15s     Validación     Automático          Agentes ven
(10 min)   (rápido)   y escritura    (1 paso)           en tiempo real
Lead
```

## Modelo de datos del lead

| Campo | Obligatorio | Descripción | Columna Google Sheets |
| --- | --- | --- | --- |
| Numero | N/A | Identificador secuencial auto-incremental. Lo asigna la app al registrar. | A |
| Celular | Sí | Identificador principal del lead. No debe duplicarse. | B |
| Nombre | No | Nombre del interesado. | C |
| Interés | Sí | Carrera, curso, diplomado, posgrado o cualquier otro interés. | D |
| Estado | Sí | Estado actual del lead. | E |
| Observaciones | No | Información adicional del seguimiento. | F |
| Fecha de registro | Sí | Fecha asociada al registro del lead. | G |
| Agente | No | Nombre del agente de ventas asignado. | H |
| Último contacto | No | Fecha del último contacto realizado al lead. | I |
| Nota interna | No | Comentarios privados del equipo (no se muestran al lead). | J |

## Registro de lead

El formulario debe permitir registrar un lead en pocos segundos, escribiendo directamente en Google Sheets.

### Campos del formulario

- Celular (obligatorio, autofocus)
- Nombre (opcional)
- Interés (obligatorio, texto libre)
- Estado (obligatorio, selector)
- Observaciones (opcional, textarea)
- Fecha de registro (precargada con la fecha actual)

### Flujo de registro

1. El usuario completa el formulario.
2. Se verifica en Google Sheets si el celular ya existe.
3. Si no existe, se agrega una nueva fila al final del sheet.
4. Si existe, se muestra un mensaje de error y se ofrece editar.

La operación completa debe durar menos de 15 segundos.

### Validaciones

- Celular: obligatorio y no duplicado.
- Interés: obligatorio y de texto libre.
- Estado: obligatorio y seleccionado de una lista.
- Fecha: obligatoria, por defecto la fecha actual.

## Interés

El campo Interés no está limitado a carreras y debe permitir registrar cualquier tipo de consulta, por ejemplo:

- Carrera
- Curso
- Diplomado
- Posgrado
- Taller
- Programa
- Otro

El usuario debe poder escribir libremente el interés cuando no exista una opción predefinida.

## Estados

El sistema debe manejar los siguientes estados:

- Nuevo
- Información enviada
- Interesado
- Visitará
- Inscrito
- No interesado
- No responde
- Número incorrecto

La lista de estados debe poder modificarse fácilmente en el futuro mediante un array en Python.

### Mapeo de colores (Fase 2)

Cada estado tiene una clase CSS asociada que define sus colores (background, texto, borde). El mapeo se define en **`ESTADO_BADGE_CLASS`** en `app.py` y es la **fuente única de verdad**. Las clases CSS correspondientes están en `static/style.css` con prefijo `estado-`.

Para agregar un nuevo estado o cambiar un color:

1. Añadir el estado al array `ESTADOS` en `app.py`.
2. Mapearlo a una clase en `ESTADO_BADGE_CLASS` (ej: `'Nuevo estado': 'estado-nuevo-estado'`).
3. Añadir la regla CSS en `static/style.css` (ej: `.estado-nuevo-estado { ... }`).

Si un estado no tiene entrada en el dict, se usa la clase `estado-default` (gris neutro).

## Consulta de leads

Debe existir una vista con todos los registros obtenidos directamente de Google Sheets.

### Información mostrada por cada registro

- Numero
- Fecha
- Celular
- Nombre
- Interés
- Estado
- Agente
- Último contacto
- Observaciones

### Acciones disponibles

- Buscar por celular, nombre, interés o agente
- Editar cualquier campo
- Actualizar estado rápidamente
- Actualizar observaciones
- Eliminar (opcional, con confirmación)

### Comportamiento

- La vista consulta Google Sheets en cada carga (datos en vivo).
- No hay caché para garantizar que los agentes vean lo último.
- Las búsquedas se filtran en memoria después de obtener los datos.

## Búsqueda

La búsqueda debe ser inmediata y debe permitir buscar por:

- Celular
- Nombre
- Interés

### Comportamiento esperado

- El usuario escribe en el campo de búsqueda.
- La aplicación filtra los resultados obtenidos de Google Sheets.
- Los resultados se muestran instantáneamente.
- Si no hay búsqueda, se muestran todos los leads.

## Edición

Toda la información de un lead podrá modificarse directamente en Google Sheets.

### Campos editables

- Celular
- Nombre
- Interés
- Estado
- Observaciones
- Fecha de registro

### Flujo de edición

1. El usuario hace clic en "Editar" junto al lead.
2. Se carga el formulario con los datos actuales.
3. El usuario modifica los campos necesarios.
4. Al guardar, se actualizan las celdas correspondientes en Google Sheets.

La operación debe durar menos de 5 segundos.

### Validaciones en edición

- Al cambiar el celular, se verifica que no esté duplicado con otro lead.
- Si el celular ya existe en otro registro, se muestra un error.

## Validaciones generales

### Celular

- Obligatorio.
- No admite duplicados.
- Formato de texto libre, pudiendo incluir +, -, espacios.

### Interés

- Obligatorio.
- Debe permitir texto libre.
- Mínimo 2 caracteres.

### Estado

- Obligatorio.
- Debe coincidir con la lista predefinida.

### Fecha

- Obligatoria.
- Por defecto, la fecha actual.
- Formato: YYYY-MM-DD.

## Experiencia de usuario

El sistema debe priorizar la velocidad y la simplicidad.

### Objetivos de rendimiento

- Registrar un lead en menos de 15 segundos.
- Buscar un lead en menos de 3 segundos.
- Actualizar un estado en menos de 5 segundos.
- Carga inicial de la página en menos de 2 segundos.

### Diseño de interfaz

- Simple, limpia y minimalista.
- Enfoque único en registro y seguimiento de leads.
- Formularios con campos claros.
- Botones grandes y fáciles de pulsar.
- Feedback visual inmediato con estados de carga y mensajes de éxito/error.
- Navegación intuitiva con botón "Volver" en todas las páginas.

### Accesibilidad y usabilidad

- Autofocus en el primer campo del formulario.
- Tab para navegar entre campos.
- Enter para enviar formularios.
- Confirmación antes de eliminar.
- Mensajes claros de error.

## Seguridad y privacidad

### Almacenamiento

- Los datos se almacenan exclusivamente en Google Sheets.
- El acceso está controlado por las credenciales de Google.
- La aplicación no almacena datos sensibles localmente.

### Configuración

- Las credenciales de Google se guardan en credentials.json.
- Este archivo no debe compartirse ni versionarse.
- La cuenta de servicio tiene acceso solo al sheet específico.

## Requisitos no funcionales

- Responsive: funciona en pantallas de escritorio y tablets.
- Carga rápida: sin assets pesados.
- Formularios simples: máximo 6 campos.
- Navegación intuitiva: menos de 3 clics para cualquier acción.
- Persistencia de datos garantizada por Google Sheets.
- Diseño minimalista.
- Código modular y comentado para futuras ampliaciones.
- Sin dependencias externas de almacenamiento.
- Offline-first: funciona localmente sin internet, salvo para guardar en Google Sheets.

## Limitaciones conocidas

- Dependencia de internet para leer y escribir en Google Sheets.
- Límites de uso de la API de Google Sheets.
- Sin caché: cada consulta es en vivo y puede ser más lenta con miles de registros.
- Un solo usuario por ahora: el operador registra y los agentes solo consultan el sheet.

## Posibles mejoras futuras

- Caché local con SQLite.
- Historial de cambios.
- Integración con WhatsApp.
- Importación desde Excel.
- Exportación a Excel.
- Dashboard con estadísticas.
- Gestión de asesores.
- Etiquetas para categorización adicional.
- Recordatorios de seguimiento.

## Notas de implementación

### Configuración inicial

1. Crear proyecto en Google Cloud Console.
2. Habilitar la API de Google Sheets.
3. Crear cuenta de servicio y descargar credenciales.
4. Compartir el sheet con la cuenta de servicio.
5. Instalar dependencias Python.
6. Ejecutar python app.py.

### Mantenimiento

- Actualizar estados desde el array ESTADOS en app.py.
- Las columnas del sheet deben coincidir con las del código.
- No modificar la estructura del sheet sin actualizar el código.

### Escalabilidad

- Si el sheet crece por encima de 10,000 registros, considerar índices o caché.
- Para múltiples usuarios, considerar migrar a una base de datos SQL.
- La estructura actual soporta hasta 5 millones de celdas.

## Diagrama de flujo

```text
[WhatsApp] → [Usuario] → [App Flask] → [Google Sheets API] → [Google Sheets]
    ↓            ↓            ↓                ↓                    ↓
  Mensaje      Registra      Valida y       Escribe en         Agentes ven
  recibido     manualmente   escribe        tiempo real        en vivo
```
