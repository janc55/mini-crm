"""Tests del matching por email (Fase 1.5)."""
import os
os.environ['CRM_DB_PATH'] = os.path.join(os.path.dirname(__file__), 'test_crm.db')
os.environ['CRM_CREDENTIALS_FILE'] = os.path.join(os.path.dirname(__file__), 'test_credentials.json')
os.environ['GOOGLE_SHEET_ID'] = 'test_id'
os.environ['GOOGLE_SHEET_ID_BACKUP'] = 'test_backup_id'

from app import app
from werkzeug.security import generate_password_hash
from models import get_db, User
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
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('maria', generate_password_hash('maria123'), 'Maria Lopez', 'maria@gmail.com', 'agente'))
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('pedro', generate_password_hash('pedro123'), 'Pedro Garcia', 'pedro@gmail.com', 'agente'))
    conn.commit()
    conn.close()


def login(client, username, password):
    client.get('/logout', follow_redirects=True)
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)


print('=' * 60)
print('TEST SUITE: Matching por email (Fase 1.5)')
print('=' * 60)

HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
rows_data = [
    HEADER,
    ['1', '+56911111111', 'Lead 1', 'Sistemas', 'Nuevo', '', '01/01/2026', 'maria@gmail.com', '', ''],
    ['2', '+56922222222', 'Lead 2', 'Medicina', 'Nuevo', '', '02/01/2026', 'pedro@gmail.com', '', ''],
    ['3', '+56933333333', 'Lead 3', 'Sistemas', 'Nuevo', '', '03/01/2026', '', '', ''],
    ['4', '+56944444444', 'Lead 4', 'Sistemas', 'Nuevo', '', '04/01/2026', 'Maria@Gmail.COM', '', ''],
]

def t1():
    setup()
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = rows_data
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'maria', 'maria123')
        body = c.get('/').get_data(as_text=True)
        assert 'Lead 1' in body
        assert 'Lead 2' not in body
        assert 'Lead 3' not in body
        assert 'Lead 4' in body  # normalizacion
        assert 'Maria Lopez' in body  # nombre resuelto desde email
test('Maria ve solo sus leads (incluyendo normalizacion de mayusculas)', t1)

def t2():
    setup()
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = rows_data
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'pedro', 'pedro123')
        body = c.get('/').get_data(as_text=True)
        assert 'Lead 2' in body
        assert 'Lead 1' not in body
test('Pedro ve solo sus leads', t2)

def t3():
    setup()
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = rows_data
    mock_sheet.append_row = MagicMock()
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'maria', 'maria123')
        c.post('/add', data={
            'celular': '+56999999999', 'nombre': 'Test', 'interes': 'Sistemas',
            'estado': 'Nuevo', 'fecha_registro': '10/07/2026', 'agente': 'fake@email.com',
        }, follow_redirects=False)
        row = mock_sheet.append_row.call_args[0][0]
        assert row[7] == 'maria@gmail.com'
test('Maria autoasigna su email al crear lead (ignora valor del form)', t3)

print()
print(f'Resultados: {pass_count} pasaron, {fail_count} fallaron')
if fail_count > 0:
    import sys
    sys.exit(1)
