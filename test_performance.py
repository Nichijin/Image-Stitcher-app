#!/usr/bin/env python3
"""
性能测试脚本
用于测试优化前后的处理速度
"""

import os
import time
import sys
import logging
from PIL import Image
import numpy as np

# 禁用日志输出
logging.basicConfig(level=logging.CRITICAL)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.CRITICAL)

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_stitcher.image_processor import fast_load_and_resize, apply_enhancements
from image_stitcher.memory_pool import memory_pool

def generate_test_images(count=10, size=(800, 600)):
    """生成测试图像"""
    test_images = []
    for i in range(count):
        # 创建一个随机图像
        img = Image.new('RGB', size, color=(255, 255, 255))
        # 添加一些随机内容
        for j in range(100):
            x = np.random.randint(0, size[0])
            y = np.random.randint(0, size[1])
            color = (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))
            for k in range(5):
                for l in range(5):
                    if x+k < size[0] and y+l < size[1]:
                        img.putpixel((x+k, y+l), color)
        test_images.append(img)
    return test_images

def test_preprocessing_speed():
    """测试预处理速度"""
    print("=== 测试预处理速度 ===")
    
    # 生成测试图像
    test_images = generate_test_images(10, (800, 600))
    
    # 保存测试图像到临时文件
    temp_files = []
    for i, img in enumerate(test_images):
        temp_file = f"temp_test_image_{i}.jpg"
        img.save(temp_file, quality=95)
        temp_files.append(temp_file)
    
    try:
        # 测试加载和调整大小速度
        start_time = time.time()
        resized_images = []
        for path in temp_files:
            img = fast_load_and_resize(path, 400, 300)
            resized_images.append(img)
        load_time = time.time() - start_time
        print(f"加载和调整大小时间: {load_time:.2f}秒")
        
        # 测试增强速度
        start_time = time.time()
        enhanced_images = []
        for img in resized_images:
            enhanced = apply_enhancements(img, brightness=1.2, contrast=1.1, sharpness=1.3)
            enhanced_images.append(enhanced)
        enhance_time = time.time() - start_time
        print(f"图像增强时间: {enhance_time:.2f}秒")
        
        return load_time, enhance_time
    finally:
        # 清理临时文件
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

def test_stitching_speed():
    """测试拼接速度"""
    print("\n=== 测试拼接速度 ===")
    
    # 生成测试图像
    test_images = generate_test_images(4, (400, 300))
    
    try:
        # 测试水平拼接
        start_time = time.time()
        # 简单的水平拼接测试
        width = sum(img.width for img in test_images[:2])
        height = max(img.height for img in test_images[:2])
        canvas = Image.new('RGB', (width, height), color=(255, 255, 255))
        x_offset = 0
        for img in test_images[:2]:
            canvas.paste(img, (x_offset, 0))
            x_offset += img.width
        horizontal_time = time.time() - start_time
        print(f"水平拼接时间: {horizontal_time:.2f}秒")
        
        # 测试垂直拼接
        start_time = time.time()
        width = max(img.width for img in test_images[:2])
        height = sum(img.height for img in test_images[:2])
        canvas = Image.new('RGB', (width, height), color=(255, 255, 255))
        y_offset = 0
        for img in test_images[:2]:
            canvas.paste(img, (0, y_offset))
            y_offset += img.height
        vertical_time = time.time() - start_time
        print(f"垂直拼接时间: {vertical_time:.2f}秒")
        
        return horizontal_time + vertical_time
    finally:
        pass

def test_memory_pool_efficiency():
    """测试内存池效率"""
    print("\n=== 测试内存池效率 ===")
    
    # 测试内存分配和释放
    shape = (1000, 1000, 3)
    dtype = np.uint8
    
    # 不使用内存池
    start_time = time.time()
    for i in range(100):
        arr = np.empty(shape, dtype=dtype)
        # 使用数组
        arr.fill(255)
    no_pool_time = time.time() - start_time
    print(f"不使用内存池时间: {no_pool_time:.2f}秒")
    
    # 使用内存池
    start_time = time.time()
    for i in range(100):
        arr = memory_pool.get(shape, dtype)
        # 使用数组
        arr.fill(255)
        # 归还到池
        memory_pool.put(arr)
    with_pool_time = time.time() - start_time
    print(f"使用内存池时间: {with_pool_time:.2f}秒")
    
    # 计算效率提升
    improvement = (no_pool_time - with_pool_time) / no_pool_time * 100
    print(f"内存池效率提升: {improvement:.1f}%")
    
    return no_pool_time, with_pool_time

def main():
    """主测试函数"""
    print("开始性能测试...\n")
    
    # 测试预处理速度
    load_time, enhance_time = test_preprocessing_speed()
    
    # 测试拼接速度
    stitch_time = test_stitching_speed()
    
    # 测试内存池效率
    no_pool_time, with_pool_time = test_memory_pool_efficiency()
    
    print("\n=== 测试结果汇总 ===")
    print(f"预处理总时间: {load_time + enhance_time:.2f}秒")
    print(f"拼接时间: {stitch_time:.2f}秒")
    print(f"内存池效率提升: {(no_pool_time - with_pool_time) / no_pool_time * 100:.1f}%")
    print("\n测试完成！")

if __name__ == "__main__":
    main()
