# debug_full_table.py
import pdfplumber
import requests

# Mesmo PDF do Barça vs SAH que já usamos
pdf_url = "https://res.ehf.eu/doxtore/TLCEQLGQDD/uZmIpvhei6cdVrjznr1dSkzit8LlAqexyMbSLGb4tD8RWTtwm9fUEf4aU2k02uJf-jHKP5HcgT-W-ztf7JV9wG2jboZv70mXLCy14DgeBvmi8jbeRXBYF1a2Ece5fh4i"

print("Baixando PDF...")
response = requests.get(pdf_url)
with open('debug.pdf', 'wb') as f:
    f.write(response.content)

print("Analisando TODAS as linhas de TODAS as tabelas...\n")

with pdfplumber.open('debug.pdf') as pdf:
    for page_idx, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        if tables:
            for table_idx, table in enumerate(tables):
                print(
                    f"=== PÁGINA {page_idx+1} - TABELA {table_idx+1} ({len(table)} linhas) ===")
                for row_idx, row in enumerate(table):
                    print(f"  [{row_idx}] {row}")
                print()
