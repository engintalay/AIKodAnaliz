"""GELIS4: RAG Index management routes."""
import json
from flask import Blueprint, request, jsonify
from backend.database import db
from backend.rag_index import RagIndex
from backend.permission_manager import get_user_from_session, check_project_access
from backend.logger import logger

bp = Blueprint('rag', __name__, url_prefix='/api/rag')


def _require_admin():
    user = get_user_from_session()
    if not user or user.get('role') != 'admin':
        return None, (jsonify({'error': 'Admin yetkisi gerekli'}), 403)
    return user, None


# ------------------------------------------------------------------
# Per-project build & status
# ------------------------------------------------------------------

@bp.route('/project/<int:project_id>/build', methods=['POST'])
@check_project_access('read')
def build_project_index(project_id):
    """Rebuild FTS5 index + start embedding generation for one project."""
    data = request.get_json(silent=True) or {}
    rebuild_embeddings = data.get('embeddings', True)
    rebuild_fts = data.get('fts', True)

    fts_count = 0
    if rebuild_fts:
        fts_count = RagIndex.build_fts(project_id)

    if rebuild_embeddings:
        RagIndex.build_embeddings_async(project_id)

    return jsonify({
        'message': 'İndeks oluşturma başlatıldı',
        'fts_indexed': fts_count,
        'embeddings': 'arka planda çalışıyor' if rebuild_embeddings else 'atlandı',
    }), 202


@bp.route('/project/<int:project_id>/status', methods=['GET'])
@check_project_access('read')
def project_index_status(project_id):
    """Return index coverage for a project."""
    status = RagIndex.get_build_status(project_id)

    # FTS coverage
    try:
        fts_rows = db.execute_query(
            'SELECT COUNT(*) FROM fts_functions WHERE function_id IN (SELECT id FROM functions WHERE project_id = ?)',
            (project_id,)
        )
        status['fts_indexed'] = fts_rows[0][0] if fts_rows else 0
    except Exception:
        status['fts_indexed'] = 0

    return jsonify(status), 200


# ------------------------------------------------------------------
# Admin: rebuild all projects
# ------------------------------------------------------------------

@bp.route('/admin/rebuild-all', methods=['POST'])
def rebuild_all():
    """Rebuild FTS5 for ALL projects (admin only). Embeddings per-project."""
    _, err = _require_admin()
    if err:
        return err

    fts_count = RagIndex.build_fts()  # Rebuilds entire table

    projects = db.execute_query('SELECT id FROM projects')
    for proj in projects:
        RagIndex.build_embeddings_async(proj[0])

    return jsonify({
        'message': f'Tüm projeler için FTS5 yeniden oluşturuldu ({fts_count} fonksiyon). Embedding arka planda çalışıyor.',
        'fts_total': fts_count,
        'projects': len(projects),
    }), 202
