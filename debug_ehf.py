# debug_ehf_deep.py
import requests
from bs4 import BeautifulSoup
import json

url = "https://ehfcl.eurohandball.com/men/2026-27/matches/"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("📡 Acessando página...\n")
response = requests.get(url, headers=headers, timeout=10)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')

    # Procura por divs que pareçam ser cards de partidas
    print("🔍 Procurando por elementos de partidas...\n")

    # Tenta encontrar divs com classes comuns
    possible_match_divs = soup.find_all('div', class_=lambda x: x and any(
        word in x.lower() for word in ['match', 'game', 'fixture', 'event', 'card', 'result']
    ))

    print(
        f"Encontrados {len(possible_match_divs)} divs com classes de partida\n")

    if possible_match_divs:
        print("Primeiros 5:\n")
        for div in possible_match_divs[:5]:
            print(div)
            print("\n" + "="*80 + "\n")

    # Procura por scripts com dados JSON
    print("\n🔍 Procurando por dados em scripts...\n")
    scripts = soup.find_all('script')
    print(f"Total de scripts encontrados: {len(scripts)}\n")

    for idx, script in enumerate(scripts[:5]):
        content = script.string
        if content and len(content) > 100:
            print(f"Script {idx}:")
            print(content[:500])
            print("\n" + "="*80 + "\n")
else:
    print(f"❌ Erro {response.status_code}")
