# debug_links.py
import requests
from bs4 import BeautifulSoup

url = "https://ehfcl.eurohandball.com/men/2026-27/matches/"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("📡 Buscando links...\n")

response = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

# Procura pelos links
match_links = soup.find_all('a', class_='table-row table-row--results')

print(f"Total encontrado: {len(match_links)}\n")

for idx, link in enumerate(match_links, 1):
    href = link.get('href')
    text = link.text.strip()[:100]

    print(f"{idx}. href: {href}")
    print(f"   text: {text}\n")
