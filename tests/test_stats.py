"""Tests del dashboard de estadisticas (Fase 4)."""
import os
os.environ['CRM_DB_PATH'] = os.path.join(os.path.dirname(__file__), 'test_crm.db')
os.environ['CRM_CREDENTIALS_FILE'] = os.path.join(os.path.dirname(__file__), 'test_credentials.json')
os.environ['GOOGLE_SHEET_ID'] = 'test_id'

from datetime import datetime, timedelta
from app import app, get_all_leads
from werkzeug.security import generate_password_hash
from models import get_db, User
from stats import parse_date, compute_stats
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
                ('admin', generate_password_hash('admin123'), 'Admin', 'admin@local', 'admin'))
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
print('TEST SUITE: Estadisticas (Fase 4)')
print('=' * 60)

def t1():
    assert parse_date('10/07/2026') is not None
    assert parse_date('2026-07-10') is not None
    assert parse_date('') is None
    assert parse_date('not a date') is None
test('parse_date maneja varios formatos', t1)

def t2():
    today = datetime.today().date()
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    rows = [HEADER]
    for i in range(3):
        rows.append([str(i+1), f'+5691111{i:02d}', f'M{i+1}', 'Sistemas', 'Nuevo', '', today.strftime('%d/%m/%Y'), 'maria@gmail.com', '', ''])
    for i in range(4):
        rows.append([str(i+4), f'+5692222{i:02d}', f'P{i+1}', 'Derecho', 'Inscrito' if i == 0 else 'Interesado', '', today.strftime('%d/%m/%Y'), 'pedro@gmail.com', '', ''])
    old = (today - timedelta(days=100)).strftime('%d/%m/%Y')
    rows.append(['8', '+56933333301', 'Old1', 'Medicina', 'Inscrito', '', old, 'maria@gmail.com', '', ''])
    rows.append(['9', '+56933333302', 'Old2', 'Medicina', 'Nuevo', '', old, 'pedro@gmail.com', '', ''])
    rows.append(['10', '+56944444444', 'None', 'Sistemas', 'Nuevo', '', today.strftime('%d/%m/%Y'), '', '', ''])

    class FakeSheet:
        def __init__(self, data): self.data = data
        def get_all_values(self): return self.data
    leads = get_all_leads(FakeSheet(rows))
    stats = compute_stats(leads)
    assert stats['total_leads'] == 10
    assert stats['inscritos'] == 2
    assert stats['en_seguimiento'] == 8
    assert stats['conversion_rate'] == 20.0
test('compute_stats calcula KPIs correctos', t2)

def t3():
    today = datetime.today().date()
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    rows = [HEADER]
    for i in range(3):
        rows.append([str(i+1), f'+5691111{i:02d}', f'M{i+1}', 'Sistemas', 'Nuevo', '', today.strftime('%d/%m/%Y'), 'maria@gmail.com', '', ''])
    class FakeSheet:
        def __init__(self, data): self.data = data
        def get_all_values(self): return self.data
    leads = get_all_leads(FakeSheet(rows))
    s_maria = compute_stats(leads, agent='maria@gmail.com')
    assert s_maria['total_leads'] == 3
test('Filtro por agente funciona', t3)

def t4():
    today = datetime.today().date()
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    rows = [HEADER, ['1', '+56911111111', 'L1', 'SIS', 'Nuevo', '', today.strftime('%d/%m/%Y'), 'maria@gmail.com', '', '']]
    class FakeSheet:
        def __init__(self, data): self.data = data
        def get_all_values(self): return self.data
    leads = get_all_leads(FakeSheet(rows))
    stats = compute_stats(leads, date_from=today - timedelta(days=29), date_to=today)
    assert stats['total_leads'] == 1
    assert len(stats['by_day']) == 30
test('Filtro por fecha y by_day con 30 dias', t4)

def t5():
    setup()
    today = datetime.today().date()
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    rows = [HEADER, ['1', '+56911111111', 'L1', 'SIS', 'Nuevo', '', today.strftime('%d/%m/%Y'), 'maria@gmail.com', '', '']]
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = rows
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'admin', 'admin123')
        r = c.get('/stats')
        body = r.get_data(as_text=True)
        assert r.status_code == 200
        assert 'Total leads' in body
        assert 'chart-estados' in body
        assert 'chart-agents' in body
        assert 'chart-days' in body
test('GET /stats renderiza dashboard para admin', t5)

def t6():
    setup()
    c = app.test_client()
    login(c, 'maria', 'maria123')
    r = c.get('/stats', follow_redirects=False)
    assert r.status_code == 302
test('Agente NO puede acceder a /stats', t6)

def t7():
    setup()
    today = datetime.today().date()
    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    rows = [HEADER, ['1', '+56911111111', 'L1', 'SIS', 'Nuevo', '', today.strftime('%d/%m/%Y'), 'maria@gmail.com', '', '']]
    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = rows
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        login(c, 'admin', 'admin123')
        r = c.get('/stats?range=7d')
        body = r.get_data(as_text=True)
        assert '7 dias' in body
        r = c.get('/stats?range=30d&agent=maria@gmail.com')
        body = r.get_data(as_text=True)
        assert '30 dias' in body
        assert 'maria@gmail.com' in body
test('Filtros en URL funcionan', t7)

print()
print(f'Resultados: {pass_count} pasaron, {fail_count} fallaron')
if fail_count > 0:
    import sys
    sys.exit(1)
