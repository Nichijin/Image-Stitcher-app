#!/usr/bin/env python3
"""
测试libvips集成效果
比较不同图像处理引擎的性能
"""

import os
import time
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_stitcher.image_processor import fast_load_and_resize, LIBVIPS_AVAILABLE, OPENCV_AVAILABLE

# 生成测试图像
from PIL import Image
import numpy as np

def generate_test_image(path, size=(1200, 800)):
    """生成测试图像"""
    img = Image.new('RGB', size, color=(255, 255, 255))
    # 添加一些随机内容
    for i in range(200):
        x = np.random.randint(0, size[0])
        y = np.random.randint(0, size[1])
        color = (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))
        for j in range(10):
            for k in range(10):
                if x+j < size[0] and y+k < size[1]:
                    img.putpixel((x+j, y+k), color)
    img.save(path, quality=95)
    return path

def test_processing_speed():
    """测试图像处理速度"""
    print("=== 测试图像处理速度 ===")
    print(f"libvips 可用: {LIBVIPS_AVAILABLE}")
    print(f"OpenCV 可用: {OPENCV_AVAILABLE}")
    print()
    
    # 生成测试图像
    test_image_path = generate_test_image("test_speed_image.jpg", size=(1600, 1200))
    
    try:
        # 测试参数
        test_cases = [
            (400, 300),   # 小尺寸
            (800, 600),   # 中等尺寸
            (1200, 900),  # 大尺寸
        ]
        
        for target_w, target_h in test_cases:
            print(f"测试尺寸: {target_w}x{target_h}")
            
            # 测试多次取平均值
            times = []
            for i in range(5):
                start_time = time.time()
                img = fast_load_and_resize(test_image_path, target_w, target_h)
                end_time = time.time()
                times.append(end_time - start_time)
            
            avg_time = sum(times) / len(times)
            print(f"平均处理时间: {avg_time:.4f}秒")
            print()
            
        return True
    finally:
        # 清理测试文件
        if os.path.exists(test_image_path):
            os.remove(test_image_path)

def test_batch_processing():
    """测试批量处理速度"""
    print("=== 测试批量处理速度 ===")
    
    # 生成多个测试图像
    test_images = []
    for i in range(5):
        path = generate_test_image(f"test_batch_{i}.jpg", size=(1200, 800))
        test_images.append(path)
    
    try:
        # 测试批量处理
        target_w, target_h = 800, 600
        
        start_time = time.time()
        for path in test_images:
            img = fast_load_and_resize(path, target_w, target_h)
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_time = total_time / len(test_images)
        
        print(f"批量处理 {len(test_images)} 张图像:")
        print(f"总时间: {total_time:.2f}秒")
        print(f"平均每张: {avg_time:.4f}秒")
        print()
        
        return True
    finally:
        # 清理测试文件
        for path in test_images:
            if os.path.exists(path):
                os.remove(path)

def main():
    """主测试函数"""
    print("开始测试 libvips 集成效果...\n")
    
    # 测试单张图像处理速度
    test_processing_speed()
    
    # 测试批量处理速度
    test_batch_processing()
    
    print("测试完成！")

if __name__ == "__main__":
    main()
