from flask import Blueprint, request, jsonify, session
from backend.database import db
from backend.permission_manager import (
    check_permission, get_user_from_session, grant_project_permission,
    revoke_project_permission, get_user_projects, get_project_users
)
import json

bp = Blueprint('user', __name__, url_prefix='/api/users')

@bp.route('/login', methods=['POST'])
def login():
    """User login"""
    data = request.json
    username = (data.get('username') or '').strip()
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    try:
        rows = db.execute_query(
            'SELECT id, username, role, is_active FROM users WHERE username = ? AND password = ?',
            (username, password)
        )
        
        if not rows:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        user = dict(rows[0])
        
        if not user['is_active']:
            return jsonify({'error': 'User account is disabled'}), 403
        
        # Store in session
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            },
            'message': 'Login successful'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/register', methods=['POST'])
def register():
    """Register new user (Admin only)"""
    # Check authentication
    user = get_user_from_session()
    if not user or user['role'] != 'admin':
        return jsonify({'error': 'Only admins can create users'}), 403
    
    data = request.json
    username = (data.get('username') or '').strip()
    password = data.get('password')
    role = data.get('role', 'analyzer')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if role not in ['admin', 'developer', 'analyzer']:
        return jsonify({'error': 'Invalid role'}), 400
    
    try:
        user_id = db.execute_insert(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            (username, password, role)
        )
        
        # Create default settings
        db.execute_insert(
            'INSERT INTO user_settings (user_id, theme, notifications_enabled, items_per_page) VALUES (?, ?, ?, ?)',
            (user_id, 'light', 1, 20)
        )
        
        return jsonify({'user_id': user_id, 'message': 'User registered'}), 201
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'Username already exists'}), 409
        return jsonify({'error': str(e)}), 500

@bp.route('/logout', methods=['POST'])
def logout():
    """User logout"""
    session.clear()
    return jsonify({'message': 'Logout successful'}), 200

@bp.route('/current', methods=['GET'])
def get_current_user():
    """Get current user info"""
    user = get_user_from_session()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    
    return jsonify({
        'id': user['id'],
        'username': user['username'],
        'role': user['role'],
        'full_name': user.get('full_name', ''),
        'email': user.get('email', '')
    }), 200

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


# ========== ADMIN USER MANAGEMENT ==========

@bp.route('/admin/all', methods=['GET'])
@check_permission('manage_users')
def get_all_users():
    """Admin: Get all users"""
    try:
        rows = db.execute_query(
            '''SELECT id, username, role, full_name, email, is_active, created_at 
               FROM users ORDER BY created_at DESC'''
        )
        users = [dict(row) for row in rows]
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/create', methods=['POST'])
@check_permission('manage_users')
def admin_create_user():
    """Admin: Create new user"""
    data = request.json
    username = (data.get('username') or '').strip()
    password = data.get('password')
    role = data.get('role', 'analyzer')
    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip()
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if role not in ['admin', 'developer', 'analyzer']:
        return jsonify({'error': 'Invalid role'}), 400
    
    try:
        user_id = db.execute_insert(
            '''INSERT INTO users (username, password, role, full_name, email, is_active)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (username, password, role, full_name, email, 1)
        )
        
        # Create default user settings
        db.execute_insert(
            '''INSERT INTO user_settings (user_id, theme, notifications_enabled, items_per_page)
               VALUES (?, ?, ?, ?)''',
            (user_id, 'light', 1, 20)
        )
        
        return jsonify({'user_id': user_id, 'message': 'User created'}), 201
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'Username already exists'}), 409
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/<int:user_id>', methods=['GET'])
@check_permission('manage_users')
def admin_get_user(user_id):
    """Admin: Get user details"""
    try:
        rows = db.execute_query(
            '''SELECT u.id, u.username, u.role, u.full_name, u.email, u.is_active, u.created_at,
                      s.theme, s.notifications_enabled, s.items_per_page
               FROM users u
               LEFT JOIN user_settings s ON u.id = s.user_id
               WHERE u.id = ?''',
            [user_id]
        )
        if not rows:
            return jsonify({'error': 'User not found'}), 404
        
        user = dict(rows[0])
        return jsonify(user), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/<int:user_id>', methods=['PUT'])
@check_permission('manage_users')
def admin_update_user(user_id):
    """Admin: Update user"""
    data = request.json
    
    try:
        updates = []
        params = []
        
        if 'full_name' in data:
            updates.append('full_name = ?')
            params.append(data['full_name'])
        
        if 'email' in data:
            updates.append('email = ?')
            params.append(data['email'])
        
        if 'role' in data and data['role'] in ['admin', 'developer', 'analyzer']:
            updates.append('role = ?')
            params.append(data['role'])
        
        if 'is_active' in data:
            updates.append('is_active = ?')
            params.append(data['is_active'])
        
        if 'password' in data and data['password']:
            updates.append('password = ?')
            params.append(data['password'])
        
        if updates:
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            db.execute_update(query, params)
        
        return jsonify({'message': 'User updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/admin/<int:user_id>/delete', methods=['DELETE'])
@check_permission('manage_users')
def admin_delete_user(user_id):
    """Admin: Delete user"""
    try:
        # Don't allow deleting the last admin
        admin_count = db.execute_query(
            'SELECT COUNT(*) as cnt FROM users WHERE role = ?',
            ['admin']
        )[0]['cnt']
        
        current_role = db.execute_query(
            'SELECT role FROM users WHERE id = ?',
            [user_id]
        )
        
        if current_role and current_role[0]['role'] == 'admin' and admin_count <= 1:
            return jsonify({'error': 'Cannot delete the last admin user'}), 400
        
        # Delete user and related data
        db.execute_update('DELETE FROM user_marks WHERE user_id = ?', [user_id])
        db.execute_update('DELETE FROM project_permissions WHERE user_id = ?', [user_id])
        db.execute_update('DELETE FROM user_settings WHERE user_id = ?', [user_id])
        db.execute_update('DELETE FROM users WHERE id = ?', [user_id])
        
        return jsonify({'message': 'User deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== USER SETTINGS ==========

@bp.route('/settings', methods=['GET'])
def get_user_settings():
    """Get current user settings"""
    try:
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        rows = db.execute_query(
            '''SELECT u.id, u.username, u.role, u.full_name, u.email,
                      s.theme, s.notifications_enabled, s.items_per_page, s.default_filter, s.ai_api_url
               FROM users u
               LEFT JOIN user_settings s ON u.id = s.user_id
               WHERE u.id = ?''',
            [user['id']]
        )
        
        if not rows:
            return jsonify({'error': 'User not found'}), 404
        
        settings = dict(rows[0])
        return jsonify(settings), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/settings', methods=['PUT'])
def update_user_settings():
    """Update user settings"""
    try:
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        user_id = user['id']
        
        # Update user profile
        if 'full_name' in data or 'email' in data:
            updates = []
            params = []
            if 'full_name' in data:
                updates.append('full_name = ?')
                params.append(data['full_name'])
            if 'email' in data:
                updates.append('email = ?')
                params.append(data['email'])
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            db.execute_update(query, params)
        
        # Update settings
        settings_updates = []
        settings_params = []
        
        if 'theme' in data:
            settings_updates.append('theme = ?')
            settings_params.append(data['theme'])
        
        if 'notifications_enabled' in data:
            settings_updates.append('notifications_enabled = ?')
            settings_params.append(data['notifications_enabled'])
        
        if 'items_per_page' in data:
            settings_updates.append('items_per_page = ?')
            settings_params.append(data['items_per_page'])
        
        if 'default_filter' in data:
            settings_updates.append('default_filter = ?')
            settings_params.append(data['default_filter'])

        if 'ai_api_url' in data:
            settings_updates.append('ai_api_url = ?')
            settings_params.append((data['ai_api_url'] or '').strip() or None)
        
        if settings_updates:
            settings_params.append(user_id)
            query = f"UPDATE user_settings SET {', '.join(settings_updates)} WHERE user_id = ?"
            db.execute_update(query, settings_params)
        
        return jsonify({'message': 'Settings updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/change-password', methods=['PUT'])
def change_password():
    """Change password for current logged-in user"""
    try:
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.json or {}
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'error': 'Current password and new password are required'}), 400

        if len(new_password) < 4:
            return jsonify({'error': 'New password must be at least 4 characters'}), 400

        if current_password == new_password:
            return jsonify({'error': 'New password must be different from current password'}), 400

        verify_rows = db.execute_query(
            'SELECT id FROM users WHERE id = ? AND password = ?',
            [user['id'], current_password]
        )

        if not verify_rows:
            return jsonify({'error': 'Current password is incorrect'}), 401

        db.execute_update(
            'UPDATE users SET password = ? WHERE id = ?',
            [new_password, user['id']]
        )

        return jsonify({'message': 'Password updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== PROJECT PERMISSIONS ==========

@bp.route('/projects/<int:project_id>/permissions', methods=['GET'])
def get_project_permissions(project_id):
    """Get all users with access to project"""
    try:
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Check if user can manage permissions
        user_role = user['role']
        is_owner = False
        
        if user_role in ['admin']:
            is_owner = True
        elif user_role == 'developer':
            proj = db.execute_query(
                'SELECT admin_id FROM projects WHERE id = ?',
                [project_id]
            )
            if proj and proj[0]['admin_id'] == user['id']:
                is_owner = True
        
        if not is_owner and user_role != 'admin':
            return jsonify({'error': 'Permission denied'}), 403
        
        users = get_project_users(project_id)
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/projects/<int:project_id>/permissions/grant', methods=['POST'])
def grant_permission(project_id):
    """Grant project permission to user"""
    try:
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        target_user_id = data.get('user_id')
        permission_level = data.get('permission_level', 'read')
        read_only = data.get('read_only', True)
        
        success, message = grant_project_permission(
            project_id, target_user_id, user['id'], permission_level, read_only
        )
        
        if not success:
            return jsonify({'error': message}), 400
        
        return jsonify({'message': message}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/projects/<int:project_id>/permissions/revoke', methods=['POST'])
def revoke_permission(project_id):
    """Revoke project permission from user"""
    try:
        user = get_user_from_session()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        target_user_id = data.get('user_id')
        
        success, message = revoke_project_permission(
            project_id, target_user_id, user['id']
        )
        
        if not success:
            return jsonify({'error': message}), 400
        
        return jsonify({'message': message}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
