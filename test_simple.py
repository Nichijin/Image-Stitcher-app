#!/usr/bin/env python3
# 简单测试脚本

import os
import sys
import time
import tempfile
from PIL import Image

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_stitcher.pipeline import ImagePipeline
from image_stitcher.pipeline_pool import PipelinePool

# 创建测试图像
def create_test_images(count=10, size=(400, 300)):
    """创建测试图像"""
    temp_dir = tempfile.mkdtemp()
    image_paths = []
    
    for i in range(count):
        img = Image.new('RGB', size, color=(73, 109, 137))
        path = os.path.join(temp_dir, f'test_{i:03d}.jpg')
        img.save(path, 'JPEG')
        image_paths.append(path)
    
    return image_paths, temp_dir

# 测试流水线池基本功能
def test_pipeline_pool_basic():
    """测试流水线池基本功能"""
    print("\n=== 测试流水线池基本功能 ===")
    
    try:
        # 创建测试图像
        image_paths, temp_dir = create_test_images()
        output_dir = os.path.join(temp_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"创建了 {len(image_paths)} 张测试图像")
        
        # 创建流水线池
        pool = PipelinePool(min_pipelines=1, max_pipelines=2)
        print(f"流水线池初始化完成，当前流水线数量: {pool.pipeline_count}")
        
        # 测试任务分配
        config = {
            'output_folder': output_dir,
            'page_num': 1,
            'layout': 'grid',
            'flip_mode': 0,
            'is_reversed': False
        }
        
        # 添加任务
        print("添加测试任务...")
        pool.add_task(image_paths, config)
        
        # 等待处理完成
        print("等待处理完成...")
        start_time = time.time()
        while not pool.is_processing_complete():
            time.sleep(1)
            elapsed = time.time() - start_time
            if elapsed > 30:  # 30秒超时
                print("处理超时，强制退出")
                break
        
        elapsed_time = time.time() - start_time
        print(f"处理完成，耗时: {elapsed_time:.2f}秒")
        
        # 测试调试信息
        debug_info = pool.get_debug_info()
        print(f"调试信息获取成功，流水线数量: {debug_info['pool_info']['pipeline_count']}")
        
        # 停止流水线池
        print("停止流水线池...")
        pool.stop()
        
        print("\n=== 测试成功完成 ===")
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时文件
        import shutil
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir)
            print("清理临时文件完成")

# 主测试函数
def main():
    print("开始测试流水线池...")
    test_pipeline_pool_basic()

if __name__ == "__main__":
    main()
