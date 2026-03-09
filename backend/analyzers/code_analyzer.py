import ast
import re
from typing import List, Dict, Tuple

try:
    import sqlparse
    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False

class CodeAnalyzer:
    """Multi-language code analyzer"""
    
    def __init__(self):
        self.language = None
        self.functions = []
        self.entry_points = []
        self.dependencies = []
    
    def analyze(self, file_path: str, content: str, language: str) -> Dict:
        """Analyze source code and extract metadata"""
        self.language = language.lower()
        self.content = content
        
        if self.language == "python":
            return self._analyze_python(file_path, content)
        elif self.language in ["java", "javascript", "typescript"]:
            return self._analyze_java_like(file_path, content)
        elif self.language in ["php"]:
            return self._analyze_php(file_path, content)
        elif self.language == "sql":
            return self._analyze_sql(file_path, content)
        elif self.language in ["css", "html"]:
            return self._analyze_markup(content)
        else:
            return self._analyze_generic(content)
    
    def _analyze_python(self, file_path: str, content: str) -> Dict:
        """Analyze Python code"""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {'error': str(e), 'functions': [], 'entry_points': []}
        
        functions = []
        entry_points = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'type': 'function',
                    'start_line': node.lineno,
                    'end_line': node.end_lineno or node.lineno,
                    'parameters': [arg.arg for arg in node.args.args],
                    'return_type': self._extract_return_type(node),
                    'signature': self._get_python_signature(node),
                    'is_entry': node.name in ['main', '__main__', 'run'],
                    'class_name': getattr(node, 'parent_class_name', None),
                    'package_name': file_path.replace('/', '.').replace('\\', '.').replace('.py', '') if file_path else None
                }
                functions.append(func_info)
                if func_info['is_entry']:
                    entry_points.append(func_info)
            
            elif isinstance(node, ast.ClassDef):
                func_info = {
                    'name': node.name,
                    'type': 'class',
                    'start_line': node.lineno,
                    'end_line': node.end_lineno or node.lineno,
                    'parameters': [],
                    'return_type': None,
                    'signature': f"class {node.name}",
                    'is_entry': False,
                    'class_name': None,
                    'package_name': file_path.replace('/', '.').replace('\\', '.').replace('.py', '') if file_path else None
                }
                functions.append(func_info)
                
                # Tag methods with their parent class
                for child in node.body:
                    if isinstance(child, ast.FunctionDef):
                        child.parent_class_name = node.name
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': self._extract_imports_python(tree)
        }
    
    def _analyze_java_like(self, file_path: str, content: str) -> Dict:
        """Analyze Java/JavaScript/TypeScript code"""
        functions = []
        entry_points = []
        
        # Package pattern
        package_match = re.search(r'package\s+([^;]+);', content)
        package_name = package_match.group(1).strip() if package_match else None
        
        # Function pattern for Java/JS/TS
        func_pattern = r'(?:public|private|protected|static|async)?\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+)?\s*[{:]'
        matches = re.finditer(func_pattern, content)
        
        # Class pattern
        classes = []
        class_pattern = r'(?:public|private|protected)?\s*(?:abstract)?\s*class\s+(\w+)'
        for m in re.finditer(class_pattern, content):
            classes.append({'name': m.group(1), 'start': m.start()})

        
        lines = content.split('\n')
        
        # Blacklist of keywords that are not functions
        keywords = {'if', 'else', 'for', 'while', 'do', 'switch', 'catch', 'try', 'finally', 'return'}
        
        for match in matches:
            func_name = match.group(1)
            
            if func_name in keywords:
                continue
                
            line_num = content[:match.start()].count('\n') + 1
            
            # Extract parameters
            params_match = re.search(r'\(([^)]*)\)', content[match.start():match.start()+200])
            params = []
            if params_match:
                params_str = params_match.group(1)
                params = [p.strip().split()[-1] for p in params_str.split(',') if p.strip()]
            
            # Find closest parent class
            current_class = None
            for cls in reversed(classes):
                if cls['start'] < match.start():
                    current_class = cls['name']
                    break
            
            func_info = {
                'name': func_name,
                'type': 'function' if func_name not in ['main', 'constructor'] else 'entry',
                'start_line': line_num,
                'end_line': self._find_block_end_line(content, match.start(), match.end(), line_num),
                'parameters': params,
                'return_type': 'void',  # Default
                'signature': content[match.start():match.end()].strip(),
                'is_entry': func_name in ['main', 'constructor', 'init'],
                'class_name': current_class,
                'package_name': package_name
            }
            functions.append(func_info)
            
            if func_info['is_entry']:
                entry_points.append(func_info)
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': self._extract_imports_generic(content)
        }
    
    def _analyze_php(self, file_path: str, content: str) -> Dict:
        """Analyze PHP code"""
        functions = []
        entry_points = []
        
        # PHP function pattern
        func_pattern = r'(?:public|private|protected)?\s*function\s+(\w+)\s*\(([^)]*)\)'
        matches = re.finditer(func_pattern, content)
        
        # Class and namespace pattern
        ns_match = re.search(r'namespace\s+([^;]+);', content)
        package_name = ns_match.group(1).strip() if ns_match else None
        
        classes = []
        class_pattern = r'class\s+(\w+)'
        for m in re.finditer(class_pattern, content):
            classes.append({'name': m.group(1), 'start': m.start()})
        
        for match in matches:
            func_name = match.group(1)
            params_str = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            
            # Parse parameters
            params = []
            for param in params_str.split(','):
                param = param.strip()
                if param:
                    params.append(param.split()[-1] if ' ' in param else param)
            
            # Find closest parent class
            current_class = None
            for cls in reversed(classes):
                if cls['start'] < match.start():
                    current_class = cls['name']
                    break
                    
            func_info = {
                'name': func_name,
                'type': 'function',
                'start_line': line_num,
                'end_line': self._find_block_end_line(content, match.start(), match.end(), line_num),
                'parameters': params,
                'return_type': 'mixed',
                'signature': match.group(0),
                'is_entry': func_name in ['main', 'index', 'run'],
                'class_name': current_class,
                'package_name': package_name
            }
            functions.append(func_info)
            
            if func_info['is_entry']:
                entry_points.append(func_info)
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': self._extract_imports_generic(content)
        }
    
    def _analyze_markup(self, content: str) -> Dict:
        """Analyze HTML/CSS"""
        return {
            'functions': [],
            'entry_points': [],
            'dependencies': []
        }
    
    def _analyze_generic(self, content: str) -> Dict:
        """Generic code analysis fallback"""
        functions = []
        
        # Try to find function-like patterns
        func_pattern = r'(?:def|function|func|fn)\s+(\w+)\s*\(([^)]*)\)'
        matches = re.finditer(func_pattern, content)
        
        for match in matches:
            func_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            func_info = {
                'name': func_name,
                'type': 'function',
                'start_line': line_num,
                'end_line': self._find_block_end_line(content, match.start(), match.end(), line_num),
                'parameters': match.group(2).split(','),
                'return_type': None,
                'signature': match.group(0),
                'is_entry': False
            }
            functions.append(func_info)
        
        return {
            'functions': functions,
            'entry_points': [],
            'dependencies': []
        }
    
    def _extract_return_type(self, node) -> str:
        """Extract return type from Python function"""
        if node.returns:
            return ast.unparse(node.returns)
        return None
    
    def _get_python_signature(self, node) -> str:
        """Get Python function signature"""
        args = [arg.arg for arg in node.args.args]
        return f"def {node.name}({', '.join(args)})"
    
    def _extract_imports_python(self, tree) -> List[str]:
        """Extract imports from Python AST"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(f"from {node.module}")
        return imports
    
    def _extract_imports_generic(self, content: str) -> List[str]:
        """Extract imports using regex"""
        imports = []
        import_pattern = r'^(?:import|from|require|include)\s+["\']?([^"\';\n]+)["\']?'
        for line in content.split('\n'):
            match = re.match(import_pattern, line.strip())
            if match:
                imports.append(match.group(1))
        return imports

    def _find_block_end_line(self, content: str, match_start: int, match_end: int, start_line: int) -> int:
        """Find end line of a function-like block by balancing braces from match position."""
        open_idx = content.find('{', match_end)

        if open_idx == -1:
            return start_line

        depth = 0
        in_single_quote = False
        in_double_quote = False
        escaped = False

        for i in range(open_idx, len(content)):
            ch = content[i]

            if escaped:
                escaped = False
                continue

            if ch == '\\':
                escaped = True
                continue

            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                continue

            if ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                continue

            if in_single_quote or in_double_quote:
                continue

            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return content[:i + 1].count('\n') + 1

        # Fallback if block is not balanced
        return content.count('\n') + 1

    def _analyze_sql(self, file_path: str, content: str) -> Dict:
        """Analyze SQL code using sqlparse"""
        if not SQLPARSE_AVAILABLE:
            return {
                'functions': [],
                'entry_points': [],
                'dependencies': [],
                'error': 'sqlparse not installed'
            }
        
        functions = []
        entry_points = []
        dependencies = []
        
        # Parse SQL statements
        statements = sqlparse.parse(content)
        
        for stmt in statements:
            stmt_type = stmt.get_type()
            tokens = list(stmt.flatten())
            
            # Extract CREATE PROCEDURE/FUNCTION
            if stmt_type == 'CREATE':
                # Check if it's a procedure or function
                stmt_str = str(stmt).upper()
                
                if 'PROCEDURE' in stmt_str or 'FUNCTION' in stmt_str:
                    # Extract name
                    name_match = re.search(r'(?:PROCEDURE|FUNCTION)\s+([\w.]+)', stmt_str, re.IGNORECASE)
                    if name_match:
                        obj_name = name_match.group(1)
                        obj_type = 'procedure' if 'PROCEDURE' in stmt_str else 'function'
                        
                        # Extract parameters
                        params_match = re.search(r'\(([^)]+)\)', str(stmt), re.IGNORECASE)
                        params = []
                        if params_match:
                            params_str = params_match.group(1)
                            # Simple parameter extraction
                            params = [p.strip().split()[0] for p in params_str.split(',') if p.strip()]
                        
                        line_num = content[:content.find(str(stmt))].count('\n') + 1 if str(stmt) in content else 1
                        
                        func_info = {
                            'name': obj_name,
                            'type': obj_type,
                            'start_line': line_num,
                            'end_line': line_num + str(stmt).count('\n'),
                            'parameters': params,
                            'return_type': None,
                            'signature': ' '.join(str(stmt).split()[:5]) + '...',
                            'is_entry': False,
                            'class_name': None,
                            'package_name': file_path
                        }
                        functions.append(func_info)
                
                # Extract CREATE VIEW
                elif 'VIEW' in stmt_str:
                    name_match = re.search(r'VIEW\s+([\w.]+)', stmt_str, re.IGNORECASE)
                    if name_match:
                        view_name = name_match.group(1)
                        line_num = content[:content.find(str(stmt))].count('\n') + 1 if str(stmt) in content else 1
                        
                        func_info = {
                            'name': view_name,
                            'type': 'view',
                            'start_line': line_num,
                            'end_line': line_num + str(stmt).count('\n'),
                            'parameters': [],
                            'return_type': None,
                            'signature': 'CREATE VIEW ' + view_name,
                            'is_entry': False,
                            'class_name': None,
                            'package_name': file_path
                        }
                        functions.append(func_info)
                
                # Extract CREATE TRIGGER
                elif 'TRIGGER' in stmt_str:
                    name_match = re.search(r'TRIGGER\s+([\w.]+)', stmt_str, re.IGNORECASE)
                    if name_match:
                        trigger_name = name_match.group(1)
                        line_num = content[:content.find(str(stmt))].count('\n') + 1 if str(stmt) in content else 1
                        
                        func_info = {
                            'name': trigger_name,
                            'type': 'trigger',
                            'start_line': line_num,
                            'end_line': line_num + str(stmt).count('\n'),
                            'parameters': [],
                            'return_type': None,
                            'signature': 'CREATE TRIGGER ' + trigger_name,
                            'is_entry': True,
                            'class_name': None,
                            'package_name': file_path
                        }
                        functions.append(func_info)
                        entry_points.append(func_info)
            
            # Extract table references as dependencies
            if stmt_type in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']:
                # Basic table extraction from FROM/INTO clauses
                table_pattern = r'(?:FROM|JOIN|INTO|UPDATE)\s+([\w.]+)'
                for match in re.finditer(table_pattern, str(stmt), re.IGNORECASE):
                    table_name = match.group(1)
                    if table_name.upper() not in ['SELECT', 'WHERE', 'SET', 'VALUES']:
                        if table_name not in dependencies:
                            dependencies.append(table_name)
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': dependencies
        }
