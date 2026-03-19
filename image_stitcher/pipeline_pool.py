import threading
import time
from typing import List, Dict, Optional
from .pipeline import ImagePipeline
from .resource_monitor import resource_monitor

class PipelinePool:
    """流水线池管理类"""
    
    def __init__(self, min_pipelines: int = 1, max_pipelines: int = 4):
        """初始化流水线池"""
        self.min_pipelines = min_pipelines
        self.max_pipelines = max_pipelines
        self.pipelines: List[ImagePipeline] = []
        self.pipeline_count = 0
        self.stop_event = threading.Event()
        self.task_queue = []
        self.current_index = 0
        self.lock = threading.Lock()
        
        # 初始化流水线
        self._initialize_pipelines()
        
        # 启动监控线程（非守护线程，确保可以正常关闭）
        self.monitor_thread = threading.Thread(target=self._monitor_pool)
        self.monitor_thread.start()
    
    def _initialize_pipelines(self):
        """初始化流水线实例"""
        # 根据系统资源计算初始流水线数量
        initial_count = self._calculate_optimal_pipelines()
        for i in range(initial_count):
            self._add_pipeline()
    
    def _calculate_optimal_pipelines(self) -> int:
        """根据系统资源计算最佳流水线数量"""
        resources = resource_monitor.get_system_resources()
        cpu_count = resources['cpu_count']
        memory_available = resources['memory_available_mb']
        
        # 每个流水线至少需要2个CPU核心和1GB内存
        max_by_cpu = max(1, cpu_count // 2)
        max_by_memory = max(1, int(memory_available // 2048))
        
        return min(self.max_pipelines, max(self.min_pipelines, min(max_by_cpu, max_by_memory)))
    
    def _add_pipeline(self):
        """添加一个新的流水线实例"""
        if self.pipeline_count >= self.max_pipelines:
            return
        
        try:
            pipeline = ImagePipeline()
            with self.lock:
                pipeline_id = len(self.pipelines)
                pipeline.id = pipeline_id
                self.pipelines.append(pipeline)
                self.pipeline_count += 1
            print(f"[INFO] 流水线池: 添加新流水线实例 (ID: {pipeline_id})，当前总数: {self.pipeline_count}")
        except Exception as e:
            print(f"[ERROR] 流水线池: 添加流水线失败: {e}")
    
    def _remove_pipeline(self):
        """移除一个流水线实例"""
        if self.pipeline_count <= self.min_pipelines:
            return
        
        try:
            with self.lock:
                if self.pipelines:
                    pipeline = self.pipelines.pop()
                    self.pipeline_count -= 1
                    # 停止流水线
                    pipeline.shutdown()
            print(f"[INFO] 流水线池: 移除流水线实例，当前总数: {self.pipeline_count}")
        except Exception as e:
            print(f"[ERROR] 流水线池: 移除流水线失败: {e}")
    
    def add_task(self, image_paths: List[str], config: Dict):
        """添加任务到流水线池"""
        if not self.pipelines:
            print("[ERROR] 流水线池: 无可用流水线实例")
            return
        
        # 使用轮询策略分配任务
        pipeline = self._get_next_pipeline()
        pipeline.add_task(image_paths, config)
    
    def _get_next_pipeline(self) -> ImagePipeline:
        """获取下一个可用的流水线（轮询策略）"""
        with self.lock:
            if self.current_index >= len(self.pipelines):
                self.current_index = 0
            pipeline = self.pipelines[self.current_index]
            self.current_index += 1
            return pipeline
    
    def _get_least_loaded_pipeline(self) -> ImagePipeline:
        """获取负载最小的流水线（负载均衡策略）"""
        with self.lock:
            if not self.pipelines:
                raise Exception("无可用流水线")
            
            # 计算每个流水线的负载（队列长度总和）
            pipeline_loads = []
            for i, pipeline in enumerate(self.pipelines):
                total_load = (
                    pipeline.load_queue.qsize() +
                    pipeline.preprocess_queue.qsize() +
                    pipeline.stitch_queue.qsize() +
                    pipeline.postprocess_queue.qsize() +
                    pipeline.save_queue.qsize()
                )
                pipeline_loads.append((total_load, i))
            
            # 选择负载最小的流水线
            pipeline_loads.sort()
            return self.pipelines[pipeline_loads[0][1]]
    
    def is_processing_complete(self) -> bool:
        """检查所有流水线是否处理完成"""
        with self.lock:
            for pipeline in self.pipelines:
                if not pipeline.is_processing_complete():
                    return False
            return True
    
    def wait_completion(self, timeout: Optional[float] = None):
        """等待所有流水线处理完成"""
        start_time = time.time()
        while not self.stop_event.is_set():
            if self.is_processing_complete():
                break
            if timeout and time.time() - start_time > timeout:
                break
            time.sleep(0.5)
    
    def _monitor_pool(self):
        """监控流水线池状态并调整大小"""
        import sys
        print("[INFO] 启动流水线池监控线程")
        while True:
            # 首先检查停止标志
            if self.stop_event.is_set():
                print("[INFO] 检测到停止标志，流水线池监控线程退出")
                break
            
            # 检查Python解释器是否正在关闭
            if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                break
            
            try:
                # 检查系统资源和负载
                resources = resource_monitor.get_system_resources()
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    print("[INFO] 检测到停止标志，流水线池监控线程退出")
                    break
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                    break
                
                cpu_usage = resources['cpu_usage']
                memory_usage = resources['memory_usage']
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    print("[INFO] 检测到停止标志，流水线池监控线程退出")
                    break
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                    break
                
                # 计算当前总负载
                total_load = 0
                with self.lock:
                    for pipeline in self.pipelines:
                        # 再次检查停止标志和解释器状态
                        if self.stop_event.is_set():
                            print("[INFO] 检测到停止标志，流水线池监控线程退出")
                            return
                        if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                            print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                            return
                        total_load += (
                            pipeline.load_queue.qsize() +
                            pipeline.preprocess_queue.qsize() +
                            pipeline.stitch_queue.qsize() +
                            pipeline.postprocess_queue.qsize() +
                            pipeline.save_queue.qsize()
                        )
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    print("[INFO] 检测到停止标志，流水线池监控线程退出")
                    break
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                    break
                
                # 根据负载和系统资源调整流水线数量
                if total_load > 50 and cpu_usage < 70 and memory_usage < 70:
                    # 再次检查停止标志和解释器状态
                    if self.stop_event.is_set():
                        print("[INFO] 检测到停止标志，流水线池监控线程退出")
                        return
                    if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                        print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                        return
                    # 负载高且系统资源充足，增加流水线
                    self._add_pipeline()
                elif total_load < 10 and self.pipeline_count > self.min_pipelines:
                    # 再次检查停止标志和解释器状态
                    if self.stop_event.is_set():
                        print("[INFO] 检测到停止标志，流水线池监控线程退出")
                        return
                    if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                        print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                        return
                    # 负载低，减少流水线
                    self._remove_pipeline()
                
                # 每1秒检查一次，但当stop_event被设置时立即退出
                if self.stop_event.wait(1):
                    print("[INFO] 检测到停止标志，流水线池监控线程退出")
                    break
            except Exception as e:
                # 检查是否是解释器关闭导致的异常
                if "interpreter shutdown" in str(e):
                    print("[INFO] 检测到解释器正在关闭，流水线池监控线程退出")
                    break
                # 检查是否是停止标志导致的异常
                if "stop_event" in str(e):
                    print("[INFO] 检测到停止事件，流水线池监控线程退出")
                    break
                print(f"[ERROR] 流水线池监控错误: {e}")
                # 发生错误时也使用wait，确保可以及时响应停止事件
                if self.stop_event.wait(1):
                    print("[INFO] 检测到停止标志，流水线池监控线程退出")
                    break
        print("[INFO] 流水线池监控线程已退出")
    
    def stop(self):
        """停止所有流水线"""
        print("[INFO] 开始关闭流水线池...")
        
        # 1. 设置停止标志，通知所有线程退出
        self.stop_event.set()
        print("[INFO] 已设置停止标志")
        
        # 2. 等待监控线程退出（优先于流水线关闭）
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            try:
                # 设置一个合理的超时时间，避免无限等待
                print("[INFO] 等待流水线池监控线程退出...")
                self.monitor_thread.join(timeout=2.0)
                print("[INFO] 流水线池监控线程已退出")
            except Exception as e:
                print(f"[ERROR] 等待监控线程结束失败: {e}")
        
        # 3. 等待所有流水线关闭
        print("[INFO] 开始关闭所有流水线...")
        with self.lock:
            for i, pipeline in enumerate(self.pipelines):
                print(f"[INFO] 关闭流水线实例 {i}...")
                pipeline.shutdown()
                print(f"[INFO] 流水线实例 {i} 已关闭")
        
        print("[INFO] 流水线池: 所有流水线已停止")
    
    def get_debug_info(self):
        """获取流水线池的调试信息"""
        import psutil
        import os
        import threading
        
        # 获取当前进程信息
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=0)
        
        # 获取所有流水线的信息
        pipeline_infos = []
        with self.lock:
            for i, pipeline in enumerate(self.pipelines):
                try:
                    pipeline_info = {
                        'id': i,
                        'is_alive': True,
                        'queue_status': {
                            'load_queue': pipeline.load_queue.qsize(),
                            'preprocess_queue': pipeline.preprocess_queue.qsize(),
                            'stitch_queue': pipeline.stitch_queue.qsize(),
                            'postprocess_queue': pipeline.postprocess_queue.qsize(),
                            'save_queue': pipeline.save_queue.qsize()
                        },
                        'thread_pool_sizes': pipeline.thread_pool_sizes
                    }
                    pipeline_infos.append(pipeline_info)
                except Exception as e:
                    pipeline_infos.append({
                        'id': i,
                        'is_alive': False,
                        'error': str(e)
                    })
        
        # 构建调试信息
        debug_info = {
            'process_info': {
                'pid': os.getpid(),
                'cpu_percent': cpu_percent,
                'memory_rss_mb': memory_info.rss / (1024 * 1024),
                'memory_vms_mb': memory_info.vms / (1024 * 1024)
            },
            'pool_info': {
                'pipeline_count': self.pipeline_count,
                'min_pipelines': self.min_pipelines,
                'max_pipelines': self.max_pipelines
            },
            'pipeline_infos': pipeline_infos,
            'queue_status': {
                'load_queue': sum(p.get('queue_status', {}).get('load_queue', 0) for p in pipeline_infos),
                'preprocess_queue': sum(p.get('queue_status', {}).get('preprocess_queue', 0) for p in pipeline_infos),
                'stitch_queue': sum(p.get('queue_status', {}).get('stitch_queue', 0) for p in pipeline_infos),
                'postprocess_queue': sum(p.get('queue_status', {}).get('postprocess_queue', 0) for p in pipeline_infos),
                'save_queue': sum(p.get('queue_status', {}).get('save_queue', 0) for p in pipeline_infos),
                'total_load_queue': sum(p.get('queue_status', {}).get('load_queue', 0) for p in pipeline_infos),
                'total_preprocess_queue': sum(p.get('queue_status', {}).get('preprocess_queue', 0) for p in pipeline_infos),
                'total_stitch_queue': sum(p.get('queue_status', {}).get('stitch_queue', 0) for p in pipeline_infos),
                'total_postprocess_queue': sum(p.get('queue_status', {}).get('postprocess_queue', 0) for p in pipeline_infos),
                'total_save_queue': sum(p.get('queue_status', {}).get('save_queue', 0) for p in pipeline_infos)
            },
            'thread_status': {
                'monitor_thread': getattr(self, 'monitor_thread', threading.Thread()).is_alive()
            },
            'executor_status': {
                'load_workers': 0,
                'preprocess_workers': 0,
                'stitch_workers': 0,
                'postprocess_workers': 0,
                'save_workers': 0
            },
            'dynamic_info': {
                'batch_mode_enabled': False,
                'is_high_load': False,
                'last_adjustment_time': 0
            },
            'active_threads': threading.active_count()
        }
        
        # 如果有流水线，从第一个流水线获取更详细的信息
        if pipeline_infos and pipeline_infos[0].get('is_alive', False):
            with self.lock:
                if self.pipelines:
                    first_pipeline = self.pipelines[0]
                    # 获取线程池状态
                    if hasattr(first_pipeline, 'thread_pool_sizes'):
                        thread_pool_sizes = first_pipeline.thread_pool_sizes
                        debug_info['executor_status'] = {
                            'load_workers': thread_pool_sizes.get('load', 0),
                            'preprocess_workers': thread_pool_sizes.get('preprocess', 0),
                            'stitch_workers': thread_pool_sizes.get('stitch', 0),
                            'postprocess_workers': thread_pool_sizes.get('postprocess', 0),
                            'save_workers': thread_pool_sizes.get('save', 0)
                        }
                    # 获取动态信息
                    if hasattr(first_pipeline, 'load_status'):
                        debug_info['dynamic_info'] = first_pipeline.load_status
        
        return debug_info

# 创建全局流水线池实例
pipeline_pool = PipelinePool()
