"""Corre todos los tests del proyecto.

IMPORTANTE: estos tests usan archivos AISLADOS en tests/ (test_crm.db,
test_credentials.json) y NUNCA tocan los archivos reales del usuario en la raiz
del proyecto (crm.db, credentials.json).

Uso: python tests/run_all.py
"""
import os
import sys
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
TEST_FILES = [
    'test_estados_colores.py',
    'test_users.py',
    'test_email_matching.py',
    'test_round_robin.py',
    'test_stats.py',
    'test_backup.py',
]

# Limpiar DB de tests anterior (la recreamos al inicio de cada test)
test_db = os.path.join(HERE, 'test_crm.db')
if os.path.exists(test_db):
    os.remove(test_db)

print('=' * 60)
print(f'Ejecutando {len(TEST_FILES)} archivos de tests...')
print('=' * 60)
print()
print('Los tests usan archivos AISLADOS en tests/ (test_crm.db, test_credentials.json).')
print('NO tocan crm.db ni credentials.json de la raiz del proyecto.')
print()

start = time.time()
errors_per_file = {}

for test_file in TEST_FILES:
    print('=' * 60)
    print(f'>>> {test_file}')
    print('=' * 60)
    path = os.path.join(HERE, test_file)
    env = os.environ.copy()
    # Aniadir el directorio raiz al PYTHONPATH para que `import app` funcione
    env['PYTHONPATH'] = PROJECT_ROOT + os.pathsep + env.get('PYTHONPATH', '')
    result = subprocess.run(
        [sys.executable, path],
        capture_output=True,
        text=True,
        env=env,
        cwd=PROJECT_ROOT,
    )
    print(result.stdout)
    if result.stderr:
        print('STDERR:', result.stderr)
    if result.returncode != 0:
        errors_per_file[test_file] = result.returncode

elapsed = time.time() - start

print()
print('=' * 60)
print(f'Termino en {elapsed:.1f}s')
if errors_per_file:
    print(f'Archivos con errores: {list(errors_per_file.keys())}')
    sys.exit(1)
else:
    print('Todos los archivos de tests terminaron sin errores de ejecucion.')
    print('(Revisa el output de cada uno para ver cuantos tests pasaron.)')
