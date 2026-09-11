# debug_pdf_structure.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import pdfplumber
import requests
import time
import os

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=webdriver.ChromeOptions()
)

try:
    # Abrir partida
    print("Abrindo partida...")
    driver.get(
        "https://www.eurohandball.com/en/matches/202711020101053/Barça-SAHAarhus/")
    time.sleep(3)

    # Encontrar o link do PDF
    print("Procurando Statistic Reports...")
    links = driver.find_elements(By.TAG_NAME, "a")

    pdf_url = None
    for link in links:
        if "statistic" in link.text.lower():
            pdf_url = link.get_attribute('href')
            print(f"✅ Encontrado: {pdf_url[:80]}...\n")
            break

    if pdf_url:
        # Baixar o PDF
        print("Baixando PDF...")
        response = requests.get(pdf_url)

        with open('temp_stats.pdf', 'wb') as f:
            f.write(response.content)

        print(f"✅ PDF baixado ({len(response.content)} bytes)\n")

        # Ler e analisar
        print("="*80)
        print("ESTRUTURA DO PDF")
        print("="*80 + "\n")

        with pdfplumber.open('temp_stats.pdf') as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()

                if tables:
                    print(f"PÁGINA {page_idx + 1}\n")

                    for table_idx, table in enumerate(tables):
                        print(f"Tabela {table_idx + 1}:")

                        if table:
                            # Headers
                            print(f"Headers: {table[0]}\n")

                            # Primeiros 5 jogadores
                            print("Primeiros 5 jogadores:")
                            for row in table[1:6]:
                                print(f"  {row}\n")

                        print("-"*80 + "\n")

        # Limpar
        os.remove('temp_stats.pdf')

finally:
    driver.quit()
