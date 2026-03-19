import psutil
import os
import time
from typing import Dict, Tuple, Optional

class ResourceMonitor:
    """系统资源监控器"""
    
    def __init__(self):
        """初始化资源监控器"""
        self.cpu_count = os.cpu_count() or 1
        self.total_memory = psutil.virtual_memory().total
        self.min_memory_threshold = 500 * 1024 * 1024  # 500MB
        self.max_cpu_usage_threshold = 80.0  # 80%
        self.max_memory_usage_threshold = 70.0  # 70%
    
    def get_system_resources(self) -> Dict:
        """获取当前系统资源使用情况"""
        try:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            available_memory = memory.available
            
            return {
                'cpu_count': self.cpu_count,
                'cpu_usage': cpu_usage,
                'memory_total': self.total_memory,
                'memory_usage': memory_usage,
                'memory_available': available_memory,
                'memory_available_mb': available_memory / (1024 * 1024)
            }
        except Exception as e:
            print(f"获取系统资源失败: {e}")
            return {
                'cpu_count': self.cpu_count,
                'cpu_usage': 0.0,
                'memory_total': self.total_memory,
                'memory_usage': 0.0,
                'memory_available': self.total_memory,
                'memory_available_mb': self.total_memory / (1024 * 1024)
            }
    
    def get_optimal_workers(self, task_type: str = 'io') -> int:
        """根据系统资源获取最佳线程数"""
        resources = self.get_system_resources()
        
        # 基础线程数
        base_workers = min(8, resources['cpu_count'])
        
        # 根据内存情况调整
        memory_factor = 1.0
        if resources['memory_available_mb'] < 1024:  # 小于1GB可用内存
            memory_factor = 0.5
        elif resources['memory_available_mb'] < 2048:  # 小于2GB可用内存
            memory_factor = 0.75
        elif resources['memory_available_mb'] > 4096:  # 大于4GB可用内存
            memory_factor = 1.25
        elif resources['memory_available_mb'] > 6144:  # 大于6GB可用内存
            memory_factor = 1.5            
        elif resources['memory_available_mb'] > 8192:  # 大于8GB可用内存
            memory_factor = 1.75 


        # 根据CPU使用情况调整
        cpu_factor = 1.0
        if resources['cpu_usage'] > 70:
            cpu_factor = 0.75
        elif resources['cpu_usage'] > 50:
            cpu_factor = 0.9
        
        # 根据任务类型调整
        task_factor = 1.0
        if task_type == 'io':
            task_factor = 1.5  # I/O密集型任务可以使用更多线程
        elif task_type == 'cpu':
            task_factor = 1.0  # CPU密集型任务线程数不宜超过CPU核心数
        
        # 计算最终线程数
        workers = int(base_workers * memory_factor * cpu_factor * task_factor)
        
        # 确保线程数在合理范围内
        return max(1, min(16, workers))
    
    def is_system_overloaded(self) -> bool:
        """检查系统是否过载"""
        resources = self.get_system_resources()
        
        # 检查CPU使用率
        if resources['cpu_usage'] > self.max_cpu_usage_threshold:
            return True
        
        # 检查内存使用率
        if resources['memory_usage'] > self.max_memory_usage_threshold:
            return True
        
        # 检查可用内存
        if resources['memory_available'] < self.min_memory_threshold:
            return True
        
        return False
    
    def get_adjusted_batch_size(self, base_batch_size: int) -> int:
        """根据系统资源调整批处理大小"""
        resources = self.get_system_resources()
        
        # 根据可用内存调整批处理大小
        if resources['memory_available_mb'] < 1024:
            return max(1, base_batch_size // 2)
        elif resources['memory_available_mb'] > 8192:
            return min(base_batch_size * 2, 100)
        else:
            return base_batch_size

# 创建全局资源监控器实例
resource_monitor = ResourceMonitor()