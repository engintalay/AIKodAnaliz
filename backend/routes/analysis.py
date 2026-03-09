from flask import Blueprint, request, jsonify
from backend.database import db
from backend.analyzers.advanced_analyzer import AdvancedCodeAnalyzer
from backend.lmstudio_client import LMStudioClient
from backend.progress_tracker import progress_tracker
from backend.logger import logger, log_analysis, log_ai_call, log_error
from backend.permission_manager import get_user_from_session
import json
import uuid
import re
import threading

CALL_NAME_PATTERN = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
QUALIFIED_CALL_PATTERN = re.compile(r'(\w+)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(')  # receiver.method()
PY_IMPORT_PATTERN = re.compile(r'^\s*(?:from\s+[\w\.]+\s+import\s+([\w\s,\*]+)|import\s+([\w\.,\s]+))', re.MULTILINE)
JS_IMPORT_PATTERN = re.compile(r'^\s*import\s+(?:([\w\{\}\s,\*]+)\s+from\s+)?[\"\'][^\"\']+[\"\']', re.MULTILINE)
JAVA_IMPORT_PATTERN = re.compile(r'^\s*import\s+(?:static\s+)?([\w\.\*]+)\s*;', re.MULTILINE)
CALL_KEYWORDS = {
    'if', 'for', 'while', 'switch', 'catch', 'return', 'new', 'super', 'this',
    'else', 'try', 'throw', 'typeof', 'sizeof'
}
COMMON_EXTERNAL_CALLS = {
    'print', 'len', 'str', 'int', 'float', 'dict', 'list', 'set', 'tuple',
    'fetch', 'setTimeout', 'setInterval', 'require', 'console', 'log',
    'System', 'Math', 'String', 'Integer', 'Long', 'Double'
}


def _is_ai_error_response(summary_text):
    """True when model output is an error payload, not a valid summary."""
    if not summary_text:
        return True
    text = str(summary_text).strip()
    return (
        text.startswith('Error:')
        or 'LMStudio returned 400' in text
        or text.startswith('⚠️ AI Analiz Hatası:')
    )


def _load_ai_runtime_settings():
    """Load runtime AI generation parameters from ai_settings table."""
    ai_settings = {}
    settings_rows = db.execute_query(
        'SELECT setting_name, setting_value, data_type FROM ai_settings'
    )
    for row in settings_rows:
        setting = dict(row)
        name = setting['setting_name']
        value = setting['setting_value']
        data_type = setting['data_type']

        if data_type == 'integer':
            ai_settings[name] = int(value)
        elif data_type == 'float':
            ai_settings[name] = float(value)
        else:
            ai_settings[name] = value

    return {
        'temperature': ai_settings.get('temperature'),
        'top_p': ai_settings.get('top_p'),
        'max_tokens': ai_settings.get('max_tokens')
    }


def _accumulate_ai_metrics(task_id, call_stats):
    """Accumulate AI token/time stats into progress tracker metrics."""
    if not task_id or not call_stats:
        return

    task_progress = progress_tracker.get_progress(task_id) or {}
    existing = task_progress.get('metrics', {}) if isinstance(task_progress, dict) else {}

    prev_calls = int(existing.get('ai_calls') or 0)
    prev_prompt = int(existing.get('ai_prompt_tokens') or 0)
    prev_completion = int(existing.get('ai_completion_tokens') or 0)
    prev_total = int(existing.get('ai_total_tokens') or 0)
    prev_duration = float(existing.get('ai_total_duration_seconds') or 0.0)

    prompt_tokens = int(call_stats.get('prompt_tokens') or 0)
    completion_tokens = int(call_stats.get('completion_tokens') or 0)
    total_tokens = int(call_stats.get('total_tokens') or 0)
    duration_seconds = float(call_stats.get('duration_seconds') or 0.0)

    progress_tracker.set_metrics(
        task_id,
        ai_calls=prev_calls + 1,
        ai_prompt_tokens=prev_prompt + prompt_tokens,
        ai_completion_tokens=prev_completion + completion_tokens,
        ai_total_tokens=prev_total + total_tokens,
        ai_total_duration_seconds=round(prev_duration + duration_seconds, 3),
    )


def extract_imported_symbols(content, language):
    """Return imported/external symbol names so they are not mapped as project-internal calls."""
    symbols = set()
    lang = (language or '').lower()

    if lang == 'python':
        for match in PY_IMPORT_PATTERN.finditer(content or ''):
            from_imports = match.group(1)
            direct_imports = match.group(2)

            if from_imports:
                for item in from_imports.split(','):
                    token = item.strip().split(' as ')[-1].strip()
                    if token and token != '*':
                        symbols.add(token)

            if direct_imports:
                for item in direct_imports.split(','):
                    module_name = item.strip().split(' as ')[-1].strip().split('.')[-1]
                    if module_name:
                        symbols.add(module_name)

    elif lang in ('javascript', 'typescript'):
        for match in JS_IMPORT_PATTERN.finditer(content or ''):
            imported = (match.group(1) or '').strip()
            if not imported:
                continue
            imported = imported.replace('{', '').replace('}', '')
            for item in imported.split(','):
                token = item.strip().split(' as ')[-1].strip()
                if token and token != '*':
                    symbols.add(token)

    elif lang == 'java':
        for match in JAVA_IMPORT_PATTERN.finditer(content or ''):
            imported_path = match.group(1)
            if not imported_path:
                continue
            leaf = imported_path.split('.')[-1]
            if leaf and leaf != '*':
                symbols.add(leaf)

    return symbols

bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')

@bp.route('/test-connection', methods=['GET'])
def test_lmstudio_connection():
    """Test LMStudio connection"""
    try:
        user = get_user_from_session()
        client = LMStudioClient(user_id=user['id'] if user else None)
        status = client.test_connection()
        return jsonify(status), 200 if status['status'] == 'connected' else 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/project/<int:project_id>', methods=['POST'])
def analyze_project(project_id):
    """Analyze entire project"""
    task_id = request.args.get('task_id')
    try:
        logger.info(f"Starting analysis for project {project_id}")
        
        if task_id:
            progress_tracker.start_task(task_id, total_steps=100)
            progress_tracker.update(
                task_id,
                progress=2,
                step='Analiz hazırlanıyor...',
                detail=f'Proje {project_id} için analiz başlatıldı'
            )
        
        # Clear previous analysis data (allow re-analysis)
        # Note: This will clear AI summaries. If re-analyzing, user should save important summaries.
        db.execute_update('DELETE FROM function_calls WHERE project_id = ?', (project_id,))
        db.execute_update('DELETE FROM entry_points WHERE project_id = ?', (project_id,))
        db.execute_update('DELETE FROM functions WHERE project_id = ?', (project_id,))
        
        # Get all files in project
        rows = db.execute_query(
            'SELECT id, content, language, file_name FROM source_files WHERE project_id = ?',
            (project_id,)
        )
        
        if task_id:
            progress_tracker.update(
                task_id,
                progress=8,
                step='Kaynak dosyalar alındı',
                detail=f'Toplam {len(rows)} dosya analiz kuyruğunda'
            )
        
        log_analysis(project_id, "Retrieved source files", count=len(rows))
        
        analyzer = AdvancedCodeAnalyzer()
        all_functions = []
        all_entry_points = []
        skipped_unsupported = 0
        skipped_with_error = 0
        total_files = len(rows) if rows else 1
        
        for idx, row in enumerate(rows):
            file_id = row[0]
            content = row[1]
            language = row[2]
            file_name = row[3]
            
            logger.debug(f"[Project {project_id}] Analyzing file {idx+1}/{len(rows)}: {file_name}")
            if task_id:
                file_progress = 10 + int(((idx + 1) / total_files) * 70)
                progress_tracker.update(
                    task_id,
                    progress=file_progress,
                    step=f'Analiz ediliyor: {file_name} ({idx+1}/{len(rows)})',
                    detail=f'Dosya işleniyor: {file_name}'
                )
            
            # Analyze file. Unsupported languages should not abort the whole project analysis.
            try:
                result = analyzer.analyze(file_name, content, language)
            except ValueError as e:
                skipped_unsupported += 1
                logger.debug(
                    f"[Project {project_id}] Skipped unsupported file: {file_name} "
                    f"(language={language}, reason={e})"
                )
                if task_id:
                    progress_tracker.update(
                        task_id,
                        detail=f'Atlandı (desteklenmeyen dil): {file_name} [{language}]'
                    )
                continue
            except Exception as e:
                skipped_with_error += 1
                logger.warning(
                    f"[Project {project_id}] File analysis failed: {file_name} "
                    f"(language={language}, error={e})"
                )
                if task_id:
                    progress_tracker.update(
                        task_id,
                        detail=f'Atlandı (analiz hatası): {file_name}'
                    )
                continue
            
            log_analysis(project_id, f"Analyzed {file_name}", 
                        functions_found=len(result.get('functions', [])),
                        language=language)
            if task_id:
                progress_tracker.update(
                    task_id,
                    detail=(
                        f'Analiz tamam: {file_name} | '
                        f"{len(result.get('functions', []))} fonksiyon"
                    )
                )
            
            # Store functions and entry points
            for func in result.get('functions', []):
                func_id = db.execute_insert(
                    '''INSERT INTO functions 
                    (project_id, file_id, function_name, function_type, 
                    start_line, end_line, signature, parameters, return_type,
                    class_name, package_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (project_id, file_id, func['name'], func['type'],
                    func['start_line'], func['end_line'], func['signature'],
                    json.dumps(func['parameters']), func.get('return_type', ''),
                    func.get('class_name'), func.get('package_name'))
                )
                all_functions.append(func_id)
                logger.debug(f"[Project {project_id}] Stored function: {func['name']} (ID: {func_id})")
                
                # If this function is marked as entry point, add to entry_points table
                if func.get('is_entry', False):
                    entry_type = 'service' if func.get('type') == 'entry' else 'main'
                    db.execute_insert(
                        '''INSERT INTO entry_points 
                        (project_id, function_id, entry_type)
                        VALUES (?, ?, ?)''',
                        (project_id, func_id, entry_type)
                    )
                    all_entry_points.append(func_id)
                    logger.debug(f"[Project {project_id}] Marked as entry point: {func['name']} (type: {entry_type})")
                
        log_analysis(project_id, "Function extraction complete", total_functions=len(all_functions))
        if task_id:
            progress_tracker.update(
                task_id,
                progress=85,
                step='Fonksiyon çağrıları çıkarılıyor...',
                detail='Bağımlılık analizi başlatıldı'
            )
        log_analysis(
            project_id,
            "Files skipped during analysis",
            unsupported=skipped_unsupported,
            failed=skipped_with_error
        )
        
        # --- SECOND PASS: Detect Function Calls (OPTIMIZED) ---
        logger.debug(f"[Project {project_id}] Starting dependency detection")
        
        # Get all functions with their file contents again to scan for calls
        funcs_query = db.execute_query(
            '''SELECT f.id, f.file_id, f.function_name, f.class_name, f.start_line, f.end_line, s.content, s.language
               FROM functions f 
               JOIN source_files s ON f.file_id = s.id 
               WHERE f.project_id = ?''',
            (project_id,)
        )
        
        funcs_data = [dict(row) for row in funcs_query]
        dependencies_found = 0
        total_funcs = len(funcs_data)
        
        # ✅ Qualified Name Mapping: Build hash tables for O(1) lookup
        # Map 1: ClassName.FunctionName → function_id (primary lookup)
        qualified_map = {}
        # Map 2: FunctionName → [list of function_ids] (fallback for unqualified calls)
        func_name_list = {}
        # Map 3: ClassName → [list of function_ids] (for same-class matching)
        class_funcs_map = {}
        
        for func in funcs_data:
            func_id = func['id']
            func_name = func['function_name']
            class_name = func.get('class_name')
            
            # Map 2: Track all functions by name (for fallback)
            if func_name not in func_name_list:
                func_name_list[func_name] = []
            func_name_list[func_name].append({
                'id': func_id,
                'class': class_name,
                'func_data': func
            })
            
            # Map 1: Qualified name (ClassName.FunctionName)
            if class_name:
                qualified_key = f"{class_name}.{func_name}"
                qualified_map[qualified_key] = func_id
            
            # Map 3: Track functions by class (for same-class context matching)
            if class_name:
                if class_name not in class_funcs_map:
                    class_funcs_map[class_name] = {}
                class_funcs_map[class_name][func_name] = func_id
        
        imported_symbols_by_file = {}
        
        # ✅ OPTIMIZATION 2: Collect all inserts for batch operation
        function_calls_batch = []
        inserted_pairs = set()
        
        for idx, caller in enumerate(funcs_data):
            # Extract caller's block
            lines = caller['content'].split('\n')
            start = max(0, caller['start_line'] - 1)
            end = min(len(lines), caller['end_line'])
            caller_code = '\n'.join(lines[start:end])

            # Determine file-level external/imported symbols once and cache by file_id
            file_id = caller['file_id']
            if file_id not in imported_symbols_by_file:
                imported_symbols_by_file[file_id] = extract_imported_symbols(
                    caller.get('content', ''),
                    caller.get('language', '')
                )
            file_imported_symbols = imported_symbols_by_file[file_id]

            caller_class = caller.get('class_name')
            caller_id = caller['id']
            
            # ✅ Extract QUALIFIED calls first: receiver.method()
            qualified_calls = set()
            for match in QUALIFIED_CALL_PATTERN.finditer(caller_code):
                receiver = match.group(1)
                method_name = match.group(2)
                if method_name not in CALL_KEYWORDS:
                    qualified_calls.add((receiver, method_name))
            
            # ✅ Extract UNQUALIFIED calls: foo()
            unqualified_calls = {
                match.group(1)
                for match in CALL_NAME_PATTERN.finditer(caller_code)
                if match.group(1) not in CALL_KEYWORDS
            }
            
            # Filter out external/imported symbols
            unqualified_local = {
                name for name in unqualified_calls
                if name not in COMMON_EXTERNAL_CALLS and name not in file_imported_symbols
            }
            
            # ✅ RESOLUTION STRATEGY:
            # 1. Try Qualified Calls: ONLY this/self.method() → same class method
            # 2. Try Unqualified in Same Class: method() inside ClassName
            # 3. Try Global Unqualified: method() anywhere (if unique)
            
            # 1. QUALIFIED CALLS: ONLY this/self receiver (safe, type-known)
            # Skip other receivers like selector.execute() - no type info available
            for receiver, method_name in qualified_calls:
                # ONLY match this/self (we know the type = current class)
                if receiver.lower() not in ('this', 'self'):
                    # Unknown receiver type - cannot reliably match without type inference
                    # Example: selector.execute() - is selector a DALResult? ServiceHandler? Unknown!
                    continue
                
                # this.method() or self.method() → look in same class
                if caller_class and caller_class in class_funcs_map:
                    if method_name in class_funcs_map[caller_class]:
                        callee_id = class_funcs_map[caller_class][method_name]
                        
                        if caller_id == callee_id:
                            continue
                        
                        pair = (caller_id, callee_id)
                        if pair in inserted_pairs:
                            continue
                        
                        function_calls_batch.append(
                            (project_id, caller_id, callee_id, 'qualified_call')
                        )
                        inserted_pairs.add(pair)
                        dependencies_found += 1
            
            # 2. UNQUALIFIED CALLS: foo()
            for called_name in unqualified_local:
                callee_candidates = func_name_list.get(called_name, [])
                
                if not callee_candidates:
                    continue
                
                # Priority: Same class > Single match > Skip
                same_class_candidates = [c for c in callee_candidates if c['class'] == caller_class]
                
                if same_class_candidates:
                    # Prefer same class
                    callee_id = same_class_candidates[0]['id']
                elif len(callee_candidates) == 1:
                    # Only one function with this name globally → use it
                    callee_id = callee_candidates[0]['id']
                else:
                    # Multiple candidates, ambiguous → skip
                    logger.debug(
                        f"[Project {project_id}] Ambiguous call '{called_name}' from "
                        f"{caller_class}.{caller['function_name']} - "
                        f"multiple targets found. Skipping."
                    )
                    continue
                
                if caller_id == callee_id:
                    continue
                
                pair = (caller_id, callee_id)
                if pair in inserted_pairs:
                    continue
                
                function_calls_batch.append(
                    (project_id, caller_id, callee_id, 'unqualified_call')
                )
                inserted_pairs.add(pair)
                dependencies_found += 1
            
            # ✅ OPTIMIZATION 3: Update progress during dependency detection
            if task_id and total_funcs > 0:
                progress_percent = (idx + 1) / total_funcs
                dep_progress = 82 + int(progress_percent * 18)  # 82%-100% range
                progress_tracker.update(
                    task_id,
                    progress=dep_progress,
                    step='Fonksiyon çağrıları tespit ediliyor...',
                    detail=f'Bağımlılık analizi: {idx+1}/{total_funcs} fonksiyon ({int(progress_percent*100)}%)'
                )
        
        # ✅ OPTIMIZATION 2: Batch insert all at once (single transaction)
        if function_calls_batch:
            try:
                db.execute_many(
                    '''INSERT INTO function_calls 
                    (project_id, caller_function_id, callee_function_id, call_type)
                    VALUES (?, ?, ?, ?)''',
                    function_calls_batch
                )
                logger.debug(f"[Project {project_id}] Batch inserted {len(function_calls_batch)} function calls")
            except Exception as e:
                logger.warning(f"[Project {project_id}] Batch insert failed: {e}, falling back to individual inserts")
                for insert_data in function_calls_batch:
                    db.execute_insert(
                        '''INSERT INTO function_calls 
                        (project_id, caller_function_id, callee_function_id, call_type)
                        VALUES (?, ?, ?, ?)''',
                        insert_data
                    )
        
        log_analysis(project_id, "Analysis complete", 
                    functions=len(all_functions), 
                    dependencies=dependencies_found)
        if task_id:
            progress_tracker.complete(
                task_id,
                success=True,
                message=(
                    f'Analiz tamamlandı: {len(all_functions)} fonksiyon, '
                    f'{dependencies_found} bağımlılık'
                )
            )
        
        logger.info(f"Analysis completed for project {project_id}: {len(all_functions)} functions, {dependencies_found} dependencies")
        
        return jsonify({
            'message': 'Project analyzed',
            'functions_found': len(all_functions),
            'entry_points_found': len(all_entry_points),
            'files_skipped_unsupported': skipped_unsupported,
            'files_skipped_failed': skipped_with_error
        }), 200
    
    except Exception as e:
        if task_id:
            progress_tracker.complete(task_id, success=False, message=f'Analiz hatası: {e}')
        log_error(f"analyze_project (project: {project_id})", e)
        return jsonify({'error': str(e)}), 500

def _generate_ai_summary_recursive(function_id, client, visited=None, depth=0, task_id=None, total_deps=0, processed=0, temperature=None, top_p=None, max_tokens=None, track_progress=True):
    """Recursively generate AI summaries for function and its dependencies
    
    Args:
        function_id: Function ID to analyze
        client: LMStudioClient instance
        visited: Set of already processed function IDs (prevents infinite recursion)
        depth: Current recursion depth (limit to prevent stack overflow)
        task_id: Optional task ID for progress tracking
        total_deps: Total number of dependencies to process
        processed: Number of dependencies already processed
        temperature: Model temperature for AI
        top_p: Top-p sampling parameter
        max_tokens: Maximum tokens in response
        track_progress: Whether this call should update numeric progress percentage
    
    Returns:
        tuple: (str: Generated AI summary, int: updated processed count)
    """
    MAX_DEPTH = 3  # Limit recursion depth to prevent deep call chains
    
    if visited is None:
        visited = set()
    
    if function_id in visited or depth > MAX_DEPTH:
        return None, processed
    
    visited.add(function_id)
    
    # Get function details
    row = db.execute_query(
        'SELECT f.*, s.content FROM functions f JOIN source_files s ON f.file_id = s.id WHERE f.id = ?',
        (function_id,)
    )
    
    if not row:
        logger.warning(f"Function {function_id} not found")
        return None, processed
    
    func = dict(row[0])
    
    # Check if summary already exists
    if func.get('ai_summary') and func['ai_summary'].strip() and not func['ai_summary'].startswith('⚠️'):
        logger.debug(f"Function {function_id} ({func['function_name']}) already has summary, skipping")
        if task_id:
            processed += 1
            if track_progress:
                progress = int((processed / max(total_deps, 1)) * 100)
                progress_tracker.update(
                    task_id,
                    progress=progress,
                    detail=f"✓ Atlandı (özet var): {func['function_name']}"
                )
            else:
                progress_tracker.update(
                    task_id,
                    detail=f"✓ Atlandı (özet var): {func['function_name']}"
                )
        return func['ai_summary'], processed
    
    # Get called functions (dependencies)
    called_rows = db.execute_query(
        '''SELECT f2.id, f2.function_name, f2.class_name, f2.ai_summary
           FROM function_calls fc
           JOIN functions f2 ON fc.callee_function_id = f2.id
           WHERE fc.caller_function_id = ?''',
        (function_id,)
    )
    
    # Recursively generate summaries for dependencies that don't have summaries yet
    dependency_summaries = []
    for dep_row in called_rows:
        dep = dict(dep_row)
        dep_id = dep['id']
        dep_name = dep['function_name']
        dep_class = dep.get('class_name')
        dep_summary = dep.get('ai_summary')
        
        qualified_name = f"{dep_class}.{dep_name}" if dep_class else dep_name
        
        # If dependency doesn't have summary, generate it recursively
        if not dep_summary or not dep_summary.strip() or dep_summary.startswith('⚠️') or dep_summary.startswith('Error:'):
            logger.info(f"Dependency {qualified_name} (ID: {dep_id}) has no summary, generating recursively...")
            if task_id:
                progress_tracker.update(
                    task_id,
                    step=f"Alt fonksiyon özeti üretiliyor: {qualified_name}",
                    detail=f"🔄 {qualified_name} (seviye {depth+1})"
                )
            dep_summary, processed = _generate_ai_summary_recursive(
                dep_id,
                client,
                visited,
                depth + 1,
                task_id,
                total_deps,
                processed,
                temperature,
                top_p,
                max_tokens,
                track_progress
            )
        
        if dep_summary:
            dependency_summaries.append({
                'name': qualified_name,
                'summary': dep_summary
            })
    
    # Extract function code
    content = func['content']
    lines = content.split('\n')
    start_line = max(0, (func.get('start_line') or 1) - 1)
    end_line = min(len(lines), func.get('end_line') or len(lines))
    func_code = '\n'.join(lines[start_line:end_line])
    
    qualified_func_name = f"{func.get('class_name')}.{func['function_name']}" if func.get('class_name') else func['function_name']
    log_ai_call(function_id, f"Generating summary for {qualified_func_name}", code_lines=end_line-start_line, dependencies=len(dependency_summaries))
    
    if task_id:
        progress_tracker.set_metrics(
            task_id,
            total_functions=max(total_deps, 1),
            completed_functions=processed,
            active_thread=threading.current_thread().name,
        )
        progress_tracker.update(
            task_id,
            step=f"LMStudio'ya gönderiliyor: {qualified_func_name}",
            detail=f"🤖 AI özeti üretiliyor: {qualified_func_name} ({len(dependency_summaries)} bağımlılık)"
        )
    
    # Generate AI summary with dependency context
    summary = client.analyze_function(func_code, func['signature'], dependency_summaries, 
                                     temperature=temperature, top_p=top_p, max_tokens=max_tokens)
    _accumulate_ai_metrics(task_id, getattr(client, 'last_call_stats', None))
    log_ai_call(function_id, "AI summary received", summary_length=len(summary))
    
    if _is_ai_error_response(summary):
        logger.warning(
            f"AI summary not saved for function {function_id} ({qualified_func_name}) due to AI error response: {summary[:120]}"
        )
        processed += 1
        if task_id:
            progress_tracker.set_metrics(
                task_id,
                total_functions=max(total_deps, 1),
                completed_functions=processed,
                active_thread=threading.current_thread().name,
            )
            if track_progress:
                progress = int((processed / max(total_deps, 1)) * 100)
                progress_tracker.update(
                    task_id,
                    progress=progress,
                    detail=f"⚠️ Hata alındı, kaydedilmedi: {qualified_func_name}"
                )
            else:
                progress_tracker.update(
                    task_id,
                    detail=f"⚠️ Hata alındı, kaydedilmedi: {qualified_func_name}"
                )
        return None, processed

    # Save only valid summaries
    db.execute_update(
        'UPDATE functions SET ai_summary = ? WHERE id = ?',
        (summary, function_id)
    )
    
    processed += 1
    if task_id:
        progress_tracker.set_metrics(
            task_id,
            total_functions=max(total_deps, 1),
            completed_functions=processed,
            active_thread=threading.current_thread().name,
        )
        if track_progress:
            progress = int((processed / max(total_deps, 1)) * 100)
            progress_tracker.update(
                task_id,
                progress=progress,
                detail=f"✓ Tamamlandı: {qualified_func_name} ({len(summary)} karakter)"
            )
        else:
            progress_tracker.update(
                task_id,
                detail=f"✓ Tamamlandı: {qualified_func_name} ({len(summary)} karakter)"
            )
    
    logger.info(f"AI summary generated and saved for function {function_id} ({qualified_func_name})")
    return summary, processed


@bp.route('/function/<int:function_id>/ai-summary', methods=['POST'])
def get_ai_summary(function_id):
    """Get AI summary for function (with recursive dependency summary generation)"""
    task_id = request.args.get('task_id')
    
    try:
        logger.info(f"Requesting AI summary for function {function_id}")
        
        if task_id:
            progress_tracker.start_task(task_id, total_steps=100)
            progress_tracker.update(
                task_id,
                progress=5,
                step='Bağlantı kontrol ediliyor...',
                detail='LMStudio bağlantısı test ediliyor'
            )
        
        # Check LMStudio connection first
        user = get_user_from_session()
        client = LMStudioClient(user_id=user['id'] if user else None)
        connection_status = client.test_connection()
        
        if connection_status['status'] != 'connected':
            # LMStudio not available - return error immediately without timeout
            summary = (
                f"⚠️ AI Analiz Hatası: {connection_status['message']}\n\n"
                f"LMStudio sunucusu çalışmıyor. Lütfen LMStudio'yu başlatmaya çalışın ({client.api_url})"
            )
            log_ai_call(function_id, "LMStudio not connected", error=connection_status['message'])
            
            if task_id:
                progress_tracker.complete(
                    task_id,
                    success=False,
                    message=f"LMStudio bağlantı hatası: {connection_status['message']}"
                )
            
            # Get function name for response
            row = db.execute_query(
                'SELECT function_name FROM functions WHERE id = ?',
                (function_id,)
            )
            func_name = dict(row[0])['function_name'] if row else 'Unknown'
            
            return jsonify({
                'function_id': function_id,
                'function_name': func_name,
                'summary': summary,
                'saved': False
            }), 503
        
        if task_id:
            progress_tracker.update(
                task_id,
                progress=10,
                step='Bağımlılıklar kontrol ediliyor...',
                detail='✓ LMStudio bağlantısı başarılı'
            )
        
        # Count total dependencies to process
        dep_count_rows = db.execute_query(
            '''SELECT COUNT(DISTINCT fc.callee_function_id) as cnt
               FROM function_calls fc
               WHERE fc.caller_function_id = ?''',
            (function_id,)
        )
        total_deps = dict(dep_count_rows[0])['cnt'] + 1 if dep_count_rows else 1  # +1 for main function
        
        if task_id:
            progress_tracker.update(
                task_id,
                progress=15,
                step='AI özeti üretiliyor...',
                detail=f'Toplam {total_deps} fonksiyon özetlenecek'
            )
            progress_tracker.set_metrics(
                task_id,
                total_functions=max(total_deps, 1),
                completed_functions=0,
                active_thread=threading.current_thread().name,
            )
        
        settings = _load_ai_runtime_settings()
        temperature = settings['temperature']
        top_p = settings['top_p']
        max_tokens = settings['max_tokens']
        
        # Generate summary recursively (will handle dependencies automatically)
        summary, _ = _generate_ai_summary_recursive(function_id, client, task_id=task_id, total_deps=total_deps,
                                                   temperature=temperature, top_p=top_p, max_tokens=max_tokens)
        
        if not summary:
            # Distinguish missing function from failed AI generation
            row = db.execute_query(
                'SELECT function_name FROM functions WHERE id = ?',
                (function_id,)
            )
            if not row:
                if task_id:
                    progress_tracker.complete(task_id, success=False, message='Fonksiyon bulunamadı')
                return jsonify({'error': 'Function not found'}), 404

            if task_id:
                progress_tracker.complete(task_id, success=False, message='AI yanıtı geçersiz olduğu için kaydedilmedi')
            return jsonify({'error': 'AI response was invalid and not saved'}), 502
        
        # Get function name for response
        row = db.execute_query(
            'SELECT function_name FROM functions WHERE id = ?',
            (function_id,)
        )
        func_name = dict(row[0])['function_name'] if row else 'Unknown'
        
        if task_id:
            progress_tracker.complete(
                task_id,
                success=True,
                message=f'AI özeti başarıyla oluşturuldu: {func_name}'
            )
        
        return jsonify({
            'function_id': function_id,
            'function_name': func_name,
            'summary': summary
        }), 200
    
    except Exception as e:
        log_error(f"get_ai_summary (function: {function_id})", e)
        if task_id:
            progress_tracker.complete(task_id, success=False, message=f'Hata: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/file/<int:file_id>', methods=['POST'])
def analyze_file_missing_functions(file_id):
    """Analyze all missing function summaries in a file"""
    try:
        task_id = request.args.get('task_id')

        # Get all functions in this file without summaries
        func_result = db.execute_query(
            '''SELECT f.id FROM functions f
               WHERE f.file_id = ? AND (
                   f.ai_summary IS NULL OR f.ai_summary = '' OR f.ai_summary LIKE '⚠️%' OR f.ai_summary LIKE 'Error:%'
               )
               ORDER BY f.id''',
            (file_id,)
        )
        
        if not func_result:
            return jsonify({
                'success': True,
                'message': 'Bu dosyanın tüm fonksiyonlarının özeti var',
                'functions_analyzed': 0,
                'task_id': task_id
            }), 200

        total_funcs = len(func_result)
        if task_id:
            progress_tracker.start_task(task_id, total_steps=100)
            progress_tracker.set_metrics(
                task_id,
                total_functions=total_funcs,
                completed_functions=0,
                active_thread=threading.current_thread().name,
            )
            progress_tracker.update(
                task_id,
                progress=5,
                step='Dosya analizi hazırlanıyor...',
                detail=f'Toplam {total_funcs} fonksiyon analiz edilecek'
            )
        
        # Create LMStudio client
        user = get_user_from_session()
        client = LMStudioClient(user_id=user['id'] if user else None)
        connection_status = client.test_connection()
        
        if connection_status['status'] != 'connected':
            if task_id:
                progress_tracker.complete(task_id, success=False, message=f"LMStudio bağlantı hatası: {connection_status['message']}")
            return jsonify({
                'success': False,
                'error': f"LMStudio bağlantı hatası: {connection_status['message']}"
            }), 503
        
        settings = _load_ai_runtime_settings()
        temperature = settings['temperature']
        top_p = settings['top_p']
        max_tokens = settings['max_tokens']
        
        # Analyze each function
        analyzed = 0
        for idx, func_row in enumerate(func_result):
            func_id = func_row[0]

            if task_id:
                progress_tracker.update(
                    task_id,
                    progress=min(95, 10 + int((idx / max(total_funcs, 1)) * 85)),
                    step=f'Fonksiyon analizi ({idx + 1}/{total_funcs})',
                    detail=f'Fonksiyon ID {func_id} analiz ediliyor'
                )
                progress_tracker.set_metrics(
                    task_id,
                    total_functions=total_funcs,
                    completed_functions=analyzed,
                    active_thread=threading.current_thread().name,
                )
            
            # Get total functions to set up progress tracking
            dep_count_rows = db.execute_query(
                '''SELECT COUNT(DISTINCT fc.callee_function_id) as cnt
                   FROM function_calls fc
                   WHERE fc.caller_function_id = ?''',
                (func_id,)
            )
            total_deps = dict(dep_count_rows[0])['cnt'] + 1 if dep_count_rows else 1
            
            # Generate summary
            summary, _ = _generate_ai_summary_recursive(
                func_id, client, 
                task_id=task_id,
                temperature=temperature, 
                top_p=top_p, 
                max_tokens=max_tokens,
                total_deps=total_deps,
                track_progress=False
            )
            
            if summary and not _is_ai_error_response(summary):
                analyzed += 1

            if task_id:
                progress_tracker.set_metrics(
                    task_id,
                    total_functions=total_funcs,
                    completed_functions=analyzed,
                    active_thread=threading.current_thread().name,
                )

        if task_id:
            progress_tracker.complete(task_id, success=True, message=f'Dosya analizi tamamlandı ({analyzed}/{total_funcs})')
        
        return jsonify({
            'success': True,
            'functions_analyzed': analyzed,
            'functions_total': total_funcs,
            'message': f'{analyzed} fonksiyon İncelendi',
            'task_id': task_id
        }), 200
    
    except Exception as e:
        log_error(f"analyze_file_missing_functions (file: {file_id})", e)
        task_id = request.args.get('task_id')
        if task_id:
            progress_tracker.complete(task_id, success=False, message=f'Hata: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/errors', methods=['GET'])
def list_error_summaries():
    """List functions whose AI summary starts with Error:"""
    try:
        project_id = request.args.get('project_id')

        query = '''SELECT f.id as function_id, f.function_name, f.class_name, f.ai_summary,
                          f.project_id, p.name as project_name, s.file_path
                   FROM functions f
                   LEFT JOIN projects p ON f.project_id = p.id
                   LEFT JOIN source_files s ON f.file_id = s.id
                   WHERE f.ai_summary LIKE 'Error:%' '''
        params = []

        if project_id:
            query += ' AND f.project_id = ? '
            params.append(project_id)

        query += ' ORDER BY f.project_id, s.file_path, f.id '

        rows = db.execute_query(query, params)
        items = []
        for row in rows:
            item = dict(row)
            class_name = item.get('class_name')
            fn_name = item.get('function_name')
            item['qualified_name'] = f"{class_name}.{fn_name}" if class_name else fn_name
            items.append(item)

        return jsonify({'total': len(items), 'items': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/errors/clear', methods=['POST'])
def clear_error_summaries():
    """Clear Error: summaries (set ai_summary to NULL)."""
    try:
        data = request.json or {}
        function_ids = data.get('function_ids')
        project_id = data.get('project_id')

        if function_ids:
            placeholders = ','.join(['?'] * len(function_ids))
            params = list(function_ids)
            query = f"UPDATE functions SET ai_summary = NULL WHERE id IN ({placeholders}) AND ai_summary LIKE 'Error:%'"
            cleared = db.execute_update(query, params)
        elif project_id:
            cleared = db.execute_update(
                "UPDATE functions SET ai_summary = NULL WHERE project_id = ? AND ai_summary LIKE 'Error:%'",
                [project_id]
            )
        else:
            cleared = db.execute_update(
                "UPDATE functions SET ai_summary = NULL WHERE ai_summary LIKE 'Error:%'"
            )

        return jsonify({'success': True, 'cleared': cleared}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/errors/reanalyze', methods=['POST'])
def reanalyze_error_summaries():
    """Re-analyze functions with Error: summaries recursively (including errored dependencies)."""
    task_id = request.args.get('task_id')
    try:
        data = request.json or {}
        function_ids = data.get('function_ids')
        project_id = data.get('project_id')

        if function_ids:
            placeholders = ','.join(['?'] * len(function_ids))
            rows = db.execute_query(
                f"SELECT id FROM functions WHERE id IN ({placeholders})",
                list(function_ids)
            )
        elif project_id:
            rows = db.execute_query(
                "SELECT id FROM functions WHERE project_id = ? AND ai_summary LIKE 'Error:%' ORDER BY id",
                [project_id]
            )
        else:
            rows = db.execute_query(
                "SELECT id FROM functions WHERE ai_summary LIKE 'Error:%' ORDER BY id"
            )

        targets = [dict(r)['id'] for r in rows]
        total = len(targets)

        if total == 0:
            return jsonify({'success': True, 'message': 'Yeniden analiz gerektiren Error özeti bulunamadı', 'total': 0}), 200

        if task_id:
            progress_tracker.start_task(task_id, total_steps=100)
            progress_tracker.set_metrics(
                task_id,
                total_functions=total,
                completed_functions=0,
                active_thread=threading.current_thread().name,
            )
            progress_tracker.update(task_id, progress=5, step='Error özetleri yeniden analiz ediliyor...', detail=f'{total} fonksiyon işlenecek')

        user = get_user_from_session()
        client = LMStudioClient(user_id=user['id'] if user else None)
        connection_status = client.test_connection()
        if connection_status['status'] != 'connected':
            if task_id:
                progress_tracker.complete(task_id, success=False, message=f"LMStudio bağlantı hatası: {connection_status['message']}")
            return jsonify({'success': False, 'error': connection_status['message']}), 503

        settings = _load_ai_runtime_settings()
        temperature = settings['temperature']
        top_p = settings['top_p']
        max_tokens = settings['max_tokens']

        completed = 0
        success_count = 0
        failed_count = 0

        for idx, function_id in enumerate(targets):
            if task_id:
                progress_tracker.update(
                    task_id,
                    progress=min(95, 10 + int((idx / max(total, 1)) * 85)),
                    step=f'Error özeti yeniden analiz ({idx + 1}/{total})',
                    detail=f'Fonksiyon ID {function_id}'
                )

            dep_count_rows = db.execute_query(
                '''SELECT COUNT(DISTINCT fc.callee_function_id) as cnt
                   FROM function_calls fc
                   WHERE fc.caller_function_id = ?''',
                (function_id,)
            )
            total_deps = dict(dep_count_rows[0])['cnt'] + 1 if dep_count_rows else 1

            summary, _ = _generate_ai_summary_recursive(
                function_id,
                client,
                task_id=task_id,
                total_deps=total_deps,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                track_progress=False
            )

            completed += 1
            if summary and not _is_ai_error_response(summary):
                success_count += 1
            else:
                failed_count += 1

            if task_id:
                progress_tracker.set_metrics(
                    task_id,
                    total_functions=total,
                    completed_functions=completed,
                    active_thread=threading.current_thread().name,
                )

        if task_id:
            progress_tracker.complete(
                task_id,
                success=True,
                message=f'Reanalyze tamamlandı ({success_count}/{total})'
            )

        return jsonify({
            'success': True,
            'total': total,
            'reanalyzed': success_count,
            'failed': failed_count,
            'task_id': task_id,
            'message': f'{success_count} fonksiyon başarıyla yeniden analiz edildi'
        }), 200
    except Exception as e:
        if task_id:
            progress_tracker.complete(task_id, success=False, message=f'Hata: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/function/<int:function_id>', methods=['GET'])
def get_function_details(function_id):
    """Get single function details including source code"""
    try:
        row = db.execute_query(
            '''SELECT f.id, f.function_name, f.function_type, f.signature, f.parameters, 
                      f.return_type, f.ai_summary, f.start_line, f.end_line, s.content, 
                      f.class_name
               FROM functions f 
               LEFT JOIN source_files s ON f.file_id = s.id 
               WHERE f.id = ?''',
            (function_id,)
        )
        
        if not row:
            return jsonify({'error': 'Function not found'}), 404
        
        func = dict(row[0])
        
        # Extract the exact function code block
        if func.get('content') and func.get('start_line') and func.get('end_line'):
            lines = func['content'].split('\n')
            start = max(0, func['start_line'] - 1)
            end = min(len(lines), func['end_line'])
            func['source_code'] = '\n'.join(lines[start:end])
        else:
            func['source_code'] = 'Kaynak kod bulunamadı veya ayrıştırılamadı.'
            
        # Don't send the entire file content back
        func.pop('content', None)
        
        # Parse parameters from JSON string
        if func['parameters']:
            try:
                func['parameters'] = json.loads(func['parameters'])
            except:
                func['parameters'] = func['parameters'].split(',')
        
        # Build qualified name for display
        qualified_name = func['function_name']
        if func.get('class_name'):
            qualified_name = f"{func['class_name']}.{func['function_name']}"
        func['qualified_name'] = qualified_name

        # Add call graph neighbors with qualified names
        called_rows = db.execute_query(
            '''SELECT f2.id, f2.function_name, f2.class_name
               FROM function_calls fc
               JOIN functions f2 ON fc.callee_function_id = f2.id
               WHERE fc.caller_function_id = ?''',
            (function_id,)
        )
        caller_rows = db.execute_query(
            '''SELECT f1.id, f1.function_name, f1.class_name
               FROM function_calls fc
               JOIN functions f1 ON fc.caller_function_id = f1.id
               WHERE fc.callee_function_id = ?''',
            (function_id,)
        )
        
        # Format with qualified names
        func['called_functions'] = [
            {
                'id': dict(row)['id'],
                'function_name': dict(row)['function_name'],
                'class_name': dict(row).get('class_name'),
                'qualified_name': f"{dict(row)['class_name']}.{dict(row)['function_name']}" 
                                if dict(row).get('class_name') 
                                else dict(row)['function_name']
            }
            for row in called_rows
        ]
        func['called_by_functions'] = [
            {
                'id': dict(row)['id'],
                'function_name': dict(row)['function_name'],
                'class_name': dict(row).get('class_name'),
                'qualified_name': f"{dict(row)['class_name']}.{dict(row)['function_name']}" 
                                if dict(row).get('class_name') 
                                else dict(row)['function_name']
            }
            for row in caller_rows
        ]
        
        return jsonify(func), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/function/<int:function_id>/summary', methods=['PUT'])
def update_function_summary(function_id):
    """Manually update function summary"""
    try:
        data = request.json
        if not data or 'summary' not in data:
            return jsonify({'error': 'No summary provided'}), 400
            
        summary = data['summary']
        
        db.execute_update(
            'UPDATE functions SET ai_summary = ? WHERE id = ?',
            (summary, function_id)
        )
        
        return jsonify({
            'message': 'Summary updated successfully',
            'function_id': function_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/project/<int:project_id>/functions', methods=['GET'])
def get_project_functions(project_id):
    """Get all functions in project"""
    try:
        rows = db.execute_query(
            '''SELECT f.id, f.function_name, f.function_type, f.start_line, f.end_line, f.ai_summary, 
                      f.class_name, f.package_name, s.file_path 
               FROM functions f 
               LEFT JOIN source_files s ON f.file_id = s.id 
               WHERE f.project_id = ?''',
            (project_id,)
        )
        functions = []
        for row in rows:
            func_dict = dict(row)
            # Add qualified name for disambiguation
            class_name = func_dict.get('class_name')
            func_name = func_dict['function_name']
            qualified_name = f"{class_name}.{func_name}" if class_name else func_name
            func_dict['qualified_name'] = qualified_name
            functions.append(func_dict)

        # Build caller/callee maps for function tab
        dep_rows = db.execute_query(
            '''SELECT fc.caller_function_id, fc.callee_function_id,
                      caller.function_name AS caller_name,
                      callee.function_name AS callee_name,
                      caller.class_name AS caller_class,
                      callee.class_name AS callee_class
               FROM function_calls fc
               JOIN functions caller ON caller.id = fc.caller_function_id
               JOIN functions callee ON callee.id = fc.callee_function_id
               WHERE fc.project_id = ?''',
            (project_id,)
        )

        called_map = {}
        caller_map = {}
        for dep in dep_rows:
            caller_id = dep['caller_function_id']
            callee_id = dep['callee_function_id']
            callee_name = dep['callee_name']
            caller_name = dep['caller_name']
            callee_class = dep['callee_class']
            caller_class = dep['caller_class']
            
            # Build qualified names
            callee_qualified = f"{callee_class}.{callee_name}" if callee_class else callee_name
            caller_qualified = f"{caller_class}.{caller_name}" if caller_class else caller_name
            
            called_map.setdefault(caller_id, []).append({
                'id': callee_id,
                'function_name': callee_name,
                'class_name': callee_class,
                'qualified_name': callee_qualified
            })
            caller_map.setdefault(callee_id, []).append({
                'id': caller_id,
                'function_name': caller_name,
                'class_name': caller_class,
                'qualified_name': caller_qualified
            })

        for func in functions:
            func_id = func['id']
            func['called_functions'] = called_map.get(func_id, [])
            func['called_by_functions'] = caller_map.get(func_id, [])

        return jsonify(functions), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/dependencies/<int:project_id>', methods=['GET'])
def get_dependencies(project_id):
    """Get function call dependencies"""
    try:
        rows = db.execute_query(
            '''SELECT fc.id, f1.function_name as caller, f2.function_name as callee
            FROM function_calls fc
            JOIN functions f1 ON fc.caller_function_id = f1.id
            JOIN functions f2 ON fc.callee_function_id = f2.id
            WHERE fc.project_id = ?''',
            (project_id,)
        )
        dependencies = [dict(row) for row in rows]
        return jsonify(dependencies), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
