from flask import Blueprint, request, jsonify
import os
import zipfile
from datetime import datetime
from backend.database import db
from backend.progress_tracker import progress_tracker
from backend.logger import logger, log_upload, log_error, log_audit
from backend.rag_index import RagIndex
from config.config import UPLOAD_DIR
import uuid
import subprocess
import shutil
from backend.permission_manager import check_permission, check_project_access, get_user_from_session, get_user_projects

bp = Blueprint('project', __name__, url_prefix='/api/projects')

LANGUAGE_ALIASES = {
    'js': 'javascript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'htm': 'html',
    'xhtml': 'html',
    'jspf': 'jsp',
    'tag': 'jsp',
    'tagx': 'jsp',
}

# WAR içindeki web içeriklerini özellikle dahil et
WAR_TEXT_EXTENSIONS = {
    'html', 'htm', 'xhtml', 'jsp', 'jspf', 'tag', 'tagx',
    'js', 'mjs', 'cjs', 'jsx', 'ts', 'tsx', 'css', 'scss', 'sass', 'less',
    'xml', 'json', 'yml', 'yaml', 'properties', 'sql',
    'java', 'kt', 'groovy', 'py', 'php', 'txt', 'md'
}

SKIP_BINARY_EXTENSIONS = {
    'jar', 'war', 'zip', 'class', 'exe', 'dll', 'so', 'dylib',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'ico', 'bmp', 'svgz',
    'pdf', 'woff', 'woff2', 'ttf', 'eot', 'otf', 'mp3', 'mp4', 'avi', 'mov'
}

@bp.route('/', methods=['GET'])
def list_projects():
    """List all projects user has access to"""
    try:
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
            
        projects = get_user_projects(user['id'])
        enhanced = []
        for row in projects:
            proj = dict(row)

            # RAG / AI analysis metrics
            status = RagIndex.get_build_status(proj['id'])
            total_funcs = status.get('total_functions', 0) or 0
            indexed = status.get('indexed', 0) or 0

            # FTS index coverage
            try:
                fts_rows = db.execute_query(
                    'SELECT COUNT(*) FROM fts_functions WHERE function_id IN (SELECT id FROM functions WHERE project_id = ?)',
                    (proj['id'],)
                )
                fts_indexed = fts_rows[0][0] if fts_rows else 0
            except Exception:
                fts_indexed = 0

            # AI summary coverage
            try:
                ai_rows = db.execute_query(
                    'SELECT COUNT(*) FROM functions WHERE project_id = ? AND ai_summary IS NOT NULL AND ai_summary != ""',
                    (proj['id'],)
                )
                ai_count = ai_rows[0][0] if ai_rows else 0
            except Exception:
                ai_count = 0

            proj['total_functions'] = total_funcs
            proj['rag_embedding_indexed'] = indexed
            proj['rag_fts_indexed'] = fts_indexed
            proj['ai_summary_count'] = ai_count
            proj['ai_summary_pct'] = total_funcs > 0 and round((ai_count / total_funcs) * 100) or 0
            proj['rag_status'] = status.get('status', 'idle')

            enhanced.append(proj)

        return jsonify(enhanced), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:project_id>', methods=['GET'])
@check_project_access('read')
def get_project(project_id):
    """Get project details"""
    try:
        row = db.execute_query('SELECT * FROM projects WHERE id = ?', (project_id,))
        if not row:
            return jsonify({'error': 'Project not found'}), 404
        user = get_user_from_session()
        log_audit(user, 'project_view', 'project', project_id, request=request)
        return jsonify(dict(row[0])), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:project_id>', methods=['PUT'])
@check_project_access('write')
def update_project(project_id):
    """Update project details (like description)"""
    try:
        data = request.json
        if not data or 'description' not in data:
            return jsonify({'error': 'Description is required'}), 400
            
        description = data['description']
        
        db.execute_update(
            'UPDATE projects SET description = ? WHERE id = ?',
            (description, project_id)
        )
        
        # Fetch updated record
        row = db.execute_query('SELECT * FROM projects WHERE id = ?', (project_id,))
        if not row:
            return jsonify({'error': 'Project not found after update'}), 404
            
        logger.info(f"Updated project description for project_id={project_id}")
        user = get_user_from_session()
        log_audit(user, 'project_update', 'project', project_id, details=f'description updated', request=request)
        return jsonify(dict(row[0])), 200
        
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        return jsonify({'error': str(e)}), 500

def _extract_nested_jars(extract_dir, logger):
    """Extract JAR files nested in WAR (typically in WEB-INF/lib)"""
    jar_count = 0
    
    # Walk through all directories
    for root, dirs, files in os.walk(extract_dir):
        for file_name in files:
            if file_name.lower().endswith('.jar'):
                jar_path = os.path.join(root, file_name)
                jar_extract_dir = os.path.join(root, file_name.replace('.jar', '_extracted'))
                
                try:
                    # Create extraction directory
                    os.makedirs(jar_extract_dir, exist_ok=True)
                    
                    # Extract JAR file
                    with zipfile.ZipFile(jar_path, 'r') as jar_ref:
                        jar_ref.extractall(jar_extract_dir)
                        jar_count += 1
                        logger.debug(f"Extracted JAR: {jar_path} to {jar_extract_dir}")
                        
                except Exception as e:
                    logger.warning(f"Failed to extract JAR {jar_path}: {e}")
                    continue
    
    if jar_count > 0:
        logger.info(f"Successfully extracted {jar_count} JAR files from WAR")
    
    return jar_count


def _detect_language(file_name):
    ext = os.path.splitext(file_name)[1].lower().lstrip('.')
    if not ext:
        return 'unknown'
    return LANGUAGE_ALIASES.get(ext, ext)


def _is_binary_file(file_path):
    """Quick binary detection to avoid indexing unreadable assets."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(2048)
        if not chunk:
            return False
        if b'\x00' in chunk:
            return True
        non_text = sum(1 for b in chunk if b < 9 or (13 < b < 32))
        return (non_text / len(chunk)) > 0.30
    except Exception:
        return True


def _should_index_file(file_name, file_path, is_war=False):
    ext = os.path.splitext(file_name)[1].lower().lstrip('.')

    if ext in SKIP_BINARY_EXTENSIONS:
        return False

    # WAR yüklemelerinde web sayfası için gerekli metin dosyalarını öncelikli indeksle
    if is_war and ext and ext not in WAR_TEXT_EXTENSIONS:
        return False

    if _is_binary_file(file_path):
        return False

    return True

@bp.route('/upload', methods=['POST'])
@check_permission('create_project')
def upload_project():
    """Upload and analyze project"""
    if 'file' not in request.files:
        logger.warning("Upload attempt without file")
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    project_name = request.form.get('name', file.filename.split('.')[0])
    project_desc = request.form.get('description', '')
    
    file_lower = file.filename.lower()
    if not (file_lower.endswith('.zip') or file_lower.endswith('.war')):
        logger.warning(f"Upload attempt with non-ZIP/WAR file: {file.filename}")
        return jsonify({'error': 'Only ZIP and WAR files allowed'}), 400
    
    is_war = file_lower.endswith('.war')

    # Generate task ID for progress tracking
    task_id = str(uuid.uuid4())
    logger.info(f"Starting upload: {project_name} | Task: {task_id}")

    try:
        progress_tracker.start_task(task_id, total_steps=100)
        progress_tracker.update(task_id, progress=5, step='Proje kaydı oluşturuluyor...', detail='Veritabanına proje kaydediliyor')

        # Create project record
        user = get_user_from_session()
        project_id = db.execute_insert(
            'INSERT INTO projects (name, description, admin_id) VALUES (?, ?, ?)',
            (project_name, project_desc, user['id'])
        )

        log_upload(project_id, "Project record created", task_id=task_id, name=project_name)

        progress_tracker.update(task_id, progress=10, step='ZIP dosyası kaydediliyor...', detail=f'Dosya boyutu: {len(file.read())} bytes')
        file.seek(0)  # Reset file pointer after read

        # Save and extract zip/war payload
        zip_path = os.path.join(UPLOAD_DIR, f'project_{project_id}.zip')
        file.save(zip_path)
        log_upload(project_id, "ZIP file saved", path=zip_path)

        progress_tracker.update(task_id, progress=20, step='ZIP dosyası açılıyor...', detail=f'Dosya: {zip_path}')

        extract_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            log_upload(project_id, "ZIP/WAR extracted", total_files=total_files)
            progress_tracker.update(task_id, progress=25, step=f'ZIP/WAR içeriği çıkarılıyor... ({total_files} dosya bulundu)', detail=f'Toplam {total_files} dosya çıkarılacak')
            zip_ref.extractall(extract_dir)

        # If WAR file, extract nested JARs
        if is_war:
            progress_tracker.update(task_id, progress=26, step='WAR içindeki JAR dosyaları çıkarılıyor...', detail='Nested JAR dosyaları taranıyor')
            logger.info(f"[Project {project_id}] Extracting nested JARs from WAR file")
            _extract_nested_jars(extract_dir, logger)

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
            current_progress = 30 + int((idx / total_to_process) * 60) if total_to_process > 0 else 30
            progress_tracker.update(
                task_id,
                progress=current_progress,
                step=f'Dosya işleniyor: {file_name} ({idx + 1}/{total_to_process})',
                detail=f'İşleniyor: {rel_path}'
            )

            if not _should_index_file(file_name, file_path, is_war=is_war):
                skipped_files += 1
                logger.debug(f"[Project {project_id}] Skipped non-text/binary: {rel_path}")
                continue

            # Determine language (normalized aliases)
            language = _detect_language(file_name)

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


@bp.route('/<int:project_id>/add-file', methods=['POST'])
@check_project_access('write')
def add_files_to_project(project_id):
    """Add new files to an existing project (GELIS8)"""
    try:
        # Check project exists
        project = db.execute_query('SELECT * FROM projects WHERE id = ?', (project_id,))
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if 'file' not in request.files:
            logger.warning(f"Add file attempt without file for project {project_id}")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        task_id = str(uuid.uuid4())
        logger.info(f"Starting add file: {file.filename} to Project {project_id} | Task: {task_id}")
        
        try:
            progress_tracker.start_task(task_id, total_steps=100)
            progress_tracker.update(task_id, progress=5, step='Dosya işleniyor...', detail=f'Dosya: {file.filename}')
            
            user = get_user_from_session()
            log_upload(project_id, "Add file initiated", task_id=task_id, file_name=file.filename)
            
            file_lower = file.filename.lower()
            processed_files = 0
            skipped_files = 0
            added_documents = 0
            added_single_file_id = None
            
            # Determine file type and process accordingly
            if file_lower.endswith(('.zip', '.war', '.jar')):
                # Extract archive files
                progress_tracker.update(task_id, progress=10, step='Arşiv dosyası çıkarılıyor...', detail=f'İçerik analiz ediliyor')
                
                # Create temporary extraction directory
                temp_extract_dir = os.path.join(UPLOAD_DIR, f'temp_{project_id}_{task_id}')
                os.makedirs(temp_extract_dir, exist_ok=True)
                
                # Save and extract
                with zipfile.ZipFile(file.stream, 'r') as archive_ref:
                    file_list = archive_ref.namelist()
                    total_files = len(file_list)
                    progress_tracker.update(task_id, progress=20, step=f'Arşiv açılıyor ({total_files} dosya)', detail='')
                    archive_ref.extractall(temp_extract_dir)
                
                # Extract nested JARs if WAR
                if file_lower.endswith('.war'):
                    progress_tracker.update(task_id, progress=25, step='WAR içindeki JAR dosyaları çıkarılıyor...', detail='')
                    _extract_nested_jars(temp_extract_dir, logger)
                
                # Process extracted files
                progress_tracker.update(task_id, progress=30, step='Dosyalar işleniyor...', detail='Kaynak dosyalar veritabanına aktarılıyor')
                
                all_files = []
                for root, dirs, files in os.walk(temp_extract_dir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        all_files.append((fpath, fname))
                
                total_to_process = len(all_files)
                
                for idx, (fpath, fname) in enumerate(all_files):
                    rel_path = os.path.relpath(fpath, temp_extract_dir)
                    current_progress = 30 + int((idx / total_to_process) * 60) if total_to_process > 0 else 30
                    progress_tracker.update(task_id, progress=current_progress, detail=f'İşleniyor: {rel_path}')
                    
                    if not _should_index_file(fname, fpath, is_war=file_lower.endswith('.war')):
                        skipped_files += 1
                        continue
                    
                    language = _detect_language(fname)
                    
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        # Add to source_files
                        file_id = db.execute_insert(
                            '''INSERT INTO source_files
                            (project_id, file_path, file_name, language, content)
                            VALUES (?, ?, ?, ?, ?)''',
                            (project_id, rel_path, fname, language, content)
                        )
                        processed_files += 1
                        logger.debug(f"[Project {project_id}] Added file: {rel_path} (ID: {file_id})")
                    except Exception as e:
                        skipped_files += 1
                        logger.warning(f"[Project {project_id}] Failed to process {rel_path}: {str(e)}")
                        continue
                
                # Cleanup
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
                
            elif file_lower.endswith(('.pdf', '.doc', '.docx', '.txt', '.md')):
                # Document files for RAG
                progress_tracker.update(task_id, progress=30, step='Doküman işleniyor...', detail='RAG analizine hazırlanıyor')
                
                document_type = 'pdf' if file_lower.endswith('.pdf') else \
                               'docx' if file_lower.endswith('.docx') else \
                               'doc' if file_lower.endswith('.doc') else \
                               'text'
                
                # Save document file
                doc_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}', 'documents')
                os.makedirs(doc_dir, exist_ok=True)
                
                doc_path = os.path.join(doc_dir, file.filename)
                file.save(doc_path)
                
                file_size = os.path.getsize(doc_path)
                
                # Extract text content based on document type (simplified)
                extracted_text = ""
                try:
                    if file_lower.endswith('.pdf'):
                        # For PDF, we'd need PyPDF2 or similar - for now store filename in extracted_text
                        extracted_text = f"PDF Document: {file.filename}"
                    elif file_lower.endswith(('.doc', '.docx')):
                        extracted_text = f"Document: {file.filename}"
                    elif file_lower.endswith('.txt'):
                        with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                            extracted_text = f.read()
                    elif file_lower.endswith('.md'):
                        with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                            extracted_text = f.read()
                except Exception as e:
                    logger.warning(f"Failed to extract text from {file.filename}: {e}")
                    extracted_text = f"Document: {file.filename}"
                
                # Add to project_documents
                doc_id = db.execute_insert(
                    '''INSERT INTO project_documents
                    (project_id, file_name, file_path, file_type, document_type, 
                     file_size, extracted_text, source_folder)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (project_id, file.filename, os.path.relpath(doc_path, UPLOAD_DIR), 
                     document_type, document_type, file_size, extracted_text, 'documents')
                )
                added_documents = 1
                logger.debug(f"[Project {project_id}] Added document: {file.filename} (ID: {doc_id})")
                
            elif file_lower.endswith(('.java', '.sql', '.py', '.js', '.ts', '.php')):
                # Single source code files
                progress_tracker.update(task_id, progress=30, step='Kaynak dosyası işleniyor...', detail=f'{file.filename}')
                
                language = _detect_language(file.filename)
                
                # Sanitize filename to prevent directory traversal
                safe_name = os.path.basename(file.filename).strip()
                if not safe_name:
                    raise ValueError(f"Geçersiz dosya adı: {file.filename}")
                
                # Read file content
                file.seek(0)
                content = file.read().decode('utf-8', errors='ignore')
                
                # Save to project directory
                file_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}')
                os.makedirs(file_dir, exist_ok=True)
                
                save_path = os.path.join(file_dir, safe_name)
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Add to source_files (update if already exists)
                existing = db.execute_query(
                    'SELECT id FROM source_files WHERE project_id = ? AND file_path = ?',
                    (project_id, safe_name)
                )
                if existing:
                    db.execute_update(
                        'UPDATE source_files SET content = ?, language = ? WHERE project_id = ? AND file_path = ?',
                        (content, language, project_id, safe_name)
                    )
                    file_id = existing[0][0]
                    logger.info(f"[Project {project_id}] Updated existing source file: {safe_name} (ID: {file_id})")
                else:
                    file_id = db.execute_insert(
                        '''INSERT INTO source_files
                        (project_id, file_path, file_name, language, content)
                        VALUES (?, ?, ?, ?, ?)''',
                        (project_id, safe_name, safe_name, language, content)
                    )
                    logger.info(f"[Project {project_id}] Added source file: {safe_name} (ID: {file_id})")
                processed_files = 1
                added_single_file_id = file_id
            else:
                return jsonify({'error': f'Unsupported file type: {file.filename}'}), 400
            
            progress_tracker.update(task_id, progress=90, step='Temizlik yapılıyor...', detail='Geçici dosyalar temizleniyor')
            progress_tracker.complete(
                task_id, 
                success=True, 
                message=f'Tamamlandı! {processed_files} kaynak dosya, {added_documents} doküman eklendi, {skipped_files} atlandı'
            )
            
            log_upload(project_id, "File addition complete", processed=processed_files, documents=added_documents, skipped=skipped_files)
            
            return jsonify({
                'project_id': project_id,
                'task_id': task_id,
                'file_name': file.filename,
                'files_processed': processed_files,
                'documents_added': added_documents,
                'files_skipped': skipped_files,
                'added_file_id': added_single_file_id,
                'message': 'Files added successfully'
            }), 201
            
        except Exception as e:
            log_error(f"add_files_to_project (task: {task_id})", e, project_id=project_id)
            progress_tracker.complete(task_id, success=False, message=f'Hata: {str(e)}')
            return jsonify({'error': str(e), 'task_id': task_id}), 500
            
    except Exception as e:
        logger.error(f"Error in add_files_to_project: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/git-info', methods=['POST'])
def get_git_info():
    """Get Git repository information (branches, repo name)"""
    try:
        data = request.get_json()
        repo_url = data.get('url', '').strip()
        
        if not repo_url:
            return jsonify({'error': 'Repository URL is required'}), 400
        
        # Extract repo name from URL
        # https://github.com/user/repo.git -> repo
        # https://github.com/user/repo -> repo
        repo_name = repo_url.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        # Get remote branches using git ls-remote
        # Create environment without proxy settings
        git_env = os.environ.copy()
        for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
            git_env.pop(proxy_var, None)
        git_env['NO_PROXY'] = '*'
        git_env['no_proxy'] = '*'
        
        # Run git ls-remote to get branches
        ls_remote_command = ['git', 'ls-remote', '--heads', repo_url]
        
        try:
            result = subprocess.run(
                ls_remote_command, 
                capture_output=True, 
                text=True, 
                timeout=30,
                env=git_env
            )
            
            if result.returncode != 0:
                logger.warning(f"Git ls-remote failed: {result.stderr}")
                # Return default branches if ls-remote fails
                return jsonify({
                    'repo_name': repo_name,
                    'branches': ['main', 'master', 'develop'],
                    'default_branch': 'main',
                    'warning': 'Branch listesi alınamadı, varsayılan branch\'ler gösteriliyor'
                }), 200
            
            # Parse branches from ls-remote output
            # Format: <hash>\trefs/heads/<branch-name>
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line and 'refs/heads/' in line:
                    branch_name = line.split('refs/heads/')[-1].strip()
                    if branch_name:
                        branches.append(branch_name)
            
            # Determine default branch (prefer main > master > first available)
            default_branch = 'main'
            if 'main' in branches:
                default_branch = 'main'
            elif 'master' in branches:
                default_branch = 'master'
            elif branches:
                default_branch = branches[0]
            
            # If no branches found, return defaults
            if not branches:
                branches = ['main', 'master']
                default_branch = 'main'
            
            return jsonify({
                'repo_name': repo_name,
                'branches': branches,
                'default_branch': default_branch
            }), 200
            
        except subprocess.TimeoutExpired:
            return jsonify({
                'repo_name': repo_name,
                'branches': ['main', 'master', 'develop'],
                'default_branch': 'main',
                'warning': 'Repository erişimi zaman aşımına uğradı'
            }), 200
        except FileNotFoundError:
            return jsonify({'error': 'Git is not installed on the system'}), 500
        
    except Exception as e:
        logger.error(f"Error fetching git info: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/import-git', methods=['POST'])
@check_permission('create_project')
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
        user = get_user_from_session()
        project_id = db.execute_insert(
            'INSERT INTO projects (name, description, admin_id) VALUES (?, ?, ?)',
            (project_name, project_desc, user['id'])
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
        
        # Create environment without proxy settings
        git_env = os.environ.copy()
        for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
            git_env.pop(proxy_var, None)
        git_env['NO_PROXY'] = '*'
        git_env['no_proxy'] = '*'
        
        try:
            result = subprocess.run(clone_command, capture_output=True, text=True, timeout=300, env=git_env)
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
            
            if not _should_index_file(file_name, file_path, is_war=False):
                skipped_files += 1
                logger.debug(f"[Project {project_id}] Skipped non-text/binary: {rel_path}")
                continue

            # Determine language (normalized aliases)
            language = _detect_language(file_name)
            
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
@check_project_access('read')
def get_project_files(project_id):
    """Get all source files and documents in project"""
    try:
        source_rows = db.execute_query(
            'SELECT id, file_name, file_path, language, NULL as document_type, \'source\' as entry_type FROM source_files WHERE project_id = ?',
            (project_id,)
        )
        doc_rows = db.execute_query(
            'SELECT id, file_name, file_path, NULL as language, document_type, \'document\' as entry_type FROM project_documents WHERE project_id = ?',
            (project_id,)
        )
        files = [dict(row) for row in (source_rows or [])]
        documents = [dict(row) for row in (doc_rows or [])]
        return jsonify({'source_files': files, 'documents': documents}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:project_id>/files/<int:file_id>', methods=['GET'])
@check_project_access('read')
def get_project_file_content(project_id, file_id):
    """Return raw source file content for viewing."""
    try:
        row = db.execute_query(
            'SELECT id, file_name, file_path, language, content FROM source_files WHERE project_id = ? AND id = ?',
            (project_id, file_id)
        )
        if not row:
            return jsonify({'error': 'File not found'}), 404

        return jsonify(dict(row[0])), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:project_id>', methods=['DELETE'])
@check_project_access('write')
def delete_project(project_id):
    """Delete project and all related data"""
    try:
        import shutil
        
        # Delete in correct order (child to parent) to respect foreign keys
        # 1. Delete function calls (references functions)
        db.execute_update('DELETE FROM function_calls WHERE project_id = ?', (project_id,))
        
        # 2. Delete entry points (references functions)
        db.execute_update('DELETE FROM entry_points WHERE project_id = ?', (project_id,))
        
        # 3. Delete user marks (references functions/projects)
        db.execute_update('DELETE FROM user_marks WHERE project_id = ?', (project_id,))
        
        # 4. Delete functions (references source_files)
        db.execute_update('DELETE FROM functions WHERE project_id = ?', (project_id,))
        
        # 5. Delete source files (references projects)
        db.execute_update('DELETE FROM source_files WHERE project_id = ?', (project_id,))
        
        # 6. Finally delete project
        db.execute_update('DELETE FROM projects WHERE id = ?', (project_id,))
        
        # Delete physical files
        extract_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}')
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        
        # Also try to delete Git clone directory if exists
        git_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}_git')
        if os.path.exists(git_dir):
            shutil.rmtree(git_dir, ignore_errors=True)
        
        logger.info(f"Project {project_id} deleted successfully")
        user = get_user_from_session()
        log_audit(user, 'project_delete', 'project', project_id, request=request)
        return jsonify({'message': 'Project deleted'}), 200
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/progress/<task_id>', methods=['GET'])
def get_upload_progress(task_id):
    """Get progress for an upload task"""
    try:
        progress = progress_tracker.get_progress(task_id)
        
        if progress is None:
            # Return a terminal payload so older clients can stop polling.
            return jsonify({
                'task_id': task_id,
                'status': 'failed',
                'progress': 100,
                'current_step': 'Task not found (expired/restarted).',
                'details': [
                    {
                        'message': 'İlerleme görevi bulunamadı. İstek sonlandırıldı.',
                        'timestamp': None
                    }
                ],
                'metrics': {
                    'total_functions': 0,
                    'completed_functions': 0,
                    'remaining_functions': 0,
                    'active_thread': None,
                    'estimated_remaining_seconds': None,
                },
                'task_exists': False
            }), 200
        
        return jsonify(progress), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
