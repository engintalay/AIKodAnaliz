"""AI Chat routes – per-project conversational assistant."""
import json
from flask import Blueprint, request, jsonify, Response, stream_with_context
from backend.database import db
from backend.lmstudio_client import LMStudioClient
from backend.permission_manager import get_user_from_session, check_project_access
from backend.logger import logger, log_audit
from backend.rag_index import RagIndex

bp = Blueprint('chat', __name__, url_prefix='/api/chat')

# ------------------------------------------------------------------
# Context retrieval helpers
# ------------------------------------------------------------------

def _build_context(project_id: int, project_name: str, query: str, function_ids: list[int] | None = None) -> tuple[str, str, list]:
    """Return (system_prompt, context_block, refs) for the LLM.
    Uses RagIndex for hybrid embedding + FTS5 + LIKE search.
    Also searches doc_chunks (GELIS8) for relevant document passages.

    If `function_ids` is provided, those functions are used as the primary context.
    """
    if function_ids:
        funcs = RagIndex.search(project_id, query, limit=len(function_ids) or 10, function_ids=function_ids)
    else:
        funcs = RagIndex.search(project_id, query)

    context_lines = []
    refs = []  # For the frontend to render as links
    for f in funcs:
        qualified = f['function_name']
        if f.get('class_name'):
            qualified = f"{f['class_name']}.{qualified}"
        if f.get('package_name'):
            qualified = f"{f['package_name']}.{qualified}"
        summary = f.get('ai_summary') or ''
        file_name = f.get('file_name') or ''
        sig = f.get('signature') or ''
        context_lines.append(
            f"- **{qualified}** (`{file_name}`)"
            + (f"\n  İmza: `{sig}`" if sig else '')
            + (f"\n  Özet: {summary}" if summary else '')
        )
        refs.append({'id': f.get('id'), 'name': qualified, 'file': file_name})

    context_block = '\n'.join(context_lines) if context_lines else 'İlgili fonksiyon bulunamadı.'

    # Also search doc_chunks for relevant document passages (GELIS8)
    doc_hits = RagIndex.search_doc_chunks(project_id, query, limit=3)
    doc_block = ''
    if doc_hits:
        doc_parts = []
        for hit in doc_hits:
            if hit['score'] > 0.35:   # Only include reasonably relevant chunks
                doc_parts.append(f"[{hit['file_name']}#{hit['chunk_index']}]\n{hit['content']}")
        if doc_parts:
            doc_block = '\n\n'.join(doc_parts)

    system_prompt = (
        f"Sen '{project_name}' projesinin AI kod asistanısın. "
        "YALNIZCA Türkçe yanıt ver. "
        "Aşağıdaki proje fonksiyonlarından yola çıkarak soruyu yanıtla. "
        "Eğer soruyla ilgili fonksiyon bulunamazsa bunu açıkça belirt. "
        "Kod snippet'i verirken Markdown kullan.\n\n"
        "=== PROJE FONKSİYONLARI ===\n"
        f"{context_block}\n"
        "==========================="
        + (("\n\n=== PROJE DOKÜMANLARI ===\n" + doc_block + "\n========================") if doc_block else '')
    )
    return system_prompt, context_block, refs


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@bp.route('/project/<int:project_id>', methods=['POST'])
@check_project_access('read')
def chat_with_project(project_id):
    """Streaming SSE chat endpoint.
    
    Body JSON: { "message": "...", "history": [{"role": ..., "content": ...}, ...] }
    Response: text/event-stream  (each chunk: 'data: <token>\\n\\n', ends with 'data: [DONE]\\n\\n')
    """
    user = get_user_from_session()

    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    history = data.get('history', [])  # list of {role, content}
    context_function_ids = data.get('context_function_ids') or None

    if not user_message:
        return jsonify({'error': 'Mesaj boş olamaz'}), 400

    # Fetch project info
    proj_rows = db.execute_query('SELECT id, name FROM projects WHERE id = ?', (project_id,))
    if not proj_rows:
        return jsonify({'error': 'Proje bulunamadı'}), 404
    project_name = dict(proj_rows[0])['name']

    system_prompt, _, refs = _build_context(project_id, project_name, user_message, function_ids=context_function_ids)

    # Build message list for LLM
    messages = [dict(h) for h in history if h.get('role') in ('user', 'assistant')]
    messages.append({'role': 'user', 'content': user_message})

    log_audit(user, 'chat_message_sent', 'project', project_id,
              details=user_message[:100], request=request)

    refs_json = json.dumps(refs, ensure_ascii=False)

    def generate():
        import re as _re

        try:
            client = LMStudioClient(user_id=user['id'] if user else None)

            # Send reference functions list first so the frontend can display links
            yield f"event:refs\ndata:{refs_json}\n\n"

            buffer = ''
            think_stripped = False   # True once we've dealt with any think block
            in_think = False         # Currently inside <think>...</think>

            for chunk in client.chat_stream(messages, system_prompt=system_prompt):
                if think_stripped:
                    # Fast path: think block already handled, stream directly
                    escaped = chunk.replace('\n', '\\n')
                    yield f"data:{escaped}\n\n"
                    continue

                buffer += chunk

                if '<think>' in buffer:
                    in_think = True
                    if '</think>' in buffer:
                        # Strip the entire think block and start streaming the rest
                        cleaned = _re.sub(r'<think>.*?</think>', '', buffer, flags=_re.DOTALL).lstrip('\n')
                        think_stripped = True
                        in_think = False
                        buffer = ''
                        if cleaned:
                            escaped = cleaned.replace('\n', '\\n')
                            yield f"data:{escaped}\n\n"
                    # else: still buffering the think block
                elif not in_think and len(buffer) >= 15:
                    # No think tag detected after 15 chars → safe to stream normally
                    think_stripped = True
                    escaped = buffer.replace('\n', '\\n')
                    yield f"data:{escaped}\n\n"
                    buffer = ''

            # Flush any remaining buffer after stream ends
            if buffer and not in_think:
                cleaned = _re.sub(r'<think>.*?</think>', '', buffer, flags=_re.DOTALL).lstrip('\n')
                if cleaned:
                    escaped = cleaned.replace('\n', '\\n')
                    yield f"data:{escaped}\n\n"

            yield "data:[DONE]\n\n"

        except GeneratorExit:
            return
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            try:
                yield f"data:⚠️ Hata: {str(e)}\n\n"
                yield "data:[DONE]\n\n"
            except GeneratorExit:
                return


    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # disable Nginx buffering
        }
    )


@bp.route('/project/<int:project_id>/search', methods=['GET'])
@check_project_access('read')
def search_functions(project_id):
    """Quick function search for the chat autocomplete."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([]), 200
    funcs = _search_functions(project_id, query, limit=15)
    result = []
    for f in funcs:
        qualified = f['function_name']
        if f.get('class_name'):
            qualified = f"{f['class_name']}.{qualified}"
        result.append({'name': qualified, 'file': f.get('file_name', '')})
    return jsonify(result), 200
