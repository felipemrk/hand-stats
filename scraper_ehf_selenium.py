# scraper_ehf_selenium.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pdfplumber
import requests
import sqlite3
import time
import os
import tempfile
import shutil
import re
from urllib.parse import unquote


class EHFScraperSelenium:
    def __init__(self):
        self.db_name = 'jogadores.db'
        self.download_dir = tempfile.mkdtemp()

        options = webdriver.ChromeOptions()
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "safebrowsing.enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        options.add_argument('--start-maximized')

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        self._ensure_columns()

    def _ensure_columns(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(players)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'attempts' not in columns:
            cursor.execute(
                'ALTER TABLE players ADD COLUMN attempts INTEGER DEFAULT 0')
        if 'seven_meter' not in columns:
            cursor.execute(
                'ALTER TABLE players ADD COLUMN seven_meter INTEGER DEFAULT 0')

        conn.commit()
        conn.close()

    def _click_load_more_until_exhausted(self, max_clicks=50):
        """Clica repetidamente no botão 'carregar mais'/'load more' até ele
        desaparecer ou parar de trazer partidas novas (com limite de segurança)."""
        load_more_xpath = (
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'load more') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'carregar mais') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'ver mais')] | "
            "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'load more') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'carregar mais') or "
            "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'ver mais')]"
        )

        previous_count = len(self.driver.find_elements(
            By.CLASS_NAME, "table-row--results"))
        clicks = 0

        while clicks < max_clicks:
            buttons = self.driver.find_elements(By.XPATH, load_more_xpath)
            visible_buttons = [b for b in buttons if b.is_displayed()]

            if not visible_buttons:
                break

            button = visible_buttons[0]
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView(true);", button)
                button.click()
            except Exception:
                break

            clicks += 1

            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: len(d.find_elements(
                        By.CLASS_NAME, "table-row--results")) > previous_count
                )
            except Exception:
                # Botão não trouxe partidas novas: considera esgotado
                break

            new_count = len(self.driver.find_elements(
                By.CLASS_NAME, "table-row--results"))
            if new_count <= previous_count:
                break
            previous_count = new_count

        if clicks > 0:
            print(f"   🔄 Botão 'carregar mais' clicado {clicks}x")

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

        self._click_load_more_until_exhausted()

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

    def parse_player_row(self, row):
        """Extrai nome, gols, tentativas e 7m de uma linha"""
        if not row:
            return None

        if isinstance(row, list):
            line = ' '.join(str(cell) for cell in row if cell)
        else:
            line = str(row)

        line = line.strip()

        if not line:
            return None

        if line.upper().startswith('TOTAL'):
            return None

        # Número + Nome (QUALQUER caractere não-dígito, cobre acentos e letras eslavas)
        # + Gols + Arremessos + %
        match = re.match(
            r'^(\d{1,2})\s*([^\d\s][^\d]*?)\s+(\d+)\s+(\d+)\s+(\d+)',
            line
        )

        if not match:
            return None

        name_raw = match.group(2).strip()
        goals = int(match.group(3))
        attempts = int(match.group(4))

        # Remove código de país entre parênteses no final, ex: "(FRA)"
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name_raw).strip()

        if not name or len(name) < 2:
            return None

        remainder = line[match.end():]
        seven_match = re.search(r'(\d+)/(\d+)\s+(\d+)%', remainder)
        seven_meter = int(seven_match.group(1)) if seven_match else 0

        return {
            'name': name,
            'goals': goals,
            'attempts': attempts,
            'seven_meter': seven_meter
        }

    def extract_players_from_pdf(self, pdf_path):
        """Extrai jogadores de um PDF"""
        try:
            all_rows = []

            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()

                    if not tables:
                        continue

                    next_table_is_players = False

                    for table in tables:
                        if not table or len(table) == 0:
                            continue

                        header = table[0]

                        is_header_table = any('Player' in str(h) for h in header) and any(
                            'Total' in str(h) for h in header)

                        if is_header_table:
                            for row in table[1:]:
                                parsed = self.parse_player_row(row)
                                if parsed:
                                    all_rows.append(parsed)

                            next_table_is_players = True
                            continue

                        if next_table_is_players:
                            for row in table:
                                parsed = self.parse_player_row(row)
                                if parsed:
                                    all_rows.append(parsed)

                            next_table_is_players = False

            return all_rows

        except Exception as e:
            print(f"      ❌ Erro ao ler PDF: {str(e)}")
            return []

    def get_team_names(self, match_url):
        """Extrai nomes dos times, com fallback pela URL"""
        home_team = None
        away_team = None

        try:
            home_el = self.driver.find_element(
                By.CSS_SELECTOR, ".team-block--first .name")
            home_team = home_el.text.strip()
        except:
            pass

        try:
            away_el = self.driver.find_element(
                By.CSS_SELECTOR, ".team-block--second .name")
            away_team = away_el.text.strip()
        except:
            pass

        # Fallback: extrai da URL (ex: "Barça-SAHAarhus")
        if not home_team or not away_team:
            try:
                slug = match_url.rstrip('/').split('/')[-1]
                slug = unquote(slug)
                if '-' in slug:
                    parts = slug.split('-', 1)
                    home_team = home_team or parts[0].strip()
                    away_team = away_team or parts[1].strip()
            except:
                pass

        return home_team or "Unknown", away_team or "Unknown"

    def extract_player_stats_from_match(self, match_url):
        self.driver.get(match_url)
        time.sleep(2)

        home_team, away_team = self.get_team_names(match_url)

        print(f"   🏆 {home_team} vs {away_team}")

        try:
            links = self.driver.find_elements(By.TAG_NAME, "a")
            pdf_url = None

            for link in links:
                if "statistic" in link.text.lower():
                    pdf_url = link.get_attribute('href')
                    print("   📊 Encontrado Statistic Reports")
                    break

            if pdf_url:
                print("   📄 Baixando PDF...")
                response = requests.get(pdf_url)

                pdf_path = os.path.join(self.download_dir, 'temp_stats.pdf')
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)

                all_rows = self.extract_players_from_pdf(pdf_path)

                # Divide entre time de casa e visitante (primeira metade / segunda metade)
                metade = len(all_rows) // 2
                for i, player in enumerate(all_rows):
                    player['team'] = home_team if i < metade else away_team

                print(
                    f"      {'✅' if all_rows else '⚠️'} {len(all_rows)} jogadores extraídos")

                if os.path.exists(pdf_path):
                    os.remove(pdf_path)

                return all_rows, home_team, away_team
            else:
                print(f"   ⚠️ PDF não encontrado")
                return [], home_team, away_team

        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")
            return [], home_team, away_team

    def update_database(self, all_players_data):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        players_dict = {}

        for player_data in all_players_data:
            name = player_data.get('name', '').strip()
            goals = player_data.get('goals', 0)
            attempts = player_data.get('attempts', 0)
            seven_meter = player_data.get('seven_meter', 0)
            team = player_data.get('team', 'Unknown')

            if name and len(name) > 1:
                key = name.lower()
                if key not in players_dict:
                    players_dict[key] = {
                        'name': name,
                        'team': team,
                        'games': 0,
                        'goals': 0,
                        'attempts': 0,
                        'seven_meter': 0
                    }

                players_dict[key]['games'] += 1
                players_dict[key]['goals'] += goals
                players_dict[key]['attempts'] += attempts
                players_dict[key]['seven_meter'] += seven_meter

                if team and team != 'Unknown':
                    players_dict[key]['team'] = team

        cursor.execute('DELETE FROM players')

        for player_key, player_info in players_dict.items():
            cursor.execute('''
                INSERT INTO players (name, team, games, goals, attempts, seven_meter)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                player_info['name'],
                player_info['team'],
                player_info['games'],
                player_info['goals'],
                player_info['attempts'],
                player_info['seven_meter']
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
                try:
                    players, home, away = self.extract_player_stats_from_match(
                        match_url)
                    all_players_data.extend(players)
                except Exception as e:
                    print(f"   ❌ Erro nesta partida: {str(e)}")
                time.sleep(1)

            if all_players_data:
                self.update_database(all_players_data)
                print("="*60)
                print("✅ SCRAPING CONCLUÍDO!")
                print("="*60 + "\n")
                return True
            else:
                print("❌ Nenhum dado foi coletado!")
                return False

        finally:
            self.driver.quit()
            shutil.rmtree(self.download_dir, ignore_errors=True)


if __name__ == '__main__':
    scraper = EHFScraperSelenium()
    scraper.run()
