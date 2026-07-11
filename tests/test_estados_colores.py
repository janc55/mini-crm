"""Tests de colores de estados (Fase 2)."""
import os
os.environ['CRM_DB_PATH'] = os.path.join(os.path.dirname(__file__), 'test_crm.db')
os.environ['CRM_CREDENTIALS_FILE'] = os.path.join(os.path.dirname(__file__), 'test_credentials.json')
os.environ['GOOGLE_SHEET_ID'] = 'test_id'

from app import app, ESTADOS, ESTADO_BADGE_CLASS
from models import get_db, User
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


print('=' * 60)
print('TEST SUITE: Mapeo de colores (Fase 2)')
print('=' * 60)


def t1():
    for estado in ESTADOS:
        assert estado in ESTADO_BADGE_CLASS, f'Falta mapeo para {estado}'
test('Todos los estados tienen clase CSS mapeada', t1)

def t2():
    conn = get_db()
    conn.execute('DELETE FROM users')
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('admin', generate_password_hash('admin123'), 'Admin', 'admin@local', 'admin'))
    conn.commit()
    conn.close()

    HEADER = ['Numero', 'Celular', 'Nombre', 'Interes', 'Estado', 'Observaciones', 'Fecha Registro', 'Agente', 'Ultimo contacto', 'Nota interna']
    rows = [HEADER]
    for i, estado in enumerate(ESTADOS):
        rows.append([str(i+1), f'+5691111111{i}', f'Lead {i+1}', 'Sistemas', estado, '', '01/01/2026', '', '', ''])

    mock_sheet = MagicMock()
    mock_sheet.get_all_values.return_value = rows
    with patch('app.get_initialized_sheet', return_value=mock_sheet):
        c = app.test_client()
        c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
        body = c.get('/').get_data(as_text=True)
        for estado in ESTADOS:
            css_class = ESTADO_BADGE_CLASS[estado]
            short = css_class.replace('estado-', '')
            assert f'estado-{short}' in body, f'Falta clase {css_class} para {estado}'
test('Render correcto de cada estado en la tabla', t2)

def t3():
    from models import ESTADO_BADGE_CLASS_NORM
    estado_sin_tilde = 'Numero incorrecto'
    assert ESTADO_BADGE_CLASS_NORM.get('numero incorrecto') is not None
test('Lookup normalizado para "Numero incorrecto" (sin tilde)', t3)

print()
print(f'Resultados: {pass_count} pasaron, {fail_count} fallaron')
if fail_count > 0:
    import sys
    sys.exit(1)
