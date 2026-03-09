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
        
        # Get entry points from database
        entry_rows = db.execute_query(
            '''SELECT function_id, entry_type FROM entry_points WHERE project_id = ?''',
            (project_id,)
        )
        
        # Build entry point set
        entry_point_ids = {row[0] for row in entry_rows}
        
        # Get dependencies
        dep_rows = db.execute_query(
            '''SELECT caller_function_id, callee_function_id 
            FROM function_calls WHERE project_id = ?''',
            (project_id,)
        )
        
        # Build nodes
        nodes = []
        node_ids = set()  # Track which function IDs are in the diagram
        
        for row in func_rows:
            func_id = row[0]
            func_name = row[1]
            class_name = row[5]
            node_ids.add(func_id)
            
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

@bp.route('/function/<int:function_id>/callgraph', methods=['GET'])
def get_function_callgraph(function_id):
    """Get a highly focused call graph for a single function (1 level up, 2 levels down)"""
    try:
        # Step 1: Find the target function and its project_id
        target_res = db.execute_query('SELECT id, project_id FROM functions WHERE id = ?', (function_id,))
        if not target_res:
            return jsonify({'error': 'Function not found'}), 404
            
        project_id = target_res[0][1]
        
        # We need to collect valid node IDs before fetching full nodes
        valid_node_ids = {function_id}
        edges = []
        
        # Get Level 1 Up (Callers of the target function)
        callers = db.execute_query(
            '''SELECT caller_function_id, callee_function_id 
               FROM function_calls 
               WHERE callee_function_id = ? AND project_id = ?''',
            (function_id, project_id)
        )
        for row in callers:
            valid_node_ids.add(row[0])
            edges.append({'from': row[0], 'to': row[1]})
            
        # Get Level 1 Down (Callees of the target function)
        callees = db.execute_query(
            '''SELECT caller_function_id, callee_function_id 
               FROM function_calls 
               WHERE caller_function_id = ? AND project_id = ?''',
            (function_id, project_id)
        )
        l1_down_ids = set()
        for row in callees:
            valid_node_ids.add(row[1])
            l1_down_ids.add(row[1])
            edges.append({'from': row[0], 'to': row[1]})
            
        # Get Level 2 Down (Callees of the Level 1 Callees)
        if l1_down_ids:
            placeholders = ','.join(['?'] * len(l1_down_ids))
            query = f'''SELECT caller_function_id, callee_function_id 
                       FROM function_calls 
                       WHERE caller_function_id IN ({placeholders}) AND project_id = ?'''
            params = list(l1_down_ids) + [project_id]
            l2_callees = db.execute_query(query, params)
            for row in l2_callees:
                valid_node_ids.add(row[1])
                # Ensure we don't duplicate edges if already added
                edge_dict = {'from': row[0], 'to': row[1]}
                if edge_dict not in edges:
                    edges.append(edge_dict)

        # Step 2: Fetch full node details for all collected IDs
        nodes = []
        if valid_node_ids:
            placeholders = ','.join(['?'] * len(valid_node_ids))
            func_query = f'''SELECT id, function_name, function_type, class_name, ai_summary
                             FROM functions 
                             WHERE id IN ({placeholders})'''
            func_rows = db.execute_query(func_query, list(valid_node_ids))
            
            for row in func_rows:
                f_id = row[0]
                f_name = row[1]
                f_type = row[2]
                c_name = row[3]
                summary = row[4]
                
                qualified_label = f"{c_name}.{f_name}" if c_name else f_name
                
                nodes.append({
                    'id': f_id,
                    'label': qualified_label,
                    'function_name': f_name,
                    'class_name': c_name,
                    'type': f_type,
                    'summary': summary or 'No summary',
                    'title': f"{qualified_label} ({f_type})",
                    'is_entry_point': False, # Not strictly tracked for focal graphs
                    'is_target_node': f_id == function_id # Important for UI highlighting
                })
                
        return jsonify({
            'nodes': nodes,
            'edges': edges,
            'target_node_id': function_id,
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
