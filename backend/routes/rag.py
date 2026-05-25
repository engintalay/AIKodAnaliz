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

@bp.route('/project/<int:project_id>/search', methods=['GET'])
@check_project_access('read')
def search_project(project_id):
    """Search project functions using the RAG index.

    Returns ranked list of matching functions (with score) so the UI can show results
    before the user sends a question to the AI.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Sorgu boş olamaz'}), 400

    function_results = RagIndex.search(project_id, query, limit=15)
    for item in function_results:
        item['result_type'] = 'function'

    # Document retrieval: combine embedding and lexical fallback, then dedupe.
    doc_results_map = {}

    def _add_doc_hit(hit: dict, score_scale: float = 1.0):
        file_name = hit.get('file_name') or ''
        chunk_index = int(hit.get('chunk_index', 0) or 0)
        raw_score = float(hit.get('score') or 0.0) * score_scale
        if raw_score <= 0:
            return

        excerpt = (hit.get('content') or '').strip()
        if len(excerpt) > 260:
            excerpt = excerpt[:260].rstrip() + '...'

        key = (file_name, chunk_index)
        existing = doc_results_map.get(key)
        payload = {
            'id': None,
            'function_name': f"Doküman: {file_name or 'bilinmiyor'}",
            'class_name': None,
            'package_name': None,
            'ai_summary': excerpt,
            'signature': None,
            'file_name': file_name,
            'doc_chunk_index': chunk_index,
            'score': round(raw_score, 4),
            'result_type': 'document',
        }
        if not existing or payload['score'] > existing['score']:
            doc_results_map[key] = payload

    # Embedding hits (0-1 scale), keep moderate threshold.
    for hit in RagIndex.search_doc_chunks(project_id, query, limit=10):
        if float(hit.get('score') or 0.0) >= 0.15:
            _add_doc_hit(hit, score_scale=1.0)

    # Lexical fallback always contributes (highly useful for exact phrase matches).
    for hit in RagIndex.search_doc_chunks_fallback(project_id, query, limit=10):
        _add_doc_hit(hit, score_scale=1.0)

    doc_results = sorted(doc_results_map.values(), key=lambda x: x['score'], reverse=True)[:8]

    results = sorted(function_results + doc_results, key=lambda x: float(x.get('score') or 0.0), reverse=True)[:20]

    best_score = 0.0
    if results:
        best_score = max(0.0, max((r.get('score') or 0.0) for r in results))
    return jsonify({
        'results': results,
        'best_score': best_score,
        'confidence': best_score,
    }), 200


@bp.route('/project/<int:project_id>/build', methods=['POST'])
@check_project_access('read')
def build_project_index(project_id):
    """Rebuild FTS5 index + start embedding generation for one project."""
    data = request.get_json(silent=True) or {}
    rebuild_embeddings = data.get('embeddings', True)
    rebuild_fts = data.get('fts', True)
    force_rebuild = data.get('force_rebuild', False)

    fts_count = 0
    if rebuild_fts:
        fts_count = RagIndex.build_fts(project_id)

    if rebuild_embeddings:
        RagIndex.build_embeddings_async(project_id, force_rebuild=force_rebuild)

    return jsonify({
        'message': 'İndeks oluşturma başlatıldı',
        'fts_indexed': fts_count,
        'embeddings': 'arka planda çalışıyor' if rebuild_embeddings else 'atlandı',
        'embedding_mode': 'full' if force_rebuild else 'incremental',
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
        RagIndex.build_embeddings_async(proj[0], force_rebuild=False)

    return jsonify({
        'message': f'Tüm projeler için FTS5 yeniden oluşturuldu ({fts_count} fonksiyon). Embedding arka planda çalışıyor.',
        'fts_total': fts_count,
        'projects': len(projects),
    }), 202
