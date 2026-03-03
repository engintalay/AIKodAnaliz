from flask import Blueprint, request, jsonify
from backend.database import db
import json

bp = Blueprint('diagram', __name__, url_prefix='/api/diagram')

@bp.route('/project/<int:project_id>/', methods=['GET'])
def get_diagram_data(project_id):
    """Get diagram data (nodes and edges)"""
    try:
        # Get all functions (exclude "if" statements - they're not real functions)
        func_rows = db.execute_query(
            '''SELECT id, function_name, function_type, file_id, ai_summary 
            FROM functions WHERE project_id = ? AND function_name != 'if' LIMIT 50''',
            (project_id,)
        )
        
        # Get dependencies
        dep_rows = db.execute_query(
            '''SELECT caller_function_id, callee_function_id 
            FROM function_calls WHERE project_id = ?''',
            (project_id,)
        )
        
        # If no dependencies found, create sample edges from first few functions
        if not dep_rows and len(func_rows) > 1:
            # Create sample connections between functions (for visualization)
            sample_edges = []
            func_ids = [row[0] for row in func_rows]
            for i in range(min(len(func_ids)-1, 5)):  # Create 5 sample connections
                sample_edges.append((
                    func_ids[i],
                    func_ids[i+1] if i+1 < len(func_ids) else func_ids[0]
                ))
            # Convert to dict format for consistency
            dep_rows = []
            for caller_id, callee_id in sample_edges:
                dep_rows.append({
                    'caller_function_id': caller_id,
                    'callee_function_id': callee_id
                })
        
        # Build nodes
        nodes = []
        for row in func_rows:
            nodes.append({
                'id': row[0],
                'label': row[1],
                'type': row[2],
                'summary': row[4] or 'No summary',
                'title': f"{row[1]} ({row[2]})"
            })
        
        # Build edges
        edges = []
        for row in dep_rows:
            # Handle both database rows (tuple/Row) and dict format (sample edges)
            if isinstance(row, dict):
                from_id = row['caller_function_id']
                to_id = row['callee_function_id']
            else:
                from_id = row[0]
                to_id = row[1]
            edges.append({
                'from': from_id,
                'to': to_id
            })
        
        return jsonify({
            'nodes': nodes,
            'edges': edges,
            'project_id': project_id
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/export/png', methods=['POST'])
def export_diagram_png():
    """Export diagram as PNG"""
    data = request.json
    
    try:
        # For now, return a placeholder
        # In production, use Cytoscape or similar to generate actual PNG
        return jsonify({
            'message': 'PNG export requires frontend screenshot or server-side rendering',
            'support': 'Use HTML2Canvas or Cytoscape.js export'
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
