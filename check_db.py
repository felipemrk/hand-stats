# check_db.py
import sqlite3

conn = sqlite3.connect('jogadores.db')
cursor = conn.cursor()

# Busca TODOS os jogadores que contenham "cikus" de qualquer forma
cursor.execute(
    "SELECT name, team, games, goals FROM players WHERE name LIKE '%ikus%' OR name LIKE '%CIKU%'")
resultados = cursor.fetchall()

print(f"Encontrados: {len(resultados)}\n")
for r in resultados:
    print(r)

conn.close()
