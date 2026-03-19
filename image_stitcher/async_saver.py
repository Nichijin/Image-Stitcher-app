import threading
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import os

class AsyncSaver:
    """异步图像保存器"""
    
    def __init__(self, max_workers=4):
        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        # 保存任务数量
        self.task_count = 0
        # 锁
        self.lock = threading.Lock()
        # 线程池是否已关闭
        self._shutdown = False
    
    def save(self, image, path, format="JPEG", **params):
        """异步保存图像"""
        if not image:
            return
        
        # 检查线程池是否已关闭
        if self._shutdown:
            print(f"保存图像失败 {path}: 线程池已关闭，改为同步保存")
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                image.save(path, format, **params)
                image.close()
            except Exception as e:
                print(f"同步保存图像失败 {path}: {e}")
            return
        
        # 提交保存任务
        with self.lock:
            self.task_count += 1
        
        def save_task(img, p):
            try:
                # 确保目录存在
                os.makedirs(os.path.dirname(p), exist_ok=True)
                # 保存图像
                img.save(p, format, **params)
                # 释放图像资源
                img.close()
            except Exception as e:
                print(f"保存图像失败 {p}: {e}")
            finally:
                with self.lock:
                    self.task_count -= 1
        
        # 提交到线程池
        self.executor.submit(save_task, image, path)
    
    def wait_completion(self):
        """等待所有保存任务完成"""
        # 不关闭线程池，只是等待所有任务完成
        # 这里我们使用一个简单的轮询方式等待任务完成
        while self.get_task_count() > 0:
            import time
            time.sleep(0.1)
    
    def get_task_count(self):
        """获取当前任务数量"""
        with self.lock:
            return self.task_count
    
    def shutdown(self):
        """关闭异步保存器，关闭线程池"""
        try:
            self._shutdown = True  # 先设置标志，防止新任务提交
            self.executor.shutdown(wait=False)  # 使用wait=False，避免等待所有任务完成
            print("异步保存器线程池已关闭")
        except Exception as e:
            print(f"关闭异步保存器线程池失败: {e}")

# 创建全局异步保存器实例
async_saver = AsyncSaver(max_workers=4)