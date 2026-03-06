from flask import Blueprint, request, jsonify
from backend.database import db
import json

bp = Blueprint('diagram', __name__, url_prefix='/api/diagram')

@bp.route('/project/<int:project_id>/', methods=['GET'])
def get_diagram_data(project_id):
    """Get diagram data (nodes and edges)"""
    try:
        # Get all functions with qualified names (include class_name for disambiguation)
        # REDUCED from 50 to 30 nodes to minimize memory usage
        func_rows = db.execute_query(
            '''SELECT id, function_name, function_type, file_id, ai_summary, class_name
            FROM functions WHERE project_id = ? AND function_name != 'if' LIMIT 30''',
            (project_id,)
        )
        
        # Get dependencies
        dep_rows = db.execute_query(
            '''SELECT caller_function_id, callee_function_id 
            FROM function_calls WHERE project_id = ?''',
            (project_id,)
        )
        
        # Build nodes
        nodes = []
        node_ids = set()  # Track which function IDs are in the diagram
        
        # Detect entry points (functions with no incoming calls)
        called_in = set()
        for dep_row in dep_rows:
            called_in.add(dep_row[1])  # callee_function_id
        
        entry_point_ids = set()
        for row in func_rows:
            func_id = row[0]
            node_ids.add(func_id)  # Add to node_ids set
            if func_id not in called_in:
                entry_point_ids.add(func_id)
        
        for row in func_rows:
            func_id = row[0]
            func_name = row[1]
            class_name = row[5]
            # Build qualified label: ClassName.functionName or just functionName
            qualified_label = f"{class_name}.{func_name}" if class_name else func_name
            is_entry = func_id in entry_point_ids
            
            nodes.append({
                'id': func_id,
                'label': qualified_label,
                'function_name': func_name,
                'class_name': class_name,
                'type': row[2],
                'summary': row[4] or 'No summary',
                'title': f"{qualified_label} ({row[2]})",
                'is_entry_point': is_entry
            })
        
        # Build edges - only include edges where both source and target exist in nodes
        edges = []
        for row in dep_rows:
            from_id = row[0]
            to_id = row[1]
            # Only add edge if both nodes exist in the diagram
            if from_id in node_ids and to_id in node_ids:
                edges.append({
                    'from': from_id,
                    'to': to_id
                })
        
        return jsonify({
            'nodes': nodes,
            'edges': edges,
           'project_id': project_id,
           'entry_points': list(entry_point_ids)
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
