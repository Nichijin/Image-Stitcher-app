#!/usr/bin/env python3
# 测试预览拼接功能

import sys
import os
from image_stitcher.image_processor import process_image_batch

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_preview_mode():
    """测试预览模式"""
    print("开始测试预览模式...")
    
    # 准备测试数据
    # 这里使用一些示例图片路径，实际测试时需要替换为真实的图片路径
    image_paths = []
    # 生成一些虚拟的图片路径用于测试
    for i in range(10):
        # 假设当前目录下有测试图片
        test_img = f"test_image_{i}.jpg"
        if os.path.exists(test_img):
            image_paths.append(test_img)
    
    # 如果没有测试图片，使用一些占位路径
    if not image_paths:
        print("警告：未找到测试图片，使用占位路径进行测试")
        # 使用一些可能存在的图片路径
        for i in range(10):
            image_paths.append(f"C:\\Windows\\Web\\Wallpaper\\Theme1\\img{i%3}.jpg")
    
    print(f"测试图片数量: {len(image_paths)}")
    
    # 测试配置
    config = {
        "layout": "网格",
        "target_width": 800,
        "target_height": 600,
        "rows": 2,
        "cols": 4,
        "h_spacing": 30,
        "v_spacing": 30,
        "margin_top": 0,
        "margin_bottom": 0,
        "margin_left": 0,
        "margin_right": 0,
        "enhance_enabled": True,
        "brightness": 1.0,
        "contrast": 1.0,
        "sharpness": 1.0,
        "show_grid": False,
        "flip_mode": "无",
        "gen_row_reversed": True
    }
    
    try:
        # 测试预览模式
        print("测试预览模式...")
        import time
        start_time = time.time()
        
        results = process_image_batch(image_paths, config, preview_mode=True)
        
        end_time = time.time()
        print(f"预览模式处理时间: {end_time - start_time:.2f}秒")
        print(f"预览模式生成结果数量: {len(results)}")
        
        if results:
            print(f"预览模式生成的第一张图片尺寸: {results[0].width}x{results[0].height}")
            # 保存预览结果
            preview_path = "preview_test_result.jpg"
            results[0].save(preview_path)
            print(f"预览结果已保存到: {preview_path}")
        
        # 测试正常模式（对比）
        print("\n测试正常模式（对比）...")
        start_time = time.time()
        
        # 只处理前10张图片，避免处理时间过长
        normal_results = process_image_batch(image_paths[:10], config, preview_mode=False)
        
        end_time = time.time()
        print(f"正常模式处理时间: {end_time - start_time:.2f}秒")
        print(f"正常模式生成结果数量: {len(normal_results)}")
        
        if normal_results:
            print(f"正常模式生成的第一张图片尺寸: {normal_results[0].width}x{normal_results[0].height}")
        
        print("\n测试完成！")
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_preview_mode()
