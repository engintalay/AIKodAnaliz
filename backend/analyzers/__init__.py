# Analyzers package
from backend.analyzers.advanced_analyzer import AdvancedCodeAnalyzer

# For backward compatibility
try:
    from backend.analyzers.code_analyzer import CodeAnalyzer
except ImportError:
    CodeAnalyzer = AdvancedCodeAnalyzer

__all__ = ['AdvancedCodeAnalyzer', 'CodeAnalyzer']

