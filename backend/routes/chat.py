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

    # Search doc_chunks for relevant document passages (GELIS8).
    # First try embedding-based retrieval, then fall back to lexical retrieval
    # when embeddings are not ready or confidence is low.
    doc_hits = RagIndex.search_doc_chunks(project_id, query, limit=5)
    doc_block = ''
    doc_parts = []
    if doc_hits:
        for hit in doc_hits:
            if hit.get('score', 0.0) > 0.30:
                doc_parts.append(f"[{hit['file_name']}#{hit['chunk_index']}]\n{hit['content']}")

    if not doc_parts:
        fallback_hits = RagIndex.search_doc_chunks_fallback(project_id, query, limit=3)
        for hit in fallback_hits:
            doc_parts.append(f"[{hit['file_name']}#{hit['chunk_index']}]\n{hit['content']}")

    if doc_parts:
        doc_block = '\n\n'.join(doc_parts[:3])

    system_prompt = (
        f"Sen '{project_name}' projesinin AI kod asistanısın. "
        "YALNIZCA Türkçe yanıt ver. "
        "Kesinlikle iç düşünce, plan, analiz adımları veya kanal/meta etiketleri (ör. think, thought, analysis, final) yazma. "
        "Sadece kullanıcıya gösterilecek nihai yanıtı üret. "
        "Aşağıdaki proje fonksiyonlarından yola çıkarak soruyu yanıtla. "
        "Proje dokümanlarında soru ile ilgili açık bilgi varsa cevabı öncelikle doküman içeriğine dayandır. "
        "Olabildiğince detaylı ve açıklayıcı ol. Teknik detaylara girmekten çekinme. Kodun ne yaptığını, nasıl çalıştığını, neden öyle yapıldığını anlat. Eğer kodda belirsizlikler varsa, mümkün olan en iyi tahminini yaparak bunları da açıklamaya çalış. Eğer kodun amacı veya işlevi hakkında kesin bir fikrin yoksa, bunu açıkça belirt ve olası senaryoları sıralayarak açıklamaya çalış. Kodun hangi problemleri çözmeye çalıştığını, hangi ihtiyaçlara hizmet ettiğini, hangi durumlarda kullanışlı olabileceğini anlat. Kodun güçlü ve zayıf yönlerini, potansiyel riskleri veya yan etkileri varsa bunları da açıklamaya çalış. Kodun nasıl geliştirilebileceği veya iyileştirilebileceği konusunda önerilerin varsa bunları da paylaş. Kodun genel bağlamını, kullanım senaryolarını ve teknik detaylarını mümkün olan en iyi şekilde açıklamaya çalış. "
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
    max_tokens = data.get('max_tokens') or None
    if max_tokens:
        try:
            max_tokens = int(max_tokens)
        except (ValueError, TypeError):
            max_tokens = None

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

            in_think = False
            in_reasoning_channel = False

            def _strip_think_blocks(text: str) -> str:
                nonlocal in_think
                if not text:
                    return ''

                out = text

                if in_think:
                    end_idx = out.find('</think>')
                    if end_idx == -1:
                        return ''
                    out = out[end_idx + len('</think>'):]
                    in_think = False

                while True:
                    start_idx = out.find('<think>')
                    if start_idx == -1:
                        break
                    end_idx = out.find('</think>', start_idx)
                    if end_idx == -1:
                        out = out[:start_idx]
                        in_think = True
                        break
                    out = out[:start_idx] + out[end_idx + len('</think>'):]

                return out

            def _strip_reasoning_channel(text: str) -> str:
                nonlocal in_reasoning_channel
                if not text:
                    return ''

                out = text

                # Remove isolated metadata channel markers if they appear inline.
                out = _re.sub(r'<\|channel\|>\s*(?:assistant|final)\b', '', out, flags=_re.IGNORECASE)

                if in_reasoning_channel:
                    final_match = _re.search(r'<\|channel\|>\s*final\b', out, flags=_re.IGNORECASE)
                    if not final_match:
                        return ''
                    out = out[final_match.end():]
                    in_reasoning_channel = False

                while True:
                    thought_match = _re.search(r'<\|channel\|>\s*(?:thought|analysis)\b', out, flags=_re.IGNORECASE)
                    if not thought_match:
                        break

                    prefix = out[:thought_match.start()]
                    rest = out[thought_match.end():]
                    final_match = _re.search(r'<\|channel\|>\s*final\b', rest, flags=_re.IGNORECASE)

                    if final_match:
                        out = prefix + rest[final_match.end():]
                        continue

                    out = prefix
                    in_reasoning_channel = True
                    break

                # Remove any remaining serialized metadata tokens.
                out = _re.sub(r'<\|[^>]+\|>', '', out)
                return out

            for chunk in client.chat_stream(messages, system_prompt=system_prompt, max_tokens=max_tokens):
                cleaned_chunk = _strip_think_blocks(chunk)
                cleaned_chunk = _strip_reasoning_channel(cleaned_chunk)
                if cleaned_chunk:
                    # SSE data lines must be single-line; keep newlines as escaped literals.
                    escaped = cleaned_chunk.replace('\n', '\\n')
                    if escaped:
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
