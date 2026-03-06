"""Role and Permission Management"""
from functools import wraps
from flask import request, jsonify, session
from backend.database import db
from backend.logger import logger

# Role Hierarchy and Permissions
ROLE_HIERARCHY = {
    'admin': 100,      # Full access to everything
    'developer': 50,   # Can create/manage projects, give permissions
    'analyzer': 10     # Read-only access to assigned projects
}

ROLE_PERMISSIONS = {
    'admin': {
        'manage_users': True,
        'manage_roles': True,
        'create_project': True,
        'delete_project': True,
        'manage_project_permissions': True,
        'edit_project': True,
        'upload_files': True,
        'access_all_projects': True,
        'view_analytics': True,
        'modify_summaries': True,
        'manage_ai_settings': True,
        'export_data': True
    },
    'developer': {
        'manage_users': False,
        'manage_roles': False,
        'create_project': True,
        'delete_project': True,      # Only own projects
        'manage_project_permissions': True,  # For own projects
        'edit_project': True,               # Only own projects
        'upload_files': True,               # To own projects
        'access_all_projects': False,
        'view_analytics': True,             # Own projects
        'modify_summaries': True,           # Own projects
        'manage_ai_settings': False,
        'export_data': True                 # Own projects
    },
    'analyzer': {
        'manage_users': False,
        'manage_roles': False,
        'create_project': False,
        'delete_project': False,
        'manage_project_permissions': False,
        'edit_project': False,
        'upload_files': False,
        'access_all_projects': False,
        'view_analytics': True,      # Assigned projects
        'modify_summaries': False,   # Always read-only
        'manage_ai_settings': False,
        'export_data': True          # Assigned projects
    }
}

def get_user_from_session():
    """Get current user from session"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    result = db.execute_query('SELECT * FROM users WHERE id = ?', [user_id])
    return dict(result[0]) if result else None

def check_permission(permission_key):
    """Decorator to check if user has specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_user_from_session()
            if not user:
                return jsonify({'error': 'Unauthorized'}), 401
            
            role = user['role']
            permissions = ROLE_PERMISSIONS.get(role, {})
            
            if not permissions.get(permission_key, False):
                return jsonify({'error': 'Permission denied'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_project_access(permission_type='read'):
    """Decorator to check project access based on user role and permissions
    
    Args:
        permission_type: 'read' or 'write'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_user_from_session()
            if not user:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Get project_id from route parameters
            project_id = kwargs.get('project_id') or request.view_args.get('project_id')
            
            if not project_id:
                return jsonify({'error': 'Project ID required'}), 400
            
            # Check access
            has_access, is_readonly = check_user_project_access(user['id'], project_id)
            
            if not has_access:
                return jsonify({'error': 'No access to this project'}), 403
            
            # For write operations, check if user is read-only
            if permission_type == 'write' and is_readonly:
                return jsonify({'error': 'Read-only access. Cannot modify this project'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_user_project_access(user_id, project_id):
    """
    Check if user has access to project
    Returns: (has_access: bool, is_readonly: bool)
    """
    user_result = db.execute_query('SELECT role FROM users WHERE id = ?', [user_id])
    if not user_result:
        return False, True
    
    user_role = user_result[0]['role']
    
    # Admin always has full access
    if user_role == 'admin':
        return True, False
    
    # Developer/Analyzer must have explicit permission
    perm_result = db.execute_query(
        'SELECT read_only FROM project_permissions WHERE project_id = ? AND user_id = ?',
        [project_id, user_id]
    )
    
    if not perm_result:
        # Check if user is the project owner
        proj_result = db.execute_query(
            'SELECT admin_id FROM projects WHERE id = ?',
            [project_id]
        )
        if proj_result and proj_result[0]['admin_id'] == user_id:
            return True, False
        return False, True
    
    # Analyzer role always has read_only = True as base constraint
    is_readonly = perm_result[0]['read_only'] or user_role == 'analyzer'
    return True, is_readonly

def grant_project_permission(project_id, user_id, granted_by_id, permission_level='read', read_only=False):
    """Grant project permission to a user"""
    try:
        # Verify granter has permission to grant
        granter_result = db.execute_query('SELECT role FROM users WHERE id = ?', [granted_by_id])
        if not granter_result:
            return False, "Granter user not found"
        
        granter_role = granter_result[0]['role']
        
        # Only admin or project owner (developer) can grant permissions
        if granter_role not in ['admin', 'developer']:
            return False, "Only developers or admins can grant permissions"
        
        # Check if granter owns the project (if not admin)
        if granter_role == 'developer':
            proj_result = db.execute_query(
                'SELECT admin_id FROM projects WHERE id = ?',
                [project_id]
            )
            if not proj_result or proj_result[0]['admin_id'] != granted_by_id:
                return False, "You can only grant permissions for your own projects"
        
        # Check grantee role
        grantee_result = db.execute_query('SELECT role FROM users WHERE id = ?', [user_id])
        if not grantee_result:
            return False, "User not found"
        
        grantee_role = grantee_result[0]['role']
        
        # Analyzer always read_only (cannot override)
        if grantee_role == 'analyzer':
            read_only = True
        
        # Insert or update permission
        existing = db.execute_query(
            'SELECT id FROM project_permissions WHERE project_id = ? AND user_id = ?',
            [project_id, user_id]
        )
        
        if existing:
            db.execute_update(
                'UPDATE project_permissions SET permission_level = ?, read_only = ? WHERE project_id = ? AND user_id = ?',
                [permission_level, read_only, project_id, user_id]
            )
        else:
            db.execute_update(
                'INSERT INTO project_permissions (project_id, user_id, permission_level, read_only, granted_by) VALUES (?, ?, ?, ?, ?)',
                [project_id, user_id, permission_level, read_only, granted_by_id]
            )
        
        return True, "Permission granted successfully"
    
    except Exception as e:
        logger.error(f"Error granting permission: {str(e)}")
        return False, str(e)

def revoke_project_permission(project_id, user_id, revoked_by_id):
    """Revoke project permission from a user"""
    try:
        # Verify revoker has permission
        revoker_result = db.execute_query('SELECT role FROM users WHERE id = ?', [revoked_by_id])
        if not revoker_result:
            return False, "Revoker user not found"
        
        revoker_role = revoker_result[0]['role']
        
        if revoker_role not in ['admin', 'developer']:
            return False, "Only developers or admins can revoke permissions"
        
        # Check if revoker owns the project
        if revoker_role == 'developer':
            proj_result = db.execute_query(
                'SELECT admin_id FROM projects WHERE id = ?',
                [project_id]
            )
            if not proj_result or proj_result[0]['admin_id'] != revoked_by_id:
                return False, "You can only revoke permissions for your own projects"
        
        db.execute_update(
            'DELETE FROM project_permissions WHERE project_id = ? AND user_id = ?',
            [project_id, user_id]
        )
        
        return True, "Permission revoked successfully"
    
    except Exception as e:
        logger.error(f"Error revoking permission: {str(e)}")
        return False, str(e)

def get_user_projects(user_id, include_shared=True):
    """Get all projects user can access"""
    user_result = db.execute_query('SELECT role FROM users WHERE id = ?', [user_id])
    if not user_result:
        return []
    
    user_role = user_result[0]['role']
    
    if user_role == 'admin':
        # Admin sees all projects
        return db.execute_query('SELECT * FROM projects ORDER BY name')
    
    # Developer sees owned + shared projects
    if user_role == 'developer':
        query = '''
            SELECT DISTINCT p.* FROM projects p
            LEFT JOIN project_permissions pp ON p.id = pp.project_id
            WHERE p.admin_id = ? OR pp.user_id = ?
            ORDER BY p.name
        '''
        return db.execute_query(query, [user_id, user_id])
    
    # Analyzer sees only shared projects
    if user_role == 'analyzer':
        query = '''
            SELECT p.* FROM projects p
            JOIN project_permissions pp ON p.id = pp.project_id
            WHERE pp.user_id = ?
            ORDER BY p.name
        '''
        return db.execute_query(query, [user_id])
    
    return []

def get_project_users(project_id):
    """Get all users with access to a project"""
    # Get owner
    owner_result = db.execute_query(
        'SELECT u.id, u.username, u.role, p.read_only FROM projects p JOIN users u ON p.admin_id = u.id WHERE p.id = ?',
        [project_id]
    )
    
    # Get users with shared access
    shared_result = db.execute_query(
        'SELECT u.id, u.username, u.role, pp.read_only FROM project_permissions pp JOIN users u ON pp.user_id = u.id WHERE pp.project_id = ?',
        [project_id]
    )
    
    users = []
    if owner_result:
        user_dict = dict(owner_result[0])
        user_dict['is_owner'] = True
        user_dict['read_only'] = False
        users.append(user_dict)
    
    for row in shared_result:
        user_dict = dict(row)
        user_dict['is_owner'] = False
        users.append(user_dict)
    
    return users
