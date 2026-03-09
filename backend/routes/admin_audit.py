"""Admin-only routes for viewing audit logs."""
from flask import Blueprint, request, jsonify
from backend.database import db
from backend.permission_manager import get_user_from_session
from backend.logger import logger

bp = Blueprint('admin_audit', __name__, url_prefix='/api/admin')


def _require_admin():
    """Return current admin user or raise a 403 tuple."""
    user = get_user_from_session()
    if not user or user.get('role') != 'admin':
        return None, (jsonify({'error': 'Forbidden – admin only'}), 403)
    return user, None


@bp.route('/audit-logs', methods=['GET'])
def list_audit_logs():
    """Return paginated, filterable audit log entries (admin only)."""
    user, err = _require_admin()
    if err:
        return err

    try:
        limit = min(int(request.args.get('limit', 200)), 1000)
        offset = int(request.args.get('offset', 0))
        action_filter = request.args.get('action', '').strip()
        user_filter = request.args.get('username', '').strip()
        from_date = request.args.get('from', '').strip()
        to_date = request.args.get('to', '').strip()

        where_clauses = []
        params = []

        if action_filter:
            where_clauses.append("action LIKE ?")
            params.append(f"%{action_filter}%")
        if user_filter:
            where_clauses.append("username LIKE ?")
            params.append(f"%{user_filter}%")
        if from_date:
            where_clauses.append("created_at >= ?")
            params.append(from_date)
        if to_date:
            where_clauses.append("created_at <= ?")
            params.append(to_date + " 23:59:59")

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_rows = db.execute_query(
            f"SELECT COUNT(*) as total FROM audit_logs {where_sql}",
            params if params else None
        )
        total = dict(count_rows[0])['total'] if count_rows else 0

        rows = db.execute_query(
            f"""SELECT id, user_id, username, action, resource_type, resource_id, details, ip_address, created_at
                FROM audit_logs {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?""",
            (params + [limit, offset]) if params else [limit, offset]
        )

        return jsonify({
            'total': total,
            'limit': limit,
            'offset': offset,
            'logs': [dict(row) for row in rows]
        }), 200

    except Exception as e:
        logger.error(f"Error listing audit logs: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/audit-logs/actions', methods=['GET'])
def list_audit_actions():
    """Return distinct action types for filter dropdowns (admin only)."""
    _, err = _require_admin()
    if err:
        return err

    try:
        rows = db.execute_query("SELECT DISTINCT action FROM audit_logs ORDER BY action")
        return jsonify([row[0] for row in rows]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
