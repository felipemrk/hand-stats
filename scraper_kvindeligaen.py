# scraper_kvindeligaen.py
"""Scraper da Kvindeligaen (Dinamarca, feminino), temporada 2026/2027.

O site tophaandbold.dk renderiza HTML no servidor (confirmado via
inspecao real) - NAO precisa de Selenium, so requests + BeautifulSoup.
As estatisticas individuais de cada jogadora vem de um endpoint JSON
interno do site (descoberto inspecionando as chamadas de rede feitas
pela ferramenta "Sammenlign spillere" / comparePlayer).

FLUXO:
1. https://tophaandbold.dk/klubber/kvindeligaen -> lista os slugs dos
   14 times (NAO hardcoded - le da propria pagina, entao acompanha se
   a liga mudar de tamanho no futuro).
2. Pagina de cada time (https://tophaandbold.dk/{slug}) -> link
   "Holdet" leva a /tophaandbold-theme/teams/view/{teamViewId}.
3. Essa pagina lista o elenco completo (goleiras, reservas, titulares -
   comissao tecnica e excluida por nao ter numero de camisa "#N" antes
   da posicao). Cada card tem um link "Statistik" com
   team%5D={statsTeamId} e player%5D={playerId} (um ID de time
   diferente do teamViewId do passo 2 - sao dois sistemas de ID
   distintos no mesmo site).
4. Esses dois IDs alimentam o endpoint JSON:
   /tophaandbold-theme/statistics/player-statistics/{YEAR}/{LEAGUE}/{BRACKET}/{statsTeamId}/{playerId}.json
   que retorna os totais da temporada. O nome dos campos depende da
   posicao: goleiras tem "Reddn"/"Straffered"/"Reddn i alt", jogadoras
   de linha tem "Mal"/"Straffemal"/"Mal i alt" (usando aqui os nomes
   sem acento no comentario por seguranca de encoding - no codigo os
   nomes reais em dinamarques sao usados). Quando a jogadora nao jogou
   nenhuma partida na temporada, o endpoint retorna os mesmos campos
   com valor 0 (nao omite nem manda NaN) - por isso salvamos ela mesmo
   assim, com 0 em tudo.
5. "Tentativas" (attempts): esse endpoint individual NAO tem essa
   informacao. A tabela geral de artilheiras
   (/tophaandbold-theme/statistics/player-score/{YEAR}/{LEAGUE}/0/0/0)
   tem a coluna "Total skud", mas e limitada as ~100 maiores
   artilheiras da liga inteira. Cruzamos por nome: quem aparece la,
   ganha o valor real de tentativas; quem nao aparece (nao marcou gol,
   ou esta fora do top 100), fica com attempts=NULL - null explicito,
   NUNCA 0, porque genuinamente nao sabemos (0 significaria "tentou e
   nao acertou nenhuma vez", o que e uma afirmacao diferente de "nao
   temos esse dado").

LIMITACAO CONHECIDA: essa fonte nao tem partidas individuais (data,
placar, adversario), entao "matches"/"player_match_stats" ficam vazios
para esta competicao - historico de time e filtro de data nao
funcionam para a Kvindeligaen por enquanto.
"""
import re
import time
import sqlite3
import requests
from bs4 import BeautifulSoup
import database

BASE_URL = 'https://tophaandbold.dk'
YEAR = 10       # temporada 2026/2027
LEAGUE = 6      # Bambuni Kvindeligaen
BRACKET = 0     # todas as fases

GENDER = 'women'
COMPETITION = 'Kvindeligaen'
SEASON = '2026/2027'

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept-Language': 'da,en;q=0.8',
}


def _get(url, **kwargs):
    response = requests.get(url, headers=HEADERS, timeout=30, **kwargs)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response


class KvindeligaenScraper:
    def __init__(self):
        database.migrate_multi_competition_schema()
        self.db_name = 'jogadores.db'

    def get_club_slugs(self):
        """Lista os slugs dos times da Kvindeligaen. Identifica cada
        card de time pela presenca de um logo de clube (klublogoer) -
        mais confiavel que tentar casar uma classe CSS especifica, que
        se mostrou malformada no HTML da pagina."""
        response = _get(f'{BASE_URL}/klubber/kvindeligaen')
        soup = BeautifulSoup(response.text, 'html.parser')

        slugs = []
        for link in soup.find_all('a', href=re.compile(r'^https://tophaandbold\.dk/[a-z0-9\-]+$')):
            if link.find('img', src=re.compile('klublogoer')):
                slugs.append(link['href'].rsplit('/', 1)[-1])

        return sorted(set(slugs))

    def get_team_view_id(self, slug):
        """Acha o ID usado em /tophaandbold-theme/teams/view/{id} (link
        'Holdet') a partir da pagina do time."""
        response = _get(f'{BASE_URL}/{slug}')
        soup = BeautifulSoup(response.text, 'html.parser')

        link = soup.find('a', href=re.compile(r'/tophaandbold-theme/teams/view/\d+'))
        if not link:
            return None

        match = re.search(r'/teams/view/(\d+)', link['href'])
        return match.group(1) if match else None

    def get_team_roster(self, view_id):
        """Elenco completo do time (exclui comissao tecnica, que nao
        tem numero de camisa "#N" antes da posicao)."""
        response = _get(f'{BASE_URL}/tophaandbold-theme/teams/view/{view_id}')
        soup = BeautifulSoup(response.text, 'html.parser')

        roster = []
        for card in soup.find_all('div', class_='team__player'):
            name_el = card.find('div', class_='team__player__name')
            if not name_el or not name_el.contents:
                continue

            name = str(name_el.contents[0]).strip()
            if not name:
                continue

            pos_el = card.find('span', class_='team__player__name__position')
            position = pos_el.get_text(strip=True) if pos_el else ''

            if not re.match(r'^#\d+', position):
                continue

            link = card.find(
                'a', href=lambda h: h and 'comparePlayer' in h and 'player%5D=' in h)
            if not link:
                continue

            team_match = re.search(r'team%5D=(\d+)', link['href'])
            player_match = re.search(r'player%5D=(\d+)', link['href'])
            if not team_match or not player_match:
                continue

            roster.append({
                'name': name,
                'position': position,
                'stats_team_id': team_match.group(1),
                'player_id': player_match.group(1),
            })

        return roster

    def get_player_season_stats(self, stats_team_id, player_id):
        """Busca o JSON de estatisticas individuais da temporada e
        retorna (nome_do_time, dict com todos os campos numericos)."""
        url = (f'{BASE_URL}/tophaandbold-theme/statistics/player-statistics/'
               f'{YEAR}/{LEAGUE}/{BRACKET}/{stats_team_id}/{player_id}.json')
        response = _get(url)
        data = response.json()
        player = data.get('player', {})

        season_stats = {}
        for block in player.get('statistics', {}).values():
            for entry in block:
                if entry.get('type') == 'number':
                    season_stats[entry['name']] = entry.get('value')

        return player.get('team_name'), season_stats

    def build_attempts_map(self):
        """Cruza a tabela geral de artilheiras (coluna 'Total skud')
        por nome. Quem nao aparece nessa tabela fica sem entrada aqui
        - o chamador deve tratar isso como attempts=NULL, nao 0."""
        url = f'{BASE_URL}/tophaandbold-theme/statistics/player-score/{YEAR}/{LEAGUE}/0/0/0'
        response = _get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', id='ranking')

        attempts_by_name = {}
        if table and table.find('tbody'):
            for row in table.find('tbody').find_all('tr'):
                name_td = row.find('td', {'data-player-id': True})
                if not name_td:
                    continue

                cells = [td.get_text(strip=True) for td in row.find_all('td')]
                if len(cells) < 13:
                    continue

                name = name_td.get_text(strip=True)
                attempts_by_name[name.lower()] = self._to_int(cells[12])

        return attempts_by_name

    def _to_int(self, value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    def run(self):
        print("\n" + "=" * 60)
        print(f"🤾 SCRAPER {COMPETITION.upper()} {SEASON} ({GENDER.upper()})")
        print("=" * 60 + "\n")

        print("🔍 Listando times da Kvindeligaen...")
        slugs = self.get_club_slugs()
        print(f"   ✅ {len(slugs)} times encontrados: {', '.join(s.upper() for s in slugs)}\n")

        if not slugs:
            print("❌ Nenhum time encontrado!")
            return False

        print("🔍 Buscando tabela geral de artilheiras (para tentativas)...")
        attempts_map = self.build_attempts_map()
        print(f"   ✅ {len(attempts_map)} jogadoras com 'tentativas' disponivel\n")

        all_players = []

        for idx, slug in enumerate(slugs, 1):
            print(f"[{idx}/{len(slugs)}] {slug.upper()}")
            try:
                view_id = self.get_team_view_id(slug)
                if not view_id:
                    print("   ⚠️ Link do elenco ('Holdet') nao encontrado")
                    continue

                roster = self.get_team_roster(view_id)
                print(f"   👥 {len(roster)} jogadoras no elenco")

                for player in roster:
                    team_name, stats = self.get_player_season_stats(
                        player['stats_team_id'], player['player_id'])

                    is_goalkeeper = 'lvogter' in player['position'].lower()
                    games = self._to_int(stats.get('Total kampe', 0))

                    if is_goalkeeper:
                        goals = 0
                        seven_meter = 0
                    else:
                        goals = self._to_int(stats.get('Mål i alt', 0))
                        seven_meter = self._to_int(stats.get('Straffemål', 0))

                    attempts = attempts_map.get(player['name'].lower())

                    all_players.append({
                        'name': player['name'],
                        'team': team_name or slug.upper(),
                        'games': games,
                        'goals': goals,
                        'attempts': attempts,
                        'seven_meter': seven_meter,
                    })

                    time.sleep(0.15)
            except Exception as e:
                print(f"   ❌ Erro no time {slug}: {str(e)}")

        if not all_players:
            print("❌ Nenhum dado foi coletado!")
            return False

        total = self.save_players(all_players)
        print(f"\n✅ {total} jogadoras no banco\n")
        print("=" * 60)
        print("✅ SCRAPING CONCLUIDO!")
        print("=" * 60 + "\n")
        return True

    def save_players(self, players):
        """Salva na tabela 'players', escopado por gender/competition/
        season - nunca mistura com dados de outras competicoes."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM players WHERE gender = ? AND competition = ? AND season = ?
        ''', (GENDER, COMPETITION, SEASON))

        players_dict = {}
        for player in players:
            players_dict[player['name'].lower()] = player

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
                GENDER,
                COMPETITION,
                SEASON,
            ))

        conn.commit()
        conn.close()
        return len(players_dict)


if __name__ == '__main__':
    scraper = KvindeligaenScraper()
    scraper.run()
