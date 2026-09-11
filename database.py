'Database'
# database.py
import sqlite3
import os


def criar_banco():
    'Criando conexão com banco'
    # Criar conexão com o banco
    conn = sqlite3.connect('jogadores.db')
    cursor = conn.cursor()

    # Criar tabela de jogadores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            team TEXT NOT NULL,
            country TEXT,
            games INTEGER DEFAULT 0,
            goals INTEGER DEFAULT 0
        )
    ''')

    # Dados iniciais (Champions League 2026/27)
    dados_iniciais = [
        ('Mathias Gidsel', 'Füchse Berlin', 'Dinamarca', 6, 47),
        ('Dika Mem', 'FC Barcelona', 'França', 6, 37),
        ('Luka Cindric', 'Paris Saint-Germain', 'França', 6, 35),
        ('Nikola Karabatic', 'Paris Saint-Germain', 'França', 5, 28),
        ('Rasmus Lauge', 'Aalborg Handball', 'Dinamarca', 6, 34),
        ('Andy Chapman', 'Pick Szeged', 'Inglaterra', 6, 32),
        ('Mikael Appelgren', 'Kielce', 'Suécia', 6, 31),
        ('Sander Sagosen', 'Paris Saint-Germain', 'Noruega', 5, 25),
        ('Xavier Barachet', 'FC Barcelona', 'França', 6, 29),
        ('Rene Toft Hansen', 'Aalborg Handball', 'Dinamarca', 6, 30),
    ]

    # Inserir dados
    try:
        for nome, time, pais, jogos, gols in dados_iniciais:
            cursor.execute('''
                INSERT OR IGNORE INTO players (name, team, country, games, goals)
                VALUES (?, ?, ?, ?, ?)
            ''', (nome, time, pais, jogos, gols))
    except Exception as e:
        print(f"Erro ao inserir dados: {e}")

    conn.commit()
    conn.close()
    print("✅ Banco de dados criado com sucesso!")


if __name__ == '__main__':
    criar_banco()
