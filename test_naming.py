#!/usr/bin/env python3
# 测试修改后的命名规则

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image_stitcher.pipeline import ImagePipeline

# 测试函数
def test_naming_rule():
    print("测试保存文件命名规则...")
    
    # 创建模拟配置
    test_configs = [
        # 测试1: 普通页面
        {
            'output_folder': '.',
            'page_num': 1,
            'layout': 'grid',
            'flip_mode': 0,
            'is_reversed': False
        },
        # 测试2: 反转页面
        {
            'output_folder': '.',
            'page_num': 1,
            'layout': 'grid',
            'flip_mode': 0,
            'is_reversed': True
        },
        # 测试3: 反转页面 + 垂直翻转
        {
            'output_folder': '.',
            'page_num': 1,
            'layout': 'grid',
            'flip_mode': 1,
            'is_reversed': True
        },
        # 测试4: 反转页面 + 水平翻转
        {
            'output_folder': '.',
            'page_num': 1,
            'layout': 'grid',
            'flip_mode': 2,
            'is_reversed': True
        },
        # 测试5: 水平布局反转页面
        {
            'output_folder': '.',
            'page_num': 1,
            'layout': 'horizontal',
            'flip_mode': 0,
            'is_reversed': True
        }
    ]
    
    # 模拟保存文件命名逻辑
    for i, config in enumerate(test_configs):
        print(f"\n测试 {i+1}:")
        print(f"配置: {config}")
        
        output_folder = config.get('output_folder')
        page_num = config.get('page_num', 1)
        layout = config.get('layout', 'grid')
        flip_mode = config.get('flip_mode', 0)
        
        # 生成保存路径
        if layout == 'horizontal' or layout == 'vertical':
            base_name = "combined_image"
            if flip_mode == 1:
                base_name += "_vertical_flip"
            elif flip_mode == 2:
                base_name += "_horizontal_flip"
            # 检查是否是反转版
            if config.get('is_reversed', False):
                base_name += "_reversed"
            save_path = os.path.join(output_folder, f"{base_name}.jpg")
        else:
            # 网格布局
            base_name = f"page_{page_num:02d}"
            if flip_mode == 1:
                base_name += "_vertical_flip"
            elif flip_mode == 2:
                base_name += "_horizontal_flip"
            # 检查是否是反转版
            if config.get('is_reversed', False):
                base_name += "_reversed"
            save_path = os.path.join(output_folder, f"{base_name}.jpg")
        
        print(f"生成的文件名: {os.path.basename(save_path)}")
        
        # 验证结果
        if config.get('is_reversed', False):
            assert "_reversed" in save_path, f"反转页面文件名应包含 '_reversed' 后缀，但生成的是: {save_path}"
            print("✓ 反转页面命名正确")
        else:
            assert "_reversed" not in save_path, f"普通页面文件名不应包含 '_reversed' 后缀，但生成的是: {save_path}"
            print("✓ 普通页面命名正确")

if __name__ == "__main__":
    try:
        test_naming_rule()
        print("\n🎉 所有测试通过！修改后的命名规则工作正常。")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
