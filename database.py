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


def migrate_multi_competition_schema():
    """Migracao idempotente: adiciona gender/competition/season para
    suportar multiplas competicoes/naipes. Dados existentes sao marcados
    automaticamente como gender='men', competition='EHF Champions League',
    season='2026/27' - nada e perdido ou duplicado."""
    conn = sqlite3.connect('jogadores.db')
    cursor = conn.cursor()

    try:
        cursor.execute('BEGIN')

        # matches: ja tem competition/season, falta gender
        cursor.execute("PRAGMA table_info(matches)")
        matches_columns = [col[1] for col in cursor.fetchall()]
        if matches_columns and 'gender' not in matches_columns:
            cursor.execute(
                "ALTER TABLE matches ADD COLUMN gender TEXT DEFAULT 'men'")

        # player_match_stats: falta gender e competition
        cursor.execute("PRAGMA table_info(player_match_stats)")
        pms_columns = [col[1] for col in cursor.fetchall()]
        if pms_columns and 'gender' not in pms_columns:
            cursor.execute(
                "ALTER TABLE player_match_stats ADD COLUMN gender TEXT DEFAULT 'men'")
        if pms_columns and 'competition' not in pms_columns:
            cursor.execute(
                "ALTER TABLE player_match_stats ADD COLUMN competition TEXT DEFAULT 'EHF Champions League'")

        # players: UNIQUE(name) embutido impede ALTER simples, precisa recriar
        cursor.execute("PRAGMA table_info(players)")
        players_columns = [col[1] for col in cursor.fetchall()]
        if players_columns and 'gender' not in players_columns:
            cursor.execute('''
                CREATE TABLE players_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    country TEXT,
                    games INTEGER DEFAULT 0,
                    goals INTEGER DEFAULT 0,
                    attempts INTEGER DEFAULT 0,
                    seven_meter INTEGER DEFAULT 0,
                    gender TEXT DEFAULT 'men',
                    competition TEXT DEFAULT 'EHF Champions League',
                    season TEXT DEFAULT '2026/27',
                    UNIQUE(name, team, gender, competition, season)
                )
            ''')

            cursor.execute('''
                INSERT INTO players_new
                    (id, name, team, country, games, goals, attempts, seven_meter,
                     gender, competition, season)
                SELECT
                    id, name, team, country, games, goals, attempts, seven_meter,
                    'men', 'EHF Champions League', '2026/27'
                FROM players
            ''')

            cursor.execute('DROP TABLE players')
            cursor.execute('ALTER TABLE players_new RENAME TO players')

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    criar_banco()
