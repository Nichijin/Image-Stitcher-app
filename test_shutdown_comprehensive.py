#!/usr/bin/env python3
# 综合测试应用程序的关闭过程

import sys
import os
import time
import threading

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_shutdown_comprehensive():
    """综合测试应用程序的关闭过程"""
    print("开始综合测试应用程序关闭过程...")
    print(f"当前活跃线程数: {threading.active_count()}")
    
    try:
        # 导入并初始化应用程序
        from image_stitcher.pipeline_pool import pipeline_pool
        
        print(f"应用程序初始化完成")
        print(f"当前流水线数量: {pipeline_pool.pipeline_count}")
        print(f"初始化后活跃线程数: {threading.active_count()}")
        
        # 等待几秒钟，让监控线程有机会运行并执行一些负载检查
        print("\n等待5秒，让监控线程运行并执行负载检查...")
        for i in range(5):
            print(f"等待中... {i+1}/5")
            time.sleep(1)
            print(f"当前活跃线程数: {threading.active_count()}")
        
        # 关闭应用程序
        print("\n开始关闭应用程序...")
        start_time = time.time()
        
        # 记录关闭前的线程状态
        print(f"关闭前活跃线程数: {threading.active_count()}")
        
        # 调用stop方法关闭所有流水线
        pipeline_pool.stop()
        
        end_time = time.time()
        print(f"\n应用程序关闭完成，耗时: {end_time - start_time:.2f}秒")
        
        # 等待几秒钟，观察是否有线程继续运行
        print("\n等待10秒，观察是否有线程继续运行...")
        for i in range(10):
            current_threads = threading.active_count()
            print(f"等待中... {i+1}/10, 活跃线程数: {current_threads}")
            time.sleep(1)
        
        # 检查最终的线程状态
        final_threads = threading.active_count()
        print(f"\n最终活跃线程数: {final_threads}")
        
        if final_threads <= 2:  # 通常只有主线程和垃圾收集线程
            print("\n✅ 测试成功！所有线程都已正常退出")
            return True
        else:
            print("\n❌ 测试失败！仍有线程在运行")
            # 打印所有活跃线程的信息
            print("\n活跃线程信息:")
            for thread in threading.enumerate():
                print(f"  - {thread.name} (daemon: {thread.daemon})")
            return False
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理资源
        print("\n测试完成，清理资源...")

if __name__ == "__main__":
    success = test_shutdown_comprehensive()
    sys.exit(0 if success else 1)
