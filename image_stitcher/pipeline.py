import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import os
import time
from collections import deque
from .resource_monitor import resource_monitor

# 日志工具函数
def log_message(level, message):
    """记录日志消息"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    print(f"[{timestamp}] [{level.upper()}] {message}")

def log_debug(message):
    """记录调试级别日志"""
    log_message('debug', message)

def log_info(message):
    """记录信息级别日志"""
    log_message('info', message)

def log_warning(message):
    """记录警告级别日志"""
    log_message('warning', message)

def log_error(message):
    """记录错误级别日志"""
    log_message('error', message)

class ImagePipeline:
    """图像流水线处理"""
    
    def __init__(self):
        log_info("初始化图像流水线...")
        
        # 创建五个阶段的队列
        self.load_queue = queue.Queue(maxsize=8)      # 加载队列
        self.preprocess_queue = queue.Queue(maxsize=2)  # 预处理队列
        self.stitch_queue = queue.Queue(maxsize=1)     # 拼接队列
        self.postprocess_queue = queue.Queue(maxsize=1)  # 后处理队列
        self.save_queue = queue.Queue(maxsize=1)       # 保存队列
        
        log_info(f"队列初始化完成: load={self.load_queue.maxsize}, preprocess={self.preprocess_queue.maxsize}, "
                 f"stitch={self.stitch_queue.maxsize}, postprocess={self.postprocess_queue.maxsize}, "
                 f"save={self.save_queue.maxsize}")
        
        # 根据系统资源动态调整线程池大小
        log_info("根据系统资源计算最佳线程数...")
        load_workers = resource_monitor.get_optimal_workers(task_type='io')
        preprocess_workers = resource_monitor.get_optimal_workers(task_type='cpu')
        stitch_workers = resource_monitor.get_optimal_workers(task_type='cpu')
        postprocess_workers = resource_monitor.get_optimal_workers(task_type='cpu')
        save_workers = resource_monitor.get_optimal_workers(task_type='io')
        
        log_info(f"计算线程数: load={load_workers}, preprocess={preprocess_workers}, "
                 f"stitch={stitch_workers}, postprocess={postprocess_workers}, "
                 f"save={save_workers}")
        
        # 创建线程池
        self.load_executor = ThreadPoolExecutor(max_workers=load_workers)
        self.preprocess_executor = ThreadPoolExecutor(max_workers=preprocess_workers)
        self.stitch_executor = ThreadPoolExecutor(max_workers=stitch_workers)
        self.postprocess_executor = ThreadPoolExecutor(max_workers=postprocess_workers)
        self.save_executor = ThreadPoolExecutor(max_workers=save_workers)
        
        # 线程池大小记录
        self.thread_pool_sizes = {
            'load': load_workers,
            'preprocess': preprocess_workers,
            'stitch': stitch_workers,
            'postprocess': postprocess_workers,
            'save': save_workers
        }
        
        # 停止标志
        self.stop_event = threading.Event()
        
        # 监控数据
        self.metrics = {
            'queue_lengths': {
                'load': deque(maxlen=100),  # 最近100次记录
                'preprocess': deque(maxlen=100),
                'stitch': deque(maxlen=100),
                'postprocess': deque(maxlen=100),
                'save': deque(maxlen=100)
            },
            'process_times': {
                'load': deque(maxlen=100),
                'preprocess': deque(maxlen=100),
                'stitch': deque(maxlen=100),
                'postprocess': deque(maxlen=100),
                'save': deque(maxlen=100)
            },
            'last_update_time': time.time()
        }
        
        # 负载状态
        self.load_status = {
            'is_high_load': False,
            'batch_mode_enabled': False,
            'last_adjustment_time': 0
        }
        
        # 启动监控线程（非守护线程，确保可以正常关闭）
        self.monitor_thread = threading.Thread(target=self._monitor_pipeline)
        
        # 启动线程池工作线程
        log_info("启动各阶段工作线程...")
        self._start_worker_threads()
        
        # 启动监控线程
        log_info("启动监控线程...")
        self.monitor_thread.start()
        log_info("图像流水线初始化完成！")
    
    def _start_worker_threads(self):
        """启动各阶段的工作线程"""
        # 启动预处理工作线程
        log_info(f"启动预处理工作线程: {self.thread_pool_sizes['preprocess']}个")
        for _ in range(self.thread_pool_sizes['preprocess']):
            self.preprocess_executor.submit(self._preprocess_worker)
        
        # 启动拼接工作线程
        log_info(f"启动拼接工作线程: {self.thread_pool_sizes['stitch']}个")
        for _ in range(self.thread_pool_sizes['stitch']):
            self.stitch_executor.submit(self._stitch_worker)
        
        # 启动后处理工作线程
        log_info(f"启动后处理工作线程: {self.thread_pool_sizes['postprocess']}个")
        for _ in range(self.thread_pool_sizes['postprocess']):
            self.postprocess_executor.submit(self._postprocess_worker)
        
        # 启动保存工作线程
        log_info(f"启动保存工作线程: {self.thread_pool_sizes['save']}个")
        for _ in range(self.thread_pool_sizes['save']):
            self.save_executor.submit(self._save_worker)
    
    def add_task(self, image_paths, config):
        """添加任务到流水线"""
        # 计算有效路径数量（非None）
        valid_count = sum(1 for path in image_paths if path is not None)
        log_info(f"提交任务到流水线: {len(image_paths)}个图像(有效{valid_count}个), 布局={config.get('layout', 'grid')}, "
                 f"页面={config.get('page_num', 1)}")
        # 提交加载任务（整个页面的图像一起处理）
        future = self.load_executor.submit(self._load_worker, image_paths, config)
        return future
    
    def _load_worker(self, image_paths, config):
        """第一阶段：加载图像"""
        if self.stop_event.is_set():
            log_debug("加载工作线程收到停止信号")
            return
        
        start_time = time.time()
        try:
            log_debug(f"开始加载任务: {len(image_paths)}个图像")
            # 将整个页面的图像路径和配置传递给预处理阶段
            # 这样可以在预处理阶段一起处理所有图像，然后在拼接阶段进行拼接
            self.load_queue.put((image_paths, config))
            process_time = time.time() - start_time
            log_debug(f"加载任务完成，耗时: {process_time:.2f}秒, 队列长度: {self.load_queue.qsize()}")
            # 记录处理时间
            self.metrics['process_times']['load'].append(process_time)
        except Exception as e:
            log_error(f"加载图像失败: {e}")
    
    def _preprocess_worker(self):
        """第二阶段：预处理图像"""
        while not self.stop_event.is_set():
            try:
                # 从加载队列中获取任务（整个页面的图像）
                image_paths, config = self.load_queue.get(timeout=1)
                
                start_time = time.time()
                log_debug(f"开始预处理任务: {len(image_paths)}个图像, 目标尺寸={config.get('target_w')}x{config.get('target_h')}")
                
                # 执行预处理
                try:
                    from concurrent.futures import ThreadPoolExecutor
                    from .image_processor import load_and_enhance_image
                    
                    # 提取配置参数
                    target_w = config.get('target_w')
                    target_h = config.get('target_h')
                    enhance_enabled = config.get('enhance_enabled', False)
                    brightness = config.get('brightness', 0)
                    contrast = config.get('contrast', 0)
                    sharpness = config.get('sharpness', 0)
                    
                    # 定义单图像处理函数
                    def process_single_image(path):
                        # 处理None占位符
                        if path is None:
                            return None
                        try:
                            if enhance_enabled:
                                img = load_and_enhance_image(path, target_w, target_h, brightness, contrast, sharpness)
                            else:
                                from .image_processor import fast_load_and_resize
                                img = fast_load_and_resize(path, target_w, target_h)
                            return img
                        except Exception as e:
                            log_error(f"处理图像失败 {path}: {e}")
                            return None
                    
                    # 动态计算最佳线程数
                    import os
                    cpu_count = os.cpu_count() or 4
                    # 根据图像数量和CPU核心数计算最佳线程数
                    # 确保每个线程至少处理1个图像，最多使用所有CPU核心
                    optimal_workers = min(cpu_count, max(1, len(image_paths)))
                    
                    # 并行处理图像
                    processed_images = []
                    
                    # 使用ThreadPoolExecutor并行处理
                    with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                        # 使用map函数并行处理所有图像
                        processed_images = list(executor.map(process_single_image, image_paths))
                    
                    # 将预处理后的图像列表传递给拼接阶段
                    self.preprocess_queue.put((processed_images, image_paths, config))
                    process_time = time.time() - start_time
                    log_debug(f"预处理任务完成，耗时: {process_time:.2f}秒, 队列长度: {self.preprocess_queue.qsize()}")
                    # 记录处理时间
                    self.metrics['process_times']['preprocess'].append(process_time)
                    
                    # 提交新的工作任务到线程池
                    if not self.stop_event.is_set():
                        self.preprocess_executor.submit(self._preprocess_worker)
                except Exception as e:
                    log_error(f"预处理图像失败: {e}")
                    # 即使发生错误，也要提交新的工作任务
                    if not self.stop_event.is_set():
                        self.preprocess_executor.submit(self._preprocess_worker)
                finally:
                    self.load_queue.task_done()
            except queue.Empty:
                # 队列为空时，继续提交新的工作任务
                if not self.stop_event.is_set():
                    self.preprocess_executor.submit(self._preprocess_worker)
                continue
    
    def _stitch_worker(self):
        """第三阶段：拼接图像"""
        while not self.stop_event.is_set():
            try:
                # 从预处理队列中获取任务（整个页面的图像）
                processed_images, image_paths, config = self.preprocess_queue.get(timeout=1)
                
                start_time = time.time()
                layout = config.get('layout', 'grid')
                # 计算有效图像数量（非None）
                valid_count = sum(1 for img in processed_images if img is not None)
                log_debug(f"开始拼接任务: {len(processed_images)}个图像(有效{valid_count}个), 布局={layout}")
                
                # 执行拼接
                try:
                    from PIL import Image
                    import numpy as np
                    
                    # NumPy 拼接函数
                    def stitch_grid_numpy(images, rows, cols, h_spacing, v_spacing, margins, target_w, target_h):
                        """使用 NumPy 进行网格拼接"""
                        margin_top, margin_bottom, margin_left, margin_right = margins
                        
                        # 计算画布大小
                        canvas_width = margin_left + margin_right + cols * target_w + (cols - 1) * h_spacing
                        canvas_height = margin_top + margin_bottom + rows * target_h + (rows - 1) * v_spacing
                        
                        # 创建画布
                        canvas = np.full((canvas_height, canvas_width, 3), 255, dtype=np.uint8)
                        
                        # 拼接图像
                        for idx, img in enumerate(images[:rows * cols]):
                            # 跳过None值（空位占位符）
                            if img is None:
                                continue
                            row, col = divmod(idx, cols)
                            x = margin_left + col * (target_w + h_spacing)
                            y = margin_top + row * (target_h + v_spacing)
                            
                            # 转换为 NumPy 数组
                            img_np = np.array(img)
                            h, w = img_np.shape[:2]
                            
                            # 粘贴到画布
                            canvas[y:y+h, x:x+w] = img_np
                        
                        return Image.fromarray(canvas)
                    
                    def stitch_horizontal_numpy(images):
                        """使用 NumPy 进行水平拼接"""
                        if not images:
                            return None
                        
                        # 过滤掉None值
                        valid_images = [img for img in images if img is not None]
                        if not valid_images:
                            return None
                        
                        # 计算画布大小
                        total_width = sum(img.width for img in valid_images)
                        max_height = max(img.height for img in valid_images)
                        
                        # 创建画布
                        canvas = np.full((max_height, total_width, 3), 255, dtype=np.uint8)
                        
                        # 拼接图像
                        current_pos = 0
                        for img in valid_images:
                            img_np = np.array(img)
                            h, w = img_np.shape[:2]
                            canvas[:h, current_pos:current_pos+w] = img_np
                            current_pos += w
                        
                        return Image.fromarray(canvas)
                    
                    def stitch_vertical_numpy(images):
                        """使用 NumPy 进行垂直拼接"""
                        if not images:
                            return None
                        
                        # 过滤掉None值
                        valid_images = [img for img in images if img is not None]
                        if not valid_images:
                            return None
                        
                        # 计算画布大小
                        max_width = max(img.width for img in valid_images)
                        total_height = sum(img.height for img in valid_images)
                        
                        # 创建画布
                        canvas = np.full((total_height, max_width, 3), 255, dtype=np.uint8)
                        
                        # 拼接图像
                        current_pos = 0
                        for img in valid_images:
                            img_np = np.array(img)
                            h, w = img_np.shape[:2]
                            canvas[current_pos:current_pos+h, :w] = img_np
                            current_pos += h
                        
                        return Image.fromarray(canvas)
                    
                    # 根据配置执行不同的拼接逻辑
                    if layout == 'grid':
                        # 网格布局拼接逻辑
                        rows = config.get('rows', 2)
                        cols = config.get('cols', 2)
                        h_spacing = config.get('h_spacing', 30)
                        v_spacing = config.get('v_spacing', 30)
                        margin_top = config.get('margin_top', 0)
                        margin_bottom = config.get('margin_bottom', 0)
                        margin_left = config.get('margin_left', 0)
                        margin_right = config.get('margin_right', 0)
                        target_w = config.get('target_w', 800)
                        target_h = config.get('target_h', 600)
                        
                        log_debug(f"网格拼接配置: {rows}x{cols}, 间距={h_spacing}x{v_spacing}, 边距={margin_top},{margin_bottom},{margin_left},{margin_right}")
                        
                        # 使用 NumPy 拼接
                        result = stitch_grid_numpy(
                            processed_images, rows, cols, h_spacing, v_spacing,
                            (margin_top, margin_bottom, margin_left, margin_right),
                            target_w, target_h
                        )
                        
                        # 找到第一个非None的路径用于保存
                        first_valid_path = None
                        for path in image_paths:
                            if path is not None:
                                first_valid_path = path
                                break
                        
                        # 根据翻转模式决定直接传递给保存阶段还是后处理阶段
                        flip_mode = config.get('flip_mode', 0)
                        if flip_mode == 0:
                            # 翻转模式为0，直接传递给保存阶段
                            log_debug("翻转模式为0，直接传递给保存阶段")
                            self.save_queue.put((result, first_valid_path, config))
                        else:
                            # 翻转模式不为0，传递给后处理阶段
                            self.stitch_queue.put((result, first_valid_path, config))
                        
                    elif layout == 'horizontal':
                        # 水平布局拼接逻辑
                        if not processed_images:
                            log_warning("水平拼接任务没有图像")
                            continue
                        
                        # 检查是否有有效图像（非None）
                        valid_images = [img for img in processed_images if img is not None]
                        if not valid_images:
                            log_warning("水平拼接任务没有有效图像")
                            continue
                        
                        # 使用 NumPy 拼接
                        result = stitch_horizontal_numpy(processed_images)
                        if result:
                            # 找到第一个非None的路径用于保存
                            first_valid_path = None
                            for path in image_paths:
                                if path is not None:
                                    first_valid_path = path
                                    break
                            
                            # 根据翻转模式决定直接传递给保存阶段还是后处理阶段
                            flip_mode = config.get('flip_mode', 0)
                            if flip_mode == 0:
                                # 翻转模式为0，直接传递给保存阶段
                                log_debug("翻转模式为0，直接传递给保存阶段")
                                self.save_queue.put((result, first_valid_path, config))
                            else:
                                # 翻转模式不为0，传递给后处理阶段
                                self.stitch_queue.put((result, first_valid_path, config))
                        
                    elif layout == 'vertical':
                        # 垂直布局拼接逻辑
                        if not processed_images:
                            log_warning("垂直拼接任务没有图像")
                            continue
                        
                        # 检查是否有有效图像（非None）
                        valid_images = [img for img in processed_images if img is not None]
                        if not valid_images:
                            log_warning("垂直拼接任务没有有效图像")
                            continue
                        
                        # 使用 NumPy 拼接
                        result = stitch_vertical_numpy(processed_images)
                        if result:
                            # 找到第一个非None的路径用于保存
                            first_valid_path = None
                            for path in image_paths:
                                if path is not None:
                                    first_valid_path = path
                                    break
                            
                            # 根据翻转模式决定直接传递给保存阶段还是后处理阶段
                            flip_mode = config.get('flip_mode', 0)
                            if flip_mode == 0:
                                # 翻转模式为0，直接传递给保存阶段
                                log_debug("翻转模式为0，直接传递给保存阶段")
                                self.save_queue.put((result, first_valid_path, config))
                            else:
                                # 翻转模式不为0，传递给后处理阶段
                                self.stitch_queue.put((result, first_valid_path, config))
                        
                    else:
                        # 默认处理 - 网格布局
                        if not processed_images:
                            log_warning("默认拼接任务没有图像")
                            continue
                        
                        # 检查是否有有效图像（非None）
                        valid_images = [img for img in processed_images if img is not None]
                        if not valid_images:
                            log_warning("默认拼接任务没有有效图像")
                            continue
                        
                        # 简单拼接为网格
                        rows = 2
                        cols = (len(processed_images) + 1) // 2
                        
                        # 找到第一个非None的图像来获取尺寸
                        first_valid_img = None
                        first_valid_path = None
                        for idx, img in enumerate(processed_images):
                            if img is not None:
                                first_valid_img = img
                                first_valid_path = image_paths[idx]
                                break
                        
                        if first_valid_img is None:
                            log_warning("默认拼接任务没有有效图像")
                            continue
                        
                        target_w = first_valid_img.width
                        target_h = first_valid_img.height
                        
                        log_debug(f"默认网格拼接: {rows}x{cols}, 尺寸={target_w}x{target_h}")
                        
                        # 使用 NumPy 拼接
                        result = stitch_grid_numpy(
                            processed_images, rows, cols, 0, 0,
                            (0, 0, 0, 0),
                            target_w, target_h
                        )
                        
                        # 根据翻转模式决定直接传递给保存阶段还是后处理阶段
                        flip_mode = config.get('flip_mode', 0)
                        if flip_mode == 0:
                            # 翻转模式为0，直接传递给保存阶段
                            log_debug("翻转模式为0，直接传递给保存阶段")
                            self.save_queue.put((result, first_valid_path, config))
                        else:
                            # 翻转模式不为0，传递给后处理阶段
                            self.stitch_queue.put((result, first_valid_path, config))
                    
                    process_time = time.time() - start_time
                    log_debug(f"拼接任务完成，耗时: {process_time:.2f}秒, 队列长度: {self.stitch_queue.qsize()}")
                    # 记录处理时间
                    self.metrics['process_times']['stitch'].append(process_time)
                    
                    # 提交新的工作任务到线程池
                    if not self.stop_event.is_set():
                        self.stitch_executor.submit(self._stitch_worker)
                except Exception as e:
                    log_error(f"拼接图像失败: {e}")
                    # 即使发生错误，也要提交新的工作任务
                    if not self.stop_event.is_set():
                        self.stitch_executor.submit(self._stitch_worker)
                finally:
                    # 释放processed_images资源
                    if processed_images:
                        # 尝试关闭每个图像
                        for img in processed_images:
                            try:
                                if img is not None:
                                    img.close()
                            except:
                                pass
                        # 清空列表
                        processed_images = None
                    self.preprocess_queue.task_done()
            except queue.Empty:
                # 队列为空时，继续提交新的工作任务
                if not self.stop_event.is_set():
                    self.stitch_executor.submit(self._stitch_worker)
                continue
    
    def _postprocess_worker(self):
        """第四阶段：后处理图像"""
        while not self.stop_event.is_set():
            try:
                # 从拼接队列中获取任务
                img, path, config = self.stitch_queue.get(timeout=1)
                
                start_time = time.time()
                flip_mode = config.get('flip_mode', 0)
                log_debug(f"开始后处理任务: 翻转模式={flip_mode}")
                
                # 执行后处理
                try:
                    # 当翻转模式为0时，直接跳过该阶段
                    if flip_mode == 0:
                        log_debug("翻转模式为0，跳过后处理阶段")
                        # 直接传递给保存阶段
                        self.save_queue.put((img, path, config))
                    else:
                        from PIL import Image
                        
                        # 应用翻转
                        if flip_mode == 1:  # FLIP_VERTICAL
                            log_debug("应用上下翻转")
                            img = img.transpose(Image.FLIP_TOP_BOTTOM)
                        elif flip_mode == 2:  # FLIP_HORIZONTAL
                            log_debug("应用左右翻转")
                            img = img.transpose(Image.FLIP_LEFT_RIGHT)
                        
                        # 将后处理后的图像传递给保存阶段
                        self.save_queue.put((img, path, config))
                    
                    process_time = time.time() - start_time
                    log_debug(f"后处理任务完成，耗时: {process_time:.2f}秒, 队列长度: {self.save_queue.qsize()}")
                    # 记录处理时间
                    self.metrics['process_times']['postprocess'].append(process_time)
                    
                    # 提交新的工作任务到线程池
                    if not self.stop_event.is_set():
                        self.postprocess_executor.submit(self._postprocess_worker)
                except Exception as e:
                    log_error(f"后处理图像失败 {path}: {e}")
                    # 释放图像资源
                    try:
                        img.close()
                    except:
                        pass
                    # 即使发生错误，也要提交新的工作任务
                    if not self.stop_event.is_set():
                        self.postprocess_executor.submit(self._postprocess_worker)
                finally:
                    self.stitch_queue.task_done()
            except queue.Empty:
                # 队列为空时，继续提交新的工作任务
                if not self.stop_event.is_set():
                    self.postprocess_executor.submit(self._postprocess_worker)
                continue
    
    def _save_worker(self):
        """第五阶段：保存图像"""
        # 导入异步保存器
        from .async_saver import async_saver
        
        while not self.stop_event.is_set():
            try:
                # 从保存队列中获取任务
                img, path, config = self.save_queue.get(timeout=1)
                
                # 检查是否已停止
                if self.stop_event.is_set():
                    self.save_queue.task_done()
                    break
                
                start_time = time.time()
                output_folder = config.get('output_folder')
                page_num = config.get('page_num', 1)
                layout = config.get('layout', 'grid')
                flip_mode = config.get('flip_mode', 0)
                
                # 根据布局类型和翻转模式生成保存路径
                if layout == 'horizontal' or layout == 'vertical':
                    # 水平或垂直布局
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
                
                log_debug(f"开始保存任务: {os.path.basename(save_path)}")
                
                # 执行异步保存
                try:
                    # 使用异步保存器保存图像
                    async_saver.save(img, save_path, "JPEG", quality=90, optimize=True, progressive=True)
                    
                    process_time = time.time() - start_time
                    log_debug(f"保存任务提交完成，耗时: {process_time:.2f}秒, 保存路径: {os.path.basename(save_path)}")
                    # 记录处理时间
                    self.metrics['process_times']['save'].append(process_time)
                    
                    # 提交新的工作任务到线程池
                    if not self.stop_event.is_set():
                        self.save_executor.submit(self._save_worker)
                except Exception as e:
                    log_error(f"保存图像失败 {save_path}: {e}")
                    # 即使发生错误，也要提交新的工作任务
                    if not self.stop_event.is_set():
                        self.save_executor.submit(self._save_worker)
                finally:
                    self.save_queue.task_done()
            except queue.Empty:
                # 队列为空时，继续提交新的工作任务
                if not self.stop_event.is_set():
                    self.save_executor.submit(self._save_worker)
                continue
    
    def _monitor_pipeline(self):
        """监控流水线状态并自动调整"""
        log_info("启动流水线监控线程")
        import sys
        while True:
            # 首先检查停止标志
            if self.stop_event.is_set():
                log_info("检测到停止标志，监控线程退出")
                break
                
            # 检查Python解释器是否正在关闭
            if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                log_info("检测到解释器正在关闭，监控线程退出")
                break
                
            try:
                # 收集队列长度
                self._collect_queue_lengths()
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    log_info("检测到停止标志，监控线程退出")
                    break
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    log_info("检测到解释器正在关闭，监控线程退出")
                    break
                
                # 检查负载并调整
                self._check_load_and_adjust()
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    log_info("检测到停止标志，监控线程退出")
                    break
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    log_info("检测到解释器正在关闭，监控线程退出")
                    break
                
                # 检查批处理模式
                self._check_batch_mode()
                
                # 每0.5秒检查一次，但当stop_event被设置时立即退出
                self.stop_event.wait(0.5)
            except Exception as e:
                # 检查是否是解释器关闭导致的异常
                if "interpreter shutdown" in str(e):
                    log_info("检测到解释器正在关闭，监控线程退出")
                    break
                # 检查是否是停止标志导致的异常
                if "stop_event" in str(e):
                    log_info("检测到停止事件，监控线程退出")
                    break
                log_error(f"监控线程错误: {e}")
                # 发生错误时也使用wait，确保可以及时响应停止事件
                self.stop_event.wait(1)
        log_info("监控线程已退出")
    
    def _collect_queue_lengths(self):
        """收集队列长度数据"""
        current_time = time.time()
        
        # 获取各队列长度
        load_size = self.load_queue.qsize()
        preprocess_size = self.preprocess_queue.qsize()
        stitch_size = self.stitch_queue.qsize()
        postprocess_size = self.postprocess_queue.qsize()
        save_size = self.save_queue.qsize()
        
        # 记录各队列长度
        self.metrics['queue_lengths']['load'].append((current_time, load_size))
        self.metrics['queue_lengths']['preprocess'].append((current_time, preprocess_size))
        self.metrics['queue_lengths']['stitch'].append((current_time, stitch_size))
        self.metrics['queue_lengths']['postprocess'].append((current_time, postprocess_size))
        self.metrics['queue_lengths']['save'].append((current_time, save_size))
        
        # 更新最后更新时间
        self.metrics['last_update_time'] = current_time
        
        # 每10次检查打印一次队列状态
        if len(self.metrics['queue_lengths']['load']) % 10 == 0:
            log_debug(f"[流水线ID: {getattr(self, 'id', 'unknown')}] 队列状态: load={load_size}, preprocess={preprocess_size}, "
                     f"stitch={stitch_size}, postprocess={postprocess_size}, save={save_size}")
    
    def _check_load_and_adjust(self):
        """检查负载并调整线程池大小"""
        # 检查是否已设置停止标志
        if self.stop_event.is_set():
            return
        
        # 检查Python解释器是否正在关闭
        import sys
        if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
            return
        
        current_time = time.time()
        
        # 避免过于频繁的调整（至少30秒一次）
        if current_time - self.load_status['last_adjustment_time'] < 30:
            return
        
        # 再次检查停止标志和解释器状态
        if self.stop_event.is_set():
            return
        if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
            return
        
        # 检查各阶段的队列长度
        queue_status = {
            'load': self.load_queue.qsize(),
            'preprocess': self.preprocess_queue.qsize(),
            'stitch': self.stitch_queue.qsize(),
            'postprocess': self.postprocess_queue.qsize(),
            'save': self.save_queue.qsize()
        }
        
        # 再次检查停止标志和解释器状态
        if self.stop_event.is_set():
            return
        if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
            return
        
        log_info(f"检查负载状态: {queue_status}")
        
        # 检查是否需要调整线程池大小
        for stage, queue_size in queue_status.items():
            # 再次检查停止标志和解释器状态，避免在处理过程中应用关闭
            if self.stop_event.is_set():
                return
            
            # 检查Python解释器是否正在关闭
            if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                return
            
            # 如果队列长度超过阈值（队列容量的70%），考虑扩容
            # 使用队列的实际最大大小
            queue_max_size = {
                'load': self.load_queue.maxsize,
                'preprocess': self.preprocess_queue.maxsize,
                'stitch': self.stitch_queue.maxsize,
                'postprocess': self.postprocess_queue.maxsize,
                'save': self.save_queue.maxsize
            }[stage]
            
            threshold = queue_max_size * 0.7
            if queue_size > threshold:
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    return
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    return
                
                log_info(f"队列{stage}超过阈值({threshold})，当前长度: {queue_size}，准备扩容")
                self._resize_thread_pool(stage, 'increase')
            elif queue_size < queue_max_size * 0.3 and self.thread_pool_sizes[stage] > 1:
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    return
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    return
                
                # 如果队列长度很小且线程池大小大于1，考虑缩容
                log_info(f"队列{stage}低于缩容阈值({queue_max_size * 0.3})，当前长度: {queue_size}，准备缩容")
                self._resize_thread_pool(stage, 'decrease')
        
        # 再次检查停止标志和解释器状态
        if self.stop_event.is_set():
            return
        if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
            return
        
        # 更新最后调整时间
        self.load_status['last_adjustment_time'] = current_time
        log_debug(f"负载检查完成，下次检查时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time + 30))}")
    
    def _resize_thread_pool(self, stage, action):
        """调整线程池大小"""
        # 检查是否已设置停止标志
        if self.stop_event.is_set():
            return
        
        # 检查Python解释器是否正在关闭
        import sys
        if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
            return
        
        current_size = self.thread_pool_sizes[stage]
        
        if action == 'increase':
            # 最多增加到当前大小的2倍，且不超过系统最大线程数
            max_workers = resource_monitor.get_optimal_workers(
                task_type='io' if stage in ['load', 'save'] else 'cpu'
            ) * 2
            new_size = min(current_size * 2, max_workers)
        else:  # decrease
            # 最少保留1个线程
            new_size = max(current_size // 2, 1)
        
        # 再次检查停止标志和解释器状态
        if self.stop_event.is_set():
            return
        if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
            return
        
        if new_size != current_size:
            # 再次检查停止标志和解释器状态，避免在处理过程中应用关闭
            if self.stop_event.is_set():
                return
            
            # 检查Python解释器是否正在关闭
            if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                return
                
            log_info(f"调整{stage}线程池大小: {current_size} -> {new_size} (操作: {action})")
            
            try:
                # 获取旧线程池
                old_executor = getattr(self, f"{stage}_executor")
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    return
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    return
                
                # 创建新线程池
                new_executor = ThreadPoolExecutor(max_workers=new_size)
                setattr(self, f"{stage}_executor", new_executor)
                
                # 为新线程池初始化worker任务
                worker_method = getattr(self, f"_{stage}_worker")
                for i in range(new_size):
                    # 再次检查停止标志和解释器状态
                    if self.stop_event.is_set():
                        new_executor.shutdown(wait=False)
                        return
                    
                    # 检查Python解释器是否正在关闭
                    if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                        new_executor.shutdown(wait=False)
                        return
                        
                    new_executor.submit(worker_method)
                    log_debug(f"为{stage}线程池提交新的worker任务 {i+1}/{new_size}")
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    return
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    return
                
                # 更新线程池大小记录
                self.thread_pool_sizes[stage] = new_size
                log_info(f"{stage}线程池大小更新完成: {new_size}个线程")
                
                # 再次检查停止标志和解释器状态
                if self.stop_event.is_set():
                    # 即使检测到停止标志，也要关闭旧的线程池
                    log_info(f"检测到停止标志，关闭旧的{stage}线程池")
                    old_executor.shutdown(wait=False)
                    return
                if hasattr(sys, 'is_finalizing') and sys.is_finalizing():
                    # 即使解释器正在关闭，也要关闭旧的线程池
                    log_info(f"检测到解释器正在关闭，关闭旧的{stage}线程池")
                    old_executor.shutdown(wait=False)
                    return
                
                # 等待旧线程池完成当前任务后关闭
                log_debug(f"开始关闭旧的{stage}线程池")
                old_executor.shutdown(wait=False)  # 使用wait=False，避免等待所有任务完成
                log_debug(f"旧的{stage}线程池已关闭")
            except Exception as e:
                # 检查是否是解释器关闭导致的异常
                if "interpreter shutdown" in str(e):
                    log_info("检测到解释器正在关闭，调整线程池大小操作取消")
                    return
                # 检查是否是停止标志导致的异常
                if "stop_event" in str(e):
                    log_info("检测到停止事件，调整线程池大小操作取消")
                    return
                log_error(f"调整线程池大小失败: {e}")
    
    def _check_batch_mode(self):
        """检查是否需要启用批处理模式"""
        # 检查输入队列（load_queue）是否突增
        load_queue_size = self.load_queue.qsize()
        
        # 如果load队列长度超过10，启用批处理模式
        if load_queue_size > 10 and not self.load_status['batch_mode_enabled']:
            log_info(f"输入突增，启用批处理模式 (队列长度: {load_queue_size})")
            self.load_status['batch_mode_enabled'] = True
            self.load_status['is_high_load'] = True
            # 同时增加处理阶段的线程池大小，以应对批处理需求
            for stage in ['preprocess', 'stitch', 'postprocess', 'save']:
                if self.thread_pool_sizes[stage] < 4:  # 确保至少有4个线程处理批处理任务
                    log_info(f"为批处理模式调整{stage}线程池大小")
                    self._resize_thread_pool(stage, 'increase')
        elif load_queue_size < 5 and self.load_status['batch_mode_enabled']:
            # 如果load队列长度小于5，禁用批处理模式
            log_info(f"负载降低，禁用批处理模式 (队列长度: {load_queue_size})")
            self.load_status['batch_mode_enabled'] = False
            self.load_status['is_high_load'] = False
    
    def shutdown(self):
        """关闭流水线"""
        log_info("开始关闭流水线...")
        
        # 1. 设置停止标志，通知所有线程退出
        self.stop_event.set()
        log_info("已设置停止标志")
        
        # 2. 等待监控线程退出（优先于线程池关闭）
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            try:
                # 设置一个合理的超时时间，避免无限等待
                log_info("等待监控线程退出...")
                self.monitor_thread.join(timeout=2.0)
                log_info("监控线程已退出")
            except Exception as e:
                log_error(f"等待监控线程结束失败: {e}")
        
        # 3. 等待队列处理完成
        log_info(f"等待load队列处理完成，当前长度: {self.load_queue.qsize()}")
        self.load_queue.join()
        log_info("load队列处理完成")
        
        log_info(f"等待preprocess队列处理完成，当前长度: {self.preprocess_queue.qsize()}")
        self.preprocess_queue.join()
        log_info("preprocess队列处理完成")
        
        log_info(f"等待stitch队列处理完成，当前长度: {self.stitch_queue.qsize()}")
        self.stitch_queue.join()
        log_info("stitch队列处理完成")
        
        log_info(f"等待postprocess队列处理完成，当前长度: {self.postprocess_queue.qsize()}")
        self.postprocess_queue.join()
        log_info("postprocess队列处理完成")
        
        log_info(f"等待save队列处理完成，当前长度: {self.save_queue.qsize()}")
        self.save_queue.join()
        log_info("save队列处理完成")
        
        # 4. 等待异步保存任务完成
        log_info("等待异步保存任务完成...")
        from .async_saver import async_saver
        log_info(f"当前异步保存任务数量: {async_saver.get_task_count()}")
        async_saver.wait_completion()
        log_info("异步保存任务已完成")
        
        # 关闭异步保存器线程池
        try:
            async_saver.shutdown()
            log_info("异步保存器已关闭")
        except Exception as e:
            log_error(f"关闭异步保存器失败: {e}")
        
        # 5. 关闭线程池
        log_info("开始关闭线程池...")
        try:
            self.load_executor.shutdown(wait=False)  # 使用wait=False，避免等待所有任务完成
            log_info("load线程池已关闭")
        except Exception as e:
            log_error(f"关闭load线程池失败: {e}")
        
        try:
            self.preprocess_executor.shutdown(wait=False)  # 使用wait=False，避免等待所有任务完成
            log_info("preprocess线程池已关闭")
        except Exception as e:
            log_error(f"关闭preprocess线程池失败: {e}")
        
        try:
            self.stitch_executor.shutdown(wait=False)  # 使用wait=False，避免等待所有任务完成
            log_info("stitch线程池已关闭")
        except Exception as e:
            log_error(f"关闭stitch线程池失败: {e}")
        
        try:
            self.postprocess_executor.shutdown(wait=False)  # 使用wait=False，避免等待所有任务完成
            log_info("postprocess线程池已关闭")
        except Exception as e:
            log_error(f"关闭postprocess线程池失败: {e}")
        
        try:
            self.save_executor.shutdown(wait=False)  # 使用wait=False，避免等待所有任务完成
            log_info("save线程池已关闭")
        except Exception as e:
            log_error(f"关闭save线程池失败: {e}")
        
        log_info("流水线已完全关闭")
    
    def is_processing_complete(self):
        """检查是否所有任务都已处理完成"""
        # 检查所有队列是否为空
        queue_status = {
            'load': self.load_queue.qsize(),
            'preprocess': self.preprocess_queue.qsize(),
            'stitch': self.stitch_queue.qsize(),
            'postprocess': self.postprocess_queue.qsize(),
            'save': self.save_queue.qsize()
        }
        # 检查是否有异步保存任务
        from .async_saver import async_saver
        async_tasks = async_saver.get_task_count()
        
        # 所有队列为空且没有异步保存任务时，才认为处理完成
        all_queues_empty = all(size == 0 for size in queue_status.values())
        return all_queues_empty and async_tasks == 0

    def get_debug_info(self):
        """获取调试信息"""
        import psutil
        import os
        import threading
        
        # 获取当前进程信息
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        # 使用非阻塞方式获取 CPU 使用率
        cpu_percent = process.cpu_percent(interval=0)
        
        # 获取队列状态
        queue_status = {
            'load_queue': self.load_queue.qsize(),
            'preprocess_queue': self.preprocess_queue.qsize(),
            'stitch_queue': self.stitch_queue.qsize(),
            'postprocess_queue': self.postprocess_queue.qsize(),
            'save_queue': self.save_queue.qsize()
        }
        
        # 获取线程状态（监控线程）
        thread_status = {
            'monitor_thread': getattr(self, 'monitor_thread', threading.Thread()).is_alive()
        }
        
        # 获取线程池状态
        executor_status = {
            'load_workers': self.load_executor._max_workers,
            'preprocess_workers': self.preprocess_executor._max_workers,
            'stitch_workers': self.stitch_executor._max_workers,
            'postprocess_workers': self.postprocess_executor._max_workers,
            'save_workers': self.save_executor._max_workers
        }
        
        # 获取当前活跃线程数
        active_threads = threading.active_count()
        
        # 获取动态流水线信息
        dynamic_info = {
            'batch_mode_enabled': self.load_status.get('batch_mode_enabled', False),
            'is_high_load': self.load_status.get('is_high_load', False),
            'last_adjustment_time': self.load_status.get('last_adjustment_time', 0),
            'thread_pool_sizes': self.thread_pool_sizes
        }
        
        # 获取最近的队列长度趋势
        recent_queue_trends = {}
        for stage, data in self.metrics['queue_lengths'].items():
            if data:
                # 取最近10个数据点的平均值
                try:
                    recent_data = data[-10:] if len(data) >= 10 else data
                    avg_length = sum(point[1] for point in recent_data) / len(recent_data)
                    recent_queue_trends[stage] = round(avg_length, 2)
                except Exception as e:
                    recent_queue_trends[stage] = 0
            else:
                recent_queue_trends[stage] = 0
        
        return {
            'memory_mb': memory_info.rss / 1024 / 1024,
            'cpu_percent': cpu_percent,
            'queue_status': queue_status,
            'thread_status': thread_status,
            'executor_status': executor_status,
            'active_threads': active_threads,
            'dynamic_info': dynamic_info,
            'recent_queue_trends': recent_queue_trends
        }

