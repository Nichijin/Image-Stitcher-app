#!/usr/bin/env python3
# 测试应用程序的关闭过程

import sys
import os
import time

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_shutdown():
    """测试应用程序的关闭过程"""
    print("开始测试应用程序关闭过程...")
    
    try:
        # 导入并初始化应用程序
        from image_stitcher.pipeline_pool import pipeline_pool
        
        print("应用程序初始化完成")
        print(f"当前流水线数量: {pipeline_pool.pipeline_count}")
        
        # 等待几秒钟，让监控线程有机会运行
        print("等待3秒，让监控线程运行...")
        time.sleep(3)
        
        # 关闭应用程序
        print("\n开始关闭应用程序...")
        start_time = time.time()
        
        pipeline_pool.stop()
        
        end_time = time.time()
        print(f"\n应用程序关闭完成，耗时: {end_time - start_time:.2f}秒")
        
        # 等待几秒钟，观察是否有其他线程继续运行
        print("\n等待5秒，观察是否有其他线程继续运行...")
        time.sleep(5)
        
        print("\n测试完成！")
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_shutdown()
