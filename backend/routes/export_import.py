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
            'SELECT id, name, description, created_at FROM projects WHERE id = ?',
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
                    'created_at': project['created_at'],
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
                embedding_rows = db.execute_query(
                    'SELECT * FROM function_embeddings WHERE function_id IN '
                    '(SELECT id FROM functions WHERE project_id = ?)',
                    (project_id,)
                )
                embeddings = [dict(e) for e in embedding_rows]
                zf.writestr('embeddings.json', json.dumps(embeddings, ensure_ascii=False, indent=2))
                
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
        
        # Import functions
        functions_path = os.path.join(extract_dir, 'functions.json')
        if os.path.exists(functions_path):
            with open(functions_path, 'r', encoding='utf-8') as f:
                functions = json.load(f)
            
            for func in functions:
                func['project_id'] = new_project_id
                # Remove old IDs, let them be auto-generated
                old_id = func.pop('id', None)
                
                db.execute_update(
                    '''INSERT INTO functions 
                       (project_id, function_name, class_name, file_name, signature, ai_summary)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (func['project_id'], func['function_name'], func.get('class_name'),
                     func['file_name'], func.get('signature'), func.get('ai_summary'))
                )
        
        # Import source files
        source_files_path = os.path.join(extract_dir, 'source_files.json')
        if os.path.exists(source_files_path):
            with open(source_files_path, 'r', encoding='utf-8') as f:
                source_files = json.load(f)
            
            for sf in source_files:
                sf['project_id'] = new_project_id
                sf.pop('id', None)
                
                db.execute_update(
                    '''INSERT INTO source_files 
                       (project_id, file_path, file_type, size_bytes)
                       VALUES (?, ?, ?, ?)''',
                    (sf['project_id'], sf['file_path'], sf.get('file_type'), sf.get('size_bytes'))
                )
        
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
        
        # Import RAG embeddings
        embeddings_path = os.path.join(extract_dir, 'embeddings.json')
        if os.path.exists(embeddings_path):
            with open(embeddings_path, 'r', encoding='utf-8') as f:
                embeddings = json.load(f)
            
            # Map old function IDs to new ones
            func_id_map = {}
            old_funcs = db.execute_query(
                'SELECT id FROM functions WHERE project_id = ? ORDER BY id',
                (new_project_id,)
            )
            for i, func in enumerate(functions if 'functions' in locals() else []):
                if i < len(old_funcs):
                    new_id = dict(old_funcs[i])['id']
                    func_id_map[func.get('id')] = new_id
            
            for emb in embeddings:
                old_func_id = emb.pop('function_id', None)
                new_func_id = func_id_map.get(old_func_id)
                if new_func_id:
                    emb.pop('id', None)
                    db.execute_update(
                        'INSERT INTO function_embeddings (function_id, embedding_json) VALUES (?, ?)',
                        (new_func_id, emb.get('embedding_json'))
                    )
        
        # Import doc chunks and embeddings
        doc_chunks_path = os.path.join(extract_dir, 'doc_chunks.json')
        doc_chunk_id_map = {}
        if os.path.exists(doc_chunks_path):
            with open(doc_chunks_path, 'r', encoding='utf-8') as f:
                doc_chunks = json.load(f)
            
            for dc in doc_chunks:
                old_id = dc.pop('id', None)
                dc['project_id'] = new_project_id
                
                db.execute_update(
                    '''INSERT INTO doc_chunks 
                       (project_id, file_name, chunk_index, content)
                       VALUES (?, ?, ?, ?)''',
                    (dc['project_id'], dc['file_name'], dc['chunk_index'], dc['content'])
                )
                
                # Get the new ID
                new_rows = db.execute_query(
                    'SELECT id FROM doc_chunks WHERE project_id = ? AND file_name = ? AND chunk_index = ?',
                    (dc['project_id'], dc['file_name'], dc['chunk_index'])
                )
                if new_rows:
                    new_id = dict(new_rows[0])['id']
                    doc_chunk_id_map[old_id] = new_id
        
        doc_embeddings_path = os.path.join(extract_dir, 'doc_embeddings.json')
        if os.path.exists(doc_embeddings_path):
            with open(doc_embeddings_path, 'r', encoding='utf-8') as f:
                doc_embs = json.load(f)
            
            for de in doc_embs:
                old_chunk_id = de.pop('doc_chunk_id', None)
                new_chunk_id = doc_chunk_id_map.get(old_chunk_id)
                if new_chunk_id:
                    de.pop('id', None)
                    db.execute_update(
                        'INSERT INTO doc_embeddings (doc_chunk_id, embedding_json) VALUES (?, ?)',
                        (new_chunk_id, de.get('embedding_json'))
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
