from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User

auth_bp = Blueprint('auth', __name__)


def requires_role(*roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_role(*roles):
                flash('No tienes permisos para acceder a esta seccion.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.get_by_username(username)
        if user and user.activo and user.check_password(password):
            login_user(user, remember=True)
            flash(f'Bienvenido, {user.nombre}!', 'success')
            next_url = request.args.get('next')
            if not next_url or not next_url.startswith('/'):
                next_url = url_for('index')
            return redirect(next_url)
        else:
            flash('Usuario o contrasena incorrectos.', 'error')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesion cerrada correctamente.', 'success')
    return redirect(url_for('auth.login'))
