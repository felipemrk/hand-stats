# teste_regex.py
import re


def parse_player_row(row):
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
    match = re.match(
        r'^(\d{1,2})\s*([^\d\s][^\d]*?)\s+(\d+)\s+(\d+)\s+(\d+)',
        line
    )
    if not match:
        return None
    name_raw = match.group(2).strip()
    goals = int(match.group(3))
    attempts = int(match.group(4))
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name_raw).strip()
    if not name or len(name) < 2:
        return None
    remainder = line[match.end():]
    seven_match = re.search(r'(\d+)/(\d+)\s+(\d+)%', remainder)
    seven_meter = int(seven_match.group(1)) if seven_match else 0
    return {'name': name, 'goals': goals, 'attempts': attempts, 'seven_meter': seven_meter}


# Linhas reais do debug que você mandou
test_rows = [
    ['1 HALLGRÍMSSON Viktor Gísli (ISL) 0 0 0'],
    ['3 SMÁRASON Janus Daði (ISL) 1 2 50 1/2 1'],
    ['6 FERNÁNDEZ Daniel 3 3 100 1/1 100% 1/1 1/1'],
    ['10MEM Dika (FRA) 7 10 70 7/9 0/1 4'],
    ['11CIKUŠA Djordje 1 2 50 1 1'],
    ['88CIKUŠA Petar 6 7 86 2/3 4/4 1 1'],
    ['Player TOTALS 39 52 75 2/3 66% 28/36 6/8 1/2 13 4 1 1 1'],
]

for row in test_rows:
    resultado = parse_player_row(row)
    print(f"{row}")
    print(f"  → {resultado}\n")
