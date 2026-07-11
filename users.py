from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import User

users_bp = Blueprint('users', __name__)


def admin_required(f):
    """Requiere rol admin. Renderiza 403 si el usuario no es admin."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.has_role('admin'):
            flash('Solo el administrador puede gestionar usuarios.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


@users_bp.route('/users')
@admin_required
def list_users():
    users = User.all()
    return render_template('users/list.html', users=users)


@users_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def new_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip()
        rol = request.form.get('rol', '').strip()

        form_data = {
            'username': username,
            'nombre': nombre,
            'email': email,
            'rol': rol,
        }

        if not username or not password or not nombre or not email or not rol:
            flash('Todos los campos son obligatorios.', 'error')
            return render_template('users/form.html', user=form_data, is_new=True)
        if len(password) < 6:
            flash('La contrasena debe tener al menos 6 caracteres.', 'error')
            return render_template('users/form.html', user=form_data, is_new=True)
        if '@' not in email or '.' not in email:
            flash('El email no es valido.', 'error')
            return render_template('users/form.html', user=form_data, is_new=True)

        try:
            User.create_user(username=username, password=password, nombre=nombre, email=email, rol=rol)
            flash(f'Usuario "{username}" creado exitosamente.', 'success')
            return redirect(url_for('users.list_users'))
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('users/form.html', user=form_data, is_new=True)

    return render_template('users/form.html', user={}, is_new=True)


@users_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.get(user_id)
    if not user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('users.list_users'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip()
        rol = request.form.get('rol', '').strip()
        activo = request.form.get('activo') == 'on'
        new_password = request.form.get('password', '').strip()

        if not nombre or not email or not rol:
            flash('Nombre, email y rol son obligatorios.', 'error')
            return render_template('users/form.html', user=user, is_new=False)
        if '@' not in email or '.' not in email:
            flash('El email no es valido.', 'error')
            return render_template('users/form.html', user=user, is_new=False)
        if new_password and len(new_password) < 6:
            flash('La contrasena debe tener al menos 6 caracteres.', 'error')
            return render_template('users/form.html', user=user, is_new=False)

        # No permitir que el admin se desactive a si mismo
        if user.id == current_user.id and not activo:
            flash('No puedes desactivarte a ti mismo.', 'error')
            return render_template('users/form.html', user=user, is_new=False)
        # No permitir que el admin se cambie su propio rol (para no perder acceso)
        if user.id == current_user.id and rol != user.rol:
            flash('No puedes cambiar tu propio rol.', 'error')
            return render_template('users/form.html', user=user, is_new=False)

        try:
            User.update_user(user_id, nombre=nombre, email=email, rol=rol, activo=activo)
            if new_password:
                User.set_password(user_id, new_password)
            flash(f'Usuario "{user.username}" actualizado.', 'success')
            return redirect(url_for('users.list_users'))
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('users/form.html', user=user, is_new=False)

    return render_template('users/form.html', user=user, is_new=False)


@users_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = User.get(user_id)
    if not user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('users.list_users'))
    if user.id == current_user.id:
        flash('No puedes desactivarte a ti mismo.', 'error')
        return redirect(url_for('users.list_users'))
    user = User.toggle_active(user_id)
    estado = 'activado' if user.activo else 'desactivado'
    flash(f'Usuario "{user.username}" {estado}.', 'success')
    return redirect(url_for('users.list_users'))


@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Perfil propio: cualquier usuario puede editar su nombre y contrasena.
    El email NO es editable por el usuario (debe pedirlo al admin) porque cambiarlo
    desvincula sus leads previos asignados en el sheet."""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not nombre or len(nombre) < 2:
            flash('El nombre es obligatorio (minimo 2 caracteres).', 'error')
            return render_template('profile.html')

        try:
            User.update_user(current_user.id, nombre=nombre)
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('profile.html')

        # Cambio de contrasena opcional
        if new_password:
            if not current_password:
                flash('Para cambiar la contrasena debes ingresar la actual.', 'error')
                return render_template('profile.html')
            if not current_user.check_password(current_password):
                flash('La contrasena actual es incorrecta.', 'error')
                return render_template('profile.html')
            if new_password != confirm_password:
                flash('La nueva contrasena y su confirmacion no coinciden.', 'error')
                return render_template('profile.html')
            if len(new_password) < 6:
                flash('La nueva contrasena debe tener al menos 6 caracteres.', 'error')
                return render_template('profile.html')
            User.set_password(current_user.id, new_password)
            flash('Nombre y contrasena actualizados.', 'success')
        else:
            flash('Nombre actualizado.', 'success')

        return redirect(url_for('users.profile'))

    return render_template('profile.html')
