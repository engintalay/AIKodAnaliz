"""GELIS8: Add files to an existing project.

Code files  (zip, war, java, sql, py, …) → source_files table + Tree-Sitter analysis + FTS5 update
Document files (pdf, docx, txt)          → doc_chunks table + background embedding
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
    'txt', 'md',
}

ARCHIVE_EXTENSIONS = {'zip', 'war'}

DOC_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt', 'md'}

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
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or '')
            except Exception:
                pass
        return '\n'.join(parts)
    except Exception as e:
        logger.warning(f"PDF extraction failed {path}: {e}")
        return ''


def _extract_text_docx(path: str) -> str:
    try:
        import docx
        doc = docx.Document(path)
        return '\n'.join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning(f"DOCX extraction failed {path}: {e}")
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


def _embed_doc_chunks_async(project_id: int, file_name: str, chunks: list[str]):
    """Generate embeddings for doc_chunks in a background thread."""
    from backend.rag_index import _get_embedding, EMBEDDING_MODEL

    def worker():
        import requests as _req
        session = _req.Session()
        session.trust_env = False
        for idx, chunk in enumerate(chunks):
            try:
                vec = _get_embedding(chunk, session)
                if vec:
                    import json
                    db.execute_update(
                        '''UPDATE doc_chunks SET embedding = ?, model_name = ?
                           WHERE project_id = ? AND file_name = ? AND chunk_index = ?''',
                        (json.dumps(vec), EMBEDDING_MODEL, project_id, file_name, idx)
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

    proxy_tables = []
    virtual_tables = []
    classes = []
    procedures = []

    for pt in root.findall('.//PT'):
        entry = attrs(pt)
        entry['fields'] = parse_fields(pt)
        proxy_tables.append(entry)

    for vt in root.findall('.//VT'):
        entry = attrs(vt)
        # VT may contain PT references (as child tags) or other info
        entry['proxy_tables'] = [attrs(child) for child in vt.findall('PT')]
        virtual_tables.append(entry)

    for cl in root.findall('.//CLASS'):
        entry = attrs(cl)
        entry['fields'] = []
        for f in cl.findall('FIELD'):
            field_entry = attrs(f)
            if (text := (f.text or '').strip()):
                field_entry['text'] = text
            entry['fields'].append(field_entry)
        classes.append(entry)

    for sp in root.findall('.//SP'):
        entry = attrs(sp)
        entry['params'] = parse_params(sp)
        procedures.append(entry)

    return {
        'proxy_tables': proxy_tables,
        'virtual_tables': virtual_tables,
        'classes': classes,
        'procedures': procedures
    }


def _process_dalmap_file(project_id: int, file_path: str, rel_path: str, file_name: str) -> bool:
    """Process DALMap file and store its summary for later use."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()

        sections = _parse_dalmap_xml(file_path)

        import json
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
                json.dumps(sections.get('mappings', []), ensure_ascii=False),
                json.dumps(sections, ensure_ascii=False),
            )
        )
        return True
    except Exception as e:
        logger.warning(f"DALMap file processing error {rel_path}: {e}")
        return False


def _process_doc_file(project_id: int, path: str, file_name: str) -> int:
    """Extract text from doc file, store chunks. Returns chunk count."""
    ext = _ext(file_name)
    if ext == 'pdf':
        text = _extract_text_pdf(path)
    elif ext in ('docx',):
        text = _extract_text_docx(path)
    else:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception:
            text = ''

    chunks = _chunk_text(text)
    if not chunks:
        return 0

    # Delete previous chunks for this file (re-upload)
    db.execute_update(
        'DELETE FROM doc_chunks WHERE project_id = ? AND file_name = ?',
        (project_id, file_name)
    )

    for idx, chunk in enumerate(chunks):
        db.execute_insert(
            '''INSERT INTO doc_chunks (project_id, file_name, chunk_index, content)
               VALUES (?, ?, ?, ?)''',
            (project_id, file_name, idx, chunk)
        )

    # Trigger async embedding
    _embed_doc_chunks_async(project_id, file_name, chunks)
    return len(chunks)


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
        # Gather DALMap entries
        rows = db.execute_query(
            '''SELECT id, file_name, file_path, created_at, updated_at, raw_xml, sections_json
               FROM dalmap_files
               WHERE project_id = ?
               ORDER BY created_at DESC''',
            (project_id,)
        )

        dalmaps = []
        for r in rows:
            entry = dict(r)
            entry['raw_xml'] = entry.get('raw_xml') or ''
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
