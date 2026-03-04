from flask import Blueprint, request, jsonify
import os
import zipfile
from datetime import datetime
from backend.database import db
from backend.progress_tracker import progress_tracker
from backend.logger import logger, log_upload, log_error
from config.config import UPLOAD_DIR
import uuid
import subprocess
import shutil

bp = Blueprint('project', __name__, url_prefix='/api/projects')

@bp.route('/', methods=['GET'])
def list_projects():
    """List all projects"""
    try:
        rows = db.execute_query('SELECT id, name, description, upload_date, last_updated FROM projects')
        projects = [dict(row) for row in rows]
        return jsonify(projects), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details"""
    try:
        row = db.execute_query('SELECT * FROM projects WHERE id = ?', (project_id,))
        if not row:
            return jsonify({'error': 'Project not found'}), 404
        return jsonify(dict(row[0])), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/upload', methods=['POST'])
def upload_project():
    """Upload and analyze project"""
    if 'file' not in request.files:
        logger.warning("Upload attempt without file")
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    project_name = request.form.get('name', file.filename.split('.')[0])
    project_desc = request.form.get('description', '')
    
    if not file.filename.endswith('.zip'):
        logger.warning(f"Upload attempt with non-ZIP file: {file.filename}")
        return jsonify({'error': 'Only ZIP files allowed'}), 400
    
    # Generate task ID for progress tracking
    task_id = str(uuid.uuid4())
    logger.info(f"Starting upload: {project_name} | Task: {task_id}")
    
    try:
        progress_tracker.start_task(task_id, total_steps=100)
        progress_tracker.update(task_id, progress=5, step='Proje kaydı oluşturuluyor...', detail='Veritabanına proje kaydediliyor')
        
        # Create project record
        project_id = db.execute_insert(
            'INSERT INTO projects (name, description, admin_id) VALUES (?, ?, ?)',
            (project_name, project_desc, 1)  # TODO: Get actual user ID
        )
        
        log_upload(project_id, "Project record created", task_id=task_id, name=project_name)
        
        progress_tracker.update(task_id, progress=10, step='ZIP dosyası kaydediliyor...', detail=f'Dosya boyutu: {len(file.read())} bytes')
        file.seek(0)  # Reset file pointer after read
        
        # Save and extract zip
        zip_path = os.path.join(UPLOAD_DIR, f'project_{project_id}.zip')
        file.save(zip_path)
        log_upload(project_id, "ZIP file saved", path=zip_path)
        
        progress_tracker.update(task_id, progress=20, step='ZIP dosyası açılıyor...', detail=f'Dosya: {zip_path}')
        
        extract_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            log_upload(project_id, "ZIP extracted", total_files=total_files)
            progress_tracker.update(task_id, progress=25, step=f'ZIP içeriği çıkarılıyor... ({total_files} dosya bulundu)', detail=f'Toplam {total_files} dosya çıkarılacak')
            zip_ref.extractall(extract_dir)
        
        progress_tracker.update(task_id, progress=30, step='Dosyalar tarıyor ve işleniyor...', detail='Kaynak dosyalar veritabanına aktarılıyor')
        
        # Process extracted files
        processed_files = 0
        skipped_files = 0
        all_files = []
        
        # Collect all files first
        for root, dirs, files in os.walk(extract_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                all_files.append((file_path, file_name))
        
        total_to_process = len(all_files)
        logger.debug(f"[Project {project_id}] Found {total_to_process} files to process")
        
        for idx, (file_path, file_name) in enumerate(all_files):
            rel_path = os.path.relpath(file_path, extract_dir)
            
            # Update progress for each file
            current_progress = 30 + int((idx / total_to_process) * 60)  # 30-90% range
            progress_tracker.update(
                task_id, 
                progress=current_progress, 
                step=f'Dosya işleniyor: {file_name} ({idx + 1}/{total_to_process})',
                detail=f'İşleniyor: {rel_path}'
            )
            
            # Determine language
            ext = os.path.splitext(file_name)[1].lower().lstrip('.')
            language = ext if ext else 'unknown'
            
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                # Store in database
                file_id = db.execute_insert(
                    '''INSERT INTO source_files 
                    (project_id, file_path, file_name, language, content)
                    VALUES (?, ?, ?, ?, ?)''',
                    (project_id, rel_path, file_name, language, content)
                )
                processed_files += 1
                logger.debug(f"[Project {project_id}] Processed: {rel_path} (ID: {file_id})")
            except Exception as e:
                skipped_files += 1
                logger.warning(f"[Project {project_id}] Skipped {rel_path}: {str(e)}")
                progress_tracker.update(task_id, detail=f'Atlandı (okunamadı): {rel_path}')
                continue
        
        log_upload(project_id, "File processing complete", processed=processed_files, skipped=skipped_files)
        progress_tracker.update(task_id, progress=95, step='Temizlik yapılıyor...', detail='Geçici dosyalar siliniyor')
        
        # Clean up zip file
        os.remove(zip_path)
        logger.debug(f"[Project {project_id}] Temporary ZIP removed")
        
        progress_tracker.complete(task_id, success=True, message=f'Tamamlandı! {processed_files} dosya işlendi, {skipped_files} atlandı')
        logger.info(f"Upload completed: Project {project_id} | Files: {processed_files} processed, {skipped_files} skipped")
        
        return jsonify({
            'project_id': project_id,
            'task_id': task_id,
            'name': project_name,
            'files_processed': processed_files,
            'files_skipped': skipped_files,
            'message': 'Project uploaded successfully'
        }), 201
    
    except Exception as e:
        log_error(f"upload_project (task: {task_id})", e, project_name=project_name)
        progress_tracker.complete(task_id, success=False, message=f'Hata: {str(e)}')
        return jsonify({'error': str(e), 'task_id': task_id}), 500

@bp.route('/import-git', methods=['POST'])
def import_git_project():
    """Clone and analyze project from Git repository"""
    data = request.get_json()
    
    repo_url = data.get('url', '').strip()
    branch = data.get('branch', 'main').strip()
    project_name = data.get('name', '').strip()
    project_desc = data.get('description', '').strip()
    
    if not repo_url or not project_name:
        return jsonify({'error': 'Git URL and Project Name are required'}), 400
    
    task_id = str(uuid.uuid4())
    logger.info(f"Starting Git import: {project_name} from {repo_url} | Task: {task_id}")
    
    try:
        progress_tracker.start_task(task_id, total_steps=100)
        progress_tracker.update(task_id, progress=5, step='Proje kaydı oluşturuluyor...', detail='Veritabanına proje kaydediliyor')
        
        # Create project record
        project_id = db.execute_insert(
            'INSERT INTO projects (name, description, admin_id) VALUES (?, ?, ?)',
            (project_name, project_desc, 1)
        )
        
        log_upload(project_id, "Project record created (Git)", task_id=task_id, name=project_name, url=repo_url)
        progress_tracker.update(task_id, progress=10, step='Repository klonlanıyor...', detail=f'URL: {repo_url}')
        
        # Clone repository
        clone_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}_git')
        os.makedirs(clone_dir, exist_ok=True)
        
        clone_command = [
            'git', 'clone', 
            '--branch', branch,
            '--depth', '1',  # Shallow clone for speed
            '--progress',
            repo_url,
            clone_dir
        ]
        
        try:
            result = subprocess.run(clone_command, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.error(f"Git clone failed: {result.stderr}")
                raise Exception(f"Git clone failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Git clone timeout (5 minutes)")
        except FileNotFoundError:
            raise Exception("Git is not installed on the system")
        
        log_upload(project_id, "Repository cloned", clone_dir=clone_dir)
        progress_tracker.update(task_id, progress=30, step='Dosyalar tarıyor ve işleniyor...', detail='Kaynak dosyalar veritabanına aktarılıyor')
        
        # Process cloned files (same as ZIP extraction)
        processed_files = 0
        skipped_files = 0
        all_files = []
        
        # Collect all files
        for root, dirs, files in os.walk(clone_dir):
            # Skip .git directory
            if '.git' in dirs:
                dirs.remove('.git')
            
            for file_name in files:
                file_path = os.path.join(root, file_name)
                all_files.append((file_path, file_name))
        
        total_to_process = len(all_files)
        logger.debug(f"[Project {project_id}] Found {total_to_process} files to process from Git")
        
        for idx, (file_path, file_name) in enumerate(all_files):
            rel_path = os.path.relpath(file_path, clone_dir)
            
            # Update progress
            current_progress = 30 + int((idx / total_to_process) * 60) if total_to_process > 0 else 30
            progress_tracker.update(
                task_id, 
                progress=current_progress, 
                step=f'Dosya işleniyor: {file_name} ({idx + 1}/{total_to_process})',
                detail=f'İşleniyor: {rel_path}'
            )
            
            # Determine language
            ext = os.path.splitext(file_name)[1].lower().lstrip('.')
            language = ext if ext else 'unknown'
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Store in database
                file_id = db.execute_insert(
                    '''INSERT INTO source_files 
                    (project_id, file_path, file_name, language, content)
                    VALUES (?, ?, ?, ?, ?)''',
                    (project_id, rel_path, file_name, language, content)
                )
                processed_files += 1
                logger.debug(f"[Project {project_id}] Processed: {rel_path} (ID: {file_id})")
            except Exception as e:
                skipped_files += 1
                logger.warning(f"[Project {project_id}] Skipped {rel_path}: {str(e)}")
                progress_tracker.update(task_id, detail=f'Atlandı (okunamadı): {rel_path}')
                continue
        
        log_upload(project_id, "File processing complete", processed=processed_files, skipped=skipped_files)
        progress_tracker.update(task_id, progress=95, step='Temizlik yapılıyor...', detail='Geçici dosyalar siliniyor')
        
        # Clean up cloned directory
        shutil.rmtree(clone_dir, ignore_errors=True)
        logger.debug(f"[Project {project_id}] Temporary clone directory removed")
        
        progress_tracker.complete(task_id, success=True, message=f'Tamamlandı! {processed_files} dosya işlendi, {skipped_files} atlandı')
        logger.info(f"Git import completed: Project {project_id} | Files: {processed_files} processed, {skipped_files} skipped")
        
        return jsonify({
            'project_id': project_id,
            'task_id': task_id,
            'name': project_name,
            'files_processed': processed_files,
            'files_skipped': skipped_files,
            'message': 'Git project imported successfully'
        }), 201
    
    except Exception as e:
        log_error(f"import_git_project (task: {task_id})", e, project_name=project_name, repo_url=repo_url)
        progress_tracker.complete(task_id, success=False, message=f'Hata: {str(e)}')
        
        # Try to clean up failed clone
        try:
            clone_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}_git')
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir, ignore_errors=True)
        except:
            pass
        
        return jsonify({'error': str(e), 'task_id': task_id}), 500

@bp.route('/<int:project_id>/files', methods=['GET'])
def get_project_files(project_id):
    """Get all source files in project"""
    try:
        rows = db.execute_query(
            'SELECT id, file_name, file_path, language FROM source_files WHERE project_id = ?',
            (project_id,)
        )
        files = [dict(row) for row in rows]
        return jsonify(files), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete project"""
    try:
        import shutil
        
        # Delete database records
        db.execute_update('DELETE FROM projects WHERE id = ?', (project_id,))
        
        # Delete physical files
        extract_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}')
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        
        return jsonify({'message': 'Project deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/progress/<task_id>', methods=['GET'])
def get_upload_progress(task_id):
    """Get progress for an upload task"""
    try:
        progress = progress_tracker.get_progress(task_id)
        
        if progress is None:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify(progress), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
