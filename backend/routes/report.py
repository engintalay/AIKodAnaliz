"""AI Summary Coverage Report Routes"""
from flask import Blueprint, jsonify
from backend.database import db
from backend.logger import logger

bp = Blueprint('report', __name__, url_prefix='/api/report')

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
                SELECT f.id, f.function_name, f.function_type, f.class_name, 
                       f.package_name, f.ai_summary, s.file_name
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
            
            for func in func_result:
                file_name = func[6] or 'Bilinmeyen'
                has_summary = bool(func[5])
                
                if has_summary:
                    proj_with_summary += 1
                
                if file_name not in files_dict:
                    files_dict[file_name] = {
                        'total': 0,
                        'with_summary': 0,
                        'functions': []
                    }
                
                files_dict[file_name]['total'] += 1
                if has_summary:
                    files_dict[file_name]['with_summary'] += 1
                
                # Build qualified name
                qualified_name = func[1]  # function_name
                if func[3]:  # class_name
                    qualified_name = f"{func[3]}.{func[1]}"
                if func[4]:  # package_name
                    qualified_name = f"{func[4]}.{qualified_name}"
                
                files_dict[file_name]['functions'].append({
                    'name': func[1],
                    'qualified_name': qualified_name,
                    'type': func[2] or 'unknown',
                    'has_summary': has_summary,
                    'class_name': func[3],
                    'package_name': func[4]
                })
            
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
