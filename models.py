import sqlite3
import os
import unicodedata
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# Path de la DB: configurable via variable de entorno (util para tests).
# En produccion queda como 'crm.db' en la raiz del proyecto.
DB_PATH = os.environ.get('CRM_DB_PATH', 'crm.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_name(value):
    """Normaliza un string para comparacion: minusculas, sin acentos, sin espacios extremos."""
    if not value:
        return ''
    nfkd = unicodedata.normalize('NFKD', value)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def get_config(key, default=None):
    conn = get_db()
    row = conn.execute('SELECT value FROM config WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_config(key, value):
    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            rol TEXT NOT NULL CHECK(rol IN ('agente', 'marketing', 'admin')),
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            row_count INTEGER,
            status TEXT NOT NULL,
            error_message TEXT
        )
    ''')
    conn.commit()

    # Migracion: si el admin por defecto existe con email NULL, asignarle uno
    cur = conn.execute('SELECT id, email FROM users WHERE username = ?', ('admin',))
    row = cur.fetchone()
    if row and not row['email']:
        conn.execute('UPDATE users SET email = ? WHERE id = ?', ('admin@local', row['id']))
        conn.commit()

    cur = conn.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0:
        default_password_hash = generate_password_hash('admin123')
        conn.execute(
            'INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
            ('admin', default_password_hash, 'Administrador', 'admin@local', 'admin')
        )
        conn.commit()
        print('=' * 60)
        print('  USUARIO POR DEFECTO CREADO')
        print('  Usuario: admin')
        print('  Contrasena: admin123')
        print('  Email: admin@local')
        print('  IMPORTANTE: Cambia esta contrasena y configura un email real')
        print('=' * 60)

    conn.close()


# Estados posibles y mapeo a clase CSS del badge.
# Fuente unica de verdad: si agregas un estado, modifica ESTADOS y ESTADO_BADGE_CLASS.
ESTADOS = [
    'Nuevo',
    'Información enviada',
    'Interesado',
    'Visitará',
    'Inscrito',
    'No interesado',
    'No responde',
    'Número incorrecto',
]

ESTADO_BADGE_CLASS = {
    'Nuevo': 'estado-nuevo',
    'Información enviada': 'estado-info-enviada',
    'Interesado': 'estado-interesado',
    'Visitará': 'estado-visitara',
    'Inscrito': 'estado-inscrito',
    'No interesado': 'estado-no-interesado',
    'No responde': 'estado-no-responde',
    'Número incorrecto': 'estado-incorrecto',
}

ESTADO_BADGE_CLASS_NORM = {
    normalize_name(k): v for k, v in ESTADO_BADGE_CLASS.items()
}

# Colores hex para usar en graficos (Chart.js) - sincronizados con style.css
ESTADO_COLORS = {
    'estado-nuevo': '#818cf8',
    'estado-info-enviada': '#38bdf8',
    'estado-interesado': '#34d399',
    'estado-visitara': '#fbbf24',
    'estado-inscrito': '#10b981',
    'estado-no-interesado': '#f87171',
    'estado-no-responde': '#cbd5e1',
    'estado-incorrecto': '#f43f5e',
}


class User(UserMixin):
    def __init__(self, id, username, password_hash, nombre, email, rol, activo, fecha_creacion=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.nombre = nombre
        self.email = email
        self.rol = rol
        self.activo = bool(activo)
        self.fecha_creacion = fecha_creacion

    @staticmethod
    def get(user_id):
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def get_by_email(email):
        conn = get_db()
        row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if row:
            return User(**dict(row))
        return None

    @staticmethod
    def all():
        conn = get_db()
        rows = conn.execute('SELECT * FROM users ORDER BY nombre').fetchall()
        conn.close()
        return [User(**dict(r)) for r in rows]

    @staticmethod
    def all_agents():
        """Retorna todos los usuarios con rol 'agente' activos, ordenados por nombre."""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM users WHERE rol = 'agente' AND activo = 1 ORDER BY nombre"
        ).fetchall()
        conn.close()
        return [User(**dict(r)) for r in rows]

    @staticmethod
    def username_exists(username, exclude_id=None):
        conn = get_db()
        if exclude_id is None:
            row = conn.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone()
        else:
            row = conn.execute('SELECT 1 FROM users WHERE username = ? AND id != ?', (username, exclude_id)).fetchone()
        conn.close()
        return row is not None

    @staticmethod
    def email_exists(email, exclude_id=None):
        conn = get_db()
        if exclude_id is None:
            row = conn.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
        else:
            row = conn.execute('SELECT 1 FROM users WHERE email = ? AND id != ?', (email, exclude_id)).fetchone()
        conn.close()
        return row is not None

    @staticmethod
    def create_user(username, password, nombre, email, rol):
        if User.username_exists(username):
            raise ValueError(f"El usuario '{username}' ya existe.")
        if User.email_exists(email):
            raise ValueError(f"El email '{email}' ya esta registrado.")
        if rol not in ('agente', 'marketing', 'admin'):
            raise ValueError(f"Rol invalido: {rol}")
        password_hash = generate_password_hash(password)
        conn = get_db()
        cur = conn.execute(
            'INSERT INTO users (username, password_hash, nombre, email, rol) VALUES (?, ?, ?, ?, ?)',
            (username, password_hash, nombre, email, rol)
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return User.get(user_id)

    @staticmethod
    def update_user(user_id, nombre=None, email=None, rol=None, activo=None):
        user = User.get(user_id)
        if not user:
            raise ValueError(f"Usuario con id {user_id} no encontrado.")

        fields = []
        values = []
        if nombre is not None:
            fields.append('nombre = ?')
            values.append(nombre)
        if email is not None and email != user.email:
            if User.email_exists(email, exclude_id=user_id):
                raise ValueError(f"El email '{email}' ya esta registrado por otro usuario.")
            fields.append('email = ?')
            values.append(email)
        if rol is not None:
            if rol not in ('agente', 'marketing', 'admin'):
                raise ValueError(f"Rol invalido: {rol}")
            fields.append('rol = ?')
            values.append(rol)
        if activo is not None:
            fields.append('activo = ?')
            values.append(1 if activo else 0)

        if not fields:
            return user

        values.append(user_id)
        conn = get_db()
        conn.execute(f'UPDATE users SET {", ".join(fields)} WHERE id = ?', values)
        conn.commit()
        conn.close()
        return User.get(user_id)

    @staticmethod
    def set_password(user_id, new_password):
        user = User.get(user_id)
        if not user:
            raise ValueError(f"Usuario con id {user_id} no encontrado.")
        password_hash = generate_password_hash(new_password)
        conn = get_db()
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def toggle_active(user_id):
        user = User.get(user_id)
        if not user:
            raise ValueError(f"Usuario con id {user_id} no encontrado.")
        new_activo = 0 if user.activo else 1
        conn = get_db()
        conn.execute('UPDATE users SET activo = ? WHERE id = ?', (new_activo, user_id))
        conn.commit()
        conn.close()
        return User.get(user_id)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles):
        return self.rol in roles

    @property
    def is_active(self):
        return self.activo

    @property
    def is_supervisor(self):
        return self.rol in ('marketing', 'admin')

    def get_id(self):
        return str(self.id)


class Backup:
    """Registro de backups automaticos del sheet."""

    @staticmethod
    def create(row_count, status, error_message=None):
        conn = get_db()
        conn.execute(
            'INSERT INTO backups (row_count, status, error_message) VALUES (?, ?, ?)',
            (row_count, status, error_message)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def all(limit=20):
        conn = get_db()
        rows = conn.execute(
            'SELECT * FROM backups ORDER BY id DESC LIMIT ?', (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def last():
        conn = get_db()
        row = conn.execute('SELECT * FROM backups ORDER BY id DESC LIMIT 1').fetchone()
        conn.close()
        return dict(row) if row else None
