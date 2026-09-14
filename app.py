# app.py
from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)


def buscar_jogador(nome):
    """Busca um jogador no banco de dados"""
    conn = sqlite3.connect('jogadores.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT name, team, games, goals, attempts, seven_meter 
        FROM players
        WHERE LOWER(name) LIKE LOWER(?)
        LIMIT 1
    ''', (f'%{nome}%',))

    resultado = cursor.fetchone()
    conn.close()

    if resultado:
        games = resultado['games']
        goals = resultado['goals']
        attempts = resultado['attempts']
        seven_meter = resultado['seven_meter']

        # Calcula médias
        media_gols = goals / games if games > 0 else 0
        media_7m = seven_meter / games if games > 0 else 0
        media_tentativas = attempts / games if games > 0 else 0
        taxa_conversao = (goals / attempts * 100) if attempts > 0 else 0

        return {
            'name': resultado['name'],
            'team': resultado['team'],
            'games': games,
            'goals': goals,
            'attempts': attempts,
            'seven_meter': seven_meter,
            'media_gols': round(media_gols, 2),
            'media_7m': round(media_7m, 2),
            'media_tentativas': round(media_tentativas, 2),
            'taxa_conversao': round(taxa_conversao, 2)
        }
    return None


@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')


@app.route('/api/search', methods=['GET'])
def search():
    """API de busca"""
    nome = request.args.get('q', '').strip()

    if not nome or len(nome) < 2:
        return jsonify({'erro': 'Digite pelo menos 2 caracteres'}), 400

    jogador = buscar_jogador(nome)

    if jogador:
        return jsonify(jogador)
    else:
        return jsonify({'erro': 'Jogador não encontrado'}), 404


@app.route('/api/todos', methods=['GET'])
def todos():
    """Retorna todos os jogadores, opcionalmente filtrados por time"""
    team = request.args.get('team', '').strip()

    conn = sqlite3.connect('jogadores.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if team:
        cursor.execute('''
            SELECT name, team, games, goals, attempts, seven_meter
            FROM players
            WHERE team = ?
            ORDER BY goals DESC
        ''', (team,))
    else:
        cursor.execute('''
            SELECT name, team, games, goals, attempts, seven_meter
            FROM players
            ORDER BY goals DESC
        ''')
    resultados = cursor.fetchall()
    conn.close()

    jogadores = []
    for r in resultados:
        games = r['games']
        goals = r['goals']
        attempts = r['attempts']

        media_gols = goals / games if games > 0 else 0
        taxa_conversao = (goals / attempts * 100) if attempts > 0 else 0

        jogadores.append({
            'name': r['name'],
            'team': r['team'],
            'games': games,
            'goals': goals,
            'attempts': attempts,
            'seven_meter': r['seven_meter'],
            'media_gols': round(media_gols, 2),
            'taxa_conversao': round(taxa_conversao, 2)
        })

    return jsonify({
        'total': len(jogadores),
        'players': jogadores
    })


@app.route('/api/autocomplete', methods=['GET'])
def autocomplete():
    """Retorna sugestoes de nomes de jogadores para autocomplete"""
    termo = request.args.get('q', '').strip()

    if len(termo) < 2:
        return jsonify([])

    conn = sqlite3.connect('jogadores.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT name FROM players
        WHERE LOWER(name) LIKE LOWER(?)
        ORDER BY name
        LIMIT 8
    ''', (f'%{termo}%',))
    nomes = [row[0] for row in cursor.fetchall()]
    conn.close()

    return jsonify(nomes)


@app.route('/api/teams', methods=['GET'])
def teams():
    """Retorna a lista de times unicos cadastrados"""
    conn = sqlite3.connect('jogadores.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT team FROM players
        WHERE team IS NOT NULL AND team != ''
        ORDER BY team
    ''')
    times = [row[0] for row in cursor.fetchall()]
    conn.close()

    return jsonify(times)


if __name__ == '__main__':
    if not os.path.exists('jogadores.db'):
        import database
        database.criar_banco()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
