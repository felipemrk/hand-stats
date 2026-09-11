# scraper_ehf_selenium.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import sqlite3
import time


class EHFScraperSelenium:
    def __init__(self):
        self.db_name = 'jogadores.db'
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

    def get_matches_urls(self):
        print("🔍 Carregando página de partidas...\n")
        url = "https://ehfcl.eurohandball.com/men/2026-27/matches/"
        self.driver.get(url)
        print("   ⏳ Esperando dados carregar...")
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located(
                    (By.CLASS_NAME, "table-row--results"))
            )
        except:
            print("   ⚠️ Timeout ao carregar")
        time.sleep(2)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        matches = []
        match_links = soup.find_all('a', class_='table-row table-row--results')
        print(f"   ✅ {len(match_links)} links encontrados\n")
        for link in match_links:
            href = link.get('href')
            if href:
                if href.startswith('http'):
                    full_url = href
                else:
                    full_url = 'https://www.eurohandball.com' + href
                matches.append(full_url)
        print(f"✅ Total: {len(matches)} partidas\n")
        return matches

    def extract_player_stats_from_match(self, match_url):
        self.driver.get(match_url)
        time.sleep(2)

        # Procura e clica em "Statistic Reports"
        try:
            stat_reports_button = None

            # Tenta encontrar o botão por texto "Statistic Reports"
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                if "statistic" in link.text.lower():
                    stat_reports_button = link
                    break

            if stat_reports_button:
                print("   📊 Clicando em Statistic Reports...")
                stat_reports_button.click()
                time.sleep(2)
        except Exception as e:
            print(f"   ⚠️ Não conseguiu clicar em Statistic Reports: {str(e)}")

        # Extrai dados da página
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        players_data = []
        home_team = "Unknown"
        away_team = "Unknown"

        try:
            # Nomes dos times
            title = soup.find('h1')
            if title:
                title_text = title.text.strip()
                if '-' in title_text:
                    parts = title_text.split('-')
                    if len(parts) >= 2:
                        home_team = parts[0].strip()
                        away_team = parts[1].strip()

            print(f"   🏆 {home_team} vs {away_team}")

            # Procura por tabelas
            tables = soup.find_all('table')

            for table in tables:
                rows = table.find_all('tr')

                for row in rows:
                    cols = row.find_all('td')

                    if len(cols) >= 4:
                        try:
                            # Nome do jogador (geralmente col 1)
                            player_cell = cols[1] if len(cols) > 1 else cols[0]
                            player_link = player_cell.find('a')

                            if player_link:
                                player_name = player_link.text.strip()
                            else:
                                player_name = player_cell.text.strip()

                            if not player_name or len(player_name) < 2 or not player_name[0].isalpha():
                                continue

                            # Gols (procura por um número na linha)
                            goals = 0
                            for col in cols:
                                col_text = col.text.strip()
                                if col_text.isdigit() and int(col_text) > 0:
                                    goals = int(col_text)
                                    break

                            if goals >= 0:
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
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

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

        cursor.execute('DELETE FROM players')

        for player_key, player_info in players_dict.items():
            if player_info['games'] > 0:
                cursor.execute('''
                    INSERT INTO players (name, team, games, goals, attempts, seven_meter)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    player_info['name'],
                    player_info['team'],
                    player_info['games'],
                    player_info['goals'],
                    0,
                    0
                ))

        conn.commit()
        conn.close()
        print(f"\n✅ {len(players_dict)} jogadores no banco\n")

    def run(self):
        print("\n" + "="*60)
        print("🏑 SCRAPER EHF CHAMPIONS LEAGUE 2026/27")
        print("="*60 + "\n")

        try:
            match_urls = self.get_matches_urls()

            if not match_urls:
                print("❌ Nenhuma partida encontrada!")
                return False

            all_players_data = []

            for idx, match_url in enumerate(match_urls, 1):
                print(f"[{idx}/{len(match_urls)}]")
                players, home, away = self.extract_player_stats_from_match(
                    match_url)
                all_players_data.extend(players)
                time.sleep(1)

            if all_players_data:
                self.update_database(all_players_data)
                print("="*60)
                print("✅ SCRAPING CONCLUÍDO!")
                print("="*60 + "\n")
                return True

        finally:
            self.driver.quit()


if __name__ == '__main__':
    scraper = EHFScraperSelenium()
    scraper.run()
