"""Project export/import routes for GELIS18."""
import os
import json
import zipfile
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file

from backend.database import db
from backend.permission_manager import check_project_access, check_permission, get_user_from_session
from backend.rag_index import RagIndex
from backend.logger import logger, log_audit
from config.config import UPLOAD_DIR

bp = Blueprint('export_import', __name__, url_prefix='/api/projects')


def _table_exists(table_name: str) -> bool:
    """Return True if table exists in current SQLite database."""
    try:
        rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,)
        )
        return bool(rows)
    except Exception:
        return False


def _table_columns(table_name: str) -> set:
    """Return column names for a table (empty set if table is unavailable)."""
    try:
        rows = db.execute_query(f"PRAGMA table_info({table_name})")
        return {row[1] for row in rows} if rows else set()
    except Exception:
        return set()


@bp.route('/<int:project_id>/export', methods=['POST'])
@check_project_access('read')
def export_project(project_id):
    """Export a project as ZIP containing metadata, files, and RAG index.
    
    Response: application/octet-stream (ZIP file)
    """
    user = get_user_from_session()
    
    try:
        # Fetch project metadata
        proj_rows = db.execute_query(
            'SELECT id, name, description, upload_date, last_updated FROM projects WHERE id = ?',
            (project_id,)
        )
        if not proj_rows:
            return jsonify({'error': 'Proje bulunamadı'}), 404
        
        project = dict(proj_rows[0])
        project_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}')
        
        # Create temporary ZIP
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 1. Export metadata
                metadata = {
                    'project_id': project['id'],
                    'project_name': project['name'],
                    'project_description': project['description'],
                    'upload_date': project.get('upload_date'),
                    'last_updated': project.get('last_updated'),
                    'export_date': datetime.now().isoformat(),
                    'export_version': '1.0',
                }
                zf.writestr('metadata.json', json.dumps(metadata, ensure_ascii=False, indent=2))
                
                # 2. Export functions and source files
                functions = db.execute_query(
                    'SELECT * FROM functions WHERE project_id = ?',
                    (project_id,)
                )
                functions_list = [dict(f) for f in functions]
                
                # Convert datetime objects to strings for JSON
                for func in functions_list:
                    for key in func:
                        if hasattr(func[key], 'isoformat'):
                            func[key] = func[key].isoformat()
                
                zf.writestr('functions.json', json.dumps(functions_list, ensure_ascii=False, indent=2))
                
                source_files = db.execute_query(
                    'SELECT * FROM source_files WHERE project_id = ?',
                    (project_id,)
                )
                files_list = [dict(f) for f in source_files]
                for f in files_list:
                    for key in f:
                        if hasattr(f[key], 'isoformat'):
                            f[key] = f[key].isoformat()
                
                zf.writestr('source_files.json', json.dumps(files_list, ensure_ascii=False, indent=2))
                
                # 3. Export project files (uploads)
                if os.path.isdir(project_dir):
                    for root, dirs, files in os.walk(project_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join('files', os.path.relpath(file_path, project_dir))
                            zf.write(file_path, arcname)
                
                # 4. Export RAG index data
                embedding_rows = []
                if _table_exists('function_embeddings'):
                    embedding_rows = db.execute_query(
                        'SELECT * FROM function_embeddings WHERE function_id IN '
                        '(SELECT id FROM functions WHERE project_id = ?)',
                        (project_id,)
                    )
                embeddings = [dict(e) for e in embedding_rows]
                zf.writestr('embeddings.json', json.dumps(embeddings, ensure_ascii=False, indent=2))
                
                doc_chunk_rows = []
                if _table_exists('doc_chunks'):
                    doc_chunk_rows = db.execute_query(
                        'SELECT * FROM doc_chunks WHERE project_id = ?',
                        (project_id,)
                    )
                doc_chunks = [dict(d) for d in doc_chunk_rows]
                for dc in doc_chunks:
                    for key in dc:
                        if hasattr(dc[key], 'isoformat'):
                            dc[key] = dc[key].isoformat()
                zf.writestr('doc_chunks.json', json.dumps(doc_chunks, ensure_ascii=False, indent=2))
                
                doc_embeddings = []
                if _table_exists('doc_embeddings') and _table_exists('doc_chunks'):
                    doc_embeddings = db.execute_query(
                        'SELECT * FROM doc_embeddings WHERE doc_chunk_id IN '
                        '(SELECT id FROM doc_chunks WHERE project_id = ?)',
                        (project_id,)
                    )
                doc_emb = [dict(de) for de in doc_embeddings]
                zf.writestr('doc_embeddings.json', json.dumps(doc_emb, ensure_ascii=False, indent=2))
        
            log_audit(user, 'project_exported', 'project', project_id, request=request)
            
            # Send file
            return send_file(
                tmp_path,
                as_attachment=True,
                download_name=f"{project['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.aikodanaliz",
                mimetype='application/octet-stream'
            )
        
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return jsonify({'error': f'Export hatası: {str(e)}'}), 500


@bp.route('/import', methods=['POST'])
@check_permission('create_project')
def import_project():
    """Import a project from exported ZIP file.
    
    Returns: {project_id: <new_project_id>, name: <project_name>}
    """
    user = get_user_from_session()
    
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya gerekli'}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    tmp_dir = None
    try:
        # Extract ZIP
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, 'export.zip')
        file.save(zip_path)
        
        extract_dir = os.path.join(tmp_dir, 'extract')
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        
        # Load metadata
        metadata_path = os.path.join(extract_dir, 'metadata.json')
        if not os.path.exists(metadata_path):
            return jsonify({'error': 'Geçersiz export dosyası: metadata.json bulunamadı'}), 400
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Create new project in DB
        new_project_name = metadata['project_name']
        new_project_desc = metadata['project_description']
        
        # Check for name conflict
        existing = db.execute_query(
            'SELECT id FROM projects WHERE name = ?',
            (new_project_name,)
        )
        if existing:
            new_project_name = f"{new_project_name} (imported {datetime.now().strftime('%Y%m%d_%H%M%S')})"
        
        db.execute_update(
            'INSERT INTO projects (name, description, admin_id) VALUES (?, ?, ?)',
            (new_project_name, new_project_desc, user['id'])
        )
        
        new_proj_rows = db.execute_query(
            'SELECT id FROM projects WHERE name = ? AND admin_id = ? ORDER BY id DESC LIMIT 1',
            (new_project_name, user['id'])
        )
        if not new_proj_rows:
            return jsonify({'error': 'Proje oluşturulamadı'}), 500
        
        new_project_id = dict(new_proj_rows[0])['id']
        new_project_dir = os.path.join(UPLOAD_DIR, f'project_{new_project_id}')
        os.makedirs(new_project_dir, exist_ok=True)
        
        # Import source files first, then functions (functions depend on file_id)
        source_file_id_map = {}
        source_files_path = os.path.join(extract_dir, 'source_files.json')
        if os.path.exists(source_files_path):
            with open(source_files_path, 'r', encoding='utf-8') as f:
                source_files = json.load(f)
            source_files_cols = _table_columns('source_files')

            for sf in source_files:
                old_source_file_id = sf.get('id')
                file_path = sf.get('file_path') or sf.get('file_name') or ''
                file_name = sf.get('file_name') or os.path.basename(file_path)
                language = sf.get('language')
                content = sf.get('content')
                file_hash = sf.get('hash')

                insert_cols = ['project_id', 'file_path']
                insert_vals = [new_project_id, file_path]
                if 'file_name' in source_files_cols:
                    insert_cols.append('file_name')
                    insert_vals.append(file_name)
                if 'language' in source_files_cols:
                    insert_cols.append('language')
                    insert_vals.append(language)
                if 'content' in source_files_cols:
                    insert_cols.append('content')
                    insert_vals.append(content)
                if 'hash' in source_files_cols:
                    insert_cols.append('hash')
                    insert_vals.append(file_hash)

                placeholders = ','.join(['?'] * len(insert_cols))
                db.execute_update(
                    f"INSERT INTO source_files ({','.join(insert_cols)}) VALUES ({placeholders})",
                    tuple(insert_vals)
                )

                new_rows = db.execute_query(
                    'SELECT id FROM source_files WHERE project_id = ? AND file_path = ? ORDER BY id DESC LIMIT 1',
                    (new_project_id, file_path)
                )
                if new_rows and old_source_file_id is not None:
                    source_file_id_map[old_source_file_id] = dict(new_rows[0])['id']

        # Import functions with deterministic old->new mapping
        function_id_map = {}
        functions_path = os.path.join(extract_dir, 'functions.json')
        if os.path.exists(functions_path):
            with open(functions_path, 'r', encoding='utf-8') as f:
                functions = json.load(f)

            function_cols = _table_columns('functions')
            inserted_old_function_ids = []

            for func in functions:
                old_func_id = func.get('id')
                mapped_file_id = source_file_id_map.get(func.get('file_id'))
                if mapped_file_id is None:
                    # Skip rows that cannot be linked to a file in the imported project.
                    continue

                insert_cols = ['project_id', 'file_id', 'function_name']
                insert_vals = [new_project_id, mapped_file_id, func.get('function_name') or 'unknown_function']

                optional_fields = [
                    'function_type', 'start_line', 'end_line', 'signature', 'parameters',
                    'return_type', 'description', 'ai_summary', 'class_name', 'package_name'
                ]
                for field in optional_fields:
                    if field in function_cols:
                        insert_cols.append(field)
                        insert_vals.append(func.get(field))

                placeholders = ','.join(['?'] * len(insert_cols))
                db.execute_update(
                    f"INSERT INTO functions ({','.join(insert_cols)}) VALUES ({placeholders})",
                    tuple(insert_vals)
                )
                inserted_old_function_ids.append(old_func_id)

            new_func_rows = db.execute_query(
                'SELECT id FROM functions WHERE project_id = ? ORDER BY id ASC',
                (new_project_id,)
            )
            new_function_ids_in_order = [dict(r)['id'] for r in new_func_rows]
            for i, old_id in enumerate(inserted_old_function_ids):
                if old_id is not None and i < len(new_function_ids_in_order):
                    function_id_map[old_id] = new_function_ids_in_order[i]
        
        # Copy project files
        files_src = os.path.join(extract_dir, 'files')
        if os.path.isdir(files_src):
            for root, dirs, files in os.walk(files_src):
                for file in files:
                    src_file = os.path.join(root, file)
                    rel_path = os.path.relpath(src_file, files_src)
                    dst_file = os.path.join(new_project_dir, rel_path)
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    shutil.copy2(src_file, dst_file)
        
        # Import function embeddings with mapped function IDs
        embeddings_path = os.path.join(extract_dir, 'embeddings.json')
        if os.path.exists(embeddings_path) and _table_exists('function_embeddings'):
            with open(embeddings_path, 'r', encoding='utf-8') as f:
                embeddings = json.load(f)
            emb_cols = _table_columns('function_embeddings')

            for emb in embeddings:
                old_func_id = emb.get('function_id')
                new_func_id = function_id_map.get(old_func_id)
                if new_func_id:
                    insert_cols = ['function_id']
                    insert_vals = [new_func_id]

                    if 'project_id' in emb_cols:
                        insert_cols.append('project_id')
                        insert_vals.append(new_project_id)

                    # Support both legacy and current schema naming.
                    if 'embedding' in emb_cols:
                        insert_cols.append('embedding')
                        insert_vals.append(emb.get('embedding') or emb.get('embedding_json'))
                    elif 'embedding_json' in emb_cols:
                        insert_cols.append('embedding_json')
                        insert_vals.append(emb.get('embedding_json') or emb.get('embedding'))

                    if 'model_name' in emb_cols:
                        insert_cols.append('model_name')
                        insert_vals.append(emb.get('model_name'))

                    placeholders = ','.join(['?'] * len(insert_cols))
                    conflict = ' OR REPLACE' if 'function_id' in emb_cols else ''
                    db.execute_update(
                        f"INSERT{conflict} INTO function_embeddings ({','.join(insert_cols)}) VALUES ({placeholders})",
                        tuple(insert_vals)
                    )
        
        # Import doc chunks and doc embeddings with mapped chunk IDs
        doc_chunks_path = os.path.join(extract_dir, 'doc_chunks.json')
        doc_chunk_id_map = {}
        if os.path.exists(doc_chunks_path) and _table_exists('doc_chunks'):
            with open(doc_chunks_path, 'r', encoding='utf-8') as f:
                doc_chunks = json.load(f)
            doc_chunk_cols = _table_columns('doc_chunks')
            old_doc_chunk_ids_in_order = []

            for dc in doc_chunks:
                old_doc_chunk_ids_in_order.append(dc.get('id'))
                insert_cols = []
                insert_vals = []

                if 'project_id' in doc_chunk_cols:
                    insert_cols.append('project_id')
                    insert_vals.append(new_project_id)
                if 'file_name' in doc_chunk_cols:
                    insert_cols.append('file_name')
                    insert_vals.append(dc.get('file_name'))
                if 'chunk_index' in doc_chunk_cols:
                    insert_cols.append('chunk_index')
                    insert_vals.append(dc.get('chunk_index'))
                if 'content' in doc_chunk_cols:
                    insert_cols.append('content')
                    insert_vals.append(dc.get('content'))

                if insert_cols:
                    placeholders = ','.join(['?'] * len(insert_cols))
                    db.execute_update(
                        f"INSERT INTO doc_chunks ({','.join(insert_cols)}) VALUES ({placeholders})",
                        tuple(insert_vals)
                    )

            new_doc_chunk_rows = db.execute_query(
                'SELECT id FROM doc_chunks WHERE project_id = ? ORDER BY id ASC',
                (new_project_id,)
            )
            new_doc_chunk_ids_in_order = [dict(r)['id'] for r in new_doc_chunk_rows]
            for i, old_id in enumerate(old_doc_chunk_ids_in_order):
                if old_id is not None and i < len(new_doc_chunk_ids_in_order):
                    doc_chunk_id_map[old_id] = new_doc_chunk_ids_in_order[i]
        
        doc_embeddings_path = os.path.join(extract_dir, 'doc_embeddings.json')
        if os.path.exists(doc_embeddings_path) and _table_exists('doc_embeddings'):
            with open(doc_embeddings_path, 'r', encoding='utf-8') as f:
                doc_embs = json.load(f)
            doc_emb_cols = _table_columns('doc_embeddings')

            for de in doc_embs:
                old_chunk_id = de.get('doc_chunk_id')
                new_chunk_id = doc_chunk_id_map.get(old_chunk_id)
                if new_chunk_id:
                    insert_cols = []
                    insert_vals = []
                    if 'doc_chunk_id' in doc_emb_cols:
                        insert_cols.append('doc_chunk_id')
                        insert_vals.append(new_chunk_id)
                    if 'embedding' in doc_emb_cols:
                        insert_cols.append('embedding')
                        insert_vals.append(de.get('embedding') or de.get('embedding_json'))
                    elif 'embedding_json' in doc_emb_cols:
                        insert_cols.append('embedding_json')
                        insert_vals.append(de.get('embedding_json') or de.get('embedding'))

                    if insert_cols:
                        placeholders = ','.join(['?'] * len(insert_cols))
                        db.execute_update(
                            f"INSERT INTO doc_embeddings ({','.join(insert_cols)}) VALUES ({placeholders})",
                            tuple(insert_vals)
                        )
        
        log_audit(user, 'project_imported', 'project', new_project_id, request=request)
        
        return jsonify({
            'project_id': new_project_id,
            'name': new_project_name,
            'message': f'Proje başarıyla içe aktarıldı: {new_project_name}'
        }), 201
    
    except Exception as e:
        logger.error(f"Import failed: {e}")
        return jsonify({'error': f'İçe aktarma hatası: {str(e)}'}), 500
    
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
