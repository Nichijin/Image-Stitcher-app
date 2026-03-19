#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图片拼接工具入口脚本
用于PyInstaller打包
"""

import sys
import os

# 添加项目根目录到Python路径
if getattr(sys, 'frozen', False):
    # 如果是打包后的exe，添加资源目录到路径
    application_path = os.path.dirname(sys.executable)
    sys.path.insert(0, application_path)
else:
    # 如果是开发环境，添加项目根目录到路径
    application_path = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, application_path)

# 导入并运行主应用
from image_stitcher.app import main

if __name__ == "__main__":
    main()
