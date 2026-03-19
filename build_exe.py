#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图片拼接工具打包脚本
使用PyInstaller将应用打包成EXE文件
"""

import os
import subprocess
import sys

def build_exe():
    """打包应用为EXE文件"""
    
    # 项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # PyInstaller命令
    cmd = [
        'pyinstaller',
        '--name=ImageStitcher',
        '--onefile',
        '--windowed',
        '--icon=NONE',
        '--clean',
        '--noconfirm',
        f'--workpath={os.path.join(project_root, "build")}',
        f'--distpath={os.path.join(project_root, "dist")}',
        '--add-data=image_stitcher;image_stitcher',
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.filedialog',
        '--hidden-import=tkinter.messagebox',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=tkinter.simpledialog',
        '--hidden-import=concurrent.futures',
        'run.py'
    ]
    
    print("开始打包应用...")
    print(f"工作目录: {project_root}")
    print(f"命令: {' '.join(cmd)}")
    print("-" * 80)
    
    try:
        # 执行打包命令（不捕获输出，避免编码问题）
        result = subprocess.run(cmd, cwd=project_root, check=True)
        
        print("-" * 80)
        print("打包完成!")
        print(f"EXE文件位置: {os.path.join(project_root, 'dist', 'ImageStitcher.exe')}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        return False
    except Exception as e:
        print(f"打包过程中发生错误: {e}")
        return False

if __name__ == "__main__":
    success = build_exe()
    sys.exit(0 if success else 1)
