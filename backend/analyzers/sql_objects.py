"""SQL nesne çıkarımı (ortak modül).

``sqlparse`` tabanlı bu modül hem :class:`CodeAnalyzer` hem de
:class:`AdvancedCodeAnalyzer` tarafından kullanılır. Prosedür, fonksiyon,
view ve trigger'lara ek olarak ``CREATE TABLE`` ve ``CREATE INDEX``
nesnelerini de çıkarır.

Çıktı biçimi analizörlerin beklediği sözlüktür::

    {
        'functions': [ {name, type, start_line, end_line, parameters,
                        return_type, signature, is_entry, class_name,
                        package_name}, ... ],
        'entry_points': [...],
        'dependencies': [...],
    }
"""

import re
from typing import Dict, List, Tuple

try:
    import sqlparse
    SQLPARSE_AVAILABLE = True
except ImportError:  # pragma: no cover - sqlparse kurulu değilse
    SQLPARSE_AVAILABLE = False


# Yorumlar eşleşmeden önce temizlenir; böylece yorum içindeki "CREATE TABLE"
# metni yanlışlıkla nesne olarak algılanmaz.
_COMMENT_PATTERN = re.compile(r'--[^\n]*|/\*.*?\*/', re.DOTALL)

# CREATE/ALTER [OR ALTER|OR REPLACE] [modifier...] TYPE [IF NOT EXISTS] name
_OBJECT_PATTERN = re.compile(
    r'\b(CREATE|ALTER)(?:\s+OR\s+(?:ALTER|REPLACE))?\s+'
    r'((?:(?:UNIQUE|CLUSTERED|NONCLUSTERED|BITMAP|FULLTEXT|SPATIAL)\s+)*)'
    r'(PROCEDURE|PROC|FUNCTION|VIEW|TRIGGER|TABLE|INDEX)\s+'
    r'(?:IF\s+NOT\s+EXISTS\s+)?'
    r'([^\s(;]+)',
    re.IGNORECASE,
)

_CONSTRAINT_KEYWORDS = {
    'CONSTRAINT', 'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK', 'INDEX',
    'KEY', 'EXCLUDE', 'PERIOD', 'LIKE',
}

_TABLE_REF_PATTERN = re.compile(
    r'(?:FROM|JOIN|INTO|UPDATE)\s+([\w.\[\]"`]+)',
    re.IGNORECASE,
)

_TABLE_REF_SKIP = {'SELECT', 'WHERE', 'SET', 'VALUES'}


def _split_identifier(raw: str) -> List[str]:
    """``[dbo].[Tablo]`` / ``"dbo"."Tablo"`` adını parçalara ayırır."""
    parts: List[str] = []
    buf: List[str] = []
    quote = None
    for ch in raw:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch == '[':
            quote = ']'
            buf.append(ch)
        elif ch in ('"', '`'):
            quote = ch
            buf.append(ch)
        elif ch == '.':
            parts.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append(''.join(buf))
    return parts


def normalize_identifier(raw: str) -> str:
    """Tırnaklı/köşeli SQL adını sade biçime çevirir.

    ``[dbo].[ANATAKIP]`` -> ``dbo.ANATAKIP``
    ``"dbo"."PROC"``     -> ``dbo.PROC``
    """
    if not raw:
        return ''
    cleaned: List[str] = []
    for part in _split_identifier(raw.strip().rstrip(';')):
        part = part.strip()
        if len(part) >= 2 and part[0] == '[' and part[-1] == ']':
            part = part[1:-1].replace(']]', ']')
        elif len(part) >= 2 and part[0] == part[-1] and part[0] in ('"', '`', "'"):
            part = part[1:-1]
        if part:
            cleaned.append(part)
    return '.'.join(cleaned)


def _find_matching_paren(text: str, open_index: int) -> int:
    """``open_index`` konumundaki '(' için eşleşen ')' konumunu döndürür."""
    depth = 0
    quote = None
    for i in range(open_index, len(text)):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'", '`'):
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top_level(text: str) -> List[str]:
    """Parantez dışındaki virgüllerden böler (DECIMAL(10,2) korunur)."""
    items: List[str] = []
    buf: List[str] = []
    depth = 0
    quote = None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'", '`'):
            quote = ch
            buf.append(ch)
        elif ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == ',' and depth == 0:
            items.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    items.append(''.join(buf))
    return items


def _extract_columns(body: str) -> Tuple[List[str], List[str]]:
    """CREATE TABLE gövdesinden kolon adlarını ve PK kolonlarını çıkarır."""
    columns: List[str] = []
    primary_key: List[str] = []

    for item in _split_top_level(body):
        item = item.strip()
        if not item:
            continue
        first_token = item.split(None, 1)[0]
        keyword = first_token.upper().strip('"[]`')
        if keyword in _CONSTRAINT_KEYWORDS:
            # PRIMARY KEY hem doğrudan hem "CONSTRAINT <ad> PRIMARY KEY" olarak geçebilir.
            if keyword == 'PRIMARY' or (keyword == 'CONSTRAINT' and 'PRIMARY KEY' in item.upper()):
                pk_match = re.search(r'PRIMARY\s+KEY\s*\(([^)]*)\)', item, re.IGNORECASE)
                if pk_match:
                    primary_key = [
                        normalize_identifier(col)
                        for col in _split_top_level(pk_match.group(1))
                        if col.strip()
                    ]
            continue
        name = normalize_identifier(first_token)
        if name:
            columns.append(name)

    return columns, primary_key


def _extract_parameters(stmt_raw: str) -> List[str]:
    """Prosedür/fonksiyon parametrelerinin ilk sözcüklerini döndürür."""
    params_match = re.search(r'\(([^)]*)\)', stmt_raw, re.IGNORECASE)
    if not params_match:
        return []
    return [
        part.strip().split()[0]
        for part in params_match.group(1).split(',')
        if part.strip()
    ]


def _build_table_signature(name: str, columns: List[str], primary_key: List[str]) -> str:
    signature = f'CREATE TABLE {name} ({len(columns)} kolon'
    if primary_key:
        signature += ', PK: ' + ', '.join(primary_key)
    return signature + ')'


def _build_index_signature(name: str, table: str, columns: List[str], modifiers: str) -> str:
    prefix = 'CREATE '
    if modifiers:
        prefix += ' '.join(modifiers.split()) + ' '
    prefix += 'INDEX'
    signature = f'{prefix} {name}'
    if table:
        signature += f' ON {table}'
    if columns:
        signature += ' (' + ', '.join(columns) + ')'
    return signature


def _extract_index_target(stmt_clean: str) -> Tuple[str, List[str]]:
    """``ON <tablo> (<kolonlar>)`` bölümünü ayrıştırır."""
    on_match = re.search(r'\bON\s+([^\s(]+)\s*\(', stmt_clean, re.IGNORECASE)
    if not on_match:
        return '', []
    table = normalize_identifier(on_match.group(1))
    open_index = stmt_clean.find('(', on_match.end() - 1)
    if open_index == -1:
        return table, []
    close_index = _find_matching_paren(stmt_clean, open_index)
    if close_index == -1:
        return table, []
    body = stmt_clean[open_index + 1:close_index]
    columns = [
        normalize_identifier(col)
        for col in _split_top_level(body)
        if col.strip()
    ]
    return table, columns


def _extract_dependencies(statements) -> List[str]:
    """SELECT/INSERT/UPDATE/DELETE ifadelerindeki tablo referansları."""
    dependencies: List[str] = []
    for stmt in statements:
        if stmt.get_type() not in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
            continue
        for match in _TABLE_REF_PATTERN.finditer(str(stmt)):
            table_name = normalize_identifier(match.group(1))
            if not table_name or table_name.upper() in _TABLE_REF_SKIP:
                continue
            if table_name not in dependencies:
                dependencies.append(table_name)
    return dependencies


def analyze_sql(file_path: str, content: str) -> Dict:
    """SQL dosyasındaki nesneleri ve tablo bağımlılıklarını çıkarır."""
    if not SQLPARSE_AVAILABLE:
        return {
            'functions': [],
            'entry_points': [],
            'dependencies': [],
            'error': 'sqlparse not installed',
        }

    functions: List[Dict] = []
    entry_points: List[Dict] = []

    try:
        statements = sqlparse.parse(content)
        cursor = 0

        for stmt in statements:
            stmt_raw = str(stmt)
            # Satır numarası için artan imleç: aynı metin birden fazla geçse de
            # her ifade kendi konumundan hesaplanır.
            position = content.find(stmt_raw, cursor)
            if position == -1:
                position = cursor
            cursor = position + len(stmt_raw)
            start_line = content.count('\n', 0, position) + 1

            stmt_clean = _COMMENT_PATTERN.sub(' ', stmt_raw)
            object_match = _OBJECT_PATTERN.search(stmt_clean)
            if not object_match:
                continue

            verb = object_match.group(1).upper()
            modifiers = object_match.group(2) or ''
            obj_type = object_match.group(3).lower()
            if obj_type == 'proc':
                obj_type = 'procedure'
            obj_name = normalize_identifier(object_match.group(4))
            if not obj_name:
                continue

            # ALTER TABLE/INDEX mevcut nesneyi değiştirir; yeni nesne sayılmaz.
            if verb == 'ALTER' and obj_type in ('table', 'index'):
                continue

            parameters: List[str] = []
            signature = ''

            if obj_type == 'table':
                open_index = stmt_clean.find('(', object_match.end() - 1)
                columns: List[str] = []
                primary_key: List[str] = []
                if open_index != -1:
                    close_index = _find_matching_paren(stmt_clean, open_index)
                    if close_index != -1:
                        columns, primary_key = _extract_columns(
                            stmt_clean[open_index + 1:close_index]
                        )
                parameters = columns
                signature = _build_table_signature(obj_name, columns, primary_key)

            elif obj_type == 'index':
                table, columns = _extract_index_target(stmt_clean)
                parameters = columns
                signature = _build_index_signature(obj_name, table, columns, modifiers)

            else:
                if obj_type in ('procedure', 'function'):
                    parameters = _extract_parameters(stmt_raw)
                signature = ' '.join(stmt_raw.split()[:6]) + '...'

            func_info = {
                'name': obj_name,
                'type': obj_type,
                'start_line': start_line,
                'end_line': start_line + stmt_raw.count('\n'),
                'parameters': parameters,
                'return_type': None,
                'signature': signature,
                'is_entry': obj_type == 'trigger',
                'class_name': None,
                'package_name': file_path,
            }
            functions.append(func_info)

            if func_info['is_entry']:
                entry_points.append(func_info)

        dependencies = _extract_dependencies(statements)

    except Exception as e:  # pragma: no cover - sqlparse beklenmeyen hata
        return {
            'functions': [],
            'entry_points': [],
            'dependencies': [],
            'error': str(e),
        }

    return {
        'functions': functions,
        'entry_points': entry_points,
        'dependencies': dependencies,
    }
