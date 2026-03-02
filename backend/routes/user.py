from flask import Blueprint, request, jsonify
from backend.database import db
import json

bp = Blueprint('user', __name__, url_prefix='/api/users')

@bp.route('/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    try:
        user_id = db.execute_insert(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, password, 'viewer')  # Default role
        )
        return jsonify({'user_id': user_id, 'message': 'User registered'}), 201
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'Username already exists'}), 409
        return jsonify({'error': str(e)}), 500

@bp.route('/marks', methods=['POST'])
def add_mark():
    """Add mark/comment to function"""
    data = request.json
    project_id = data.get('project_id')
    function_id = data.get('function_id')
    user_id = data.get('user_id')
    mark_type = data.get('mark_type')  # 'question', 'unclear', 'incomplete'
    comment = data.get('comment')
    
    try:
        mark_id = db.execute_insert(
            '''INSERT INTO user_marks 
            (project_id, function_id, user_id, mark_type, comment, status)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (project_id, function_id, user_id, mark_type, comment, 'open')
        )
        return jsonify({'mark_id': mark_id, 'message': 'Mark added'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/marks/<int:project_id>', methods=['GET'])
def get_marks(project_id):
    """Get all marks in project"""
    try:
        rows = db.execute_query(
            '''SELECT m.*, u.username, f.function_name 
            FROM user_marks m
            JOIN users u ON m.user_id = u.id
            LEFT JOIN functions f ON m.function_id = f.id
            WHERE m.project_id = ?''',
            (project_id,)
        )
        marks = [dict(row) for row in rows]
        return jsonify(marks), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/marks/<int:mark_id>/resolve', methods=['PUT'])
def resolve_mark(mark_id):
    """Resolve mark (admin)"""
    data = request.json
    
    try:
        db.execute_update(
            'UPDATE user_marks SET status = ? WHERE id = ?',
            ('resolved', mark_id)
        )
        return jsonify({'message': 'Mark resolved'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
