# scraper_bundesliga.py
"""Scraper da Handball-Bundesliga (Alemanha, masculino).

Diferente do scraper da EHF, este NAO usa Selenium: o site
(https://www.opel-hbl.de) expoe uma API JSON publica (aparentemente da
Sportradar) por tras da interface, entao basta usar `requests`.

COMO OS IDs FORAM DESCOBERTOS (para referencia futura, ao atualizar a
temporada): abri https://www.opel-hbl.de/en/hbl/statistics com Selenium
capturando os logs de performance (Network), cliquei na aba "FIELD PLAYER"
e inspecionei as chamadas para /api/synergy/*. O parametro "seasonId"
identifica a temporada especifica (numeros de jogos/gols batem com o que a
propria pagina mostra pra temporada 2026/27 selecionada por padrao); ja o
"competitionId" usado em outros endpoints (ex: competition-statistic/player)
e um agregado HISTORICO/multi-temporada (jogadores apareciam com 500+ jogos
e milhares de gols) - por isso NAO e usado aqui.

Nao existe um endpoint publico para listar temporadas/IDs disponiveis (as
rotas /api/synergy/season, /seasons, /competition, /competitions retornam
404), entao o SEASON_ID abaixo precisa ser atualizado manualmente a cada
temporada nova, repetindo o processo de inspecao acima.
"""
import argparse
import sqlite3
import requests
import database

BASE_URL = 'https://www.opel-hbl.de/api/synergy'

# Temporada 2026/27, descoberta via inspecao de rede (ver docstring acima).
SEASON_ID = 'c4a3125f-79f2-11f1-9a19-5f7c8c2ed877'

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
}


class BundesligaScraper:
    def __init__(self, season_id=SEASON_ID, gender='men',
                 competition='Handball-Bundesliga', season='2026/27'):
        self.season_id = season_id
        self.gender = gender
        self.competition = competition
        self.season = season
        self.db_name = 'jogadores.db'

        database.migrate_multi_competition_schema()

    def fetch_player_overview(self):
        """Busca as estatisticas da temporada para todos os jogadores de
        linha (o parametro statisticType=fieldplayer cobre o elenco
        inteiro, goleiros incluidos - so vem com goals/shots zerados)."""
        url = f'{BASE_URL}/season-statistic/player-overview'
        params = {
            'seasonId': self.season_id,
            'statisticType': 'fieldplayer',
        }

        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def parse_players(self, payload):
        """Converte a resposta da API em uma lista de dicts
        {name, team, games, goals, attempts, seven_meter}."""
        resources = payload.get('includes', {}).get('resources', {})
        persons = resources.get('persons', {})
        entities = resources.get('entities', {})

        players = []
        for record in payload.get('data', []):
            person_id = record.get('person', {}).get('id')
            entity_id = record.get('entity', {}).get('id')
            stats = record.get('statistics', {})

            person = persons.get(person_id)
            if not person:
                continue

            name = person.get('nameFullLatin', '').strip()
            if not name:
                continue

            entity = entities.get(entity_id) or {}
            team = entity.get('nameFullLatin', 'Unknown')

            players.append({
                'name': name,
                'team': team,
                'games': stats.get('games', 0) or 0,
                'goals': stats.get('goalsScored', 0) or 0,
                'attempts': stats.get('shots', 0) or 0,
                'seven_meter': stats.get('sevenMetreGoalsScored', 0) or 0,
            })

        return players

    def save_players(self, players):
        """Salva os jogadores na tabela 'players', escopado por
        gender/competition/season - nunca mistura com dados de outras
        competicoes (ex: EHF Champions League)."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM players WHERE gender = ? AND competition = ? AND season = ?
        ''', (self.gender, self.competition, self.season))

        players_dict = {}
        for player in players:
            key = player['name'].lower()
            players_dict[key] = player

        for player in players_dict.values():
            cursor.execute('''
                INSERT INTO players
                    (name, team, games, goals, attempts, seven_meter,
                     gender, competition, season)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player['name'],
                player['team'],
                player['games'],
                player['goals'],
                player['attempts'],
                player['seven_meter'],
                self.gender,
                self.competition,
                self.season,
            ))

        conn.commit()
        conn.close()
        return len(players_dict)

    def run(self):
        print("\n" + "=" * 60)
        print(f"🤾 SCRAPER {self.competition.upper()} {self.season} ({self.gender.upper()})")
        print("=" * 60 + "\n")

        print("🔍 Buscando estatisticas da temporada...")
        payload = self.fetch_player_overview()

        players = self.parse_players(payload)
        print(f"   ✅ {len(players)} registros de jogadores extraidos\n")

        if not players:
            print("❌ Nenhum dado foi coletado!")
            return False

        total = self.save_players(players)
        print(f"✅ {total} jogadores no banco\n")

        print("=" * 60)
        print("✅ SCRAPING CONCLUIDO!")
        print("=" * 60 + "\n")
        return True


def parse_args():
    parser = argparse.ArgumentParser(
        description='Scraper da Handball-Bundesliga (opel-hbl.de)')
    parser.add_argument(
        '--season-id', default=SEASON_ID,
        help="ID interno da temporada na API (padrao: temporada 2026/27)")
    parser.add_argument(
        '--season', default='2026/27',
        help="Temporada, formato 'AAAA/AA' (padrao: '2026/27')")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    scraper = BundesligaScraper(season_id=args.season_id, season=args.season)
    scraper.run()
