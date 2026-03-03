"""
Advanced code analyzer using Tree-Sitter for precise AST parsing
REQUIRES: tree-sitter and tree-sitter-<language> packages
NO REGEX FALLBACK - Tree-Sitter is mandatory for accuracy
"""

import ast
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Tree-Sitter is MANDATORY
try:
    from tree_sitter import Language, Parser
    # Import individual language parsers
    import tree_sitter_java
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_php
    TREE_SITTER_REQUIRED = True
    # Backward-compatible alias used by backend/app.py startup checks
    TREE_SITTER_AVAILABLE = True
except ImportError as e:
    raise ImportError(
        f"Tree-Sitter packages required but not installed.\n"
        f"Install with: pip install tree-sitter tree-sitter-java tree-sitter-python "
        f"tree-sitter-javascript tree-sitter-typescript tree-sitter-php\n"
        f"Error: {e}"
    )


class AdvancedCodeAnalyzer:
    """Tree-Sitter based code analyzer - REQUIRES tree-sitter packages"""
    
    def __init__(self):
        if not TREE_SITTER_REQUIRED:
            raise RuntimeError(
                "Tree-Sitter is required but not available. "
                "Install: pip install tree-sitter tree-sitter-java tree-sitter-python "
                "tree-sitter-javascript tree-sitter-typescript tree-sitter-php"
            )
        
        self.language = None
        self.functions = []
        self.entry_points = []
        self.dependencies = []
        self.parser = None
        self.ts_language = None
        
        self._init_tree_sitter_parsers()
    
    def _init_tree_sitter_parsers(self):
        """Initialize Tree-Sitter parsers for all languages"""
        self.parsers = {}
        self.ts_languages = {}
        
        # Map file extensions to tree-sitter language names
        self.language_map = {
            'java': 'java',
            'javascript': 'javascript',
            'js': 'javascript',
            'typescript': 'typescript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'php': 'php',
            'python': 'python',
            'py': 'python',
        }
        
        # Pre-load parsers using individual language packages
        # Some packages expose `language()`, others use language-specific factories.
        language_modules = {
            'java': (tree_sitter_java, ['language']),
            'python': (tree_sitter_python, ['language']),
            'javascript': (tree_sitter_javascript, ['language']),
            'typescript': (tree_sitter_typescript, ['language', 'language_typescript']),
            'php': (tree_sitter_php, ['language', 'language_php', 'language_php_only']),
        }
        
        for lang_name, (lang_module, factory_names) in language_modules.items():
            try:
                language_factory = None
                for factory_name in factory_names:
                    candidate = getattr(lang_module, factory_name, None)
                    if callable(candidate):
                        language_factory = candidate
                        break

                if language_factory is None:
                    raise AttributeError(
                        f"No language factory found in module {lang_module.__name__} "
                        f"(tried: {', '.join(factory_names)})"
                    )

                language = Language(language_factory())
                parser = Parser()
                # tree-sitter>=0.25 uses parser.language property
                parser.language = language
                self.parsers[lang_name] = parser
                self.ts_languages[lang_name] = language
            except Exception as e:
                print(f"Warning: Could not load tree-sitter parser for {lang_name}: {e}")
    
    def analyze(self, file_path: str, content: str, language: str) -> Dict:
        """Analyze source code using Tree-Sitter and extract functions
        
        Args:
            file_path: Path to the source file
            content: Source code content
            language: Programming language (java, python, javascript, etc)
            
        Returns:
            Dict with 'functions', 'entry_points', 'dependencies'
            
        Raises:
            ValueError: If language not supported by Tree-Sitter
            Exception: If parsing fails
        """
        self.language = language.lower()
        self.content = content
        self.functions = []
        self.entry_points = []
        self.dependencies = []
        
        lang_name = self.language_map.get(self.language, self.language)
        if lang_name not in self.ts_languages:
            raise ValueError(
                f"Language '{language}' not supported. "
                f"Supported: {', '.join(sorted(set(self.language_map.values())))}"
            )
        
        # Always use Tree-Sitter
        return self._analyze_with_tree_sitter(file_path, content, lang_name)
    
    def _analyze_with_tree_sitter(self, file_path: str, content: str, language: str) -> Dict:
        """Analyze code using Tree-Sitter for precise AST parsing"""
        parser = self.parsers[language]
        ts_language = self.ts_languages[language]
        
        try:
            # Parse the code
            tree = parser.parse(content.encode('utf-8'))
            root = tree.root_node
            
            # Get package/namespace
            package_name = self._extract_package_ts(root, language, file_path)
            
            # Extract functions
            functions = self._extract_functions_ts(root, language, package_name, content)
            
            # Extract dependencies
            dependencies = self._extract_imports_ts(root, language, content)
            
            # Find entry points
            entry_points = [f for f in functions if f['is_entry']]
            
            return {
                'functions': functions,
                'entry_points': entry_points,
                'dependencies': dependencies
            }
        except Exception as e:
            print(f"Error in tree-sitter analysis: {e}")
            raise
    
    def _extract_functions_ts(self, node, language: str, package_name: str, content: str) -> List[Dict]:
        """Extract functions using Tree-Sitter AST"""
        functions = []
        
        # Define function query patterns for each language
        query_patterns = {
            'python': self._find_python_functions_ts,
            'java': self._find_java_functions_ts,
            'javascript': self._find_js_functions_ts,
            'typescript': self._find_js_functions_ts,
            'php': self._find_php_functions_ts,
        }
        
        if language in query_patterns:
            functions = query_patterns[language](node, package_name, content)
        else:
            functions = self._find_generic_functions_ts(node, package_name, content)
        
        return functions
    
    def _find_python_functions_ts(self, node, package_name: str, content: str) -> List[Dict]:
        """Extract Python functions using Tree-Sitter"""
        functions = []
        lines = content.split('\n')
        
        def traverse(node, parent_class=None):
            if node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Extract parameters
                    params_node = node.child_by_field_name('parameters')
                    parameters = self._extract_params_python(params_node, content)
                    
                    # Get function signature
                    func_text = '\n'.join(lines[node.start_point[0]:node.start_point[0]+3])
                    signature = f"def {func_name}({', '.join(parameters)})"
                    
                    func_info = {
                        'name': func_name,
                        'type': 'function',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': parameters,
                        'return_type': None,
                        'signature': signature,
                        'is_entry': func_name in ['main', '__main__', 'run'],
                        'class_name': parent_class,
                        'package_name': package_name
                    }
                    functions.append(func_info)
            
            elif node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    class_info = {
                        'name': class_name,
                        'type': 'class',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': [],
                        'return_type': None,
                        'signature': f"class {class_name}",
                        'is_entry': False,
                        'class_name': None,
                        'package_name': package_name
                    }
                    functions.append(class_info)
                    
                    # Traverse class children
                    for child in node.children:
                        if child.type == 'block':
                            for item in child.children:
                                traverse(item, class_name)
                    return
            
            for child in node.children:
                traverse(child, parent_class)
        
        traverse(node)
        return functions
    
    def _find_java_functions_ts(self, node, package_name: str, content: str) -> List[Dict]:
        """Extract Java functions using Tree-Sitter"""
        functions = []
        lines = content.split('\n')
        
        def traverse(node, parent_class=None):
            if node.type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    # Extract parameters
                    params = self._extract_params_java(node, content)
                    
                    # Get signature
                    sig_end = min(node.start_point[0] + 3, len(lines))
                    signature = ' '.join(lines[node.start_point[0]:sig_end]).strip()
                    
                    func_info = {
                        'name': func_name,
                        'type': 'function' if func_name not in ['main'] else 'entry',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': params,
                        'return_type': 'void',
                        'signature': signature,
                        'is_entry': func_name == 'main',
                        'class_name': parent_class,
                        'package_name': package_name
                    }
                    functions.append(func_info)
            
            elif node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    class_info = {
                        'name': class_name,
                        'type': 'class',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': [],
                        'return_type': None,
                        'signature': f"class {class_name}",
                        'is_entry': False,
                        'class_name': None,
                        'package_name': package_name
                    }
                    functions.append(class_info)
                    
                    # Traverse class body
                    for child in node.children:
                        if child.type == 'class_body':
                            for item in child.children:
                                traverse(item, class_name)
                    return
            
            for child in node.children:
                traverse(child, parent_class)
        
        traverse(node)
        return functions
    
    def _find_js_functions_ts(self, node, package_name: str, content: str) -> List[Dict]:
        """Extract JavaScript/TypeScript functions using Tree-Sitter"""
        functions = []
        lines = content.split('\n')
        
        def traverse(node, parent_class=None):
            # Function declaration
            if node.type in ['function_declaration', 'function']:
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    params = self._extract_params_js(node, content)
                    sig_line = lines[node.start_point[0]].strip()
                    
                    func_info = {
                        'name': func_name,
                        'type': 'function',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': params,
                        'return_type': None,
                        'signature': sig_line,
                        'is_entry': func_name in ['main', 'run'],
                        'class_name': parent_class,
                        'package_name': package_name
                    }
                    functions.append(func_info)
            
            # Method definition
            elif node.type in ['method_definition', 'arrow_function']:
                name_node = None
                if node.type == 'method_definition':
                    name_node = node.child_by_field_name('name')
                else:
                    # Arrow functions often don't have standalone names
                    pass
                
                if name_node:
                    func_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    params = self._extract_params_js(node, content)
                    sig_line = lines[node.start_point[0]].strip()
                    
                    func_info = {
                        'name': func_name,
                        'type': 'function',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': params,
                        'return_type': None,
                        'signature': sig_line,
                        'is_entry': False,
                        'class_name': parent_class,
                        'package_name': package_name
                    }
                    functions.append(func_info)
            
            # Class declaration
            elif node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    class_info = {
                        'name': class_name,
                        'type': 'class',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': [],
                        'return_type': None,
                        'signature': f"class {class_name}",
                        'is_entry': False,
                        'class_name': None,
                        'package_name': package_name
                    }
                    functions.append(class_info)
                    
                    # Traverse class body
                    for child in node.children:
                        if child.type == 'class_body':
                            for item in child.children:
                                traverse(item, class_name)
                    return
            
            for child in node.children:
                traverse(child, parent_class)
        
        traverse(node)
        return functions
    
    def _find_php_functions_ts(self, node, package_name: str, content: str) -> List[Dict]:
        """Extract PHP functions using Tree-Sitter"""
        functions = []
        lines = content.split('\n')
        
        def traverse(node, parent_class=None):
            if node.type == 'function_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    params = self._extract_params_php(node, content)
                    sig_line = lines[node.start_point[0]].strip() if node.start_point[0] < len(lines) else ""
                    
                    func_info = {
                        'name': func_name,
                        'type': 'function',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': params,
                        'return_type': None,
                        'signature': sig_line,
                        'is_entry': func_name in ['main', 'index', 'run'],
                        'class_name': parent_class,
                        'package_name': package_name
                    }
                    functions.append(func_info)
            
            elif node.type == 'method_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    params = self._extract_params_php(node, content)
                    sig_line = lines[node.start_point[0]].strip() if node.start_point[0] < len(lines) else ""
                    
                    func_info = {
                        'name': func_name,
                        'type': 'function',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': params,
                        'return_type': None,
                        'signature': sig_line,
                        'is_entry': False,
                        'class_name': parent_class,
                        'package_name': package_name
                    }
                    functions.append(func_info)
            
            elif node.type == 'class_declaration':
                name_node = node.child_by_field_name('name')
                if name_node:
                    class_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    class_info = {
                        'name': class_name,
                        'type': 'class',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': [],
                        'return_type': None,
                        'signature': f"class {class_name}",
                        'is_entry': False,
                        'class_name': None,
                        'package_name': package_name
                    }
                    functions.append(class_info)
                    
                    # Traverse class body
                    for child in node.children:
                        if child.type == 'declaration_list':
                            for item in child.children:
                                traverse(item, class_name)
                    return
            
            for child in node.children:
                traverse(child, parent_class)
        
        traverse(node)
        return functions
    
    def _find_generic_functions_ts(self, node, package_name: str, content: str) -> List[Dict]:
        """Generic function extraction for unsupported languages"""
        functions = []
        
        def traverse(node):
            # Look for common function patterns
            if 'function' in node.type or 'declaration' in node.type:
                name_node = node.child_by_field_name('name')
                if name_node:
                    func_name = name_node.text.decode('utf-8')
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    
                    func_info = {
                        'name': func_name,
                        'type': 'function',
                        'start_line': start_line,
                        'end_line': end_line,
                        'parameters': [],
                        'return_type': None,
                        'signature': func_name,
                        'is_entry': False,
                        'class_name': None,
                        'package_name': package_name
                    }
                    functions.append(func_info)
            
            for child in node.children:
                traverse(child)
        
        traverse(node)
        return functions
    
    def _extract_params_python(self, params_node, content: str) -> List[str]:
        """Extract Python function parameters"""
        if not params_node:
            return []
        
        try:
            param_text = params_node.text.decode('utf-8')
            # Remove parentheses and split
            param_text = param_text.strip('()')
            if not param_text:
                return []
            
            params = []
            for param in param_text.split(','):
                param = param.strip()
                if param and not param.startswith('*'):
                    # Extract just the parameter name
                    if '=' in param:
                        param = param.split('=')[0].strip()
                    if ':' in param:
                        param = param.split(':')[0].strip()
                    if param:
                        params.append(param)
            return params
        except:
            return []
    
    def _extract_params_java(self, node, content: str) -> List[str]:
        """Extract Java function parameters"""
        try:
            params_node = node.child_by_field_name('parameters')
            if not params_node:
                return []
            
            params = []
            for child in params_node.children:
                if child.type == 'formal_parameter':
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        params.append(name_node.text.decode('utf-8'))
            return params
        except:
            return []
    
    def _extract_params_js(self, node, content: str) -> List[str]:
        """Extract JavaScript/TypeScript function parameters"""
        try:
            params_node = node.child_by_field_name('parameters')
            if not params_node:
                return []
            
            params = []
            for child in params_node.children:
                if child.type == 'identifier':
                    params.append(child.text.decode('utf-8'))
            return params
        except:
            return []
    
    def _extract_params_php(self, node, content: str) -> List[str]:
        """Extract PHP function parameters"""
        try:
            params_node = node.child_by_field_name('parameters')
            if not params_node:
                return []
            
            params = []
            for child in params_node.children:
                if child.type == 'variable':
                    param_name = child.text.decode('utf-8').lstrip('$')
                    params.append(param_name)
            return params
        except:
            return []
    
    def _extract_package_ts(self, node, language: str, file_path: str) -> Optional[str]:
        """Extract package/namespace name from AST"""
        def traverse(node):
            if language == 'python':
                # Python doesn't have package declarations in code
                return file_path.replace('/', '.').replace('\\', '.').replace('.py', '')
            
            elif language == 'java':
                if node.type == 'package_declaration':
                    name_node = None
                    for child in node.children:
                        if child.type == 'scoped_identifier' or child.type == 'identifier':
                            name_node = child
                    if name_node:
                        return name_node.text.decode('utf-8')
            
            elif language in ['javascript', 'typescript']:
                # JS/TS don't have package declarations
                return None
            
            elif language == 'php':
                if node.type == 'namespace_declaration':
                    for child in node.children:
                        if child.type == 'namespace_name':
                            return child.text.decode('utf-8')
            
            for child in node.children:
                result = traverse(child)
                if result:
                    return result
            return None
        
        return traverse(node)
    
    def _extract_imports_ts(self, node, language: str, content: str) -> List[str]:
        """Extract imports/requires using Tree-Sitter"""
        imports = []
        
        def traverse(node):
            if language == 'python':
                if node.type in ['import_statement', 'import_from_statement']:
                    import_text = node.text.decode('utf-8')
                    imports.append(import_text)
            
            elif language in ['javascript', 'typescript']:
                if node.type in ['import_statement', 'require_clause']:
                    import_text = node.text.decode('utf-8')
                    imports.append(import_text)
            
            elif language == 'java':
                if node.type == 'import_declaration':
                    import_text = node.text.decode('utf-8')
                    imports.append(import_text)
            
            elif language == 'php':
                if node.type in ['use_declaration', 'require_clause', 'include_clause']:
                    import_text = node.text.decode('utf-8')
                    imports.append(import_text)
            
            for child in node.children:
                traverse(child)
        
        traverse(node)
        return imports
    
    # ========== NO LEGACY REGEX FALLBACKS - TREE-SITTER ONLY ==========
    
    def _analyze_python(self, file_path: str, content: str) -> Dict:
        """Analyze Python code (AST-based)"""
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
                    'return_type': None,
                    'signature': f"def {node.name}(...)",
                    'is_entry': node.name in ['main', '__main__', 'run'],
                    'class_name': None,
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
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': []
        }
    
    def _analyze_java_like(self, file_path: str, content: str) -> Dict:
        """Regex fallback for Java/JavaScript/TypeScript"""
        functions = []
        entry_points = []
        
        # Remove comments and strings first
        content_clean = self._remove_comments_and_strings(content, self.language)
        
        # Package pattern
        package_match = re.search(r'package\s+([^;]+);', content_clean)
        package_name = package_match.group(1).strip() if package_match else None
        
        # Function pattern (improved)
        if self.language == 'java':
            func_pattern = r'((?:public|private|protected|static|final)\s+)*(\w+)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[^{]+)?\s*\{'
        else:
            func_pattern = r'(?:async\s+)?(?:function|const|let|var)?\s*(\w+)\s*[=:]?\s*\([^)]*\)\s*(?:=>)?\s*\{'
        
        for match in re.finditer(func_pattern, content_clean):
            if self.language == 'java':
                func_name = match.group(3)
            else:
                func_name = match.group(1)
            
            if func_name in {'if', 'for', 'while', 'switch', 'catch', 'function', 'class'}:
                continue
            
            line_num = content_clean[:match.start()].count('\n') + 1
            end_line = self._find_block_end(content, match.end())
            
            func_info = {
                'name': func_name,
                'type': 'function' if func_name != 'constructor' else 'entry',
                'start_line': line_num,
                'end_line': end_line,
                'parameters': [],
                'return_type': None,
                'signature': match.group(0)[:50],
                'is_entry': func_name in ['main', 'constructor'],
                'class_name': None,
                'package_name': package_name
            }
            functions.append(func_info)
            if func_info['is_entry']:
                entry_points.append(func_info)
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': []
        }
    
    def _analyze_php(self, file_path: str, content: str) -> Dict:
        """Regex fallback for PHP"""
        functions = []
        entry_points = []
        
        content_clean = self._remove_comments_and_strings(content, 'php')
        
        # Function/method pattern
        func_pattern = r'(?:public|private|protected)?\s*(?:static)?\s*function\s+(\w+)\s*\([^)]*\)'
        
        for match in re.finditer(func_pattern, content_clean):
            func_name = match.group(1)
            line_num = content_clean[:match.start()].count('\n') + 1
            end_line = self._find_block_end(content, match.end())
            
            func_info = {
                'name': func_name,
                'type': 'function',
                'start_line': line_num,
                'end_line': end_line,
                'parameters': [],
                'return_type': None,
                'signature': match.group(0),
                'is_entry': func_name in ['main', 'index', 'run'],
                'class_name': None,
                'package_name': None
            }
            functions.append(func_info)
            if func_info['is_entry']:
                entry_points.append(func_info)
        
        return {
            'functions': functions,
            'entry_points': entry_points,
            'dependencies': []
        }
    
    def _analyze_markup(self, content: str) -> Dict:
        """Analyze HTML/CSS"""
        return {
            'functions': [],
            'entry_points': [],
            'dependencies': []
        }
    
    def _analyze_generic(self, content: str) -> Dict:
        """Generic fallback"""
        return {
            'functions': [],
            'entry_points': [],
            'dependencies': []
        }
    
    def _remove_comments_and_strings(self, content: str, language: str) -> str:
        """Remove comments and strings from code"""
        result = []
        i = 0
        
        while i < len(content):
            # Single-line comment
            if language in ['java', 'javascript', 'typescript', 'php', 'go', 'rust', 'c', 'cpp']:
                if i < len(content) - 1 and content[i:i+2] == '//':
                    while i < len(content) and content[i] != '\n':
                        result.append(' ')
                        i += 1
                    continue
            
            # Multi-line comment
            if i < len(content) - 1 and content[i:i+2] == '/*':
                while i < len(content) - 1:
                    if content[i:i+2] == '*/':
                        i += 2
                        break
                    result.append(' ')
                    i += 1
                continue
            
            # Python comment
            if language == 'python' and content[i] == '#':
                while i < len(content) and content[i] != '\n':
                    result.append(' ')
                    i += 1
                continue
            
            # String literals
            if content[i] in ['"', "'"]:
                quote = content[i]
                result.append(' ')
                i += 1
                while i < len(content):
                    if content[i] == quote and (i == 0 or content[i-1] != '\\'):
                        result.append(' ')
                        i += 1
                        break
                    result.append(' ')
                    i += 1
                continue
            
            result.append(content[i])
            i += 1
        
        return ''.join(result)
    
    def _find_block_end(self, content: str, start_pos: int) -> int:
        """Find the end of a code block using brace matching"""
        depth = 0
        i = start_pos
        
        while i < len(content):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    return content[:i+1].count('\n') + 1
            i += 1
        
        return content.count('\n') + 1
