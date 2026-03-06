from flask import Blueprint, request, jsonify
from backend.database import db
from backend.permission_manager import get_user_from_session

bp = Blueprint('ai_settings', __name__, url_prefix='/api/ai-settings')

@bp.route('/', methods=['GET'])
def get_settings():
    """Get all AI settings"""
    try:
        rows = db.execute_query('SELECT setting_name, setting_value, data_type FROM ai_settings')
        settings = {}
        for row in rows:
            setting_name = row[0]
            setting_value = row[1]
            data_type = row[2]
            
            # Convert to proper type
            if data_type == 'integer':
                settings[setting_name] = int(setting_value)
            elif data_type == 'float':
                settings[setting_name] = float(setting_value)
            elif data_type == 'boolean':
                settings[setting_name] = setting_value.lower() == 'true'
            else:
                settings[setting_name] = setting_value
        
        return jsonify(settings), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<setting_name>', methods=['PUT'])
def update_setting(setting_name):
    """Update AI setting"""
    data = request.json
    value = data.get('value')
    data_type = data.get('type', 'string')
    
    try:
        # Check if setting exists
        row = db.execute_query('SELECT id FROM ai_settings WHERE setting_name = ?', (setting_name,))
        
        if row:
            db.execute_update(
                'UPDATE ai_settings SET setting_value = ?, data_type = ? WHERE setting_name = ?',
                (str(value), data_type, setting_name)
            )
        else:
            db.execute_insert(
                'INSERT INTO ai_settings (setting_name, setting_value, data_type) VALUES (?, ?, ?)',
                (setting_name, str(value), data_type)
            )
        
        return jsonify({'message': f'Setting {setting_name} updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/lmstudio/test', methods=['POST'])
def test_lmstudio():
    """Test LMStudio connection"""
    try:
        from backend.lmstudio_client import LMStudioClient
        user = get_user_from_session()
        client = LMStudioClient(user_id=user['id'] if user else None)
        result = client.test_connection()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
