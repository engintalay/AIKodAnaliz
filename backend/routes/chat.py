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

def _build_context(project_id: int, project_name: str, query: str, function_ids: list[int] | None = None, additional_context: str | None = None) -> tuple[str, str, list]:
    """Return (system_prompt, context_block, refs) for the LLM.
    Uses RagIndex for hybrid embedding + FTS5 + LIKE search.
    Also searches doc_chunks (GELIS8) for relevant document passages.

    If `function_ids` is provided, those functions are used as the primary context.
    If `additional_context` is provided, it is prepended to the main context.
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
    
    # Prepend additional context if provided
    final_context_block = context_block
    if additional_context:
        final_context_block = (
            "=== EK BAĞLAM (Kullanıcı Tarafından Eklendi) ===\n"
            f"{additional_context}\n"
            "============================================\n\n"
            f"{context_block}"
        )


    system_prompt = (
        f"Sen '{project_name}' projesinin AI kod asistanısın. "
        "YALNIZCA Türkçe yanıt ver. "
        "Aşağıdaki proje fonksiyonlarından ve ek bağlamdan yola çıkarak soruyu yanıtla. "
        "Eğer soruyla ilgili fonksiyon bulunamazsa bunu açıkça belirt. "
        "Kod snippet'i verirken Markdown kullan.\n\n"
        "=== PROJE FONKSİYONLARI VE BAĞLAM ===\n"
        f"{final_context_block}\n"
        "======================================"
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
    
    Body JSON: { 
        "message": "...", 
        "history": [{"role": ..., "content": ...}, ...],
        "attachments": [{"id": "...", "type": "file|function"}, ...] 
    }
    Response: text/event-stream
    """
    user = get_user_from_session()

    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    history = data.get('history', [])  # list of {role, content}
    context_function_ids = data.get('context_function_ids') or None
    attachments = data.get('attachments', [])

    if not user_message and not attachments:
        return jsonify({'error': 'Mesaj boş olamaz'}), 400

    # If message is empty but there are attachments, create a default prompt.
    if not user_message and attachments:
        user_message = "Lütfen ekteki bağlamı analiz et ve bir özet sun."

    # Fetch project info
    proj_rows = db.execute_query('SELECT id, name FROM projects WHERE id = ?', (project_id,))
    if not proj_rows:
        return jsonify({'error': 'Proje bulunamadı'}), 404
    project_name = dict(proj_rows[0])['name']

    # --- Build context from attachments ---
    additional_context_parts = []
    if attachments:
        for item in attachments:
            item_id = item.get('id')
            item_type = item.get('type')
            item_name = item.get('name')

            if not item_id or not item_type:
                continue
            
            content = ''
            if item_type == 'function':
                # Fetch function source code by getting file content and slicing lines
                func_meta_rows = db.execute_query(
                    'SELECT file_id, start_line, end_line FROM functions WHERE id = ? AND project_id = ?',
                    (item_id, project_id)
                )
                if func_meta_rows:
                    meta = dict(func_meta_rows[0])
                    file_rows = db.execute_query(
                        'SELECT content FROM source_files WHERE id = ? AND project_id = ?',
                        (meta['file_id'], project_id)
                    )
                    if file_rows:
                        try:
                            full_content = file_rows[0]['content']
                            if isinstance(full_content, bytes):
                                full_content = full_content.decode('utf-8', errors='ignore')
                            
                            lines = full_content.splitlines()
                            # Ensure start/end lines are within bounds
                            start = max(0, meta['start_line'] - 1)
                            end = min(len(lines), meta['end_line'])
                            function_lines = lines[start:end]
                            content = '\n'.join(function_lines)
                        except Exception as e:
                            logger.error(f"Error extracting function code for func_id {item_id}: {e}")
                            content = f"[Hata: Fonksiyon kodu ayıklanamadı - {e}]"
            
            elif item_type == 'file':
                # Fetch file content from the virtual file system
                file_rows = db.execute_query('SELECT content FROM project_files WHERE file_path = ? AND project_id = ?', (item_id, project_id))
                if file_rows:
                    # Content might be binary, so we decode safely
                    try:
                        content = file_rows[0]['content'].decode('utf-8')
                    except (UnicodeDecodeError, AttributeError):
                        content = '[İkili dosya içeriği gösterilemiyor]'

            if content:
                additional_context_parts.append(f"--- {item_name} ({item_type}) ---\n{content}\n")
    
    additional_context = "\n".join(additional_context_parts)
    # --- End of attachment context building ---

    system_prompt, _, refs = _build_context(
        project_id, 
        project_name, 
        user_message, 
        function_ids=context_function_ids,
        additional_context=additional_context
    )

    # Build message list for LLM, filtering out any messages with empty content
    messages = [dict(h) for h in history if h.get('role') in ('user', 'assistant') and h.get('content')]
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
                # Her chunk için <think> bloklarını temizle
                cleaned_chunk = _re.sub(r'<think>.*?</think>', '', chunk, flags=_re.DOTALL)
                escaped = cleaned_chunk.replace('\n', '\n')
                if escaped:
                    yield f"data:{escaped}\n\n"

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
