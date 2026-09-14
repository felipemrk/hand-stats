# app.py
from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)

DEFAULT_GENDER = 'men'
DEFAULT_COMPETITION = 'EHF Champions League'


def get_gender_competition(args):
    """Le gender/competition da querystring, com os defaults atuais
    (men / EHF Champions League) para nao quebrar quem nao informar."""
    gender = args.get('gender', '').strip() or DEFAULT_GENDER
    competition = args.get('competition', '').strip() or DEFAULT_COMPETITION
    return gender, competition


def buscar_jogador(nome, gender, competition):
    """Busca um jogador no banco de dados, dentro de um naipe/competicao"""
    conn = sqlite3.connect('jogadores.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT name, team, games, goals, attempts, seven_meter
        FROM players
        WHERE LOWER(name) LIKE LOWER(?) AND gender = ? AND competition = ?
        LIMIT 1
    ''', (f'%{nome}%', gender, competition))

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
    gender, competition = get_gender_competition(request.args)

    if not nome or len(nome) < 2:
        return jsonify({'erro': 'Digite pelo menos 2 caracteres'}), 400

    jogador = buscar_jogador(nome, gender, competition)

    if jogador:
        return jsonify(jogador)
    else:
        return jsonify({'erro': 'Jogador não encontrado'}), 404


@app.route('/api/todos', methods=['GET'])
def todos():
    """Retorna todos os jogadores, opcionalmente filtrados por time e/ou
    por um periodo de datas. Com filtro de data, os totais sao calculados
    a partir de player_match_stats + matches (nao da tabela players)."""
    team = request.args.get('team', '').strip()
    data_inicio = request.args.get('data_inicio', '').strip()
    data_fim = request.args.get('data_fim', '').strip()
    gender, competition = get_gender_competition(request.args)

    conn = sqlite3.connect('jogadores.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if data_inicio or data_fim:
        query = '''
            SELECT pms.player_name AS name,
                   MAX(pms.team) AS team,
                   COUNT(DISTINCT pms.match_id) AS games,
                   COALESCE(SUM(pms.goals), 0) AS goals,
                   COALESCE(SUM(pms.attempts), 0) AS attempts,
                   COALESCE(SUM(pms.seven_meter), 0) AS seven_meter
            FROM player_match_stats pms
            JOIN matches m ON m.id = pms.match_id
            WHERE pms.gender = ? AND pms.competition = ?
        '''
        params = [gender, competition]

        if data_inicio:
            query += ' AND m.match_date >= ?'
            params.append(data_inicio)
        if data_fim:
            query += ' AND m.match_date <= ?'
            params.append(data_fim)
        if team:
            query += ' AND pms.team = ?'
            params.append(team)

        query += ' GROUP BY pms.player_name ORDER BY goals DESC'

        cursor.execute(query, params)
    elif team:
        cursor.execute('''
            SELECT name, team, games, goals, attempts, seven_meter
            FROM players
            WHERE team = ? AND gender = ? AND competition = ?
            ORDER BY goals DESC
        ''', (team, gender, competition))
    else:
        cursor.execute('''
            SELECT name, team, games, goals, attempts, seven_meter
            FROM players
            WHERE gender = ? AND competition = ?
            ORDER BY goals DESC
        ''', (gender, competition))
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
    gender, competition = get_gender_competition(request.args)

    if len(termo) < 2:
        return jsonify([])

    conn = sqlite3.connect('jogadores.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT name FROM players
        WHERE LOWER(name) LIKE LOWER(?) AND gender = ? AND competition = ?
        ORDER BY name
        LIMIT 8
    ''', (f'%{termo}%', gender, competition))
    nomes = [row[0] for row in cursor.fetchall()]
    conn.close()

    return jsonify(nomes)


@app.route('/api/teams', methods=['GET'])
def teams():
    """Retorna a lista de times unicos cadastrados"""
    gender, competition = get_gender_competition(request.args)

    conn = sqlite3.connect('jogadores.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT team FROM players
        WHERE team IS NOT NULL AND team != '' AND gender = ? AND competition = ?
        ORDER BY team
    ''', (gender, competition))
    times = [row[0] for row in cursor.fetchall()]
    conn.close()

    return jsonify(times)


@app.route('/api/team-history', methods=['GET'])
def team_history():
    """Retorna as partidas de um time (data, adversario, placar, casa/fora)"""
    team = request.args.get('team', '').strip()
    gender, competition = get_gender_competition(request.args)

    if not team:
        return jsonify({'erro': 'Informe o parametro team'}), 400

    conn = sqlite3.connect('jogadores.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT home_team, away_team, home_score, away_score, match_date
        FROM matches
        WHERE (home_team = ? OR away_team = ?) AND gender = ? AND competition = ?
        ORDER BY match_date DESC
    ''', (team, team, gender, competition))
    resultados = cursor.fetchall()
    conn.close()

    partidas = []
    for r in resultados:
        mandante = r['home_team'] == team
        adversario = r['away_team'] if mandante else r['home_team']
        placar_time = r['home_score'] if mandante else r['away_score']
        placar_adversario = r['away_score'] if mandante else r['home_score']

        partidas.append({
            'match_date': r['match_date'],
            'adversario': adversario,
            'placar_time': placar_time,
            'placar_adversario': placar_adversario,
            'mandante': mandante
        })

    return jsonify(partidas)


if __name__ == '__main__':
    import database

    if not os.path.exists('jogadores.db'):
        database.criar_banco()

    database.migrate_multi_competition_schema()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
