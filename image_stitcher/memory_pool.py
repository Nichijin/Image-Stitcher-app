import numpy as np
from collections import defaultdict
import psutil
import os

class MemoryPool:
    """内存池，用于管理和重用NumPy数组"""
    
    def __init__(self, max_per_key=20, max_total_size_gb=2.0):
        """初始化内存池
        
        Args:
            max_per_key: 每个键的最大数组数量
            max_total_size_gb: 内存池的最大总大小（GB）
        """
        # 按形状和 dtype 存储空闲数组
        self.pool = defaultdict(list)
        # 每个键的最大数组数量
        self.max_per_key = max_per_key
        # 内存池的最大总大小（字节）
        self.max_total_size = max_total_size_gb * 1024 * 1024 * 1024
        # 记录每个数组的大小
        self.array_sizes = {}
    
    def get(self, shape, dtype=np.uint8):
        """从池中获取一个数组，如果没有则创建"""
        key = (shape, dtype)
        if self.pool[key]:
            array = self.pool[key].pop()
            # 从大小记录中移除
            if id(array) in self.array_sizes:
                del self.array_sizes[id(array)]
            return array
        else:
            return np.empty(shape, dtype=dtype)
    
    def put(self, array):
        """将数组归还到池中"""
        if array is None:
            return
        
        # 计算数组大小
        array_size = array.nbytes
        key = (array.shape, array.dtype)
        
        # 检查内存池是否已满
        if self._get_current_size() + array_size > self.max_total_size:
            # 内存池已满，释放一些空间
            self._evict_oldest()
        
        # 限制每个键的池大小
        if len(self.pool[key]) < self.max_per_key:
            self.pool[key].append(array)
            # 记录数组大小
            self.array_sizes[id(array)] = array_size
    
    def _get_current_size(self):
        """获取当前内存池的大小"""
        return sum(self.array_sizes.values())
    
    def _evict_oldest(self):
        """释放最旧的数组"""
        # 简单策略：释放第一个遇到的非空队列中的第一个数组
        for key, arrays in self.pool.items():
            if arrays:
                array = arrays.pop(0)
                if id(array) in self.array_sizes:
                    del self.array_sizes[id(array)]
                break
    
    def clear(self):
        """清空内存池"""
        self.pool.clear()
        self.array_sizes.clear()
    
    def __len__(self):
        """返回池中数组的总数"""
        return sum(len(arrays) for arrays in self.pool.values())
    
    def get_stats(self):
        """获取内存池统计信息"""
        total_size = self._get_current_size()
        total_arrays = len(self)
        per_key_counts = {str(key): len(arrays) for key, arrays in self.pool.items() if arrays}
        
        return {
            'total_size_mb': total_size / (1024 * 1024),
            'total_arrays': total_arrays,
            'per_key_counts': per_key_counts,
            'max_per_key': self.max_per_key,
            'max_total_size_gb': self.max_total_size / (1024 * 1024 * 1024)
        }
    
    def optimize_for_shape(self, shape, dtype=np.uint8, count=5):
        """为特定形状预分配数组"""
        key = (shape, dtype)
        current_count = len(self.pool.get(key, []))
        
        # 预分配指定数量的数组
        for _ in range(max(0, count - current_count)):
            array = np.empty(shape, dtype=dtype)
            self.put(array)

# 创建全局内存池实例
memory_pool = MemoryPool()