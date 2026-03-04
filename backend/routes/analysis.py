from flask import Blueprint, request, jsonify
from backend.database import db
from backend.analyzers.advanced_analyzer import AdvancedCodeAnalyzer
from backend.lmstudio_client import LMStudioClient
from backend.progress_tracker import progress_tracker
from backend.logger import logger, log_analysis, log_ai_call, log_error
import json
import uuid
import re

CALL_NAME_PATTERN = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
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
        client = LMStudioClient()
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
            
            # Store functions
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
            
            # Store entry points
            for entry in result.get('entry_points', []):
                entry_point_id = db.execute_insert(
                    '''INSERT INTO entry_points 
                    (project_id, function_id, entry_type)
                    VALUES (?, ?, ?)''',
                    (project_id, all_functions[-1] if all_functions else None, 'main')
                )
                
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

        # Rebuild dependencies for this project on each analysis run.
        db.execute_update('DELETE FROM function_calls WHERE project_id = ?', (project_id,))
        
        # Get all functions with their file contents again to scan for calls
        funcs_query = db.execute_query(
            '''SELECT f.id, f.file_id, f.function_name, f.start_line, f.end_line, s.content, s.language
               FROM functions f 
               JOIN source_files s ON f.file_id = s.id 
               WHERE f.project_id = ?''',
            (project_id,)
        )
        
        funcs_data = [dict(row) for row in funcs_query]
        dependencies_found = 0
        total_funcs = len(funcs_data)
        
        # ✅ OPTIMIZATION 1: Build hash table for O(1) lookup instead of O(n²) nested loop
        func_name_map = {func['function_name']: func['id'] for func in funcs_data}
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

            # Find all call-like names: foo(...)
            called_names = {
                match.group(1)
                for match in CALL_NAME_PATTERN.finditer(caller_code)
                if match.group(1) not in CALL_KEYWORDS
            }
            local_called_names = {
                name for name in called_names
                if name not in COMMON_EXTERNAL_CALLS and name not in file_imported_symbols
            }
            
            # ✅ OPTIMIZATION 1: Only iterate through found calls (not all functions)
            for called_name in local_called_names:
                if called_name in func_name_map:
                    callee_id = func_name_map[called_name]
                    
                    # Basic check: Don't link function to itself
                    if caller['id'] == callee_id:
                        continue
                    
                    pair = (caller['id'], callee_id)
                    if pair in inserted_pairs:
                        continue
                    
                    # Collect for batch insert
                    function_calls_batch.append(
                        (project_id, caller['id'], callee_id, 'direct_call')
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

@bp.route('/function/<int:function_id>/ai-summary', methods=['POST'])
def get_ai_summary(function_id):
    """Get AI summary for function"""
    try:
        logger.info(f"Requesting AI summary for function {function_id}")
        
        # Get function details
        row = db.execute_query(
            'SELECT f.*, s.content FROM functions f JOIN source_files s ON f.file_id = s.id WHERE f.id = ?',
            (function_id,)
        )
        
        if not row:
            logger.warning(f"Function {function_id} not found")
            return jsonify({'error': 'Function not found'}), 404
        
        func = dict(row[0])
        
        # Extract function code
        content = func['content']
        lines = content.split('\n')
        start_line = max(0, (func.get('start_line') or 1) - 1)
        end_line = min(len(lines), func.get('end_line') or len(lines))
        func_code = '\n'.join(lines[start_line:end_line])
        
        log_ai_call(function_id, "Extracted function code", code_lines=end_line-start_line)
        
        # Check LMStudio connection first
        client = LMStudioClient()
        connection_status = client.test_connection()
        
        if connection_status['status'] != 'connected':
            # LMStudio not available - return error immediately without timeout
            summary = f"⚠️ AI Analiz Hatası: {connection_status['message']}\n\nLMStudio sunucusu çalışmıyor. Lütfen LMStudio'yu başlatmaya çalışın (http://localhost:1234)"
            log_ai_call(function_id, "LMStudio not connected", error=connection_status['message'])
        else:
            # Get AI summary
            log_ai_call(function_id, "Calling LMStudio API", signature=func['signature'])
            summary = client.analyze_function(func_code, func['signature'])
            log_ai_call(function_id, "AI summary received", summary_length=len(summary))
        
        # Save summary
        db.execute_update(
            'UPDATE functions SET ai_summary = ? WHERE id = ?',
            (summary, function_id)
        )
        
        logger.info(f"AI summary generated and saved for function {function_id}")
        
        return jsonify({
            'function_id': function_id,
            'function_name': func['function_name'],
            'summary': summary
        }), 200
    
    except Exception as e:
        log_error(f"get_ai_summary (function: {function_id})", e)
        return jsonify({'error': str(e)}), 500

@bp.route('/function/<int:function_id>', methods=['GET'])
def get_function_details(function_id):
    """Get single function details including source code"""
    try:
        row = db.execute_query(
            '''SELECT f.id, f.function_name, f.function_type, f.signature, f.parameters, 
                      f.return_type, f.ai_summary, f.start_line, f.end_line, s.content 
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

        # Add call graph neighbors for function detail view
        called_rows = db.execute_query(
            '''SELECT f2.id, f2.function_name
               FROM function_calls fc
               JOIN functions f2 ON fc.callee_function_id = f2.id
               WHERE fc.caller_function_id = ?''',
            (function_id,)
        )
        caller_rows = db.execute_query(
            '''SELECT f1.id, f1.function_name
               FROM function_calls fc
               JOIN functions f1 ON fc.caller_function_id = f1.id
               WHERE fc.callee_function_id = ?''',
            (function_id,)
        )
        func['called_functions'] = [dict(row) for row in called_rows]
        func['called_by_functions'] = [dict(row) for row in caller_rows]
        
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
        functions = [dict(row) for row in rows]

        # Build caller/callee maps for function tab
        dep_rows = db.execute_query(
            '''SELECT fc.caller_function_id, fc.callee_function_id,
                      caller.function_name AS caller_name,
                      callee.function_name AS callee_name
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
            called_map.setdefault(caller_id, []).append({
                'id': callee_id,
                'function_name': dep['callee_name']
            })
            caller_map.setdefault(callee_id, []).append({
                'id': caller_id,
                'function_name': dep['caller_name']
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
