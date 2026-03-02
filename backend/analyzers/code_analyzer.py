import ast
import re
from typing import List, Dict, Tuple

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
            return self._analyze_python(content)
        elif self.language in ["java", "javascript", "typescript"]:
            return self._analyze_java_like(content)
        elif self.language in ["php"]:
            return self._analyze_php(content)
        elif self.language in ["css", "html"]:
            return self._analyze_markup(content)
        else:
            return self._analyze_generic(content)
    
    def _analyze_python(self, content: str) -> Dict:
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
                    'is_entry': node.name in ['main', '__main__', 'run']
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
                    'is_entry': False
                }
                functions.append(func_info)
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': self._extract_imports_python(tree)
        }
    
    def _analyze_java_like(self, content: str) -> Dict:
        """Analyze Java/JavaScript/TypeScript code"""
        functions = []
        entry_points = []
        
        # Function pattern for Java/JS/TS
        func_pattern = r'(?:public|private|protected|static|async)?\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+)?\s*[{:]'
        matches = re.finditer(func_pattern, content)
        
        lines = content.split('\n')
        
        for match in matches:
            func_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            # Extract parameters
            params_match = re.search(r'\(([^)]*)\)', content[match.start():match.start()+200])
            params = []
            if params_match:
                params_str = params_match.group(1)
                params = [p.strip().split()[-1] for p in params_str.split(',') if p.strip()]
            
            func_info = {
                'name': func_name,
                'type': 'function' if func_name not in ['main', 'constructor'] else 'entry',
                'start_line': line_num,
                'end_line': line_num + 5,  # Approximate
                'parameters': params,
                'return_type': 'void',  # Default
                'signature': content[match.start():match.end()].strip(),
                'is_entry': func_name in ['main', 'constructor', 'init']
            }
            functions.append(func_info)
            
            if func_info['is_entry']:
                entry_points.append(func_info)
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': self._extract_imports_generic(content)
        }
    
    def _analyze_php(self, content: str) -> Dict:
        """Analyze PHP code"""
        functions = []
        entry_points = []
        
        # PHP function pattern
        func_pattern = r'(?:public|private|protected)?\s*function\s+(\w+)\s*\(([^)]*)\)'
        matches = re.finditer(func_pattern, content)
        
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
            
            func_info = {
                'name': func_name,
                'type': 'function',
                'start_line': line_num,
                'end_line': line_num + 10,
                'parameters': params,
                'return_type': 'mixed',
                'signature': match.group(0),
                'is_entry': func_name in ['main', 'index', 'run']
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
                'end_line': line_num + 1,
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
