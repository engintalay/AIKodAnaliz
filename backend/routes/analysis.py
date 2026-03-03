from flask import Blueprint, request, jsonify
from backend.database import db
from backend.analyzers.code_analyzer import CodeAnalyzer
from backend.lmstudio_client import LMStudioClient
import json

bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')

@bp.route('/test-connection', methods=['GET'])
def test_lmstudio_connection():
    """Test LMStudio connection"""
    try:
        client = LMStudioClient()
        status = client.test_connection()
        return jsonify(status), 200 if status['status'] == 'connected' else 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/project/<int:project_id>', methods=['POST'])
def analyze_project(project_id):
    """Analyze entire project"""
    try:
        # Get all files in project
        rows = db.execute_query(
            'SELECT id, content, language, file_name FROM source_files WHERE project_id = ?',
            (project_id,)
        )
        
        analyzer = CodeAnalyzer()
        all_functions = []
        all_entry_points = []
        
        for row in rows:
            file_id = row[0]
            content = row[1]
            language = row[2]
            file_name = row[3]
            
            # Analyze file
            result = analyzer.analyze(file_name, content, language)
            
            # Store functions
            for func in result.get('functions', []):
                func_id = db.execute_insert(
                    '''INSERT INTO functions 
                    (project_id, file_id, function_name, function_type, 
                    start_line, end_line, signature, parameters, return_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (project_id, file_id, func['name'], func['type'],
                    func['start_line'], func['end_line'], func['signature'],
                    json.dumps(func['parameters']), func.get('return_type', ''))
                )
                all_functions.append(func_id)
            
            # Store entry points
            for entry in result.get('entry_points', []):
                entry_point_id = db.execute_insert(
                    '''INSERT INTO entry_points 
                    (project_id, function_id, entry_type)
                    VALUES (?, ?, ?)''',
                    (project_id, all_functions[-1] if all_functions else None, 'main')
                )
        
        return jsonify({
            'message': 'Project analyzed',
            'functions_found': len(all_functions),
            'entry_points_found': len(all_entry_points)
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/function/<int:function_id>/ai-summary', methods=['POST'])
def get_ai_summary(function_id):
    """Get AI summary for function"""
    try:
        # Get function details
        row = db.execute_query(
            'SELECT f.*, s.content FROM functions f JOIN source_files s ON f.file_id = s.id WHERE f.id = ?',
            (function_id,)
        )
        
        if not row:
            return jsonify({'error': 'Function not found'}), 404
        
        func = dict(row[0])
        
        # Extract function code
        content = func['content']
        lines = content.split('\n')
        start_line = func['start_line'] - 1
        end_line = func['end_line']
        func_code = '\n'.join(lines[start_line:end_line])
        
        # Check LMStudio connection first
        client = LMStudioClient()
        connection_status = client.test_connection()
        
        if connection_status['status'] != 'connected':
            # LMStudio not available - return error immediately without timeout
            summary = f"⚠️ AI Analiz Hatası: {connection_status['message']}\n\nLMStudio sunucusu çalışmıyor. Lütfen LMStudio'yu başlatmaya çalışın (http://localhost:1234)"
        else:
            # Get AI summary
            summary = client.analyze_function(func_code, func['signature'])
        
        # Save summary
        db.execute_update(
            'UPDATE functions SET ai_summary = ? WHERE id = ?',
            (summary, function_id)
        )
        
        return jsonify({
            'function_id': function_id,
            'function_name': func['function_name'],
            'summary': summary
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/function/<int:function_id>', methods=['GET'])
def get_function_details(function_id):
    """Get single function details"""
    try:
        row = db.execute_query(
            'SELECT id, function_name, function_type, signature, parameters, return_type, ai_summary, start_line, end_line FROM functions WHERE id = ?',
            (function_id,)
        )
        
        if not row:
            return jsonify({'error': 'Function not found'}), 404
        
        func = dict(row[0])
        
        # Parse parameters from JSON string
        if func['parameters']:
            try:
                func['parameters'] = json.loads(func['parameters'])
            except:
                func['parameters'] = func['parameters'].split(',')
        
        return jsonify(func), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/project/<int:project_id>/functions', methods=['GET'])
def get_project_functions(project_id):
    """Get all functions in project"""
    try:
        rows = db.execute_query(
            'SELECT id, function_name, function_type, start_line, end_line, ai_summary FROM functions WHERE project_id = ?',
            (project_id,)
        )
        functions = [dict(row) for row in rows]
        return jsonify(functions), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/dependencies/<int:project_id>', methods=['GET'])
def get_dependencies(project_id):
    """Get function call dependencies"""
    try:
        rows = db.execute_query(
            '''SELECT fc.id, f1.function_name as caller, f2.function_name as callee
            FROM function_calls fc
            JOIN functions f1 ON fc.caller_function_id = f1.id
            JOIN functions f2 ON fc.callee_function_id = f2.id
            WHERE fc.project_id = ?''',
            (project_id,)
        )
        dependencies = [dict(row) for row in rows]
        return jsonify(dependencies), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
