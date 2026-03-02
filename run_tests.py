#!/usr/bin/env python3
"""
AIKodAnaliz - Kod Analiz Motoru Test Scripti
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.analyzers.code_analyzer import CodeAnalyzer

def test_java_analysis():
    """Java kodu analiz testi"""
    print("\n" + "="*50)
    print("📝 JAVA KOD ANALİZİ TETSİ")
    print("="*50)
    
    with open('tests/Calculator.java', 'r') as f:
        code = f.read()
    
    analyzer = CodeAnalyzer()
    result = analyzer.analyze('Calculator.java', code, 'java')
    
    print(f"\n✅ Bulunan {len(result['functions'])} Fonksiyon:")
    for func in result['functions']:
        print(f"  - {func['name']} ({func['type']})")
        print(f"    Satırlar: {func['start_line']}-{func['end_line']}")
        print(f"    Parametreler: {func['parameters']}")
    
    print(f"\n🎯 Entry Points: {len(result['entry_points'])}")
    for entry in result['entry_points']:
        print(f"  - {entry['name']}")
    
    return result

def test_python_analysis():
    """Python kodu analiz testi"""
    print("\n" + "="*50)
    print("📝 PYTHON KOD ANALİZİ TETSİ")
    print("="*50)
    
    with open('tests/fibonacci.py', 'r') as f:
        code = f.read()
    
    analyzer = CodeAnalyzer()
    result = analyzer.analyze('fibonacci.py', code, 'python')
    
    print(f"\n✅ Bulunan {len(result['functions'])} Fonksiyon:")
    for func in result['functions']:
        print(f"  - {func['name']} ({func['type']})")
        print(f"    Satırlar: {func['start_line']}-{func['end_line']}")
        print(f"    Parametreler: {func['parameters']}")
    
    print(f"\n🎯 Entry Points: {len(result['entry_points'])}")
    for entry in result['entry_points']:
        print(f"  - {entry['name']}")
    
    return result

def test_javascript_analysis():
    """JavaScript kodu analiz testi"""
    print("\n" + "="*50)
    print("📝 JAVASCRIPT KOD ANALİZİ TETSİ")
    print("="*50)
    
    with open('tests/example.js', 'r') as f:
        code = f.read()
    
    analyzer = CodeAnalyzer()
    result = analyzer.analyze('example.js', code, 'javascript')
    
    print(f"\n✅ Bulunan {len(result['functions'])} Fonksiyon:")
    for func in result['functions']:
        print(f"  - {func['name']} ({func['type']})")
        print(f"    Satırlar: {func['start_line']}-{func['end_line']}")
        print(f"    Parametreler: {func['parameters']}")
    
    print(f"\n🎯 Entry Points: {len(result['entry_points'])}")
    for entry in result['entry_points']:
        print(f"  - {entry['name']}")
    
    return result

def test_database():
    """Veritabanı test"""
    print("\n" + "="*50)
    print("🗄️  VERİTABANI TETSİ")
    print("="*50)
    
    from backend.database import db
    
    # Test query
    try:
        rows = db.execute_query('SELECT COUNT(*) as count FROM users')
        print(f"✅ Veritabanı bağlantısı başarılı")
        print(f"   Kullanıcı sayısı: {rows[0]['count'] if rows else 0}")
    except Exception as e:
        print(f"❌ Veritabanı hatası: {e}")

def main():
    """Tüm testleri çalıştır"""
    print("\n🚀 AIKodAnaliz - Kod Analiz Motoru Testleri")
    print("=" * 50)
    
    try:
        # Test kod analizi
        test_java_analysis()
        test_python_analysis()
        test_javascript_analysis()
        
        # Test veritabanı
        test_database()
        
        print("\n" + "="*50)
        print("✅ TÜM TESTLER BAŞARILI")
        print("="*50)
        print("\n💡 Sonraki Adımlar:")
        print("1. LMStudio'yu başlatın (http://localhost:1234)")
        print("2. Uygulamayı başlatın: ./start.sh")
        print("3. Tarayıcıda açın: http://localhost:5000")
        
    except Exception as e:
        print(f"\n❌ TEST HATASI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
