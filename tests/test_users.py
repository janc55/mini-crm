"""Tests del modulo de gestion de usuarios (Fase 1+)."""
import os
# Configurar paths aislados ANTES de importar la app
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
    conn.execute('DELETE FROM backups')
    conn.execute('INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
                ('admin', generate_password_hash('admin123'), 'Admin', 'admin@local', 'admin'))
    conn.commit()
    conn.close()


def login(client, username, password):
    client.get('/logout', follow_redirects=True)
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)


print('=' * 60)
print('TEST SUITE: Gestion de Usuarios')
print('=' * 60)

# Test simple
def t1():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    r = c.get('/users')
    assert r.status_code == 200
    assert 'Gestion de Usuarios' in r.get_data(as_text=True)
test('Admin puede acceder a /users', t1)

def t2():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    r = c.post('/users/new', data={
        'username': 'maria', 'password': 'maria123', 'nombre': 'Maria Lopez',
        'email': 'maria@gmail.com', 'rol': 'agente',
    }, follow_redirects=False)
    assert r.status_code == 302
    u = User.get_by_username('maria')
    assert u is not None and u.email == 'maria@gmail.com' and u.rol == 'agente'
test('Crear usuario agente via /users/new', t2)

def t3():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    c.post('/users/new', data={
        'username': 'dup', 'password': 'xxx123', 'nombre': 'X', 'email': 'x@x.com', 'rol': 'agente',
    })
    r = c.post('/users/new', data={
        'username': 'dup', 'password': 'yyy123', 'nombre': 'Y', 'email': 'y@y.com', 'rol': 'agente',
    }, follow_redirects=True)
    assert 'ya existe' in r.get_data(as_text=True)
test('Username duplicado es rechazado', t3)

def t4():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    c.post('/users/new', data={
        'username': 'u1', 'password': 'xxx123', 'nombre': 'X', 'email': 'same@x.com', 'rol': 'agente',
    })
    r = c.post('/users/new', data={
        'username': 'u2', 'password': 'xxx123', 'nombre': 'Y', 'email': 'same@x.com', 'rol': 'agente',
    }, follow_redirects=True)
    assert 'ya esta registrado' in r.get_data(as_text=True)
test('Email duplicado es rechazado', t4)

def t5():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    c.post('/users/new', data={
        'username': 'maria', 'password': 'maria123', 'nombre': 'M', 'email': 'm@m.com', 'rol': 'agente',
    })
    maria_id = User.get_by_username('maria').id
    r = c.post(f'/users/{maria_id}/edit', data={
        'nombre': 'Maria Updated', 'email': 'm@m.com', 'rol': 'marketing', 'activo': 'on',
    }, follow_redirects=False)
    assert r.status_code == 302
    u = User.get(maria_id)
    assert u.nombre == 'Maria Updated' and u.rol == 'marketing'
test('Editar usuario (cambiar nombre y rol)', t5)

def t6():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    c.post('/users/new', data={
        'username': 'maria', 'password': 'maria123', 'nombre': 'M', 'email': 'm@m.com', 'rol': 'agente',
    })
    maria_id = User.get_by_username('maria').id
    c.post(f'/users/{maria_id}/edit', data={
        'nombre': 'M', 'email': 'm@m.com', 'rol': 'agente', 'activo': 'on', 'password': 'newpass1',
    })
    u = User.get(maria_id)
    assert u.check_password('newpass1') and not u.check_password('maria123')
test('Reset de contrasena al editar', t6)

def t7():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    admin_id = User.get_by_username('admin').id
    r = c.post(f'/users/{admin_id}/toggle', follow_redirects=True)
    assert 'desactivarte a ti mismo' in r.get_data(as_text=True)
    assert User.get(admin_id).activo == True
test('Admin no puede desactivarse a si mismo', t7)

def t8():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    c.post('/users/new', data={
        'username': 'maria', 'password': 'maria123', 'nombre': 'M', 'email': 'm@m.com', 'rol': 'agente',
    })
    maria_id = User.get_by_username('maria').id
    c.post(f'/users/{maria_id}/toggle', follow_redirects=False)
    assert User.get(maria_id).activo == False
    c.post(f'/users/{maria_id}/toggle', follow_redirects=False)
    assert User.get(maria_id).activo == True
test('Toggle desactivar/reactivar otro usuario', t8)

def t9():
    setup()
    c = app.test_client()
    c.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
    c.post('/users/new', data={
        'username': 'maria', 'password': 'newpass1', 'nombre': 'M', 'email': 'm@m.com', 'rol': 'agente',
    })
    c.get('/logout', follow_redirects=True)
    c.post('/login', data={'username': 'maria', 'password': 'newpass1'}, follow_redirects=False)
    r = c.get('/users', follow_redirects=False)
    assert r.status_code == 302
    # Verificar que el flash tiene el mensaje
    with c.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
        assert any('administrador' in str(m).lower() for c2, m in flashes)
test('Agente no puede acceder a /users', t9)

def t10():
    setup()
    c = app.test_client()
    login(c, 'admin', 'admin123')
    admin_id = User.get_by_username('admin').id
    r = c.post(f'/users/{admin_id}/edit', data={
        'nombre': 'Admin', 'email': 'admin@local', 'rol': 'agente', 'activo': 'on',
    }, follow_redirects=True)
    assert 'cambiar tu propio rol' in r.get_data(as_text=True)
test('Admin no puede cambiar su propio rol', t10)

print()
print(f'Resultados: {pass_count} pasaron, {fail_count} fallaron')
if fail_count > 0:
    import sys
    sys.exit(1)
