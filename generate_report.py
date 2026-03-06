#!/usr/bin/env python3
"""Generate AI summary coverage report - simplified version"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import db
from datetime import datetime

def main():
    try:
        # Get all projects
        query = 'SELECT id, name, description, upload_date, last_updated FROM projects ORDER BY name'
        projects = db.execute_query(query)
        
        if not projects:
            print("\n❌ Veritabanında proje bulunamadı!")
            return
        
        # Total statistics
        total_funcs = db.execute_query('SELECT COUNT(*) as cnt FROM functions')[0][0]
        with_summary = db.execute_query('SELECT COUNT(*) as cnt FROM functions WHERE ai_summary IS NOT NULL AND ai_summary != ""')[0][0]
        without_summary = total_funcs - with_summary
        coverage = (with_summary / total_funcs * 100) if total_funcs > 0 else 0
        
        # Create report
        report = []
        report.append("# AIKodAnaliz - AI Özet Kapsama Raporu")
        report.append(f"\n**Rapor Tarihi:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
        
        report.append("## 📊 Genel İstatistikler\n")
        report.append(f"- **Toplam Fonksiyon:** {total_funcs}")
        report.append(f"- **Özetlenmiş Fonksiyon:** {with_summary} ✅")
        report.append(f"- **Özetlenmeyen Fonksiyon:** {without_summary} ❌")
        report.append(f"- **Kapsama Oranı:** {coverage:.1f}%\n")
        
        report.append("---\n")
        report.append("## 📁 Proje Bazlı Detaylı Rapor\n")
        
        for proj in projects:
            proj_id, proj_name, proj_desc, upload_date, last_updated = proj
            
            # Get project functions
            func_query = '''
                SELECT f.id, f.function_name, f.function_type, f.class_name, 
                       f.package_name, f.signature, f.ai_summary, sf.file_name
                FROM functions f
                LEFT JOIN source_files sf ON f.file_id = sf.id
                WHERE f.project_id = ?
                ORDER BY sf.file_name, f.function_name
            '''
            functions = db.execute_query(func_query, [proj_id])
            
            if not functions:
                continue
            
            # Project statistics
            proj_total = len(functions)
            proj_with = sum(1 for f in functions if f[6])  # ai_summary is index 6
            proj_without = proj_total - proj_with
            proj_coverage = (proj_with / proj_total * 100) if proj_total > 0 else 0
            
            # Project header
            report.append(f"### 📦 {proj_name}")
            report.append(f"**Açıklama:** {proj_desc or 'Belirtilmemiş'}")
            report.append(f"- **Yükleme:** {upload_date}")
            report.append(f"- **Son Güncelleme:** {last_updated}\n")
            
            # Project stats
            report.append("#### Istatistikler")
            report.append(f"- **Toplam:** {proj_total} | **Özetlendi:** {proj_with} ({proj_coverage:.1f}%) | **Yok:** {proj_without} ({100-proj_coverage:.1f}%)\n")
            
            # File-based grouping
            report.append("#### Dosya Listesi\n")
            files_dict = {}
            for func in functions:
                file_name = func[7] or 'Bilinmeyen'
                if file_name not in files_dict:
                    files_dict[file_name] = []
                files_dict[file_name].append(func)
            
            for file_name in sorted(files_dict.keys()):
                file_funcs = files_dict[file_name]
                file_with = sum(1 for f in file_funcs if f[6])
                file_total = len(file_funcs)
                file_cov = (file_with / file_total * 100) if file_total > 0 else 0
                
                report.append(f"**📄 {file_name}** - {file_with}/{file_total} özetlendi ({file_cov:.1f}%)\n")
                report.append("| Fonksiyon | Tür | Durum |")
                report.append("|-----------|-----|-------|")
                
                for func in sorted(file_funcs, key=lambda x: x[1]):
                    fname = func[1]
                    ftype = func[2] or 'unknown'
                    status = "✅" if func[6] else "❌"
                    
                    # Qualified name
                    if func[3]:  # class_name
                        fname = f"{func[3]}.{fname}"
                    if func[4]:  # package_name
                        fname = f"{func[4]}.{fname}"
                    
                    report.append(f"| {fname} | {ftype} | {status} |")
                
                report.append("")
            
            report.append("\n")
        
        # Summary
        report.append("---\n")
        report.append("## 📈 Özet\n")
        report.append(f"✅ **{with_summary} fonksiyon özetlendi**  \n")
        report.append(f"❌ **{without_summary} fonksiyon beklemede**  \n")
        report.append(f"**Genel Kapsama:** {coverage:.1f}%\n")
        
        report.append("\n### Öneriler")
        if without_summary > 0:
            report.append(f"- {without_summary} fonksiyon için AI özeti oluşturulmalıdır")
            report.append("- Her fonksiyonun yanındaki '🤖 AI Özeti Al' butonunu kullanın")
            report.append("- Veya projeyi yeniden analiz edip toplu özet oluşturun")
        else:
            report.append("✨ Tüm fonksiyonlar özetlenmiştir!")
        
        # Write report
        report_path = 'REPORT_AI_SUMMARY.md'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        # Print summary
        print("\n" + "="*70)
        print("✅ RAPOR BAŞARIYLA OLUŞTURULDU!")
        print("="*70)
        print(f"\n📄 Dosya: {os.path.abspath(report_path)}")
        print(f"\n📊 Istatistikler:")
        print(f"   Total Fonksiyon: {total_funcs}")
        print(f"   Özetlendi: {with_summary} ✅")
        print(f"   Beklemede: {without_summary} ❌")
        print(f"   Kapsama: {coverage:.1f}%")
        print("\n" + "="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
