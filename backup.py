import os
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import Backup

logger = logging.getLogger(__name__)

backup_bp = Blueprint('backup', __name__)


def run_backup():
    """Copia todos los datos del sheet principal al sheet de backup.

    Registra el resultado (exito o error) en la tabla backups.
    Retorna (success: bool, row_count: int, error: str or None).
    """
    # Import lazy para evitar circular import con app.py
    from app import get_sheet, SHEET_ID_BACKUP, CREDENTIALS_FILE

    if not SHEET_ID_BACKUP:
        msg = 'GOOGLE_SHEET_ID_BACKUP no esta configurado en .env'
        Backup.create(0, 'error', msg)
        return False, 0, msg

    if not os.path.exists(CREDENTIALS_FILE):
        msg = f"No se encontro '{CREDENTIALS_FILE}'"
        Backup.create(0, 'error', msg)
        return False, 0, msg

    try:
        # 1) Leer datos del sheet principal
        main_sheet = get_sheet()
        all_values = main_sheet.get_all_values()
        row_count = len(all_values) - 1 if all_values else 0  # restar cabecera

        # 2) Conectar al sheet de backup
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        backup_spreadsheet = client.open_by_key(SHEET_ID_BACKUP)
        backup_sheet = backup_spreadsheet.get_worksheet(0)

        # 3) Limpiar y escribir
        backup_sheet.clear()
        if all_values:
            backup_sheet.update('A1', all_values)

        Backup.create(row_count, 'success', None)
        logger.info(f'Backup exitoso: {row_count} filas')
        return True, row_count, None

    except Exception as e:
        error_msg = str(e)
        Backup.create(0, 'error', error_msg)
        logger.error(f'Error en backup: {error_msg}')
        return False, 0, error_msg


@backup_bp.route('/backup')
@login_required
def list_backups():
    if not current_user.has_role('admin'):
        flash('Solo el administrador puede acceder a los backups.', 'error')
        return redirect(url_for('index'))
    backups = Backup.all(limit=20)
    return render_template('backup/list.html', backups=backups, last_backup=Backup.last())


@backup_bp.route('/backup/run', methods=['POST'])
@login_required
def run_backup_now():
    if not current_user.has_role('admin'):
        flash('Solo el administrador puede ejecutar backups.', 'error')
        return redirect(url_for('index'))
    success, row_count, error = run_backup()
    if success:
        flash(f'Backup completado: {row_count} filas copiadas.', 'success')
    else:
        flash(f'Error en backup: {error}', 'error')
    return redirect(url_for('backup.list_backups'))
