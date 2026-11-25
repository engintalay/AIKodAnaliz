"""GELIS8: Add files to an existing project.

Code files  (zip, war, java, sql, py, …)    → source_files table + Tree-Sitter analysis + FTS5 update
Document files (pdf, docx, txt, xlsx, xls)  → doc_chunks table + background embedding
"""
import os
import uuid
import zipfile
import shutil
import threading

from flask import Blueprint, request, jsonify
from backend.database import db
from backend.logger import logger, log_audit
from backend.permission_manager import check_project_access, get_user_from_session
from config.config import UPLOAD_DIR

bp = Blueprint('project_files', __name__, url_prefix='/api/projects')

# ------------------------------------------------------------------
# Extension categories
# ------------------------------------------------------------------

CODE_EXTENSIONS = {
    'java', 'kt', 'groovy',
    'py', 'pyw',
    'js', 'mjs', 'cjs', 'jsx', 'ts', 'tsx',
    'php', 'php3', 'php4', 'php5',
    'sql',
    'html', 'htm', 'xhtml', 'jsp', 'jspf',
    'xml', 'json', 'yml', 'yaml', 'properties',
    'css', 'scss', 'sass', 'less',
    'sh', 'bat', 'ps1',
    'rb', 'go', 'rs', 'c', 'cpp', 'h', 'cs',
}

ARCHIVE_EXTENSIONS = {'zip', 'war'}

DOC_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt', 'md', 'xlsx', 'xls'}

SKIP_BINARY_EXTENSIONS = {
    'jar', 'class', 'exe', 'dll', 'so', 'dylib',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'ico', 'bmp',
    'woff', 'woff2', 'ttf', 'eot', 'otf',
    'mp3', 'mp4', 'avi', 'mov', 'zip', 'war', 'jar',
}

LANGUAGE_ALIASES = {
    'js': 'javascript', 'mjs': 'javascript', 'cjs': 'javascript',
    'jsx': 'javascript', 'ts': 'typescript', 'tsx': 'typescript',
    'htm': 'html', 'xhtml': 'html',
}

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower().lstrip('.')


def _detect_language(filename: str) -> str:
    ext = _ext(filename)
    return LANGUAGE_ALIASES.get(ext, ext) if ext else 'unknown'


def _is_binary(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            chunk = f.read(2048)
        if not chunk:
            return False
        if b'\x00' in chunk:
            return True
        non_text = sum(1 for b in chunk if b < 9 or (13 < b < 32))
        return (non_text / len(chunk)) > 0.30
    except Exception:
        return True


def _extract_text_pdf(path: str) -> str:
    pages = _extract_pdf_pages(path)
    return '\n'.join(page for page in pages if page)


def _extract_pdf_pages(path: str) -> list[str]:
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or '')
            except Exception:
                pass
        return parts
    except Exception as e:
        logger.warning(f"PDF extraction failed {path}: {e}")
        return []


def _extract_text_docx(path: str) -> str:
    try:
        import docx
        doc = docx.Document(path)
        return '\n'.join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning(f"DOCX extraction failed {path}: {e}")
        return ''


def _extract_text_excel(path: str) -> str:
    """Extract readable text from Excel files (.xlsx/.xls)."""
    ext = _ext(path)

    if ext == 'xlsx':
        try:
            import openpyxl

            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            parts = []
            for sheet in wb.worksheets:
                parts.append(f"[Sayfa] {sheet.title}")
                for row in sheet.iter_rows(values_only=True):
                    values = [str(v).strip() for v in row if v is not None and str(v).strip()]
                    if values:
                        parts.append("\t".join(values))
            return "\n".join(parts)
        except Exception as e:
            logger.warning(f"XLSX extraction failed {path}: {e}")
            return ''

    if ext == 'xls':
        try:
            import xlrd

            wb = xlrd.open_workbook(path)
            parts = []
            for sheet in wb.sheets():
                parts.append(f"[Sayfa] {sheet.name}")
                for r in range(sheet.nrows):
                    values = []
                    for c in range(sheet.ncols):
                        val = sheet.cell_value(r, c)
                        if val is None:
                            continue
                        sval = str(val).strip()
                        if sval:
                            values.append(sval)
                    if values:
                        parts.append("\t".join(values))
            return "\n".join(parts)
        except Exception as e:
            logger.warning(f"XLS extraction failed {path}: {e}")
            return ''

    return ''


def _extract_document_text(path: str, file_name: str, document_type: str | None = None) -> str:
    """Extract readable text from a stored project document."""
    ext = (document_type or _ext(file_name) or _ext(path) or '').lower()

    if ext == 'pdf':
        return _extract_text_pdf(path)
    if ext == 'docx':
        return _extract_text_docx(path)
    if ext in ('xlsx', 'xls'):
        return _extract_text_excel(path)

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ''


def _chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks of ~size chars."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def _build_document_chunks(
    path: str,
    file_name: str,
    document_type: str | None = None,
    fallback_text: str = '',
) -> tuple[str, list[dict]]:
    """Extract document text and return chunk rows with optional page metadata."""
    ext = (document_type or _ext(file_name) or _ext(path) or '').lower()

    if ext == 'pdf':
        pages = _extract_pdf_pages(path) if path and os.path.exists(path) else []
        if not pages and fallback_text.strip():
            text = fallback_text.strip()
            return text, [
                {'content': chunk, 'page_start': None, 'page_end': None}
                for chunk in _chunk_text(text)
            ]

        text = '\n'.join(page for page in pages if page)
        rows = []
        for page_no, page_text in enumerate(pages, start=1):
            for chunk in _chunk_text(page_text):
                rows.append({
                    'content': chunk,
                    'page_start': page_no,
                    'page_end': page_no,
                })
        return text, rows

    text = _extract_document_text(path, file_name, document_type) if path and os.path.exists(path) else ''
    if not text.strip():
        text = fallback_text.strip()

    return text, [
        {'content': chunk, 'page_start': None, 'page_end': None}
        for chunk in _chunk_text(text)
    ]


def _embed_doc_chunks_async(project_id: int, file_name: str, chunks: list):
    """Generate embeddings for doc_chunks in a background thread."""
    from backend.rag_index import _get_embedding, get_embedding_model

    def worker():
        import requests as _req
        session = _req.Session()
        session.trust_env = False
        emb_model = get_embedding_model()
        for idx, chunk in enumerate(chunks):
            try:
                chunk_text = chunk.get('content') if isinstance(chunk, dict) else chunk
                vec = _get_embedding(chunk_text, session)
                if vec:
                    import json
                    db.execute_update(
                        '''UPDATE doc_chunks SET embedding = ?, model_name = ?
                           WHERE project_id = ? AND file_name = ? AND chunk_index = ?''',
                        (json.dumps(vec), emb_model, project_id, file_name, idx)
                    )
            except Exception as e:
                logger.warning(f"Doc chunk embed error [{file_name}#{idx}]: {e}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def _is_dalmap_file(file_name: str) -> bool:
    """Detect if a file is a DALMap config file.

    Expected pattern: dalMapConfig_*.xml
    """
    name = file_name.lower()
    return name.startswith('dalmapconfig_') and name.endswith('.xml')


def _parse_dalmap_xml(path: str) -> dict:
    """Parse DALMap XML and return structured sections.

    Expected sections:
      - PROXYTABLES (PT)
      - VIRTUALTABLES (VT)
      - CLASSES (CLASS)
      - PROCEDURES (SP)

    Returns a dict with keys: proxy_tables, virtual_tables, classes, procedures.
    """
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        logger.warning(f"DALMap parse error {path}: {e}")
        return {}

    def attrs(elem):
        return {k: v for k, v in elem.attrib.items()}

    def parse_fields(elem):
        fields = []
        for f in elem.findall('FIELD'):
            entry = attrs(f)
            if (text := (f.text or '').strip()):
                entry['text'] = text
            fields.append(entry)
        return fields

    def parse_params(elem):
        params = []
        for p in elem.findall('PARAM'):
            entry = attrs(p)
            if (text := (p.text or '').strip()):
                entry['text'] = text
            params.append(entry)
        return params

    def parse_collections(elem):
        """Parse nested collection mappings under a CLASS/FUNCTION.

        A collection entry maps a child object to another virtual table and
        carries its own FIELD mappings. Any non-FIELD child element is treated
        as a collection entry so different DALMap schema versions are handled.
        """
        items = []
        for child in elem:
            if child.tag == 'FIELD':
                continue
            entry = attrs(child)
            entry['tag'] = child.tag
            entry['fields'] = parse_fields(child)
            entry['collections'] = parse_collections(child)
            items.append(entry)
        return items

    proxy_tables = []
    virtual_tables = []
    classes = []
    procedures = []
    functions = []

    # Scope PT lookups to the PROXYTABLES section only. VIRTUALTABLES also
    # contain <PT name="..."/> references; a global .//PT search would wrongly
    # treat those references as proxy table definitions.
    proxy_root = root.find('PROXYTABLES')
    if proxy_root is not None:
        for pt in proxy_root.findall('PT'):
            entry = attrs(pt)
            entry['fields'] = parse_fields(pt)
            proxy_tables.append(entry)

    vt_root = root.find('VIRTUALTABLES')
    if vt_root is not None:
        for vt in vt_root.findall('VT'):
            entry = attrs(vt)
            # VT references one or more proxy tables via child <PT name="..."/>
            entry['proxy_tables'] = [attrs(child) for child in vt.findall('PT')]
            virtual_tables.append(entry)

    class_root = root.find('CLASSES')
    if class_root is not None:
        for cl in class_root.findall('CLASS'):
            entry = attrs(cl)
            entry['fields'] = parse_fields(cl)
            entry['collections'] = parse_collections(cl)
            classes.append(entry)

    proc_root = root.find('PROCEDURES')
    if proc_root is not None:
        for sp in proc_root.findall('SP'):
            entry = attrs(sp)
            entry['params'] = parse_params(sp)
            procedures.append(entry)

    func_root = root.find('FUNCTIONS')
    if func_root is not None:
        for fn in func_root.findall('FUNCTION'):
            entry = attrs(fn)
            entry['params'] = parse_params(fn)
            entry['collections'] = parse_collections(fn)
            functions.append(entry)

    # Build explicit mappings used by the UI / analysis:
    #   - class -> table (CLASS name/table)
    #   - virtual table -> proxy tables (VT name -> [PT names])
    #   - proxy table -> physical table (PT name -> table)
    class_mappings = [
        {'class': c.get('name'), 'table': c.get('table')}
        for c in classes if c.get('name') or c.get('table')
    ]
    virtual_mappings = [
        {
            'virtual_table': v.get('name'),
            'proxy_tables': [p.get('name') for p in v.get('proxy_tables', []) if p.get('name')],
        }
        for v in virtual_tables if v.get('name')
    ]
    proxy_mappings = [
        {'proxy_table': p.get('name'), 'table': p.get('table'), 'db': p.get('db')}
        for p in proxy_tables if p.get('name')
    ]

    return {
        'proxy_tables': proxy_tables,
        'virtual_tables': virtual_tables,
        'classes': classes,
        'procedures': procedures,
        'functions': functions,
        'mappings': {
            'classes': class_mappings,
            'virtual_tables': virtual_mappings,
            'proxy_tables': proxy_mappings,
        },
    }


def _build_dalmap_text(sections: dict, file_name: str = '') -> str:
    """Build a readable text summary of a DALMap config for RAG indexing.

    The chat assistant only retrieves context from doc_chunks, so DALMap
    configs must be flattened into text to become searchable.

    DALMap structure and how it maps to Java code:
      VIRTUALTABLES: VT name is the table name used in Java code. A VT points
                     to one or more proxy tables (PT) and therefore to the
                     physical DB table. A `partition` attribute means the table
                     is horizontally partitioned (sharded).
      PROXYTABLES:   PT name is referenced by VTs; `table` is the real DB table.
                     FIELD id = Java field name, column = DB column name.
      CLASSES:       CLASS name is the Java class; `table` references a VT.
                     FIELD primarykey="true" marks mandatory (PK) fields.
                     Nested collection entries map child objects to other VTs
                     and describe DB-level table relations.
      FUNCTIONS:     FUNCTION name is the Java method; `table` references a VT.
      PROCEDURES:    SP name is the DB stored procedure; `id` is the name used
                     in Java code. Only input PARAMs exist (id = Java side,
                     column = SP parameter name); there is no return value.
    """
    proxy_tables = sections.get('proxy_tables') or []
    virtual_tables = sections.get('virtual_tables') or []
    classes = sections.get('classes') or []
    procedures = sections.get('procedures') or []
    functions = sections.get('functions') or []

    pt_by_name = {p.get('name'): p for p in proxy_tables if p.get('name')}
    vt_by_name = {v.get('name'): v for v in virtual_tables if v.get('name')}

    lines = []
    title = f'DALMap Konfigürasyonu: {file_name}' if file_name else 'DALMap Konfigürasyonu'
    lines.append(title)
    lines.append(
        f'Özet: {len(proxy_tables)} proxy tablo (PT), '
        f'{len(virtual_tables)} sanal tablo (VT), '
        f'{len(classes)} sınıf (CLASS), '
        f'{len(procedures)} prosedür (SP), '
        f'{len(functions)} fonksiyon.'
    )

    def _is_true(value) -> bool:
        return str(value).strip().lower() in ('true', '1', 'yes')

    def _field_text(field: dict, mark_pk: bool = False) -> str:
        name = field.get('id') or field.get('name') or field.get('text') or ''
        column = field.get('column') or ''
        ftype = field.get('type') or field.get('datatype') or ''
        text = str(name)
        if column and column != name:
            text += f'({column})'
        if ftype:
            text += f':{ftype}'
        if mark_pk and _is_true(field.get('primarykey', field.get('primaryKey'))):
            text += ' [PK]'
        return text

    def _vt_targets(vt: dict) -> list[dict]:
        """Resolve a VT to the proxy table definitions it references."""
        targets = []
        for ref in (vt.get('proxy_tables') or []):
            pt = pt_by_name.get(ref.get('name'))
            if pt:
                targets.append(pt)
        return targets

    def _db_label(pt: dict) -> str:
        table = pt.get('table') or ''
        if table and pt.get('db'):
            return f'{table} ({pt["db"]})'
        return table

    def _append_collections(target_lines: list[str], items: list[dict], indent: int) -> None:
        pad = ' ' * indent
        for item in items:
            tag = item.get('tag') or 'COLLECTION'
            name = item.get('name') or item.get('id') or ''
            line = f'{pad}{tag}: {name}'
            if item.get('table'):
                line += f" → VT: {item.get('table')}"
                vt = vt_by_name.get(item.get('table'))
                if vt:
                    dbs = [_db_label(pt) for pt in _vt_targets(vt) if pt.get('table')]
                    if dbs:
                        line += ' → DB: ' + ', '.join(dbs)
            fields = [_field_text(f, mark_pk=True) for f in (item.get('fields') or [])]
            if fields:
                line += ' | alanlar: ' + ', '.join(fields)
            target_lines.append(line)
            _append_collections(target_lines, item.get('collections') or [], indent + 2)

    # ------------------------------------------------------------------
    # VIRTUALTABLES: Java tablo adı (VT) → proxy tablo (PT) → DB tablosu
    # ------------------------------------------------------------------
    if virtual_tables:
        lines.append('')
        lines.append('=== VIRTUALTABLES (Java tablo adı ↔ DB tablosu) ===')
        for vt in virtual_tables:
            line = f"VT: {vt.get('name', '')}"
            refs = [p.get('name') for p in (vt.get('proxy_tables') or []) if p.get('name')]
            if refs:
                line += ' → PT: ' + ', '.join(refs)
            dbs = [_db_label(pt) for pt in _vt_targets(vt) if pt.get('table')]
            if dbs:
                line += ' → DB: ' + ', '.join(dbs)
            if vt.get('partition'):
                line += f" [SHARDED: partition={vt.get('partition')}]"
            lines.append(line)

    # ------------------------------------------------------------------
    # PROXYTABLES: PT adı → DB tablosu, FIELD id (Java) ↔ column (DB)
    # ------------------------------------------------------------------
    if proxy_tables:
        lines.append('')
        lines.append('=== PROXYTABLES (PT ↔ DB tablosu ve alan eşleştirmeleri) ===')
        for pt in proxy_tables:
            line = f"PT: {pt.get('name', '')}"
            if pt.get('table'):
                line += f" → DB: {pt.get('table')}"
            if pt.get('db'):
                line += f" ({pt.get('db')})"
            fields = [_field_text(f) for f in (pt.get('fields') or [])]
            if fields:
                line += ' | alanlar: ' + ', '.join(fields)
            lines.append(line)

    # ------------------------------------------------------------------
    # CLASSES: Java class → VT, PK alanları, collection eşleştirmeleri
    # ------------------------------------------------------------------
    if classes:
        lines.append('')
        lines.append('=== CLASSES (Java class ↔ VT ve collection eşleştirmeleri) ===')
        for cl in classes:
            line = f"CLASS: {cl.get('name', '')}"
            vt_name = cl.get('table')
            if vt_name:
                line += f" → VT: {vt_name}"
                vt = vt_by_name.get(vt_name)
                if vt:
                    dbs = [_db_label(pt) for pt in _vt_targets(vt) if pt.get('table')]
                    if dbs:
                        line += ' → DB: ' + ', '.join(dbs)
            fields = [_field_text(f, mark_pk=True) for f in (cl.get('fields') or [])]
            if fields:
                line += ' | alanlar: ' + ', '.join(fields)
            lines.append(line)
            _append_collections(lines, cl.get('collections') or [], 2)

    # ------------------------------------------------------------------
    # FUNCTIONS: Java method → VT, parametre eşleştirmeleri
    # ------------------------------------------------------------------
    if functions:
        lines.append('')
        lines.append('=== FUNCTIONS (Java method ↔ VT) ===')
        for fn in functions:
            line = f"FUNCTION: {fn.get('name', '')}"
            if fn.get('table'):
                line += f" → VT: {fn.get('table')}"
            params = [_field_text(p) for p in (fn.get('params') or [])]
            if params:
                line += ' | parametreler: ' + ', '.join(params)
            lines.append(line)
            _append_collections(lines, fn.get('collections') or [], 2)

    # ------------------------------------------------------------------
    # PROCEDURES: DB SP adı ↔ Java çağrı adı (id), input parametreler
    # ------------------------------------------------------------------
    if procedures:
        lines.append('')
        lines.append('=== PROCEDURES (DB SP ↔ Java çağrısı, sadece input parametreler) ===')
        for sp in procedures:
            line = f"PROC: {sp.get('name', '')}"
            meta = []
            if sp.get('id') and sp.get('id') != sp.get('name'):
                meta.append(f"id: {sp.get('id')}")
            if sp.get('db'):
                meta.append(f"db: {sp.get('db')}")
            if meta:
                line += ' (' + ', '.join(meta) + ')'
            params = [_field_text(p) for p in (sp.get('params') or [])]
            if params:
                line += ' | parametreler: ' + ', '.join(params)
            lines.append(line)

    return '\n'.join(lines).strip()


def _index_dalmap_rag(project_id: int, file_name: str, text: str) -> int:
    """Store DALMap summary text as doc_chunks so chat/RAG can retrieve it."""
    chunks = _chunk_text(text)
    if not chunks:
        return 0

    db.execute_update(
        'DELETE FROM doc_chunks WHERE project_id = ? AND file_name = ?',
        (project_id, file_name)
    )

    rows = [
        {'content': chunk, 'page_start': None, 'page_end': None}
        for chunk in chunks
    ]
    for idx, chunk in enumerate(rows):
        db.execute_insert(
            '''INSERT INTO doc_chunks (project_id, file_name, chunk_index, content, page_start, page_end)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (project_id, file_name, idx, chunk['content'], chunk.get('page_start'), chunk.get('page_end'))
        )

    _embed_doc_chunks_async(project_id, file_name, rows)
    return len(rows)


def _process_dalmap_file(project_id: int, file_path: str, rel_path: str, file_name: str) -> bool:
    """Process DALMap file and store its summary for later use."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()

        sections = _parse_dalmap_xml(file_path)

        import json
        # Re-upload: replace the previous record for the same project/file.
        db.execute_update(
            'DELETE FROM dalmap_files WHERE project_id = ? AND file_name = ?',
            (project_id, file_name)
        )
        db.execute_insert(
            '''INSERT INTO dalmap_files
               (project_id, file_name, file_path, raw_xml, tables_json, mappings_json, sections_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (
                project_id,
                file_name,
                rel_path,
                raw,
                json.dumps(sections.get('proxy_tables', []), ensure_ascii=False),
                json.dumps(sections.get('mappings', {}), ensure_ascii=False),
                json.dumps(sections, ensure_ascii=False),
            )
        )

        # Index the DALMap summary into doc_chunks so the chat assistant can
        # retrieve it (chat only searches doc_chunks, not dalmap_files).
        try:
            summary = _build_dalmap_text(sections, file_name)
            chunk_count = _index_dalmap_rag(project_id, file_name, summary)
            logger.info(f"DALMap RAG indexing: {file_name} -> {chunk_count} chunks")
        except Exception as e:
            logger.warning(f"DALMap RAG indexing failed for {file_name}: {e}")

        return True
    except Exception as e:
        logger.warning(f"DALMap file processing error {rel_path}: {e}")
        return False


def _process_doc_file(project_id: int, path: str, file_name: str) -> int:
    """Extract text from doc file, store chunks. Returns chunk count."""
    text, chunks = _build_document_chunks(path, file_name)
    if not chunks:
        return 0

    # Delete previous chunks for this file (re-upload)
    db.execute_update(
        'DELETE FROM doc_chunks WHERE project_id = ? AND file_name = ?',
        (project_id, file_name)
    )

    for idx, chunk in enumerate(chunks):
        db.execute_insert(
            '''INSERT INTO doc_chunks (project_id, file_name, chunk_index, content, page_start, page_end)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (project_id, file_name, idx, chunk['content'], chunk.get('page_start'), chunk.get('page_end'))
        )

    # GELIS20: Insert or update project_documents table to list and serve the document file later.
    try:
        file_type = _ext(file_name)
        file_size = os.path.getsize(path) if os.path.exists(path) else 0
        rel_path = os.path.relpath(path, UPLOAD_DIR)
        
        exists = db.execute_query(
            'SELECT id FROM project_documents WHERE project_id = ? AND file_name = ?',
            (project_id, file_name)
        )
        if exists:
            db.execute_update(
                '''UPDATE project_documents 
                   SET file_path = ?, file_size = ?, extracted_text = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE project_id = ? AND file_name = ?''',
                (rel_path, file_size, text, project_id, file_name)
            )
        else:
            db.execute_insert(
                '''INSERT INTO project_documents 
                   (project_id, file_name, file_path, file_type, document_type, file_size, extracted_text, source_folder)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (project_id, file_name, rel_path, file_type, file_type, file_size, text, 'documents')
            )
    except Exception as e:
        logger.warning(f"Failed to record document metadata in project_documents: {e}")

    # Trigger async embedding
    _embed_doc_chunks_async(project_id, file_name, chunks)
    return len(chunks)


def _rebuild_existing_documents_rag(project_id: int) -> dict:
    """Rebuild doc_chunks + embeddings for already stored project_documents rows."""
    rows = db.execute_query(
        '''SELECT id, file_name, file_path, file_type, document_type, extracted_text, source_folder
           FROM project_documents
           WHERE project_id = ?
           ORDER BY id ASC''',
        (project_id,)
    )

    documents_processed = 0
    chunks_created = 0
    documents_skipped = 0

    for row in rows or []:
        doc = dict(row)
        file_name = doc.get('file_name') or ''
        file_path = doc.get('file_path') or ''
        document_type = doc.get('document_type') or doc.get('file_type') or ''
        extracted_text = ''

        candidate_paths = []
        if file_path:
            candidate_paths.append(file_path if os.path.isabs(file_path) else os.path.join(UPLOAD_DIR, file_path))
        if file_name:
            source_folder = doc.get('source_folder') or 'documents'
            candidate_paths.append(os.path.join(UPLOAD_DIR, f'project_{project_id}', source_folder, file_name))
            candidate_paths.append(os.path.join(UPLOAD_DIR, f'project_{project_id}', 'documents', file_name))

        for candidate in candidate_paths:
            if candidate and os.path.exists(candidate):
                extracted_text = _extract_document_text(candidate, file_name, document_type)
                if extracted_text.strip():
                    break

        if not extracted_text.strip():
            extracted_text = (doc.get('extracted_text') or '').strip()

        if not extracted_text:
            documents_skipped += 1
            continue

        build_path = ''
        for candidate in candidate_paths:
            if candidate and os.path.exists(candidate):
                build_path = candidate
                break

        rebuilt_text, chunks = _build_document_chunks(build_path, file_name, document_type, fallback_text=extracted_text)
        if not chunks:
            documents_skipped += 1
            continue

        db.execute_update(
            'DELETE FROM doc_chunks WHERE project_id = ? AND file_name = ?',
            (project_id, file_name)
        )
        for idx, chunk in enumerate(chunks):
            db.execute_insert(
                '''INSERT INTO doc_chunks (project_id, file_name, chunk_index, content, page_start, page_end)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (project_id, file_name, idx, chunk['content'], chunk.get('page_start'), chunk.get('page_end'))
            )

        if rebuilt_text != (doc.get('extracted_text') or ''):
            db.execute_update(
                '''UPDATE project_documents
                   SET extracted_text = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND project_id = ?''',
                (rebuilt_text, doc['id'], project_id)
            )

        _embed_doc_chunks_async(project_id, file_name, chunks)
        documents_processed += 1
        chunks_created += len(chunks)

    # DALMap configs live in dalmap_files, not project_documents; re-index them
    # as well so a RAG rebuild does not drop them from chat retrieval.
    try:
        import json as _json
        dalmap_rows = db.execute_query(
            'SELECT file_name, file_path, sections_json FROM dalmap_files WHERE project_id = ?',
            (project_id,)
        )
        for row in dalmap_rows or []:
            dm = dict(row)
            dm_name = dm.get('file_name') or ''
            if not dm_name:
                continue
            sections = {}
            # Prefer re-parsing the XML so parser improvements (collections,
            # partition, PK flags) are reflected on rebuild.
            dm_path = dm.get('file_path') or ''
            if dm_path:
                abs_path = dm_path if os.path.isabs(dm_path) else os.path.join(UPLOAD_DIR, dm_path)
                if os.path.exists(abs_path):
                    sections = _parse_dalmap_xml(abs_path)
            if not sections:
                try:
                    sections = _json.loads(dm.get('sections_json') or '{}')
                except Exception:
                    sections = {}
            summary = _build_dalmap_text(sections, dm_name)
            if not summary:
                continue
            chunks_created += _index_dalmap_rag(project_id, dm_name, summary)
            documents_processed += 1
    except Exception as e:
        logger.warning(f"DALMap RAG rebuild error (project={project_id}): {e}")

    return {
        'documents_processed': documents_processed,
        'chunks_created': chunks_created,
        'documents_skipped': documents_skipped,
        'total_documents': len(rows or []),
    }


# ------------------------------------------------------------------
# Route
# ------------------------------------------------------------------

@bp.route('/<int:project_id>/add-file', methods=['POST'])
@check_project_access('write')
def add_file_to_project(project_id):
    """Add one or more files to an existing project.

    Accepts multipart/form-data with 'file' field (one or multiple files).
    Returns a summary of what was processed.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya sağlanmadı'}), 400

    uploaded_files = request.files.getlist('file')
    if not uploaded_files:
        return jsonify({'error': 'Dosya listesi boş'}), 400

    # Verify project exists
    proj = db.execute_query('SELECT id, name FROM projects WHERE id = ?', (project_id,))
    if not proj:
        return jsonify({'error': 'Proje bulunamadı'}), 404

    user = get_user_from_session()

    results = []
    code_files_added = 0
    doc_chunks_added = 0
    dalmap_files_added = 0

    # Temp staging dir for this upload batch
    stage_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}', 'added_files', str(uuid.uuid4()))
    os.makedirs(stage_dir, exist_ok=True)

    try:
        for upload in uploaded_files:
            filename = upload.filename or 'unknown'
            ext = _ext(filename)
            save_path = os.path.join(stage_dir, filename)
            upload.save(save_path)

            if ext in ARCHIVE_EXTENSIONS:
                # Extract archive, then process each file inside
                extract_sub = os.path.join(stage_dir, filename + '_extracted')
                os.makedirs(extract_sub, exist_ok=True)
                try:
                    with zipfile.ZipFile(save_path, 'r') as zf:
                        zf.extractall(extract_sub)
                except Exception as e:
                    results.append({'file': filename, 'status': 'error', 'detail': f'ZIP açılamadı: {e}'})
                    continue

                for root, _, files in os.walk(extract_sub):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        fext = _ext(fname)
                        rel = os.path.relpath(fpath, extract_sub)
                        rel_db = f'added_files/{filename}/{rel}'

                        if fext in SKIP_BINARY_EXTENSIONS:
                            continue
                        if fext in DOC_EXTENSIONS and fext not in CODE_EXTENSIONS:
                            cnt = _process_doc_file(project_id, fpath, fname)
                            doc_chunks_added += cnt
                        elif fext in CODE_EXTENSIONS or (fext and fext not in SKIP_BINARY_EXTENSIONS):
                            if _process_code_file(project_id, fpath, rel_db, fname):
                                code_files_added += 1

                results.append({'file': filename, 'status': 'ok', 'type': 'archive'})

            if _is_dalmap_file(filename):
                rel_db = f'added_files/{filename}'
                if _process_dalmap_file(project_id, save_path, rel_db, filename):
                    dalmap_files_added += 1
                    results.append({'file': filename, 'status': 'ok', 'type': 'dalmap'})
                else:
                    results.append({'file': filename, 'status': 'skipped', 'detail': 'DALMap parse edilemedi'})

            elif ext in DOC_EXTENSIONS and ext not in CODE_EXTENSIONS:
                # Pure document — only RAG
                cnt = _process_doc_file(project_id, save_path, filename)
                doc_chunks_added += cnt
                results.append({'file': filename, 'status': 'ok', 'type': 'document', 'chunks': cnt})

            else:
                # Single code file
                rel_db = f'added_files/{filename}'
                if _process_code_file(project_id, save_path, rel_db, filename):
                    code_files_added += 1
                    results.append({'file': filename, 'status': 'ok', 'type': 'code'})
                else:
                    results.append({'file': filename, 'status': 'skipped', 'detail': 'Binary ya da okunamıyor'})

        # If code files were added, trigger Tree-Sitter analysis and FTS5 update
        if code_files_added > 0:
            _trigger_analysis_async(project_id)
            _trigger_fts_update_async(project_id)

        log_audit(user, 'project_file_added', 'project', project_id,
                  details=f'{code_files_added} code, {doc_chunks_added} doc chunks',
                  request=request)

        return jsonify({
            'message': 'Dosyalar işlendi',
            'code_files_added': code_files_added,
            'doc_chunks_added': doc_chunks_added,
            'files': results,
        }), 200

    except Exception as e:
        logger.error(f"add_file_to_project error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temp staging dir (keep extracted content in project folder)
        pass  # Keep files since they're referenced by DB paths


# ------------------------------------------------------------------
# Async helpers
# ------------------------------------------------------------------

def _trigger_analysis_async(project_id: int):
    """Run Tree-Sitter function extraction in a background thread."""
    def worker():
        try:
            # Re-use the existing analysis logic via direct import
            from backend.routes.analysis import _run_tree_sitter_for_project
            _run_tree_sitter_for_project(project_id)
            logger.info(f"Post-upload analysis complete for project {project_id}")
        except ImportError:
            # Fallback: call via internal API if direct import not available
            logger.warning("_run_tree_sitter_for_project not found; skipping auto-analysis")
        except Exception as e:
            logger.error(f"Post-upload analysis error (project={project_id}): {e}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def _trigger_fts_update_async(project_id: int):
    """Rebuild FTS5 index for the project in a background thread."""
    def worker():
        try:
            from backend.rag_index import RagIndex
            RagIndex.build_fts(project_id)
        except Exception as e:
            logger.warning(f"FTS rebuild after file add error: {e}")

    t = threading.Thread(target=worker, daemon=True)
    t.start()


# ------------------------------------------------------------------
# List docs
# ------------------------------------------------------------------

@bp.route('/<int:project_id>/docs', methods=['GET'])
@check_project_access('read')
def list_project_docs(project_id):
    """Return list of indexed document files and their chunk counts."""
    rows = db.execute_query(
        '''SELECT file_name, COUNT(*) as chunk_count,
                  SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as embedded_count,
                  MAX(created_at) as added_at
           FROM doc_chunks
           WHERE project_id = ?
           GROUP BY file_name
           ORDER BY added_at DESC''',
        (project_id,)
    )
    return jsonify([dict(r) for r in rows]), 200


def _normalize_table_name(name: str) -> str:
    """Normalize SQL table names for matching (strip quotes, lower-case, drop schema)."""
    if not name:
        return ''
    name = name.strip()
    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    # If schema qualified (schema.table), take the last part
    if '.' in name:
        name = name.split('.')[-1]
    return name.lower()


def _extract_sql_create_tables_from_text(sql_text: str) -> dict:
    """Extract CREATE TABLE statements from SQL text."""
    import re

    tables = {}
    if not sql_text:
        return tables

    # Matches CREATE TABLE [IF NOT EXISTS] table_name ( ... );
    # Supports multi-line definitions and optional trailing table options.
    pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\.\"`]+)\s*\((.*?)\)\s*[^;]*;?',
        re.IGNORECASE | re.DOTALL
    )

    for m in pattern.finditer(sql_text):
        raw_name = m.group(1)
        stmt = m.group(0).strip()
        norm_name = _normalize_table_name(raw_name)
        tables[norm_name] = stmt

    return tables


def _extract_sql_procedures_from_text(sql_text: str) -> dict:
    """Extract CREATE PROCEDURE/FUNCTION statements from SQL text."""
    import re

    procs = {}
    if not sql_text:
        return procs

    # Matches CREATE [OR REPLACE] PROCEDURE|FUNCTION proc_name (...) ...;
    # Works across multiple lines.
    pattern = re.compile(
        r'CREATE\s+(?:OR\s+REPLACE\s+)?(PROCEDURE|FUNCTION)\s+([\w\.\"`]+)\s*\((.*?)\)\s*(BEGIN|AS|RETURNS|LANGUAGE|IS|\$\$)',
        re.IGNORECASE | re.DOTALL
    )

    for m in pattern.finditer(sql_text):
        raw_name = m.group(2)
        norm_name = _normalize_table_name(raw_name)
        # Attempt to grab the full statement until the matching END or semicolon.
        start = m.start()
        remainder = sql_text[start:]
        # Simple heuristic: find next semicolon after start (could be inside body), but use first semicolon after 'END' if present.
        end_idx = remainder.find(';')
        if end_idx != -1:
            stmt = remainder[:end_idx + 1].strip()
        else:
            stmt = remainder.strip()
        procs[norm_name] = stmt

    return procs


@bp.route('/<int:project_id>/dalmaps', methods=['GET'])
@check_project_access('read')
def list_dalmap_files(project_id):
    """Return list of processed DALMap files and their parsed sections."""
    try:
        # Gather DALMap entries (raw_xml is intentionally excluded: it can be large
        # and the UI only needs the parsed sections).
        rows = db.execute_query(
            '''SELECT id, file_name, file_path, created_at, updated_at, sections_json
               FROM dalmap_files
               WHERE project_id = ?
               ORDER BY created_at DESC''',
            (project_id,)
        )

        dalmaps = []
        for r in rows:
            entry = dict(r)
            try:
                import json
                entry['sections'] = json.loads(entry.get('sections_json') or '{}')
            except Exception:
                entry['sections'] = {}
            dalmaps.append(entry)

        # Gather SQL table create statements + stored procedures from uploaded .sql source files
        sql_rows = db.execute_query(
            '''SELECT file_name, content FROM source_files
               WHERE project_id = ? AND (LOWER(file_name) LIKE '%.sql' OR LOWER(language) = 'sql')''',
            (project_id,)
        )
        sql_tables = {}
        sql_procedures = {}
        for r in sql_rows:
            try:
                content = r['content'] or ''
                sql_tables.update(_extract_sql_create_tables_from_text(content))
                sql_procedures.update(_extract_sql_procedures_from_text(content))
            except Exception:
                pass

        return jsonify({'dalmaps': dalmaps, 'sql_tables': sql_tables, 'sql_procedures': sql_procedures}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:project_id>/docs/rebuild-rag', methods=['POST'])
@check_project_access('write')
def rebuild_project_docs_rag(project_id):
    """Rebuild doc_chunks and embeddings for already stored documents."""
    user = get_user_from_session()
    try:
        stats = _rebuild_existing_documents_rag(project_id)
        log_audit(
            user,
            'project_documents_rag_rebuilt',
            'project',
            project_id,
            details=f"{stats['documents_processed']} documents, {stats['chunks_created']} chunks",
            request=request,
        )
        return jsonify({
            'message': 'Mevcut dokümanlar yeniden RAG’e alındı',
            **stats,
        }), 200
    except Exception as e:
        logger.error(f"Document RAG rebuild failed for project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:project_id>/docs/file/<filename>', methods=['GET'])
@check_project_access('read')
def serve_project_document(project_id, filename):
    """Serve a project document file securely from UPLOAD_DIR."""
    from flask import send_from_directory
    try:
        rows = db.execute_query(
            'SELECT file_path FROM project_documents WHERE project_id = ? AND file_name = ?',
            (project_id, filename)
        )
        if not rows:
            return jsonify({'error': 'Doküman bulunamadı'}), 404
        
        file_path = rows[0][0]
        full_path = os.path.join(UPLOAD_DIR, file_path)
        if not os.path.exists(full_path):
            return jsonify({'error': f'Doküman dosyası sunucuda bulunamadı: {file_path}'}), 404
        
        dir_name = os.path.dirname(full_path)
        base_name = os.path.basename(full_path)
        return send_from_directory(dir_name, base_name)
    except Exception as e:
        logger.error(f"Error serving document {filename} for project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


def _delete_upload_file(rel_path: str) -> bool:
    """Delete a file inside UPLOAD_DIR safely (no path traversal).

    Returns True when a file was removed, False otherwise.
    """
    if not rel_path:
        return False
    try:
        upload_root = os.path.realpath(UPLOAD_DIR)
        full_path = os.path.realpath(
            rel_path if os.path.isabs(rel_path) else os.path.join(UPLOAD_DIR, rel_path)
        )
        if not (full_path == upload_root or full_path.startswith(upload_root + os.sep)):
            logger.warning(f"Refusing to delete file outside upload dir: {rel_path}")
            return False
        if os.path.isfile(full_path):
            os.remove(full_path)
            return True
    except Exception as e:
        logger.warning(f"Failed to delete upload file {rel_path}: {e}")
    return False


@bp.route('/<int:project_id>/docs/file/<path:filename>', methods=['DELETE'])
@check_project_access('write')
def delete_project_document(project_id, filename):
    """Delete a document/RAG file: DB rows, chunks and the physical file."""
    user = get_user_from_session()
    try:
        rows = db.execute_query(
            'SELECT id, file_path FROM project_documents WHERE project_id = ? AND file_name = ?',
            (project_id, filename)
        )
        chunk_rows = db.execute_query(
            'SELECT COUNT(*) FROM doc_chunks WHERE project_id = ? AND file_name = ?',
            (project_id, filename)
        )
        chunk_count = int(chunk_rows[0][0]) if chunk_rows else 0

        if not rows and chunk_count == 0:
            return jsonify({'error': 'Doküman bulunamadı'}), 404

        file_path = rows[0][1] if rows else ''

        db.execute_update(
            'DELETE FROM doc_chunks WHERE project_id = ? AND file_name = ?',
            (project_id, filename)
        )
        db.execute_update(
            'DELETE FROM project_documents WHERE project_id = ? AND file_name = ?',
            (project_id, filename)
        )

        file_deleted = _delete_upload_file(file_path)

        log_audit(
            user,
            'project_document_deleted',
            'project',
            project_id,
            details=f"{filename} ({chunk_count} chunks, file_deleted={file_deleted})",
            request=request,
        )
        return jsonify({
            'message': 'Doküman silindi',
            'file_name': filename,
            'deleted_chunks': chunk_count,
            'file_deleted': file_deleted,
        }), 200
    except Exception as e:
        logger.error(f"Error deleting document {filename} for project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:project_id>/dalmaps/<int:dalmap_id>', methods=['DELETE'])
@check_project_access('write')
def delete_dalmap_file(project_id, dalmap_id):
    """Delete a DALMap configuration: DB row, RAG chunks and the physical file."""
    user = get_user_from_session()
    try:
        rows = db.execute_query(
            'SELECT id, file_name, file_path FROM dalmap_files WHERE id = ? AND project_id = ?',
            (dalmap_id, project_id)
        )
        if not rows:
            return jsonify({'error': 'DALMap dosyası bulunamadı'}), 404

        file_name = rows[0][1] or ''
        file_path = rows[0][2] or ''

        chunk_rows = db.execute_query(
            'SELECT COUNT(*) FROM doc_chunks WHERE project_id = ? AND file_name = ?',
            (project_id, file_name)
        )
        chunk_count = int(chunk_rows[0][0]) if chunk_rows else 0

        db.execute_update(
            'DELETE FROM doc_chunks WHERE project_id = ? AND file_name = ?',
            (project_id, file_name)
        )
        db.execute_update(
            'DELETE FROM dalmap_files WHERE id = ? AND project_id = ?',
            (dalmap_id, project_id)
        )

        file_deleted = _delete_upload_file(file_path)

        log_audit(
            user,
            'project_dalmap_deleted',
            'project',
            project_id,
            details=f"{file_name} ({chunk_count} chunks, file_deleted={file_deleted})",
            request=request,
        )
        return jsonify({
            'message': 'DALMap dosyası silindi',
            'file_name': file_name,
            'deleted_chunks': chunk_count,
            'file_deleted': file_deleted,
        }), 200
    except Exception as e:
        logger.error(f"Error deleting DALMap {dalmap_id} for project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500
