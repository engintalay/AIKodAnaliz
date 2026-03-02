from flask import Blueprint, request, jsonify
import os
import zipfile
from datetime import datetime
from backend.database import db
from config.config import UPLOAD_DIR

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
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    project_name = request.form.get('name', file.filename.split('.')[0])
    project_desc = request.form.get('description', '')
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Only ZIP files allowed'}), 400
    
    try:
        # Create project record
        project_id = db.execute_insert(
            'INSERT INTO projects (name, description, admin_id) VALUES (?, ?, ?)',
            (project_name, project_desc, 1)  # TODO: Get actual user ID
        )
        
        # Save and extract zip
        zip_path = os.path.join(UPLOAD_DIR, f'project_{project_id}.zip')
        file.save(zip_path)
        
        extract_dir = os.path.join(UPLOAD_DIR, f'project_{project_id}')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Process extracted files
        processed_files = 0
        for root, dirs, files in os.walk(extract_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(file_path, extract_dir)
                
                # Determine language
                ext = os.path.splitext(file_name)[1].lower().lstrip('.')
                language = ext if ext else 'unknown'
                
                # Read file content
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except:
                    continue
                
                # Store in database
                file_id = db.execute_insert(
                    '''INSERT INTO source_files 
                    (project_id, file_path, file_name, language, content)
                    VALUES (?, ?, ?, ?, ?)''',
                    (project_id, rel_path, file_name, language, content)
                )
                processed_files += 1
        
        # Clean up zip file
        os.remove(zip_path)
        
        return jsonify({
            'project_id': project_id,
            'name': project_name,
            'files_processed': processed_files,
            'message': 'Project uploaded successfully'
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
