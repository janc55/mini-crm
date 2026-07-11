"""Tests del backup automatico (Fase 5)."""
import os
os.environ['CRM_DB_PATH'] = os.path.join(os.path.dirname(__file__), 'test_crm.db')
os.environ['CRM_CREDENTIALS_FILE'] = os.path.join(os.path.dirname(__file__), 'test_credentials.json')
os.environ['GOOGLE_SHEET_ID'] = 'test_id'
os.environ['GOOGLE_SHEET_ID_BACKUP'] = 'test_backup_id'

from app import app
from werkzeug.security import generate_password_hash
from models import get_db, Backup
from backup import run_backup
from unittest.mock import patch, MagicMock

pass_count = 0
fail_count = 0


def test(name, fn):
    global pass_count, fail_count
    try:
        fn()
        print(f'  PASS  {name}')
        pass_count += 1
    except AssertionError as e:
        print(f'  FAIL  {name}: {e}')
        fail_count += 1
    except Exception as e:
        print(f'  ERROR {name}: {e}')
        fail_count += 1


def setup():
    conn = get_db()
    conn.execute('DELETE FROM users')
    conn.execute('DELETE FROM backups')
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('admin', generate_password_hash('admin123'), 'Admin', 'admin@local', 'admin'))
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('maria', generate_password_hash('maria123'), 'Maria', 'maria@gmail.com', 'agente'))
    conn.commit()
    conn.close()


def login(client, username, password):
    client.get('/logout', follow_redirects=True)
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)


print('=' * 60)
print('TEST SUITE: Backup automatico (Fase 5)')
print('=' * 60)

HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
rows = [HEADER, ['1', '+56911111111', 'Lead 1', 'Sistemas', 'Nuevo', '', '01/01/2026', '', '', '']]

main_sheet = MagicMock()
main_sheet.get_all_values.return_value = rows
backup_sheet = MagicMock()
backup_sheet.clear = MagicMock()
backup_sheet.update = MagicMock()
backup_spreadsheet = MagicMock()
backup_spreadsheet.get_worksheet = MagicMock(return_value=backup_sheet)
gspread_client = MagicMock()
gspread_client.open_by_key = MagicMock(return_value=backup_spreadsheet)


def t1():
    setup()
    with patch('app.get_sheet', return_value=main_sheet), \
         patch('oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_name') as mock_creds, \
         patch('gspread.authorize', return_value=gspread_client):
        mock_creds.return_value = MagicMock()
        success, row_count, error = run_backup()
        assert success is True
        assert row_count == 1
        assert error is None
        last = Backup.last()
        assert last['status'] == 'success'
        assert last['row_count'] == 1
test('run_backup exitoso copia filas y registra', t1)


def t2():
    setup()
    with patch('app.SHEET_ID_BACKUP', ''):
        success, row_count, error = run_backup()
        assert success is False
        assert 'GOOGLE_SHEET_ID_BACKUP' in error
        last = Backup.last()
        assert last['status'] == 'error'
test('run_backup registra error si SHEET_ID_BACKUP no esta', t2)


def t3():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    r = c.get('/backup')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Backups del sheet' in body
test('GET /backup accesible para admin', t3)


def t4():
    setup()
    c = app.test_client()
    login(c, 'maria', 'maria123')
    r = c.get('/backup', follow_redirects=False)
    assert r.status_code == 302
test('GET /backup bloqueado para agentes', t4)


def t5():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    backup_sheet.update.reset_mock()
    with patch('app.get_sheet', return_value=main_sheet), \
         patch('oauth2client.service_account.ServiceAccountCredentials.from_json_keyfile_name') as mock_creds, \
         patch('gspread.authorize', return_value=gspread_client):
        mock_creds.return_value = MagicMock()
        r = c.post('/backup/run', follow_redirects=False)
        assert r.status_code == 302
        assert backup_sheet.update.called
test('POST /backup/run ejecuta backup', t5)


def t6():
    setup()
    c = app.test_client()
    login(c, 'maria', 'maria123')
    r = c.post('/backup/run', follow_redirects=False)
    assert r.status_code == 302
test('POST /backup/run bloqueado para agentes', t6)


print()
print(f'Resultados: {pass_count} pasaron, {fail_count} fallaron')
if fail_count > 0:
    import sys
    sys.exit(1)
