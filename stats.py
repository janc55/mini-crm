from collections import Counter
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request
from auth import requires_role
from models import User, normalize_name, ESTADO_BADGE_CLASS, ESTADO_COLORS

stats_bp = Blueprint('stats', __name__)


def parse_date(s):
    """Intenta parsear una fecha en varios formatos comunes. Retorna date o None."""
    if not s:
        return None
    s = s.strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d/%m/%y', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def compute_stats(leads, date_from=None, date_to=None, agent=None):
    """Calcula estadisticas a partir de una lista de leads.

    Args:
        leads: lista de dicts con keys fecha_registro, estado, agente, interes
        date_from: date object, fecha minima inclusiva
        date_to: date object, fecha maxima inclusiva
        agent: email o nombre del agente a filtrar

    Returns:
        dict con las estadisticas computadas
    """
    # Filtrar por fecha
    if date_from or date_to:
        filtered = []
        for lead in leads:
            d = parse_date(lead['fecha_registro'])
            if d is None:
                continue
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
            filtered.append(lead)
        leads = filtered

    # Filtrar por agente
    if agent:
        agent_norm = normalize_name(agent)
        leads = [l for l in leads if normalize_name(l['agente']) == agent_norm]

    total = len(leads)

    by_estado = Counter(l['estado'] for l in leads if l['estado'])
    by_agent = Counter(l['agente'] for l in leads if l['agente'])
    by_interes = Counter(l['interes'] for l in leads if l['interes'])

    # Leads por dia (ultimos 30 dias, rellenando dias sin leads con 0)
    by_day_counter = Counter()
    for l in leads:
        d = parse_date(l['fecha_registro'])
        if d:
            by_day_counter[d] += 1

    today = datetime.today().date()
    by_day_list = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        by_day_list.append({
            'date': day.isoformat(),
            'label': day.strftime('%d/%m'),
            'count': by_day_counter.get(day, 0),
        })

    inscritos = by_estado.get('Inscrito', 0)
    conversion_rate = round((inscritos / total * 100), 1) if total > 0 else 0

    # En seguimiento = todos los que no son terminal (Inscrito, No interesado, No responde, Numero incorrecto)
    terminales = {'Inscrito', 'No interesado', 'No responde', 'Numero incorrecto', 'Número incorrecto'}
    en_seguimiento = sum(c for est, c in by_estado.items() if normalize_name(est) not in {normalize_name(t) for t in terminales})

    # Top 10 agentes
    top_agents = by_agent.most_common(10)

    # Top 10 intereses
    top_intereses = by_interes.most_common(10)

    return {
        'total_leads': total,
        'by_estado': dict(by_estado),
        'by_agent': dict(by_agent),
        'by_day': by_day_list,
        'top_agents': top_agents,
        'top_intereses': top_intereses,
        'inscritos': inscritos,
        'en_seguimiento': en_seguimiento,
        'conversion_rate': conversion_rate,
    }


def get_date_range_filter():
    """Lee los query params de filtro de fecha y retorna (date_from, date_to, label)."""
    range_param = request.args.get('range', 'all')
    agent_param = request.args.get('agent', '').strip() or None
    today = datetime.today().date()

    if range_param == '7d':
        return (today - timedelta(days=6), today, '7 dias', agent_param)
    elif range_param == '30d':
        return (today - timedelta(days=29), today, '30 dias', agent_param)
    elif range_param == '90d':
        return (today - timedelta(days=89), today, '90 dias', agent_param)
    else:
        return (None, None, 'Todo el tiempo', agent_param)


@stats_bp.route('/stats')
@requires_role('marketing', 'admin')
def dashboard():
    # Import lazy para evitar circular import con app.py
    from app import get_initialized_sheet, get_all_leads, handle_error

    try:
        sheet = get_initialized_sheet()
        leads = get_all_leads(sheet)
    except Exception as e:
        return handle_error(e)

    date_from, date_to, range_label, agent_filter = get_date_range_filter()
    stats = compute_stats(leads, date_from=date_from, date_to=date_to, agent=agent_filter)

    # Construir datos para los charts
    # Estados: incluimos todos los definidos, incluso con 0
    estados_data = []
    estados_colors = []
    for estado, _class in ESTADO_BADGE_CLASS.items():
        count = stats['by_estado'].get(estado, 0)
        if count > 0:
            estados_data.append({'label': estado, 'count': count})
            estados_colors.append(ESTADO_COLORS.get(_class, '#94a3b8'))

    # Resolver emails a nombres para el chart de agentes
    agent_map = {u.email: u.nombre for u in User.all_agents()}
    agents_data = []
    for email, count in stats['top_agents']:
        name = agent_map.get(email, email)
        agents_data.append({'label': name, 'count': count, 'email': email})

    # Filtros disponibles (agentes con leads o todos los activos)
    all_agents = User.all_agents()

    return render_template(
        'stats/dashboard.html',
        stats=stats,
        estados_data=estados_data,
        estados_colors=estados_colors,
        agents_data=agents_data,
        day_data=stats['by_day'],
        range_label=range_label,
        range_param=request.args.get('range', 'all'),
        agent_filter=agent_filter or '',
        all_agents=all_agents,
    )
