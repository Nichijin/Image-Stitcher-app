import os
import re
from typing import Optional, Tuple

# 尝试导入OpenCV以进行性能优化
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# 尝试导入img2pdf以支持PDF导出
try:
    import img2pdf
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


def sanitize_path(path: str) -> str:
    """清理路径字符串，移除非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', path)


def get_image_paths_from_folder(folder: str) -> list:
    """从文件夹获取所有图片路径"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff']
    paths = []
    for root, _, files in os.walk(folder):
        for file in files:
            if os.path.splitext(file.lower())[1] in image_extensions:
                paths.append(os.path.join(root, file))
    return paths


def calculate_grid_size(num_images: int, rows: int, cols: int) -> Tuple[int, int]:
    """计算实际需要的网格大小"""
    if rows <= 0 or cols <= 0:
        return 1, num_images
    total_cells = rows * cols
    pages = (num_images + total_cells - 1) // total_cells
    return rows, cols


def estimate_pages(num_images: int, rows: int, cols: int) -> int:
    """估计生成的页数"""
    if rows <= 0 or cols <= 0:
        return 1
    total_cells = rows * cols
    return (num_images + total_cells - 1) // total_cells