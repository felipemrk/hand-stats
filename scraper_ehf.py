# scraper_ehf.py (VERSÃO CORRIGIDA)
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
import re


class EHFScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.db_name = 'jogadores.db'

    def get_page(self, url):
        """Faz requisição HTTP"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response.text
            return None
        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")
            return None

    def get_matches_urls(self):
        """Extrai URLs das partidas da página principal"""
        print("🔍 Buscando URLs das partidas...\n")

        url = "https://ehfcl.eurohandball.com/men/2026-27/matches/"
        html = self.get_page(url)

        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        matches = []

        # Procura pelos links com class="table-row table-row--results"
        match_links = soup.find_all('a', class_='table-row table-row--results')

        print(f"   Encontrados {len(match_links)} links de partidas\n")

        for link in match_links:
            href = link.get('href')
            if href:
                # Adiciona https se não tiver
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = 'https://www.eurohandball.com' + href

                matches.append(full_url)

        print(f"✅ Total: {len(matches)} partidas\n")
        return matches

    def extract_player_stats_from_match(self, match_url):
        """Extrai estatísticas de jogadores de uma partida"""

        html = self.get_page(match_url)
        if not html:
            return [], "Unknown", "Unknown"

        soup = BeautifulSoup(html, 'html.parser')
        players_data = []
        home_team = "Unknown"
        away_team = "Unknown"

        try:
            # Tenta extrair nomes dos times do título
            title = soup.find('h1')
            if title:
                title_text = title.text.strip()
                if '-' in title_text:
                    parts = title_text.split('-')
                    if len(parts) >= 2:
                        home_team = parts[0].strip()
                        away_team = parts[1].strip()

            print(f"   🏆 {home_team} vs {away_team}")

            # Procura pela tabela de Player Statistics
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')

                for row in rows:
                    cols = row.find_all('td')

                    if len(cols) >= 7:
                        try:
                            # Extrai nome do jogador (segunda coluna)
                            player_cell = cols[1]
                            player_link = player_cell.find('a')

                            if player_link:
                                player_name = player_link.text.strip()
                            else:
                                player_name = player_cell.text.strip()

                            if not player_name or len(player_name) < 2:
                                continue

                            # Extrai gols (última coluna)
                            goals_text = cols[-1].text.strip()
                            goals = int(
                                goals_text) if goals_text.isdigit() else 0

                            if player_name[0].isalpha() and goals >= 0:
                                players_data.append({
                                    'name': player_name,
                                    'goals': goals,
                                    'team': home_team
                                })
                        except (ValueError, IndexError, AttributeError):
                            continue

            if players_data:
                print(f"      ✅ {len(players_data)} jogadores")

        except Exception as e:
            print(f"      ❌ Erro: {str(e)}")

        return players_data, home_team, away_team

    def update_database(self, all_players_data):
        """Atualiza o banco com os dados"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Agrupa por jogador
        players_dict = {}

        for player_data in all_players_data:
            name = player_data.get('name', '').strip()
            goals = player_data.get('goals', 0)
            team = player_data.get('team', 'Unknown')

            if name and len(name) > 1:
                key = name.lower()
                if key not in players_dict:
                    players_dict[key] = {
                        'name': name,
                        'team': team,
                        'games': 0,
                        'goals': 0
                    }

                if goals > 0:
                    players_dict[key]['games'] += 1
                    players_dict[key]['goals'] += goals

        # Limpa e insere dados
        cursor.execute('DELETE FROM players')

        for player_key, player_info in players_dict.items():
            if player_info['games'] > 0:
                cursor.execute('''
                    INSERT INTO players (name, team, games, goals)
                    VALUES (?, ?, ?, ?)
                ''', (
                    player_info['name'],
                    player_info['team'],
                    player_info['games'],
                    player_info['goals']
                ))

        conn.commit()
        conn.close()
        print(f"\n✅ {len(players_dict)} jogadores no banco\n")

    def run(self):
        """Executa o scraper"""
        print("\n" + "="*60)
        print("🏑 SCRAPER EHF CHAMPIONS LEAGUE 2026/27")
        print("="*60 + "\n")

        # Pega URLs
        match_urls = self.get_matches_urls()

        if not match_urls:
            print("❌ Nenhuma partida encontrada!")
            return False

        all_players_data = []

        # Processa cada partida
        for idx, match_url in enumerate(match_urls, 1):
            print(f"[{idx}/{len(match_urls)}]")
            players, home, away = self.extract_player_stats_from_match(
                match_url)
            all_players_data.extend(players)
            time.sleep(1)  # Delay respeitoso

        # Atualiza banco
        if all_players_data:
            self.update_database(all_players_data)
            print("="*60)
            print("✅ SCRAPING CONCLUÍDO!")
            print("="*60 + "\n")
            return True
        else:
            print("⚠️ Nenhum dado coletado!")
            return False


if __name__ == '__main__':
    scraper = EHFScraper()
    scraper.run()
