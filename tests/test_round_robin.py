"""Tests del Round Robin (Fase 3)."""
import os
os.environ['CRM_DB_PATH'] = os.path.join(os.path.dirname(__file__), 'test_crm.db')
os.environ['CRM_CREDENTIALS_FILE'] = os.path.join(os.path.dirname(__file__), 'test_credentials.json')
os.environ['GOOGLE_SHEET_ID'] = 'test_id'

from app import app, get_next_round_robin_agent, get_config
from models import get_db, User, set_config
from werkzeug.security import generate_password_hash
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
    conn.execute('DELETE FROM config')
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('admin', generate_password_hash('admin123'), 'Admin', 'admin@local', 'admin'))
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('maria', generate_password_hash('maria123'), 'Maria Lopez', 'maria@gmail.com', 'agente'))
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('pedro', generate_password_hash('pedro123'), 'Pedro Garcia', 'pedro@gmail.com', 'agente'))
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('ana', generate_password_hash('ana123'), 'Ana Diaz', 'ana@gmail.com', 'agente'))
    conn.commit()
    conn.close()


def login(client, username, password):
    client.get('/logout', follow_redirects=True)
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)


print('=' * 60)
print('TEST SUITE: Round Robin (Fase 3)')
print('=' * 60)

def t1():
    setup()
    set_config('round_robin_index', 0)
    # Orden alfabetico: ana, maria, pedro
    a1 = get_next_round_robin_agent()
    a2 = get_next_round_robin_agent()
    a3 = get_next_round_robin_agent()
    a4 = get_next_round_robin_agent()
    assert a1.email == 'ana@gmail.com'
    assert a2.email == 'maria@gmail.com'
    assert a3.email == 'pedro@gmail.com'
    assert a4.email == 'ana@gmail.com'
test('Round Robin cicla entre agentes activos', t1)

def t2():
    setup()
    pedro = User.get_by_username('pedro')
    User.update_user(pedro.id, activo=False)
    set_config('round_robin_index', 0)
    a1 = get_next_round_robin_agent()
    a2 = get_next_round_robin_agent()
    a3 = get_next_round_robin_agent()
    assert a1.email == 'ana@gmail.com'
    assert a2.email == 'maria@gmail.com'
    assert a3.email == 'ana@gmail.com'
    User.update_user(pedro.id, activo=True)
test('Agentes inactivos se excluyen del ciclo', t2)

def t3():
    setup()
    for u in [User.get_by_username('maria'), User.get_by_username('pedro'), User.get_by_username('ana')]:
        User.update_user(u.id, activo=False)
    result = get_next_round_robin_agent()
    assert result is None
    for u in [User.get_by_username('maria'), User.get_by_username('pedro'), User.get_by_username('ana')]:
        User.update_user(u.id, activo=True)
test('Sin agentes activos, retorna None', t3)

def t4():
    setup()
    set_config('round_robin_index', 5)
    c = app.test_client()
    login(c, 'admin', 'admin123')
    c.post('/config/round-robin/reset', follow_redirects=False)
    idx = int(get_config('round_robin_index', 0))
    assert idx == 0
test('Reset del ciclo funciona', t4)

def t5():
    setup()
    set_config('round_robin_index', 0)
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = [HEADER]
    mock_sheet.append_row = MagicMock()
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'maria', 'maria123')
        c.post('/add', data={
            'celular': '+56911111111', 'nombre': 'Test', 'interes': 'Sistemas',
            'estado': 'Nuevo', 'fecha_registro': '10/07/2026', 'agente': '',
        }, follow_redirects=False)
        row = mock_sheet.append_row.call_args[0][0]
        # El primer agente en orden alfabetico es Ana, no Maria
        assert row[7] != 'maria@gmail.com'
        assert row[7] == 'ana@gmail.com'
test('Agente que crea NO se asigna a si mismo (Round Robin)', t5)

def t6():
    setup()
    set_config('round_robin_index', 0)
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = [HEADER]
    mock_sheet.append_row = MagicMock()
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'admin', 'admin123')
        c.post('/add', data={
            'celular': '+56922222222', 'nombre': 'T2', 'interes': 'Sistemas',
            'estado': 'Nuevo', 'fecha_registro': '10/07/2026', 'agente': 'ana@gmail.com',
        }, follow_redirects=False)
        row = mock_sheet.append_row.call_args[0][0]
        assert row[7] == 'ana@gmail.com'
test('Marketing puede override manual con agente especifico', t6)

def t7():
    setup()
    set_config('round_robin_index', 0)
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = [HEADER]
    mock_sheet.append_row = MagicMock()
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'admin', 'admin123')
        idx_before = int(get_config('round_robin_index', 0))
        c.post('/add', data={
            'celular': '+56933333333', 'nombre': 'T3', 'interes': 'Sistemas',
            'estado': 'Nuevo', 'fecha_registro': '10/07/2026', 'agente': '__none__',
        }, follow_redirects=False)
        row = mock_sheet.append_row.call_args[0][0]
        assert row[7] == ''
        idx_after = int(get_config('round_robin_index', 0))
        assert idx_before == idx_after
test('"Sin asignar" no avanza el contador del ciclo', t7)

def t8():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    r = c.get('/config/round-robin')
    assert r.status_code == 200
    assert 'Round Robin' in r.get_data(as_text=True) or 'Asignacion' in r.get_data(as_text=True)
test('Pagina /config/round-robin accesible para admin', t8)

def t9():
    setup()
    c = app.test_client()
    login(c, 'maria', 'maria123')
    r = c.get('/config/round-robin', follow_redirects=False)
    assert r.status_code == 302
test('Agente NO puede acceder a /config/round-robin', t9)

print()
print(f'Resultados: {pass_count} pasaron, {fail_count} fallaron')
if fail_count > 0:
    import sys
    sys.exit(1)
