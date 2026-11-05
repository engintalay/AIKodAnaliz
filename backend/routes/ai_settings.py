from flask import Blueprint, request, jsonify
from backend.ai_client import LocalAIClient
from backend.database import db
from backend.permission_manager import get_user_from_session

bp = Blueprint('ai_settings', __name__, url_prefix='/api/ai-settings')

# Sensitive settings are never returned in full; masked as ••••<last4>.
SENSITIVE_KEYS = {'api_key', 'embedding_api_key'}


def _mask_secret(value):
    value = str(value or '')
    if not value:
        return ''
    return '••••' + value[-4:]


@bp.route('/', methods=['GET'])
def get_settings():
    """Get all AI settings (sensitive keys masked)"""
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

        # Mask API keys; expose only a boolean "set" flag + masked display value.
        for key in SENSITIVE_KEYS:
            if key in settings:
                settings[f'{key}_set'] = bool(settings[key])
                settings[key] = _mask_secret(settings[key])

        return jsonify(settings), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<setting_name>', methods=['PUT'])
def update_setting(setting_name):
    """Update AI setting.

    For sensitive keys (api_key, embedding_api_key):
      - missing value / None / masked echo (starts with ••••) / empty string
        without "clear": true  ->  value is NOT changed
      - "clear": true           ->  stored value is emptied
      - any other non-empty value -> stored as-is
    """
    data = request.get_json(silent=True) or {}
    value = data.get('value')
    data_type = data.get('type', 'string')
    
    try:
        if setting_name in SENSITIVE_KEYS:
            if value is None or str(value).startswith('••••'):
                return jsonify({'message': f'Setting {setting_name} unchanged'}), 200
            if str(value) == '' and not data.get('clear'):
                return jsonify({'message': f'Setting {setting_name} unchanged'}), 200
            if data.get('clear'):
                value = ''

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
@bp.route('/provider/test', methods=['POST'])
def test_provider_connection():
    """Test provider connection.

    Optional request JSON:
    { "api_url": "http://...", "provider": "lmstudio|llamacpp", "api_key": "..." }

    If an api_url is provided, test it without saving it to the DB.
    api_key (if provided) is used only for this test, never persisted.
    When testing a DIFFERENT server than the currently effective one,
    the stored key is intentionally not sent to the new URL.
    """
    try:
        data = request.get_json(silent=True) or {}
        api_url = (data.get('api_url') or '').strip().rstrip('/')
        provider = (data.get('provider') or '').strip().lower()
        api_key = (data.get('api_key') or '').strip()

        user = get_user_from_session()
        client = LocalAIClient(user_id=user['id'] if user else None)

        if provider:
            client.provider = provider

        if api_url:
            if api_url != (client.api_url or '').rstrip('/'):
                client.api_url = api_url
                client.set_api_key(api_key)
            elif api_key:
                client.set_api_key(api_key)
        elif api_key:
            client.set_api_key(api_key)

        result = client.test_connection()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/embedding/test', methods=['POST'])
def test_embedding_connection():
    """Test the embedding endpoint (GELIS23).

    Optional request JSON (values override stored settings for this test only):
    { "embedding_model": "...", "embedding_api_url": "...",
      "embedding_api_key": "...", "api_key": "..." }

    Returns 200 with {available: bool, model, api_url, dim?, latency_ms, ...}.
    """
    try:
        from backend.rag_index import test_embedding_config
        overrides = {}
        data = request.get_json(silent=True) or {}
        for key in ('embedding_model', 'embedding_api_url', 'embedding_api_key', 'api_key'):
            if key in data and data.get(key) is not None:
                value = str(data.get(key)).strip()
                if value.startswith('••••'):
                    continue  # masked echo from UI -> keep stored value
                overrides[key] = value

        result = test_embedding_config(overrides)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
