"""GELIS4: RAG Index — FTS5 + Embedding-based semantic search.

Two-layer retrieval:
  1. FTS5  — Fast BM25-ranked full-text search (keyword-level)
  2. Embedding (optional) — Cosine-similarity over stored float vectors
                             generated via LMStudio /v1/embeddings
"""
import json
import math
import time
import threading
from typing import Optional

from backend.database import db
from backend.logger import logger
from config.config import LMSTUDIO_API_URL

# Embedding model to use (must be loaded in LMStudio)
EMBEDDING_MODEL = "text-embedding-nomic-embed-text-v1.5"
EMBEDDING_DIM = 768          # nomic-embed-text-v1.5 output dim

# ------------------------------------------------------------------
# Cosine similarity (pure-Python, no numpy dependency)
# ------------------------------------------------------------------

def _dot(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))

def _norm(v: list) -> float:
    return math.sqrt(sum(x * x for x in v))

def cosine_similarity(a: list, b: list) -> float:
    """Return cosine similarity in [0, 1] (clamped)."""
    na, nb = _norm(a), _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    sim = _dot(a, b) / (na * nb)
    return max(0.0, min(1.0, sim))

# ------------------------------------------------------------------
# LMStudio embedding call
# ------------------------------------------------------------------

def _get_embedding(text: str, session=None) -> Optional[list]:
    """Call LMStudio /v1/embeddings and return float list or None."""
    import requests
    sess = session or requests.Session()
    try:
        resp = sess.post(
            f"{LMSTUDIO_API_URL}/embeddings",
            headers={"Content-Type": "application/json"},
            json={"model": EMBEDDING_MODEL, "input": text},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["data"][0]["embedding"]
        else:
            logger.warning(f"Embedding API returned {resp.status_code}: {resp.text[:120]}")
            return None
    except Exception as e:
        logger.warning(f"Embedding request failed: {e}")
        return None

# ------------------------------------------------------------------
# RagIndex class
# ------------------------------------------------------------------

class RagIndex:
    """Manages FTS5 and embedding indexes for the functions table."""

    # Shared progress tracking for background builds
    _build_progress: dict = {}   # project_id → {"total": n, "done": n, "status": "..."}
    _lock = threading.Lock()

    # ----------------------------------------------------------------
    # FTS5 helpers
    # ----------------------------------------------------------------

    @staticmethod
    def build_fts(project_id: Optional[int] = None) -> int:
        """Populate (or refresh) the FTS5 index.
        If project_id is given, only refresh rows for that project.
        Returns number of rows indexed."""
        try:
            if project_id is not None:
                # Remove old entries for this project first
                db.execute_update(
                    '''DELETE FROM fts_functions WHERE function_id IN (
                        SELECT id FROM functions WHERE project_id = ?
                    )''',
                    (project_id,)
                )
                rows = db.execute_query(
                    '''SELECT f.id, f.function_name, f.class_name, f.package_name,
                              f.ai_summary, sf.file_name
                       FROM functions f
                       LEFT JOIN source_files sf ON f.file_id = sf.id
                       WHERE f.project_id = ?''',
                    (project_id,)
                )
            else:
                db.execute_update('DELETE FROM fts_functions', [])
                rows = db.execute_query(
                    '''SELECT f.id, f.function_name, f.class_name, f.package_name,
                              f.ai_summary, sf.file_name
                       FROM functions f
                       LEFT JOIN source_files sf ON f.file_id = sf.id'''
                )

            count = 0
            for row in rows:
                db.execute_update(
                    '''INSERT INTO fts_functions(function_id, function_name, class_name,
                       package_name, ai_summary, file_name) VALUES (?,?,?,?,?,?)''',
                    (
                        row[0],
                        row[1] or '',
                        row[2] or '',
                        row[3] or '',
                        row[4] or '',
                        row[5] or '',
                    )
                )
                count += 1

            logger.info(f"FTS5 index built: {count} functions (project={project_id})")
            return count
        except Exception as e:
            logger.error(f"FTS5 build error: {e}")
            return 0

    # ----------------------------------------------------------------
    # Embedding helpers
    # ----------------------------------------------------------------

    @classmethod
    def build_embeddings_async(cls, project_id: int, user_id: int = None):
        """Start embedding generation in a background thread."""
        key = project_id
        with cls._lock:
            if cls._build_progress.get(key, {}).get('status') == 'running':
                logger.info(f"Embedding build already running for project {project_id}")
                return
            cls._build_progress[key] = {'total': 0, 'done': 0, 'status': 'running', 'started': time.time()}

        def worker():
            try:
                import requests
                session = requests.Session()
                session.trust_env = False

                # Get functions that have ai_summary (most informative)
                rows = db.execute_query(
                    '''SELECT f.id, f.function_name, f.class_name, f.ai_summary, f.signature
                       FROM functions f
                       WHERE f.project_id = ?
                         AND f.ai_summary IS NOT NULL AND f.ai_summary != ""''',
                    (project_id,)
                )
                total = len(rows)
                with cls._lock:
                    cls._build_progress[project_id]['total'] = total

                done = 0
                for row in rows:
                    func_id = row[0]
                    name = row[1] or ''
                    cls_name = row[2] or ''
                    summary = row[3] or ''
                    sig = row[4] or ''

                    qualified = f"{cls_name}.{name}" if cls_name else name
                    text = f"{qualified}\n{sig}\n{summary}"[:2000]

                    embedding = _get_embedding(text, session)
                    if embedding:
                        db.execute_update(
                            '''INSERT OR REPLACE INTO function_embeddings
                               (function_id, project_id, embedding, model_name)
                               VALUES (?, ?, ?, ?)''',
                            (func_id, project_id, json.dumps(embedding), EMBEDDING_MODEL)
                        )
                    done += 1
                    with cls._lock:
                        cls._build_progress[project_id]['done'] = done

                elapsed = round(time.time() - cls._build_progress[project_id]['started'], 1)
                with cls._lock:
                    cls._build_progress[project_id]['status'] = 'done'
                    cls._build_progress[project_id]['elapsed'] = elapsed
                logger.info(f"Embedding build complete: project={project_id}, {done}/{total} in {elapsed}s")

            except Exception as e:
                logger.error(f"Embedding build error (project={project_id}): {e}")
                with cls._lock:
                    cls._build_progress[project_id]['status'] = 'error'
                    cls._build_progress[project_id]['error'] = str(e)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    @classmethod
    def get_build_status(cls, project_id: int) -> dict:
        """Return current build progress for a project."""
        with cls._lock:
            prog = dict(cls._build_progress.get(project_id, {'status': 'idle', 'total': 0, 'done': 0}))

        # Also report how many embeddings exist in DB
        try:
            rows = db.execute_query(
                'SELECT COUNT(*) FROM function_embeddings WHERE project_id = ?',
                (project_id,)
            )
            prog['indexed'] = rows[0][0] if rows else 0
            total_rows = db.execute_query(
                'SELECT COUNT(*) FROM functions WHERE project_id = ?',
                (project_id,)
            )
            prog['total_functions'] = total_rows[0][0] if total_rows else 0
        except Exception:
            pass
        return prog

    # ----------------------------------------------------------------
    # Hybrid search
    # ----------------------------------------------------------------

    @classmethod
    def search(cls, project_id: int, query: str, limit: int = 10, function_ids: list[int] | None = None) -> list:
        """Hybrid search: embedding cosine sim + FTS5 BM25, with LIKE fallback.

        If `function_ids` is provided, returns those functions (in same order) without running a search.
        Returns list of dicts matching the shape of _search_functions output, with an added `score` field.
        """
        if function_ids:
            # Return explicit selection (used when user chooses RAG hits before asking the LLM)
            placeholders = ','.join('?' * len(function_ids))
            rows = db.execute_query(
                f'''SELECT f.id, f.function_name, f.class_name, f.package_name,
                           f.ai_summary, f.signature, sf.file_name
                    FROM functions f
                    LEFT JOIN source_files sf ON f.file_id = sf.id
                    WHERE f.project_id = ? AND f.id IN ({placeholders})''',
                [project_id] + function_ids
            )
            row_map = {dict(r)['id']: dict(r) for r in rows}
            result = [dict(row_map[fid], score=1.0) for fid in function_ids if fid in row_map]
            return result

        # Step 1: Embedding search (if embeddings exist)
        embedding_hits = {}  # function_id → score
        try:
            count_rows = db.execute_query(
                'SELECT COUNT(*) FROM function_embeddings WHERE project_id = ?',
                (project_id,)
            )
            embedding_count = count_rows[0][0] if count_rows else 0

            if embedding_count > 0:
                query_vec = _get_embedding(query)
                if query_vec:
                    stored = db.execute_query(
                        'SELECT function_id, embedding FROM function_embeddings WHERE project_id = ?',
                        (project_id,)
                    )
                    for row in stored:
                        fid = row[0]
                        try:
                            vec = json.loads(row[1])
                            sim = cosine_similarity(query_vec, vec)
                            embedding_hits[fid] = sim
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"Embedding search error: {e}")

        # Step 2: FTS5 search
        fts_hits = {}  # function_id → bm25_score (negative = better)
        try:
            fts_count = db.execute_query(
                "SELECT COUNT(*) FROM fts_functions WHERE function_id IN (SELECT id FROM functions WHERE project_id = ?)",
                (project_id,)
            )
            if fts_count and fts_count[0][0] > 0:
                escaped = query.replace('"', '""')
                fts_rows = db.execute_query(
                    '''SELECT function_id, bm25(fts_functions) as score
                       FROM fts_functions
                       WHERE fts_functions MATCH ? AND function_id IN (
                           SELECT id FROM functions WHERE project_id = ?
                       )
                       ORDER BY score LIMIT ?''',
                    (escaped, project_id, limit * 2)
                )
                for row in fts_rows:
                    fts_hits[row[0]] = row[1]
        except Exception as e:
            logger.warning(f"FTS5 search error: {e}")

        # Step 3: Combine scores
        all_ids = set(embedding_hits.keys()) | set(fts_hits.keys())
        score_map = {}

        def combined_score(fid):
            emb = embedding_hits.get(fid, 0.0)
            # BM25 scores are negative (more negative = better), normalize to [0,1]
            bm25 = fts_hits.get(fid, 0.0)
            bm25_norm = 1.0 / (1.0 - bm25) if bm25 < 0 else 0.0
            # Weight: embeddings 60%, FTS5 40%
            s = 0.6 * emb + 0.4 * bm25_norm
            score_map[fid] = s
            return s

        if all_ids:
            ranked = sorted(all_ids, key=combined_score, reverse=True)[:limit]
        else:
            ranked = []

        # Step 4: Fetch function details
        if ranked:
            placeholders = ','.join('?' * len(ranked))
            rows = db.execute_query(
                f'''SELECT f.id, f.function_name, f.class_name, f.package_name,
                           f.ai_summary, f.signature, sf.file_name
                    FROM functions f
                    LEFT JOIN source_files sf ON f.file_id = sf.id
                    WHERE f.id IN ({placeholders})''',
                ranked
            )
            # Maintain ranking order
            row_map = {dict(r)['id']: dict(r) for r in rows}
            result = []
            for fid in ranked:
                if fid in row_map:
                    item = row_map[fid]
                    item['score'] = round(score_map.get(fid, 0.0), 4)
                    result.append(item)
            if result:
                return result

        # Step 5: Fallback to LIKE search
        logger.debug("RAG index miss — falling back to LIKE search")
        result = cls._like_fallback(project_id, query, limit)
        for item in result:
            item['score'] = 0.1
        return result

    @classmethod
    def search_doc_chunks(cls, project_id: int, query: str, limit: int = 5) -> list:
        """Search doc_chunks embeddings for relevant document passages.
        Returns list of dicts: {file_name, chunk_index, content, score}"""
        try:
            count_rows = db.execute_query(
                'SELECT COUNT(*) FROM doc_chunks WHERE project_id = ? AND embedding IS NOT NULL',
                (project_id,)
            )
            if not count_rows or count_rows[0][0] == 0:
                return []

            query_vec = _get_embedding(query)
            if not query_vec:
                return []

            stored = db.execute_query(
                'SELECT file_name, chunk_index, content, embedding FROM doc_chunks WHERE project_id = ? AND embedding IS NOT NULL',
                (project_id,)
            )
            scored = []
            for row in stored:
                try:
                    vec = json.loads(row[3])
                    sim = cosine_similarity(query_vec, vec)
                    scored.append({'file_name': row[0], 'chunk_index': row[1], 'content': row[2], 'score': sim})
                except Exception:
                    pass

            scored.sort(key=lambda x: x['score'], reverse=True)
            return scored[:limit]
        except Exception as e:
            logger.warning(f"Doc chunk search error: {e}")
            return []

    @staticmethod
    def _like_fallback(project_id: int, query: str, limit: int) -> list:
        """Original LIKE-based search as a safety net."""
        import re as _re
        stop = {'bir', 'ile', 'için', 'olan', 'ne', 'bu', 'the', 'and', 'for',
                'how', 'what', 'which', 'is', 'are', 'can', 'does', 'do',
                'yapıyor', 'nedir', 'çalışıyor', 'nasıl', 'hangi'}
        raw_tokens = []
        for word in query.split():
            raw_tokens.extend(word.split('.'))
        tokens = []
        seen = set()
        for t in raw_tokens:
            tc = _re.sub(r'[^\w]', '', t).lower()
            if len(tc) >= 3 and tc not in stop and tc not in seen:
                tokens.append(tc)
                seen.add(tc)

        if not tokens:
            rows = db.execute_query(
                '''SELECT f.id, f.function_name, f.class_name, f.package_name,
                          f.ai_summary, f.signature, sf.file_name
                   FROM functions f
                   LEFT JOIN source_files sf ON f.file_id = sf.id
                   WHERE f.project_id = ? LIMIT ?''',
                (project_id, limit)
            )
            return [dict(r) for r in rows]

        like_conditions, params = [], []
        for token in tokens[:6]:
            like_conditions.append(
                '(LOWER(f.function_name) LIKE ? OR LOWER(COALESCE(f.class_name,"")) LIKE ?'
                ' OR LOWER(COALESCE(f.ai_summary,"")) LIKE ? OR LOWER(COALESCE(sf.file_name,"")) LIKE ?)'
            )
            t = f'%{token}%'
            params += [t, t, t, t]

        where_sql = ' OR '.join(like_conditions)
        rows = db.execute_query(
            f'''SELECT f.id, f.function_name, f.class_name, f.package_name,
                       f.ai_summary, f.signature, sf.file_name
                FROM functions f
                LEFT JOIN source_files sf ON f.file_id = sf.id
                WHERE f.project_id = ? AND ({where_sql})
                ORDER BY f.function_name LIMIT ?''',
            [project_id] + params + [limit]
        )
        return [dict(r) for r in rows]
