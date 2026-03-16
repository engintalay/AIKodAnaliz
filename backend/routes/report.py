"""AI Summary Coverage Report Routes"""
from flask import Blueprint, jsonify
from backend.database import db
from backend.logger import logger
from backend.routes.analysis import _prepare_function_code_for_ai
import math

bp = Blueprint('report', __name__, url_prefix='/api/report')


def _estimate_text_tokens(text):
    if not text:
        return 0
    return int(math.ceil(len(text) / 4.0))


def _estimate_ai_input_tokens(func, dependency_summaries):
    func_code, _, code_mode = _prepare_function_code_for_ai(func)
    dep_block = []
    for dep in dependency_summaries or []:
        dep_name = dep.get('name') or ''
        dep_summary = dep.get('summary') or ''
        dep_block.append(f"{dep_name}: {dep_summary}")

    signature = func.get('signature') or ''
    estimated_payload = (
        f"SIGNATURE:\n{signature}\n\n"
        f"CODE_MODE:{code_mode}\n"
        f"CODE:\n{func_code}\n\n"
        f"DEPENDENCIES:\n" + '\n'.join(dep_block)
    )
    return _estimate_text_tokens(estimated_payload) + 180, code_mode

@bp.route('', methods=['GET'])
def get_ai_summary_report():
    """Generate AI summary coverage report with statistics"""
    try:
        # Get all projects
        projects_result = db.execute_query('SELECT id, name, description, upload_date, last_updated FROM projects ORDER BY name')
        
        if not projects_result:
            return jsonify({
                'statistics': {
                    'total': 0,
                    'with_summary': 0,
                    'without_summary': 0,
                    'coverage': '0.0%'
                },
                'projects': []
            }), 200
        
        # Get total statistics
        total_funcs = db.execute_query('SELECT COUNT(*) as cnt FROM functions')[0][0]
        with_summary = db.execute_query('SELECT COUNT(*) as cnt FROM functions WHERE ai_summary IS NOT NULL AND ai_summary != ""')[0][0]
        without_summary = total_funcs - with_summary
        coverage = (with_summary / total_funcs * 100) if total_funcs > 0 else 0
        
        # Process each project
        projects_data = []
        
        for proj in projects_result:
            project_id = proj[0]
            project_name = proj[1]
            project_desc = proj[2]
            upload_date = proj[3]
            last_updated = proj[4]
            
            # Get functions for this project
            func_result = db.execute_query('''
                  SELECT f.id, f.project_id, f.file_id, f.function_name, f.function_type,
                      f.class_name, f.package_name, f.signature, f.ai_summary,
                      s.file_name, s.id as file_id, s.content
                FROM functions f
                LEFT JOIN source_files s ON f.file_id = s.id
                WHERE f.project_id = ?
                ORDER BY s.file_name, f.function_name
            ''', [project_id])
            
            if not func_result:
                continue
            
            # Group functions by file
            files_dict = {}
            proj_with_summary = 0
            
            func_dicts = []
            for func in func_result:
                file_name = func[9] or 'Bilinmeyen'
                file_id = func[10]
                has_summary = bool(func[8])

                func_dict = {
                    'id': func[0],
                    'project_id': func[1],
                    'file_id': func[2],
                    'function_name': func[3],
                    'function_type': func[4],
                    'class_name': func[5],
                    'package_name': func[6],
                    'signature': func[7],
                    'ai_summary': func[8],
                    'file_name': file_name,
                    'content': func[11],
                }
                func_dicts.append(func_dict)
                
                if has_summary:
                    proj_with_summary += 1
                
                if file_name not in files_dict:
                    files_dict[file_name] = {
                        'file_id': file_id,
                        'total': 0,
                        'with_summary': 0,
                        'missing_functions': [],
                        'functions': []
                    }
                
                files_dict[file_name]['total'] += 1
                if has_summary:
                    files_dict[file_name]['with_summary'] += 1
                else:
                    # Track missing summaries
                    files_dict[file_name]['missing_functions'].append({
                        'function_id': func[0],
                        'name': func[3],
                        'qualified_name': f"{func[5]}.{func[3]}" if func[5] else func[3],
                        'type': func[4] or 'unknown'
                    })
                
                # Build qualified name
                qualified_name = func[3]
                if func[5]:
                    qualified_name = f"{func[5]}.{func[3]}"
                if func[6]:
                    qualified_name = f"{func[6]}.{qualified_name}"
                
                files_dict[file_name]['functions'].append({
                    'function_id': func[0],
                    'name': func[3],
                    'qualified_name': qualified_name,
                    'type': func[4] or 'unknown',
                    'has_summary': has_summary,
                    'class_name': func[5],
                    'package_name': func[6]
                })

            # Attach estimated AI token info per function using available summaries of called functions.
            dep_rows = db.execute_query(
                '''SELECT fc.caller_function_id, fc.callee_function_id,
                          callee.function_name AS callee_name,
                          callee.class_name AS callee_class,
                          callee.ai_summary AS callee_summary
                   FROM function_calls fc
                   JOIN functions callee ON callee.id = fc.callee_function_id
                   WHERE fc.project_id = ?''',
                [project_id]
            )
            called_map = {}
            for dep in dep_rows or []:
                caller_id = dep['caller_function_id']
                callee_name = dep['callee_name']
                callee_class = dep['callee_class']
                callee_summary = (dep['callee_summary'] or '').strip()
                if not callee_summary or callee_summary.startswith('⚠️') or callee_summary.startswith('Error:'):
                    continue
                called_map.setdefault(caller_id, []).append({
                    'name': f"{callee_class}.{callee_name}" if callee_class else callee_name,
                    'summary': callee_summary
                })

            token_by_id = {}
            mode_by_id = {}
            for func_dict in func_dicts:
                est_tokens, code_mode = _estimate_ai_input_tokens(
                    func_dict,
                    called_map.get(func_dict['id'], [])
                )
                token_by_id[func_dict['id']] = est_tokens
                mode_by_id[func_dict['id']] = code_mode

            for file_data in files_dict.values():
                for item in file_data['missing_functions']:
                    item['ai_estimated_input_tokens'] = token_by_id.get(item['function_id'], 0)
                    item['ai_code_mode'] = mode_by_id.get(item['function_id'], 'full')
                for item in file_data['functions']:
                    item['ai_estimated_input_tokens'] = token_by_id.get(item['function_id'], 0)
                    item['ai_code_mode'] = mode_by_id.get(item['function_id'], 'full')
            
            proj_total = len(func_result)
            proj_without = proj_total - proj_with_summary
            proj_coverage = (proj_with_summary / proj_total * 100) if proj_total > 0 else 0
            
            # Build project data
            project_obj = {
                'id': project_id,
                'name': project_name,
                'description': project_desc,
                'upload_date': upload_date,
                'last_updated': last_updated,
                'statistics': {
                    'total': proj_total,
                    'with_summary': proj_with_summary,
                    'without_summary': proj_without,
                    'coverage': f"{proj_coverage:.1f}%"
                },
                'files': files_dict
            }
            
            projects_data.append(project_obj)
        
        return jsonify({
            'statistics': {
                'total': total_funcs,
                'with_summary': with_summary,
                'without_summary': without_summary,
                'coverage': f"{coverage:.1f}%"
            },
            'projects': projects_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return jsonify({'error': str(e)}), 500
