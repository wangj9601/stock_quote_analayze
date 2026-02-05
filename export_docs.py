#!/usr/bin/env python3
"""
GMS策略文档导出工具
将Markdown格式的需求和设计文档导出为Word或PDF格式
"""

import os
import subprocess
import sys
from pathlib import Path

def check_pandoc():
    """检查是否安装了pandoc"""
    try:
        subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def export_to_word(input_files, output_file):
    """导出为Word格式"""
    cmd = ['pandoc'] + input_files + [
        '-o', output_file,
        '--toc',
        '--toc-depth=3',
        '--number-sections',
        '--highlight-style=github',
        '--reference-doc=template.docx'  # 可选：使用模板
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ 成功导出Word文档: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Word导出失败: {e}")
        return False

def export_to_pdf(input_files, output_file):
    """导出为PDF格式"""
    cmd = ['pandoc'] + input_files + [
        '-o', output_file,
        '--toc',
        '--toc-depth=3',
        '--number-sections',
        '--pdf-engine=xelatex',
        '-V', 'geometry:margin=1in',
        '-V', 'fontsize=12pt',
        '-V', 'documentclass=article'
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ 成功导出PDF文档: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ PDF导出失败: {e}")
        print("提示: PDF导出需要安装LaTeX引擎 (如MiKTeX或TeX Live)")
        return False

def main():
    """主函数"""
    print("🚀 GMS策略文档导出工具")
    print("=" * 50)
    
    # 检查pandoc
    if not check_pandoc():
        print("❌ 未找到pandoc，请先安装:")
        print("   Windows: choco install pandoc")
        print("   macOS: brew install pandoc")
        print("   Ubuntu: sudo apt-get install pandoc")
        print("   或访问: https://pandoc.org/installing.html")
        sys.exit(1)
    
    # 定义文件路径
    spec_dir = Path('.kiro/specs/gms-strategy')
    requirements_file = spec_dir / 'requirements.md'
    design_file = spec_dir / 'design.md'
    
    # 检查文件是否存在
    if not requirements_file.exists():
        print(f"❌ 需求文档不存在: {requirements_file}")
        sys.exit(1)
    
    if not design_file.exists():
        print(f"❌ 设计文档不存在: {design_file}")
        sys.exit(1)
    
    print(f"📄 找到需求文档: {requirements_file}")
    print(f"📄 找到设计文档: {design_file}")
    print()
    
    # 输入文件列表
    input_files = [str(requirements_file), str(design_file)]
    
    # 创建输出目录
    output_dir = Path('exported_docs')
    output_dir.mkdir(exist_ok=True)
    
    # 导出选项
    print("请选择导出格式:")
    print("1. Word (.docx)")
    print("2. PDF (.pdf)")
    print("3. 两种格式都导出")
    
    choice = input("请输入选择 (1/2/3): ").strip()
    
    success_count = 0
    
    if choice in ['1', '3']:
        # 导出Word
        word_output = output_dir / 'GMS策略完整文档.docx'
        if export_to_word(input_files, str(word_output)):
            success_count += 1
    
    if choice in ['2', '3']:
        # 导出PDF
        pdf_output = output_dir / 'GMS策略完整文档.pdf'
        if export_to_pdf(input_files, str(pdf_output)):
            success_count += 1
    
    if choice not in ['1', '2', '3']:
        print("❌ 无效选择")
        sys.exit(1)
    
    print()
    print("=" * 50)
    if success_count > 0:
        print(f"🎉 导出完成! 成功导出 {success_count} 个文档")
        print(f"📁 输出目录: {output_dir.absolute()}")
    else:
        print("❌ 导出失败")
        sys.exit(1)

if __name__ == '__main__':
    main()