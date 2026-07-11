from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models import User, get_config, set_config
from auth import requires_role

config_bp = Blueprint('config', __name__)


@config_bp.route('/config/round-robin')
@requires_role('marketing', 'admin')
def round_robin():
    """Muestra el estado del Round Robin: proximo agente, lista de agentes activos."""
    agents = User.all_agents()
    current_index = int(get_config('round_robin_index', 0))
    next_agent = agents[current_index % len(agents)] if agents else None
    return render_template(
        'config/round_robin.html',
        agents=agents,
        current_index=current_index,
        next_agent=next_agent,
    )


@config_bp.route('/config/round-robin/reset', methods=['POST'])
@requires_role('marketing', 'admin')
def reset_round_robin():
    """Reinicia el contador del Round Robin al primer agente activo."""
    set_config('round_robin_index', 0)
    flash('Contador de Round Robin reiniciado. El proximo lead se asignara al primer agente de la lista.', 'success')
    return redirect(url_for('config.round_robin'))
