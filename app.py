import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from models import init_db, User, normalize_name, get_config, set_config, ESTADOS, ESTADO_BADGE_CLASS, ESTADO_BADGE_CLASS_NORM
from auth import auth_bp, requires_role
from users import users_bp
from config import config_bp
from stats import stats_bp
from backup import backup_bp

from apscheduler.schedulers.background import BackgroundScheduler
import atexit
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-key-crm')

# Inicializar la base de datos local (usuarios)
init_db()

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesion para acceder.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))


# Registrar blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(config_bp)
app.register_blueprint(stats_bp)
app.register_blueprint(backup_bp)

# Inicializar scheduler para backups automaticos
# Solo se inicia una vez (evitar doble ejecucion con el reloader de Flask en debug)
_scheduler = None
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    if _scheduler is None:
        _scheduler = BackgroundScheduler(daemon=True)
        # Import lazy para evitar circular import
        from backup import run_backup
        # Backup diario a las 00:00 (medianoche)
        _scheduler.add_job(
            func=run_backup,
            trigger='cron',
            hour=0,
            minute=0,
            id='daily_backup',
            name='Backup diario del sheet',
            replace_existing=True,
        )
        _scheduler.start()
        # Apagar el scheduler al cerrar el proceso
        atexit.register(lambda: _scheduler.shutdown(wait=False))
        print('Scheduler de backups iniciado (diario a las 00:00).')

# ID de Google Sheet configurable
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')
SHEET_ID_BACKUP = os.environ.get('GOOGLE_SHEET_ID_BACKUP', '')
CREDENTIALS_FILE = os.environ.get('CRM_CREDENTIALS_FILE', 'credentials.json')

INTERESES = [
    ('Administración de Empresas', 'Administración de Empresas (ADM)'),
    ('Auditoría', 'Auditoría (AUD)'),
    ('Ingeniería de Sistemas', 'Ingeniería de Sistemas (SIS)'),
    ('Derecho', 'Derecho (DER)'),
    ('Medicina', 'Medicina (MED)'),
    ('Odontología', 'Odontología (ODO)'),
    ('Enfermería', 'Enfermería (ENF)'),
    ('Prótesis Dental', 'Prótesis Dental (PRO)'),
    ('Gastronomía, Turismo y Hotelería', 'Gastronomía, Turismo y Hotelería (GTH)'),
    ('Complementario GTH', 'Complementario GTH (COM)'),
    ('Complementario', 'Complementario'),
    ('Curso Guías de Turismo', 'Curso Guías de Turismo'),
    ('Curso Atención y Servicio', 'Curso Atención y Servicio'),
    ('Otro', 'Otro (Escribir...)')
]


def get_sheet():
    if not SHEET_ID:
        raise ValueError("La variable de entorno GOOGLE_SHEET_ID no está configurada.")
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"No se encontró el archivo '{CREDENTIALS_FILE}' en la raíz del proyecto.")

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    return spreadsheet.get_worksheet(0)


def get_initialized_sheet():
    sheet = get_sheet()
    values = sheet.get_all_values()
    if not values:
        headers = ['Numero', 'Celular', 'Nombre', 'Interés', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Último contacto', 'Nota interna']
        sheet.append_row(headers)
    return sheet


def get_all_leads(sheet):
    rows = sheet.get_all_values()
    if not rows:
        return []

    leads = []
    for idx, r in enumerate(rows[1:], start=2):
        row_data = r + [''] * (10 - len(r))
        leads.append({
            'row_idx': idx,
            'numero': row_data[0].strip(),
            'celular': row_data[1].strip(),
            'nombre': row_data[2].strip(),
            'interes': row_data[3].strip(),
            'estado': row_data[4].strip(),
            'observaciones': row_data[5].strip(),
            'fecha_registro': row_data[6].strip(),
            'agente': row_data[7].strip(),
            'ultimo_contacto': row_data[8].strip(),
            'nota_interna': row_data[9].strip(),
        })
    return leads


def can_edit_lead(lead):
    """Determina si el usuario actual puede editar el lead.

    El matching se hace por email (no por nombre) para evitar colisiones
    entre agentes con el mismo nombre. El sheet guarda el email del agente.
    """
    if current_user.is_supervisor:
        return True
    return normalize_name(lead['agente']) == normalize_name(current_user.email)


def get_agent_map():
    """Retorna un dict {email: nombre} de todos los agentes activos, para mostrar en UI."""
    return {u.email: u.nombre for u in User.all_agents()}


def get_next_round_robin_agent():
    """Retorna el proximo agente segun el ciclo de Round Robin y avanza el contador.
    Si no hay agentes activos, retorna None."""
    agents = User.all_agents()
    if not agents:
        return None
    current_index = int(get_config('round_robin_index', 0))
    agent = agents[current_index % len(agents)]
    set_config('round_robin_index', current_index + 1)
    return agent


# Inyectar can_edit_lead y current_user en todas las plantillas
@app.context_processor
def inject_globals():
    return {
        'can_edit_lead': can_edit_lead,
        'current_user': current_user,
        'ESTADO_BADGE_CLASS': ESTADO_BADGE_CLASS,
        'estado_badge_class': lambda estado: ESTADO_BADGE_CLASS_NORM.get(
            normalize_name(estado or ''), 'estado-default'
        ),
    }


@app.errorhandler(Exception)
def handle_error(e):
    error_msg = str(e)
    if isinstance(e, (FileNotFoundError, ValueError)) or "key" in error_msg.lower() or "credentials" in error_msg.lower():
        return render_template('setup_error.html', error=error_msg), 500
    return render_template('setup_error.html', error=f"Ocurrió un error inesperado: {error_msg}"), 500


@app.route('/')
@login_required
def index():
    try:
        sheet = get_initialized_sheet()
        leads = get_all_leads(sheet)
    except Exception as e:
        return handle_error(e)

    agent_map = get_agent_map()

    # Filtrar leads según rol del usuario
    if not current_user.is_supervisor:
        current_email_norm = normalize_name(current_user.email)
        leads = [l for l in leads if normalize_name(l['agente']) == current_email_norm]

    query = request.args.get('q', '').strip().lower()
    if query:
        leads = [
            l for l in leads
            if query in l['celular'].lower()
            or query in l['nombre'].lower()
            or query in l['interes'].lower()
            or query in l['agente'].lower()
            or query in agent_map.get(l['agente'], '').lower()
        ]
    leads = sorted(leads, key=lambda l: l['row_idx'], reverse=True)

    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    per_page = 50
    total_leads = len(leads)
    total_pages = max(1, (total_leads + per_page - 1) // per_page)

    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    leads_paginated = leads[start_idx:end_idx]

    return render_template(
        'index.html',
        leads=leads_paginated,
        query=query,
        page=page,
        total_pages=total_pages,
        total_leads=total_leads,
        per_page=per_page,
        agent_map=agent_map
    )


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_lead():
    if request.method == 'POST':
        celular = request.form.get('celular', '').strip()
        nombre = request.form.get('nombre', '').strip()
        interes = request.form.get('interes', '').strip()
        if interes == 'Otro':
            interes = request.form.get('interes_otro', '').strip()

        estado = request.form.get('estado', '').strip()
        observaciones = request.form.get('observaciones', '').strip()
        fecha_registro = request.form.get('fecha_registro', '').strip()
        agente = request.form.get('agente', '').strip()
        ultimo_contacto = request.form.get('ultimo_contacto', '').strip()
        nota_interna = request.form.get('nota_interna', '').strip()

        if not celular:
            flash("El celular es obligatorio.", "error")
            return render_template('add.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), form=request.form)
        if not interes or len(interes) < 2:
            flash("El campo Interés es obligatorio y debe tener al menos 2 caracteres.", "error")
            return render_template('add.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), form=request.form)
        if estado not in ESTADOS:
            flash("El estado seleccionado no es válido.", "error")
            return render_template('add.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), form=request.form)
        if not fecha_registro:
            fecha_registro = datetime.today().strftime('%d/%m/%Y')

        # Asignacion de agente:
        #   ""  -> Round Robin (default, agents siempre)
        #   "__none__" -> Sin asignar (marketing puede elegir esto)
        #   email -> Agente especifico (marketing puede override)
        if agente == '__none__':
            agente = ''
        elif not agente or current_user.has_role('agente'):
            # Round Robin: agentes siempre lo usan, marketing lo usa si no especifico
            rr_agent = get_next_round_robin_agent()
            if rr_agent:
                agente = rr_agent.email

        try:
            sheet = get_initialized_sheet()
            leads = get_all_leads(sheet)

            for lead in leads:
                if lead['celular'] == celular:
                    return render_template('add.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), form=request.form, duplicate_celular=celular)

            max_numero = 0
            for l in leads:
                try:
                    n = int(l['numero'])
                    if n > max_numero:
                        max_numero = n
                except (ValueError, TypeError):
                    continue
            next_numero = str(max_numero + 1)

            sheet.append_row([next_numero, celular, nombre, interes, estado, observaciones, fecha_registro, agente, ultimo_contacto, nota_interna])
            flash("Lead registrado exitosamente.", "success")
            return redirect(url_for('index'))
        except Exception as e:
            return handle_error(e)

    hoy = datetime.today().strftime('%d/%m/%Y')
    default_form = {
        'fecha_registro': hoy,
        'estado': ESTADOS[0],
        'agente': '',  # Round Robin por default
    }
    return render_template('add.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), form=default_form)


@app.route('/edit/<celular>', methods=['GET', 'POST'])
@login_required
def edit_lead(celular):
    celular = celular.strip()
    try:
        sheet = get_initialized_sheet()
        leads = get_all_leads(sheet)
    except Exception as e:
        return handle_error(e)

    lead_to_edit = None
    for l in leads:
        if l['celular'] == celular:
            lead_to_edit = l
            break

    if not lead_to_edit:
        flash(f"No se encontró el lead con celular {celular}.", "error")
        return redirect(url_for('index'))

    if not can_edit_lead(lead_to_edit):
        flash("No tienes permisos para editar este lead.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        nuevo_celular = request.form.get('celular', '').strip()
        nombre = request.form.get('nombre', '').strip()
        interes = request.form.get('interes', '').strip()
        if interes == 'Otro':
            interes = request.form.get('interes_otro', '').strip()

        estado = request.form.get('estado', '').strip()
        observaciones = request.form.get('observaciones', '').strip()
        fecha_registro = request.form.get('fecha_registro', '').strip()
        agente = request.form.get('agente', '').strip()
        ultimo_contacto = request.form.get('ultimo_contacto', '').strip()
        nota_interna = request.form.get('nota_interna', '').strip()

        if not nuevo_celular:
            flash("El celular es obligatorio.", "error")
            return render_template('edit.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), lead=request.form, original_celular=celular)
        if not interes or len(interes) < 2:
            flash("El campo Interés es obligatorio y debe tener al menos 2 caracteres.", "error")
            return render_template('edit.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), lead=request.form, original_celular=celular)
        if estado not in ESTADOS:
            flash("El estado seleccionado no es válido.", "error")
            return render_template('edit.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), lead=request.form, original_celular=celular)
        if not fecha_registro:
            fecha_registro = datetime.today().strftime('%Y-%m-%d')

        if nuevo_celular != celular:
            for l in leads:
                if l['celular'] == nuevo_celular:
                    flash(f"El celular '{nuevo_celular}' ya está registrado en otro lead.", "error")
                    return render_template('edit.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), lead=request.form, original_celular=celular)

        # Los agentes no pueden reasignar el agente: se preserva el email del dueno actual
        if current_user.has_role('agente'):
            agente = lead_to_edit['agente']

        try:
            row_idx = lead_to_edit['row_idx']
            range_name = f"A{row_idx}:J{row_idx}"
            sheet.update(range_name, [[lead_to_edit['numero'], nuevo_celular, nombre, interes, estado, observaciones, fecha_registro, agente, ultimo_contacto, nota_interna]])
            flash("Lead actualizado exitosamente.", "success")
            return redirect(url_for('index'))
        except Exception as e:
            return handle_error(e)

    return render_template('edit.html', estados=ESTADOS, intereses=INTERESES, agents=User.all_agents(), lead=lead_to_edit, original_celular=celular)


@app.route('/delete/<celular>', methods=['POST'])
@login_required
@requires_role('marketing', 'admin')
def delete_lead(celular):
    celular = celular.strip()
    try:
        sheet = get_initialized_sheet()
        leads = get_all_leads(sheet)

        row_idx = None
        for l in leads:
            if l['celular'] == celular:
                row_idx = l['row_idx']
                break

        if row_idx:
            sheet.delete_rows(row_idx)
            flash("Lead eliminado exitosamente.", "success")
        else:
            flash("No se pudo encontrar el lead para eliminar.", "error")

        return redirect(url_for('index'))
    except Exception as e:
        return handle_error(e)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
