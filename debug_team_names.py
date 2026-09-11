# debug_team_names.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=webdriver.ChromeOptions()
)

try:
    url = "https://www.eurohandball.com/en/matches/202711020101053/Barça-SAHAarhus/"
    driver.get(url)
    time.sleep(3)

    print("Tentando .team-block--first .name:")
    try:
        el = driver.find_element(By.CSS_SELECTOR, ".team-block--first .name")
        print(f"  ✅ Encontrado: '{el.text}'")
    except Exception as e:
        print(f"  ❌ Não encontrado: {e}")

    print("\nTentando .team-block--second .name:")
    try:
        el = driver.find_element(By.CSS_SELECTOR, ".team-block--second .name")
        print(f"  ✅ Encontrado: '{el.text}'")
    except Exception as e:
        print(f"  ❌ Não encontrado: {e}")

    print("\nURL da partida:")
    print(f"  {url}")

    print("\nTítulo da página (H1, se existir):")
    try:
        h1 = driver.find_element(By.TAG_NAME, "h1")
        print(f"  '{h1.text}'")
    except:
        print("  Nenhum H1 encontrado")

finally:
    driver.quit()
