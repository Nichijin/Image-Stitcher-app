import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import time
from PIL import Image, ImageTk, ImageEnhance, ImageDraw
import os
import gc
import json
import threading
import re
from datetime import datetime

from .config import get_current_config, save_config, load_config, validate_config
from .image_processor import process_image_batch, fast_load_and_resize, apply_enhancements
from .exporters import export_images
from .utils import get_image_paths_from_folder, estimate_pages
from .async_saver import async_saver
from .resource_monitor import resource_monitor
from .pipeline_pool import pipeline_pool
from .constants import (
    LAYOUT_HORIZONTAL, LAYOUT_VERTICAL, LAYOUT_GRID,
    FLIP_NONE, FLIP_VERTICAL, FLIP_HORIZONTAL,
    DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT,
    PROGRESS_WEIGHTS
)

# 内存监控功能
try:
    import psutil
    has_psutil = True
except ImportError:
    has_psutil = False
    print("提示: 安装 psutil 可启用内存监控功能")

def log_memory(tag=""):
    """记录当前内存使用情况"""
    if not has_psutil:
        return
    try:
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / 1024 / 1024
        print(f"[{tag}] 内存使用: {mem_mb:.1f} MB")
    except Exception as e:
        print(f"内存监控失败: {e}")


def main():
    root = tk.Tk()
    app = ImageStitcher(root)
    root.mainloop()


class ImageStitcher:
    def __init__(self, root):
        self.root = root
        self.root.title("智能图片拼接工具")
        self.root.geometry("700x920")

        # 创建 schemes 目录（用于保存方案）
        self.schemes_dir = "schemes"
        os.makedirs(self.schemes_dir, exist_ok=True)

        self.image_paths = []
        self.canvas_size = (DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT)

        # 图像增强参数（默认关闭）
        self.enhance_var = tk.BooleanVar(value=False)
        self.brightness_val = tk.DoubleVar(value=0)
        self.contrast_val = tk.DoubleVar(value=0)
        self.sharpness_val = tk.DoubleVar(value=0)

        # 拼接停止标志
        self.stop_flag = threading.Event()

        # 绑定窗口关闭事件以保存默认配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.setup_ui()
        self.load_config()  # 启动时加载上次默认配置
        
        # 启动系统资源监控更新
        self.update_resource_monitor()
        
        # 启动流水线调试信息监控
        self._update_debug_info()

    def setup_ui(self):
        # === 主窗口布局调整 ===
        # 创建主框架，分为滚动区域和底部固定区域
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)
        
        # === 滚动区域 ===
        # 创建画布和滚动条
        canvas = tk.Canvas(main_frame)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.config(yscrollcommand=scrollbar.set)
        
        # 创建滚动区域内的内容框架
        scrollable_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # 绑定滚动区域大小变化事件
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scrollable_frame.bind("<Configure>", on_frame_configure)
        
        # 绑定鼠标滚轮事件
        def on_mouse_wheel(event):
            # 对于不同操作系统，鼠标滚轮事件的处理方式不同
            if event.delta > 0:
                canvas.yview_scroll(-1, "units")
            else:
                canvas.yview_scroll(1, "units")
        canvas.bind_all("<MouseWheel>", on_mouse_wheel)
        
        # === 图片选择区域 ===
        frame_select = tk.LabelFrame(scrollable_frame, text="图片管理", padx=10, pady=10)
        frame_select.pack(pady=10, fill="x", padx=20)

        listbox_frame = tk.Frame(frame_select)
        listbox_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(listbox_frame, height=6)
        scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 双击预览单张图（带增强）
        self.listbox.bind("<Double-Button-1>", self.preview_single_image)

        btn_frame = tk.Frame(frame_select)
        btn_frame.pack(fill="x", pady=(10, 0))
        tk.Button(btn_frame, text="添加图片", command=self.add_images).pack(side="left", padx=5)
        tk.Button(btn_frame, text="选择文件夹", command=self.add_folder_images).pack(side="left", padx=5)
        tk.Button(btn_frame, text="移除选中", command=self.remove_selected).pack(side="left", padx=5)
        tk.Button(btn_frame, text="清空列表", command=self.clear_list, width=10).pack(side="left", padx=5)

        # === 输出设置区域 ===
        frame_canvas = tk.LabelFrame(scrollable_frame, text="输出设置", padx=10, pady=10)
        frame_canvas.pack(pady=10, fill="x", padx=20)

        dim_frame = tk.Frame(frame_canvas)
        dim_frame.pack(anchor="w", pady=2)
        tk.Label(dim_frame, text="画布尺寸:").pack(side="left")
        tk.Label(dim_frame, text="宽:").pack(side="left", padx=(10, 0))
        self.entry_canvas_width = tk.Entry(dim_frame, width=8)
        self.entry_canvas_width.insert(0, str(DEFAULT_CANVAS_WIDTH))
        self.entry_canvas_width.pack(side="left", padx=5)
        tk.Label(dim_frame, text="高:").pack(side="left", padx=(10, 0))
        self.entry_canvas_height = tk.Entry(dim_frame, width=8)
        self.entry_canvas_height.insert(0, str(DEFAULT_CANVAS_HEIGHT))
        self.entry_canvas_height.pack(side="left", padx=5)
        tk.Button(dim_frame, text="应用", command=self.set_canvas_size, width=6).pack(side="left", padx=10)

        a4_frame = tk.Frame(frame_canvas)
        a4_frame.pack(anchor="w", pady=5)
        self.a4_mode_var = tk.BooleanVar()
        self.landscape_var = tk.BooleanVar()
        tk.Checkbutton(a4_frame, text="A4 打印 (300 DPI)", variable=self.a4_mode_var, command=self.toggle_a4).pack(side="left")
        tk.Checkbutton(a4_frame, text="横向", variable=self.landscape_var, command=self.toggle_a4).pack(side="left", padx=(10, 0))

        # === 拼接规则区域 ===
        frame_rules = tk.LabelFrame(scrollable_frame, text="拼接规则", padx=10, pady=10)
        frame_rules.pack(pady=10, fill="x", padx=20)
        frame_rules.columnconfigure(0, weight=1)

        resize_frame = tk.Frame(frame_rules)
        resize_frame.grid(row=0, column=0, sticky="w", pady=2)
        self.resize_var = tk.BooleanVar(value=True)
        tk.Checkbutton(resize_frame, text="前置统一尺寸", variable=self.resize_var, command=self.toggle_resize).pack(side="left")
        tk.Label(resize_frame, text="目标宽:").pack(side="left", padx=(10, 0))
        self.entry_width = tk.Entry(resize_frame, width=8)
        self.entry_width.insert(0, "800")
        self.entry_width.pack(side="left", padx=5)
        tk.Label(resize_frame, text="高:").pack(side="left", padx=(10, 0))
        self.entry_height = tk.Entry(resize_frame, width=8)
        self.entry_height.insert(0, "600")
        self.entry_height.pack(side="left", padx=5)

        layout_frame = tk.Frame(frame_rules)
        layout_frame.grid(row=1, column=0, sticky="w", pady=5)
        tk.Label(layout_frame, text="布局方式:").pack(side="left")
        self.layout_var = tk.StringVar(value=LAYOUT_HORIZONTAL)
        combo = ttk.Combobox(layout_frame, textvariable=self.layout_var, values=[LAYOUT_HORIZONTAL, LAYOUT_VERTICAL, LAYOUT_GRID], state="readonly", width=10)
        combo.pack(side="left", padx=5)
        combo.bind('<<ComboboxSelected>>', self._on_layout_changed)

        # === 网格参数区域 ===
        self.grid_frame = tk.Frame(frame_rules, relief="groove", bd=1, padx=10, pady=10)
        grid_top = tk.Frame(self.grid_frame)
        grid_top.pack(anchor="w")

        tk.Label(grid_top, text="网格大小：   行:").pack(side="left")
        self.entry_rows = tk.Entry(grid_top, width=5); self.entry_rows.insert(0, "2"); self.entry_rows.pack(side="left", padx=2)
        tk.Label(grid_top, text="列:").pack(side="left", padx=(10, 0))
        self.entry_cols = tk.Entry(grid_top, width=5); self.entry_cols.insert(0, "2"); self.entry_cols.pack(side="left", padx=2)
        tk.Label(grid_top, text="H间距:").pack(side="left", padx=(10, 0))
        self.entry_h_spacing = tk.Entry(grid_top, width=5); self.entry_h_spacing.insert(0, "30"); self.entry_h_spacing.pack(side="left", padx=2)
        tk.Label(grid_top, text="V间距:").pack(side="left", padx=(10, 0))
        self.entry_v_spacing = tk.Entry(grid_top, width=5); self.entry_v_spacing.insert(0, "30"); self.entry_v_spacing.pack(side="left", padx=2)

        opt_frame = tk.Frame(grid_top)
        opt_frame.pack(side="right", padx=(20, 0))
        self.multi_page_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_frame, text="自动分页", variable=self.multi_page_var).pack(side="left")
        self.gen_row_reversed_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt_frame, text="生成行反转版", variable=self.gen_row_reversed_var).pack(side="left", padx=(10, 0))


        margin_frame = tk.Frame(self.grid_frame)
        margin_frame.pack(anchor="w", pady=(8, 0))
        for label, attr in [("页内边距：  上:", "margin_top"), ("下:", "margin_bottom"), ("左:", "margin_left"), ("右:", "margin_right")]:
            tk.Label(margin_frame, text=label).pack(side="left")
            entry = tk.Entry(margin_frame, width=5)
            entry.insert(0, "0")
            setattr(self, f"entry_{attr}", entry)
            entry.pack(side="left", padx=(0, 10))


        flip_frame = tk.Frame(self.grid_frame)
        flip_frame.pack(anchor="w", pady=(5, 0))
        tk.Label(flip_frame, text="整体翻转:").pack(side="left")
        self.flip_mode = tk.StringVar(value=FLIP_NONE)
        flip_combo = ttk.Combobox(
            flip_frame,
            textvariable=self.flip_mode,
            values=[FLIP_NONE, FLIP_VERTICAL, FLIP_HORIZONTAL],
            state="readonly",
            width=10
        )
        flip_combo.pack(side="left", padx=5)


        debug_frame = tk.Frame(self.grid_frame)
        debug_frame.pack(anchor="w", pady=(5, 0))
        self.show_grid_var = tk.BooleanVar()
        tk.Checkbutton(debug_frame, text="显示网格线（调试）", variable=self.show_grid_var).pack(side="left")

        recommend_frame = tk.Frame(self.grid_frame)
        recommend_frame.pack(anchor="w", pady=(10, 0))
        tk.Button(
            recommend_frame,
            text="🎯 根据图片尺寸推荐行列/间距",
            command=self.recommend_layout_from_image_size,
            font=("Arial", 8)
        ).pack(side="left", padx=5)
        tk.Button(
            recommend_frame,
            text="📐 根据行列/间距推荐图片尺寸",
            command=self.recommend_image_size_from_layout,
            font=("Arial", 8)
        ).pack(side="left", padx=5)

        self.grid_frame.grid(row=2, column=0, sticky="ew", pady=10)
        self.grid_frame.grid_remove()

        # === 图像增强区域（默认折叠）===
        frame_enhance = tk.LabelFrame(scrollable_frame, text="生成图像编辑", padx=10, pady=10)
        frame_enhance.pack(pady=5, fill="x", padx=20)

        enhance_switch_frame = tk.Frame(frame_enhance)
        enhance_switch_frame.pack(anchor="w")
        tk.Checkbutton(
            enhance_switch_frame,
            text="启用亮度/对比度/锐化调整",
            variable=self.enhance_var,
            command=lambda: self.enhance_frame.pack(fill="x", pady=(10,0)) if self.enhance_var.get() else self.enhance_frame.pack_forget()
        ).pack(side="left")

        self.enhance_frame = tk.Frame(frame_enhance)
        self.enhance_frame.pack(fill="x", pady=(10, 0))

        def create_scaled_scale(parent, label_text, from_val, to_val, variable, length=300):
            """创建带有吸附和阻尼效果的滑块"""
            frame = tk.Frame(parent)
            frame.pack(anchor="w", pady=2)
            tk.Label(frame, text=label_text, width=18).pack(side="left")
            
            # 保存原始值，用于实现阻尼效果
            last_value = [variable.get()]
            
            # 创建数值显示和输入框
            value_var = tk.StringVar(value=str(int(variable.get())))
            
            # 标记是否正在更新输入框，避免循环触发
            updating = False
            
            def update_value_display():
                """更新数值显示"""
                nonlocal updating
                if updating:
                    return
                updating = True
                try:
                    new_value = str(int(variable.get()))
                    # 只有当输入框的值与新值不同时才更新，避免无限循环
                    if value_var.get() != new_value:
                        value_var.set(new_value)
                finally:
                    updating = False
            
            # 为变量添加trace，当值变化时自动更新输入框
            def on_variable_change(*args):
                """处理变量变化"""
                update_value_display()
            
            variable.trace_add("write", on_variable_change)
            
            def on_entry_change(*args):
                """处理输入框变化"""
                nonlocal updating
                if updating:
                    return
                try:
                    # 尝试获取输入值
                    text = value_var.get()
                    if not text:
                        # 输入框为空时，不做处理
                        return
                    value = int(text)
                    # 确保值在范围内
                    value = max(from_val, min(to_val, value))
                    variable.set(value)
                except ValueError:
                    # 输入无效时，不做处理，等待用户输入完成
                    pass
            
            value_var.trace_add("write", on_entry_change)
            
            # 创建输入框
            entry = tk.Entry(frame, textvariable=value_var, width=6, justify="center")
            entry.pack(side="left", padx=5)
            
            # 绑定键盘事件
            def on_key_press(event):
                """处理键盘事件"""
                current_value = variable.get()
                if event.keysym == "Up":
                    new_value = min(to_val, current_value + 1)
                    variable.set(new_value)
                    update_value_display()
                elif event.keysym == "Down":
                    new_value = max(from_val, current_value - 1)
                    variable.set(new_value)
                    update_value_display()
                elif event.keysym == "PageUp":
                    new_value = min(to_val, current_value + 10)
                    variable.set(new_value)
                    update_value_display()
                elif event.keysym == "PageDown":
                    new_value = max(from_val, current_value - 10)
                    variable.set(new_value)
                    update_value_display()
                elif event.keysym == "Home":
                    variable.set(from_val)
                    update_value_display()
                elif event.keysym == "End":
                    variable.set(to_val)
                    update_value_display()
            
            entry.bind("<Up>", on_key_press)
            entry.bind("<Down>", on_key_press)
            entry.bind("<Prior>", on_key_press)  # PageUp
            entry.bind("<Next>", on_key_press)    # PageDown
            entry.bind("<Home>", on_key_press)
            entry.bind("<End>", on_key_press)
            
            def on_scale_change(value):
                value = int(float(value))
                
                # 吸附效果：当值接近0时，自动吸附到0
                if from_val < 0 and -1 < value < 1:
                    variable.set(0)
                    update_value_display()
                    return
                
                # 阻尼效果：当值接近0时，减慢变化速度
                if from_val < 0 and -10 <= value <= 10 and value != 0:
                    # 计算与0的距离，距离越近，阻尼越大
                    distance = abs(value)
                    damping_factor = 0.5  # 阻尼系数
                    
                    # 计算新值，加入阻尼
                    if value > 0:
                        new_value = max(1, int(value - damping_factor))
                    else:
                        new_value = min(-1, int(value + damping_factor))
                    
                    # 只有当新值与当前值不同时才更新，避免循环触发
                    if new_value != variable.get():
                        variable.set(new_value)
                        update_value_display()
                else:
                    variable.set(value)
                    update_value_display()
                
                last_value[0] = variable.get()
            
            scale = tk.Scale(frame, from_=from_val, to=to_val, resolution=1, 
                           orient="horizontal", variable=variable, 
                           length=length, command=on_scale_change)
            
            # 绑定鼠标滚轮事件
            def on_mouse_wheel(event):
                """处理鼠标滚轮事件"""
                current_value = variable.get()
                # 滚轮向上增加，向下减少
                delta = 1 if event.delta > 0 else -1
                # 按住Shift键时，调整幅度增大
                if event.state & 0x0001:  # Shift键
                    delta *= 10
                new_value = max(from_val, min(to_val, current_value + delta))
                variable.set(new_value)
                update_value_display()
                # 返回 "break" 阻止事件冒泡，避免页面滚动
                return "break"
            
            scale.bind("<MouseWheel>", on_mouse_wheel)
            entry.bind("<MouseWheel>", on_mouse_wheel)
            
            scale.pack(side="left")
            return frame
        
        # 创建带有吸附和阻尼效果的滑块
        create_scaled_scale(self.enhance_frame, "亮度 (-100–100):", -100, 100, self.brightness_val)
        create_scaled_scale(self.enhance_frame, "对比度 (-100–100):", -100, 100, self.contrast_val)
        create_scaled_scale(self.enhance_frame, "锐化 (0–100):", 0, 100, self.sharpness_val)
        
        # 添加重置按钮
        reset_frame = tk.Frame(self.enhance_frame)
        reset_frame.pack(anchor="w", pady=5)
        def reset_enhance_values():
            """重置所有增强参数为默认值"""
            self.brightness_val.set(0)
            self.contrast_val.set(0)
            self.sharpness_val.set(0)
        tk.Button(reset_frame, text="重置参数", command=reset_enhance_values, width=10).pack(side="left")

        self.enhance_frame.pack_forget()  # 初始隐藏

        # 添加一个占位框架，确保滚动区域有足够的高度
        placeholder_frame = tk.Frame(scrollable_frame, height=20)
        placeholder_frame.pack()

        # === 底部固定区域 ===
        # 底部固定框架
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(side="bottom", fill="x")
        
        # 调试信息监控面板
        self.debug_collapsed = True  # 默认折叠状态
        
        debug_frame = tk.LabelFrame(bottom_frame, text="", padx=5, pady=5)
        debug_frame.pack(pady=5, fill="x", padx=20)
        
        # 调试面板标题栏（包含隐藏/显示按钮）
        debug_header_frame = tk.Frame(debug_frame)
        debug_header_frame.pack(fill="x")
        
        # 标题文本
        title_label = tk.Label(debug_header_frame, text="流水线调试信息", font=('Arial', 10, 'bold'))
        title_label.pack(side="left")
        
        # 隐藏/显示按钮
        self.debug_toggle_btn = tk.Button(debug_header_frame, text="显示", command=self.toggle_debug_panel, width=8)
        self.debug_toggle_btn.pack(side="left", padx=10)
        
        # === 进度与操作区域 ===
        frame_progress = tk.LabelFrame(bottom_frame, text="状态", padx=10, pady=10)
        frame_progress.pack(pady=10, fill="x", padx=20)
        
        # 进度条和预计页数框架
        progress_frame = tk.Frame(frame_progress)
        progress_frame.pack(fill="x")
        
        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(progress_frame, variable=self.progress_var, length=600).pack(side="left", fill="x", expand=True)
        
        # 预计生成页数标签
        self.expected_pages_var = tk.StringVar(value="预计生成: 0 张")
        tk.Label(frame_progress, textvariable=self.expected_pages_var, anchor="e").pack(side="right", padx=(10, 0))
        
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(frame_progress, textvariable=self.status_var, anchor="w").pack(fill="x", pady=(5, 0))
        
        # 系统资源监控显示
        resource_frame = tk.Frame(frame_progress)
        resource_frame.pack(fill="x", pady=(5, 0))
        
        self.cpu_usage_var = tk.StringVar(value="CPU: 0%")
        self.memory_usage_var = tk.StringVar(value="内存: 0%")
        self.available_memory_var = tk.StringVar(value="可用: 0 MB")
        
        cpu_label = tk.Label(resource_frame, textvariable=self.cpu_usage_var, anchor="w")
        cpu_label.pack(side="left", padx=(0, 20))
        
        memory_label = tk.Label(resource_frame, textvariable=self.memory_usage_var, anchor="w")
        memory_label.pack(side="left", padx=(0, 20))
        
        available_label = tk.Label(resource_frame, textvariable=self.available_memory_var, anchor="w")
        available_label.pack(side="left")
        
        # 可折叠的调试信息内容
        self.debug_content_frame = tk.Frame(debug_frame)
        
        # 队列状态
        queue_frame = tk.Frame(self.debug_content_frame)
        queue_frame.pack(fill="x", pady=(0, 10))
        tk.Label(queue_frame, text="队列状态: ", font=('Arial', 10, 'bold')).pack(anchor="w")
        
        queue_status_frame = tk.Frame(queue_frame)
        queue_status_frame.pack(fill="x")
        
        self.queue_vars = {
            'load': tk.StringVar(value="0"),
            'preprocess': tk.StringVar(value="0"),
            'stitch': tk.StringVar(value="0"),
            'postprocess': tk.StringVar(value="0"),
            'save': tk.StringVar(value="0")
        }
        
        queue_labels = [
            ('加载队列:', 'load'),
            ('预处理队列:', 'preprocess'),
            ('拼接队列:', 'stitch'),
            ('后处理队列:', 'postprocess'),
            ('保存队列:', 'save')
        ]
        
        for label_text, key in queue_labels:
            frame = tk.Frame(queue_status_frame)
            frame.pack(side="left", padx=10)
            tk.Label(frame, text=label_text, font=('Arial', 9)).pack(anchor="w")
            tk.Label(frame, textvariable=self.queue_vars[key], font=('Arial', 9, 'bold')).pack(anchor="w")
        
        # 线程状态
        thread_frame = tk.Frame(self.debug_content_frame)
        thread_frame.pack(fill="x", pady=(0, 10))
        tk.Label(thread_frame, text="线程状态: ", font=('Arial', 10, 'bold')).pack(anchor="w")
        
        thread_status_frame = tk.Frame(thread_frame)
        thread_status_frame.pack(fill="x")
        
        self.thread_vars = {
            'preprocess': tk.StringVar(value="运行中"),
            'stitch': tk.StringVar(value="运行中"),
            'postprocess': tk.StringVar(value="运行中"),
            'save': tk.StringVar(value="运行中"),
            'load': tk.StringVar(value="流水线条数: 0")
        }
        
        thread_labels = [
            ('预处理线程:', 'preprocess'),
            ('拼接线程:', 'stitch'),
            ('后处理线程:', 'postprocess'),
            ('保存线程:', 'save'),
            ('流水线条数:', 'load')
        ]
        
        for label_text, key in thread_labels:
            frame = tk.Frame(thread_status_frame)
            frame.pack(side="left", padx=10)
            tk.Label(frame, text=label_text, font=('Arial', 9)).pack(anchor="w")
            tk.Label(frame, textvariable=self.thread_vars[key], font=('Arial', 9, 'bold')).pack(anchor="w")
        
        # 线程池状态
        executor_frame = tk.Frame(self.debug_content_frame)
        executor_frame.pack(fill="x")
        tk.Label(executor_frame, text="线程池状态: ", font=('Arial', 10, 'bold')).pack(anchor="w")
        
        executor_status_frame = tk.Frame(executor_frame)
        executor_status_frame.pack(fill="x")
        
        self.executor_vars = {
            'load': tk.StringVar(value="0"),
            'preprocess': tk.StringVar(value="0"),
            'stitch': tk.StringVar(value="0"),
            'postprocess': tk.StringVar(value="0"),
            'save': tk.StringVar(value="0")
        }
        
        executor_labels = [
            ('加载线程池:', 'load'),
            ('预处理线程池:', 'preprocess'),
            ('拼接线程池:', 'stitch'),
            ('后处理线程池:', 'postprocess'),
            ('保存线程池:', 'save')
        ]
        
        for label_text, key in executor_labels:
            frame = tk.Frame(executor_status_frame)
            frame.pack(side="left", padx=10)
            tk.Label(frame, text=label_text, font=('Arial', 9)).pack(anchor="w")
            tk.Label(frame, textvariable=self.executor_vars[key], font=('Arial', 9, 'bold')).pack(anchor="w")
        
        # 动态流水线信息
        dynamic_frame = tk.Frame(self.debug_content_frame)
        dynamic_frame.pack(fill="x", pady=(10, 0))
        tk.Label(dynamic_frame, text="动态流水线信息: ", font=('Arial', 10, 'bold')).pack(anchor="w")
        
        dynamic_info_frame = tk.Frame(dynamic_frame)
        dynamic_info_frame.pack(fill="x")
        
        self.dynamic_vars = {
            'batch_mode': tk.StringVar(value="禁用"),
            'load_status': tk.StringVar(value="正常"),
            'active_threads': tk.StringVar(value="0")
        }
        
        dynamic_labels = [
            ('批处理模式:', 'batch_mode'),
            ('负载状态:', 'load_status'),
            ('活跃线程数:', 'active_threads')
        ]
        
        for label_text, key in dynamic_labels:
            frame = tk.Frame(dynamic_info_frame)
            frame.pack(side="left", padx=10)
            tk.Label(frame, text=label_text, font=('Arial', 9)).pack(anchor="w")
            tk.Label(frame, textvariable=self.dynamic_vars[key], font=('Arial', 9, 'bold')).pack(anchor="w")
        
        # 进程信息
        process_frame = tk.Frame(self.debug_content_frame)
        process_frame.pack(fill="x", pady=(10, 0))
        tk.Label(process_frame, text="进程信息: ", font=('Arial', 10, 'bold')).pack(anchor="w")
        
        process_info_frame = tk.Frame(process_frame)
        process_info_frame.pack(fill="x")
        
        self.process_vars = {
            'cpu': tk.StringVar(value="0%"),
            'memory_rss': tk.StringVar(value="0 MB"),
            'memory_vms': tk.StringVar(value="0 MB")
        }
        
        process_labels = [
            ('进程CPU:', 'cpu'),
            ('物理内存:', 'memory_rss'),
            ('虚拟内存:', 'memory_vms')
        ]
        
        for label_text, key in process_labels:
            frame = tk.Frame(process_info_frame)
            frame.pack(side="left", padx=10)
            tk.Label(frame, text=label_text, font=('Arial', 9)).pack(anchor="w")
            tk.Label(frame, textvariable=self.process_vars[key], font=('Arial', 9, 'bold')).pack(anchor="w")
        
        # 流水线池详细信息
        pool_detail_frame = tk.Frame(self.debug_content_frame)
        pool_detail_frame.pack(fill="x", pady=(10, 0))
        tk.Label(pool_detail_frame, text="流水线池详细信息: ", font=('Arial', 10, 'bold')).pack(anchor="w")
        
        pool_detail_info_frame = tk.Frame(pool_detail_frame)
        pool_detail_info_frame.pack(fill="x")
        
        self.pool_detail_vars = {
            'min_pipelines': tk.StringVar(value="1"),
            'max_pipelines': tk.StringVar(value="4"),
            'active_threads': tk.StringVar(value="0")
        }
        
        pool_detail_labels = [
            ('最小流水线数:', 'min_pipelines'),
            ('最大流水线数:', 'max_pipelines'),
            ('活动线程数:', 'active_threads')
        ]
        
        for label_text, key in pool_detail_labels:
            frame = tk.Frame(pool_detail_info_frame)
            frame.pack(side="left", padx=10)
            tk.Label(frame, text=label_text, font=('Arial', 9)).pack(anchor="w")
            tk.Label(frame, textvariable=self.pool_detail_vars[key], font=('Arial', 9, 'bold')).pack(anchor="w")

        # === 操作按钮栏 ===
        btn_frame = tk.Frame(bottom_frame)
        btn_frame.pack(pady=10)
        self.btn_stitch = tk.Button(btn_frame, text="开始拼接", command=self.stitch_images, bg="#4CAF50", fg="white", font=("Arial",10,"bold"), width=12)
        self.btn_stitch.pack(side="left", padx=5)
        # 添加停止拼接按钮
        self.btn_stop = tk.Button(btn_frame, text="停止拼接", command=self.stop_stitch, bg="#f44336", fg="white", font=("Arial",10,"bold"), width=12)
        self.btn_stop.pack(side="left", padx=5)
        self.btn_preview = tk.Button(btn_frame, text="🔍 预览拼接", command=self.preview_stitch, bg="#FFC107", fg="black", font=("Arial",10,"bold"), width=12)
        self.btn_preview.pack(side="left", padx=5)
        tk.Button(btn_frame, text="💾 保存当前为方案...", command=self.save_current_as_scheme, bg="#2196F3", fg="white", width=16).pack(side="left", padx=5)
        tk.Button(btn_frame, text="📂 加载方案...", command=self.load_scheme, bg="#FF9800", fg="white", width=12).pack(side="left", padx=5)

    # ========================
    #   单张图实时预览（带增强）
    # ========================
    def _load_and_enhance_image(self, path, target_w, target_h):
        """加载并增强图像
        
        Args:
            path: 图像路径
            target_w: 目标宽度
            target_h: 目标高度
            
        Returns:
            处理后的图像
        """
        img = fast_load_and_resize(path, target_w, target_h)
        if self.enhance_var.get():
            img = apply_enhancements(img, self.brightness_val.get(), self.contrast_val.get(), self.sharpness_val.get())
        return img
    
    def preview_single_image(self, event=None):
        sel = self.listbox.curselection()
        if not sel or not self.image_paths:
            return
        idx = sel[0]
        path = self.image_paths[idx]
        try:
            img = self._load_and_enhance_image(path, 800, 600)

            win = tk.Toplevel(self.root)
            win.title(f"预览: {os.path.basename(path)}")
            ratio = min(600 / img.width, 600 / img.height, 1.0)
            preview = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(preview)
            label = tk.Label(win, image=photo)
            label.pack(padx=10, pady=10)
            win.photo = photo  # 防止被回收
            img.close()  # 及时关闭图像
        except Exception as e:
            messagebox.showerror("预览失败", f"无法打开图片：{e}")

    # ========================
    #   方案保存与加载
    # ========================

    def save_current_as_scheme(self):
        name = simpledialog.askstring("保存方案", "请输入方案名称：")
        if not name:
            return
        safe_name = self.sanitize_filename(name.strip())
        if not safe_name:
            messagebox.showwarning("无效名称", "方案名称不能为空或仅含非法字符")
            return

        filepath = os.path.join(self.schemes_dir, f"{safe_name}.json")
        if os.path.exists(filepath):
            if not messagebox.askyesno("覆盖确认", f"方案 '{safe_name}' 已存在，是否覆盖？"):
                return

        cfg = get_current_config(self)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("成功", f"方案已保存为：\nschemes/{safe_name}.json")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def load_scheme(self):
        files = [f for f in os.listdir(self.schemes_dir) if f.endswith(".json")]
        if not files:
            messagebox.showinfo("无方案", "暂无已保存的方案")
            return

        top = tk.Toplevel(self.root)
        top.title("选择方案")
        top.geometry("300x400")
        top.transient(self.root)
        top.grab_set()

        tk.Label(top, text="双击加载方案：").pack(pady=5)
        listbox = tk.Listbox(top)
        listbox.pack(fill="both", expand=True, padx=10, pady=5)
        for f in sorted(files):
            listbox.insert("end", f[:-5])

        def on_double_click(event):
            sel = listbox.curselection()
            if sel:
                name = listbox.get(sel[0])
                filepath = os.path.join(self.schemes_dir, f"{name}.json")
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    self.apply_config(cfg)
                    top.destroy()
                    messagebox.showinfo("成功", f"已加载方案：{name}")
                except Exception as e:
                    messagebox.showerror("加载失败", f"无法加载 {name}：{e}")
                    top.destroy()

        listbox.bind("<Double-1>", on_double_click)
        tk.Button(top, text="取消", command=top.destroy).pack(pady=10)

    def apply_config(self, cfg):
        try:
            self.layout_var.set(cfg.get("layout", LAYOUT_HORIZONTAL))
            if cfg.get("layout") == LAYOUT_GRID:
                self.grid_frame.grid()
            else:
                self.grid_frame.grid_remove()

            self.a4_mode_var.set(cfg.get("a4_mode", False))
            self.landscape_var.set(cfg.get("landscape", False))

            if not cfg.get("a4_mode", False):
                self.entry_canvas_width.delete(0, tk.END)
                self.entry_canvas_width.insert(0, str(cfg.get("canvas_width", DEFAULT_CANVAS_WIDTH)))
                self.entry_canvas_height.delete(0, tk.END)
                self.entry_canvas_height.insert(0, str(cfg.get("canvas_height", DEFAULT_CANVAS_HEIGHT)))
                self.set_canvas_size()

            self.resize_var.set(cfg.get("resize", True))
            self.entry_width.delete(0, tk.END)
            self.entry_width.insert(0, str(cfg.get("target_width", 800)))
            self.entry_height.delete(0, tk.END)
            self.entry_height.insert(0, str(cfg.get("target_height", 600)))
            self.toggle_resize()

            self.entry_rows.delete(0, tk.END)
            self.entry_rows.insert(0, str(cfg.get("rows", 2)))
            self.entry_cols.delete(0, tk.END)
            self.entry_cols.insert(0, str(cfg.get("cols", 2)))
            self.entry_h_spacing.delete(0, tk.END)
            self.entry_h_spacing.insert(0, str(cfg.get("h_spacing", 30)))
            self.entry_v_spacing.delete(0, tk.END)
            self.entry_v_spacing.insert(0, str(cfg.get("v_spacing", 30)))

            self.multi_page_var.set(cfg.get("multi_page", True))
            self.gen_row_reversed_var.set(cfg.get("gen_row_reversed", False))

            for attr in ["margin_top", "margin_bottom", "margin_left", "margin_right"]:
                entry = getattr(self, f"entry_{attr}")
                entry.delete(0, tk.END)
                entry.insert(0, str(cfg.get(attr, 50)))

            self.flip_mode.set(cfg.get("flip_mode", FLIP_NONE))
            self.show_grid_var.set(cfg.get("show_grid", False))

            # 图像增强
            self.enhance_var.set(cfg.get("enhance_enabled", False))
            self.brightness_val.set(cfg.get("brightness", 0))
            self.contrast_val.set(cfg.get("contrast", 0))
            self.sharpness_val.set(cfg.get("sharpness", 0))
            if cfg.get("enhance_enabled", False):
                self.enhance_frame.pack(fill="x", pady=(10, 0))
            else:
                self.enhance_frame.pack_forget()

            if cfg.get("a4_mode", False):
                self.toggle_a4()

            self.update_status()
        except Exception as e:
            messagebox.showerror("加载失败", f"方案数据损坏或版本不兼容：{e}")

    def load_config(self):
        try:
            with open("image_stitcher_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.apply_config(cfg)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
            pass

    def save_config(self):
        try:
            cfg = {
                "a4_mode": self.a4_mode_var.get(),
                "landscape": self.landscape_var.get(),
                "canvas_width": int(self.entry_canvas_width.get()) if not self.a4_mode_var.get() else 800,
                "canvas_height": int(self.entry_canvas_height.get()) if not self.a4_mode_var.get() else 600,

                "resize": self.resize_var.get(),
                "target_width": int(self.entry_width.get()) if self.resize_var.get() else 800,
                "target_height": int(self.entry_height.get()) if self.resize_var.get() else 600,

                "layout": self.layout_var.get(),

                "rows": int(self.entry_rows.get()),
                "cols": int(self.entry_cols.get()),
                "h_spacing": int(self.entry_h_spacing.get()),
                "v_spacing": int(self.entry_v_spacing.get()),

                "multi_page": self.multi_page_var.get(),
                "gen_row_reversed": self.gen_row_reversed_var.get(),

                "margin_top": int(self.entry_margin_top.get()),
                "margin_bottom": int(self.entry_margin_bottom.get()),
                "margin_left": int(self.entry_margin_left.get()),
                "margin_right": int(self.entry_margin_right.get()),

                "flip_mode": self.flip_mode.get(),
                "show_grid": self.show_grid_var.get(),

                # 图像增强
                "enhance_enabled": self.enhance_var.get(),
                "brightness": self.brightness_val.get(),
                "contrast": self.contrast_val.get(),
                "sharpness": self.sharpness_val.get(),
            }
            with open("image_stitcher_config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def toggle_debug_panel(self):
        """切换调试信息面板的显示/隐藏状态"""
        if self.debug_collapsed:
            # 显示面板
            self.debug_content_frame.pack(fill="x")
            self.debug_toggle_btn.config(text="隐藏")
            self.debug_collapsed = False
        else:
            # 隐藏面板
            self.debug_content_frame.pack_forget()
            self.debug_toggle_btn.config(text="显示")
            self.debug_collapsed = True
    
    def on_closing(self):
        # 保存配置（优先保存配置，避免资源释放后无法读取）
        self.save_config()
        
        # 停止流水线池
        try:
            from .pipeline_pool import pipeline_pool
            pipeline_pool.stop()
        except Exception as e:
            print(f"停止流水线池失败: {e}")
        
        # 销毁窗口
        self.root.destroy()

    # ========================
    #   图片管理
    # ========================

    def add_images(self):
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff"), ("所有文件", "*.*")]
        )
        if paths:
            for path in paths:
                if path not in self.image_paths:
                    self.image_paths.append(path)
                    self.listbox.insert(tk.END, os.path.basename(path))
            self.update_expected_pages()

    def add_folder_images(self):
        folder = filedialog.askdirectory(title="选择图片文件夹")
        if folder:
            paths = get_image_paths_from_folder(folder)
            if paths:
                for path in paths:
                    if path not in self.image_paths:
                        self.image_paths.append(path)
                        self.listbox.insert(tk.END, os.path.basename(path))
                self.update_expected_pages()
            else:
                messagebox.showinfo("提示", "文件夹中没有找到图片！")

    def remove_selected(self):
        sel = self.listbox.curselection()
        for idx in reversed(sel):
            self.listbox.delete(idx)
            del self.image_paths[idx]
        self.update_expected_pages()

    def clear_list(self):
        self.listbox.delete(0, tk.END)
        self.image_paths.clear()
        self.update_expected_pages()

    # ========================
    #   拼接与预览
    # ========================

    def update_expected_pages(self):
        # 只有在网格布局时才计算预计页数
        if self.layout_var.get() != LAYOUT_GRID:
            self.expected_pages_var.set("预计生成: N/A")
            return
        
        try:
            total_images = len(self.image_paths)
            if total_images == 0:
                self.expected_pages_var.set("预计生成: 0 张")
                return
            
            rows = int(self.entry_rows.get())
            cols = int(self.entry_cols.get())
            
            if rows <= 0 or cols <= 0:
                self.expected_pages_var.set("预计生成: N/A")
                return
            
            # 防止数值过大导致计算异常
            if rows > 1000 or cols > 1000:
                self.expected_pages_var.set("预计生成: N/A")
                return
            
            # 计算基本页数（向上取整）
            base_pages = (total_images + rows * cols - 1) // (rows * cols)
            
            # 如果勾选了生成反转版，则页数翻倍
            if self.gen_row_reversed_var.get():
                expected_pages = base_pages * 2
            else:
                expected_pages = base_pages
            
            self.expected_pages_var.set(f"预计生成: {expected_pages} 张")
        except ValueError:
            self.expected_pages_var.set("预计生成: N/A")

    def set_canvas_size(self):
        try:
            w, h = int(self.entry_canvas_width.get()), int(self.entry_canvas_height.get())
            if w > 0 and h > 0:
                self.canvas_size = (w, h)
        except ValueError:
            pass
        self.update_status()

    def toggle_a4(self):
        if self.a4_mode_var.get():
            w, h = (3508, 2480) if self.landscape_var.get() else (2480, 3508)
            self.canvas_size = (w, h)
            self.entry_canvas_width.delete(0, tk.END); self.entry_canvas_width.insert(0, str(w)); self.entry_canvas_width.config(state="disabled")
            self.entry_canvas_height.delete(0, tk.END); self.entry_canvas_height.insert(0, str(h)); self.entry_canvas_height.config(state="disabled")
            # 不再强制设置边距和间距，保留用户设置的值
            # for e in [self.entry_margin_top, self.entry_margin_bottom, self.entry_margin_left, self.entry_margin_right]:
            #     e.delete(0, tk.END); e.insert(0, "50")
            # self.entry_h_spacing.delete(0, tk.END); self.entry_h_spacing.insert(0, "30")
            # self.entry_v_spacing.delete(0, tk.END); self.entry_v_spacing.insert(0, "30")
            self.resize_var.set(False)
            self.toggle_resize()
        else:
            self.entry_canvas_width.config(state="normal")
            self.entry_canvas_height.config(state="normal")
            self.set_canvas_size()
        self.update_status()

    def toggle_resize(self):
        state = "normal" if self.resize_var.get() else "disabled"
        self.entry_width.config(state=state)
        self.entry_height.config(state=state)

    def _on_layout_changed(self, event=None):
        if self.layout_var.get() == LAYOUT_GRID:
            self.grid_frame.grid()
        else:
            self.grid_frame.grid_remove()
        self.update_expected_pages()

    def _on_param_changed(self, *args):
        self.update_expected_pages()

    def update_status(self):
        mode = "A4" if self.a4_mode_var.get() else "自定义"
        self.status_var.set(f"{len(self.image_paths)} 张图片 | {mode} | {self.canvas_size[0]}×{self.canvas_size[1]}")
        self.update_expected_pages()
    
    def update_resource_monitor(self):
        """更新系统资源监控数据"""
        try:
            # 获取系统资源使用情况
            resources = resource_monitor.get_system_resources()
            
            # 更新UI显示
            self.cpu_usage_var.set(f"CPU: {resources['cpu_usage']:.1f}%")
            self.memory_usage_var.set(f"内存: {resources['memory_usage']:.1f}%")
            self.available_memory_var.set(f"可用: {resources['memory_available_mb']:.0f} MB")
        except Exception as e:
            print(f"更新资源监控失败: {e}")
        
        # 设置定时器，1秒后再次更新
        self.root.after(1000, self.update_resource_monitor)

    def _update_debug_info(self):
        """更新流水线调试信息"""
        if not self.stop_flag.is_set():
            try:
                from .pipeline_pool import pipeline_pool
                # 获取调试信息
                debug_info = pipeline_pool.get_debug_info()
                
                # 更新队列状态
                queue_status = debug_info.get('queue_status', {})
                self.queue_vars['load'].set(queue_status.get('load_queue', 0))
                self.queue_vars['preprocess'].set(queue_status.get('preprocess_queue', 0))
                self.queue_vars['stitch'].set(queue_status.get('stitch_queue', 0))
                self.queue_vars['postprocess'].set(queue_status.get('postprocess_queue', 0))
                self.queue_vars['save'].set(queue_status.get('save_queue', 0))
                
                # 更新线程状态
                thread_status = debug_info.get('thread_status', {})
                thread_status_map = {True: "运行中", False: "已停止"}
                # 显示监控线程状态
                monitor_status = thread_status_map.get(thread_status.get('monitor_thread', False), "未知")
                # 线程池模式下，显示线程池模式
                self.thread_vars['preprocess'].set(f"线程池模式")
                self.thread_vars['stitch'].set(f"线程池模式")
                self.thread_vars['postprocess'].set(f"线程池模式")
                self.thread_vars['save'].set(f"监控线程: {monitor_status}")
                
                # 更新线程池状态
                executor_status = debug_info.get('executor_status', {})
                self.executor_vars['load'].set(executor_status.get('load_workers', 0))
                self.executor_vars['preprocess'].set(executor_status.get('preprocess_workers', 0))
                self.executor_vars['stitch'].set(executor_status.get('stitch_workers', 0))
                self.executor_vars['postprocess'].set(executor_status.get('postprocess_workers', 0))
                self.executor_vars['save'].set(executor_status.get('save_workers', 0))
                
                # 更新动态流水线信息
                dynamic_info = debug_info.get('dynamic_info', {})
                
                # 更新流水线条数
                pool_info = debug_info.get('pool_info', {})
                pipeline_count = pool_info.get('pipeline_count', 0)
                self.thread_vars['load'].set(f"流水线条数: {pipeline_count}")
                active_threads = debug_info.get('active_threads', 0)
                
                # 更新批处理模式
                batch_mode_enabled = dynamic_info.get('batch_mode_enabled', False)
                self.dynamic_vars['batch_mode'].set("启用" if batch_mode_enabled else "禁用")
                
                # 更新负载状态
                is_high_load = dynamic_info.get('is_high_load', False)
                self.dynamic_vars['load_status'].set("高负载" if is_high_load else "正常")
                
                # 更新活跃线程数
                self.dynamic_vars['active_threads'].set(str(active_threads))
                
                # 更新进程信息
                process_info = debug_info.get('process_info', {})
                cpu_percent = process_info.get('cpu_percent', 0)
                memory_rss_mb = process_info.get('memory_rss_mb', 0)
                memory_vms_mb = process_info.get('memory_vms_mb', 0)
                self.process_vars['cpu'].set(f"{cpu_percent:.1f}%")
                self.process_vars['memory_rss'].set(f"{memory_rss_mb:.0f} MB")
                self.process_vars['memory_vms'].set(f"{memory_vms_mb:.0f} MB")
                
                # 更新流水线池详细信息
                pool_info = debug_info.get('pool_info', {})
                min_pipelines = pool_info.get('min_pipelines', 1)
                max_pipelines = pool_info.get('max_pipelines', 4)
                self.pool_detail_vars['min_pipelines'].set(str(min_pipelines))
                self.pool_detail_vars['max_pipelines'].set(str(max_pipelines))
                self.pool_detail_vars['active_threads'].set(str(active_threads))
                
            except Exception as e:
                print(f"更新调试信息失败: {e}")
            finally:
                # 继续监控
                self.root.after(500, self._update_debug_info)

    def _disable_controls(self, disable=True):
        state = "disabled" if disable else "normal"
        # 禁用关键输入控件
        entries = [
            self.entry_canvas_width, self.entry_canvas_height,
            self.entry_width, self.entry_height,
            self.entry_rows, self.entry_cols,
            self.entry_h_spacing, self.entry_v_spacing,
            self.entry_margin_top, self.entry_margin_bottom,
            self.entry_margin_left, self.entry_margin_right,
        ]
        for e in entries:
            try:
                e.config(state=state)
            except:
                pass

        # 禁用按钮
        self.btn_stitch.config(state=state)
        # 其他按钮可按需添加

        # Checkbuttons 和 Combobox 不能直接 config(state)，但可通过变量控制逻辑
        # 此处简化：仅禁用按钮和输入框，用户仍可切换布局（不影响后台）

    def _stitch_page_from_paths(self, page_paths, target_w, target_h, enhance_enabled, brightness, contrast, sharpness, flip_mode, cfg):
        """从路径列表流式加载并拼接页面"""
        try:
            rows, cols = cfg['rows'], cfg['cols']
            h_spacing = cfg['h_spacing']
            v_spacing = cfg['v_spacing']
            margin = cfg['margin']
            mt, mb, ml, mr = margin
            cw, ch = self.canvas_size

            # 创建 NumPy 画布（更快的操作）
            import numpy as np
            canvas_np = np.full((ch, cw, 3), 255, dtype=np.uint8)

            # 批量处理图像
            processed_data = []
            
            # 定义图像处理函数
            def process_image(idx, path):
                """处理单个图像"""
                # 跳过None占位符
                if path is None:
                    return None
                try:
                    # 使用 fast_load_and_resize 函数（支持 OpenCV 加速）
                    img = fast_load_and_resize(path, target_w, target_h)

                    # 应用增强 - 只在需要时执行
                    if enhance_enabled and (brightness != 1.0 or contrast != 1.0 or sharpness != 1.0):
                        img = apply_enhancements(img, brightness, contrast, sharpness)

                    # 计算位置
                    row, col = divmod(idx, cols)
                    img_width, img_height = img.size
                    x = ml + col * (img_width + h_spacing)
                    y = mt + row * (img_height + v_spacing)

                    # 确保位置在画布范围内
                    if x + img_width <= cw and y + img_height <= ch:
                        # 将 PIL 图像转换为 NumPy 数组
                        img_np = np.array(img)
                        result = (img_np, x, y)
                    else:
                        result = None

                    # 释放内存
                    img.close()
                    del img
                    
                    return result
                except Exception as e:
                    print(f"跳过 {path}: {e}")
                    return None
            
            # 使用线程池并行处理图像
            from concurrent.futures import ThreadPoolExecutor
            
            # 根据系统资源动态调整线程池大小
            optimal_workers = resource_monitor.get_optimal_workers(task_type='io')
            with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
                # 提交任务
                futures = []
                for idx, path in enumerate(page_paths[:rows * cols]):
                    future = executor.submit(process_image, idx, path)
                    futures.append(future)
                
                # 收集结果
                for future in futures:
                    result = future.result()
                    if result:
                        processed_data.append(result)

            # 第二阶段：批量粘贴到画布
            for img_np, x, y in processed_data:
                h, w = img_np.shape[:2]
                canvas_np[y:y+h, x:x+w] = img_np

            # 清理数据
            processed_data = []

            # 绘制网格线（如果需要）
            if self.show_grid_var.get():
                import numpy as np
                # 使用 NumPy 数组操作绘制网格线
                for idx in range(min(len(page_paths), rows * cols)):
                    try:
                        # 计算位置
                        row, col = divmod(idx, cols)
                        # 使用目标尺寸计算位置
                        calc_width = target_w if target_w else 200
                        calc_height = target_h if target_h else 200
                        x = ml + col * (calc_width + h_spacing)
                        y = mt + row * (calc_height + v_spacing)
                        
                        # 确保位置在画布范围内
                        if x + calc_width <= cw and y + calc_height <= ch:
                            # 绘制上边界
                            if y >= 0 and y < ch:
                                canvas_np[y, x:x+calc_width] = [255, 0, 0]  # 红色
                            # 绘制下边界
                            if y + calc_height - 1 >= 0 and y + calc_height - 1 < ch:
                                canvas_np[y + calc_height - 1, x:x+calc_width] = [255, 0, 0]  # 红色
                            # 绘制左边界
                            if x >= 0 and x < cw:
                                canvas_np[y:y+calc_height, x] = [255, 0, 0]  # 红色
                            # 绘制右边界
                            if x + calc_width - 1 >= 0 and x + calc_width - 1 < cw:
                                canvas_np[y:y+calc_height, x + calc_width - 1] = [255, 0, 0]  # 红色
                    except:
                        pass

            # 转换回 PIL Image
            canvas = Image.fromarray(canvas_np)

            # 应用翻转
            if flip_mode == FLIP_VERTICAL:
                canvas = canvas.transpose(Image.FLIP_TOP_BOTTOM)
            elif flip_mode == FLIP_HORIZONTAL:
                canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)

            return canvas
        except Exception as e:
            print(f"拼接页面失败: {e}")
            return None

    def _reverse_rows_in_page(self, page_paths, cols):
        """
        【方案 B】真正的水平镜像 (Horizontal Mirror)
        
        逻辑：
        将图片按行分组。
        用 None 填充每一行，使其长度严格等于 cols (列数)。
        对包含 None 的整行进行反转。
        展平列表，保留 None 占位符。
        
        效果示例 (5张图, 2行4列):
        原始: [1, 2, 3, 4, 5]
        分组补全: [[1, 2, 3, 4], [5, None, None, None]]
        行内反转: [[4, 3, 2, 1], [None, None, None, 5]]
        展平后: [4, 3, 2, 1, None, None, None, 5]
        """
        if not page_paths:
            return []
        
        reversed_pages = []
        
        # 1. 按行分组并处理
        for i in range(0, len(page_paths), cols):
            # 2. 提取当前行并补全空位
            row = page_paths[i:i+cols]
            # 用 None 填充到 cols 长度
            while len(row) < cols:
                row.append(None)
            
            # 3. 对整行（包含 None）进行反转
            row.reverse()
            
            # 4. 添加到结果列表
            reversed_pages.extend(row)
        
        return reversed_pages

    def _get_config(self):
        cfg = {}
        try:
            cfg['rows'] = int(self.entry_rows.get())
            cfg['cols'] = int(self.entry_cols.get())
            cfg['h_spacing'] = max(0, int(self.entry_h_spacing.get()))
            cfg['v_spacing'] = max(0, int(self.entry_v_spacing.get()))
            cfg['margin'] = (
                max(0, int(self.entry_margin_top.get())),
                max(0, int(self.entry_margin_bottom.get())),
                max(0, int(self.entry_margin_left.get())),
                max(0, int(self.entry_margin_right.get())),
            )
            if self.resize_var.get():
                cfg['img_w'] = int(self.entry_width.get())
                cfg['img_h'] = int(self.entry_height.get())
            else:
                cfg['img_w'] = None
                cfg['img_h'] = None
        except ValueError:
            raise ValueError("请检查行/列/间距/边距/目标尺寸是否为有效数字")
        return cfg

    def grid_stitch(self, images, rows, cols, h_spacing, v_spacing, margin, img_w, img_h):
        mt, mb, ml, mr = margin
        cw, ch = self.canvas_size

        if img_w is None or img_h is None:
            raise ValueError("网格模式必须启用“前置统一尺寸”并设置目标宽高")

        result = Image.new("RGB", (cw, ch), (255, 255, 255))
        draw = ImageDraw.Draw(result) if self.show_grid_var.get() else None

        for idx, img in enumerate(images[:rows * cols]):
            row, col = divmod(idx, cols)
            resized = img.resize((img_w, img_h), Image.LANCZOS)
            x = ml + col * (img_w + h_spacing)
            y = mt + row * (img_h + v_spacing)
            result.paste(resized, (x, y))
            if draw:
                draw.rectangle([x, y, x + img_w, y + img_h], outline="red", width=1)
        return result

    def horizontal_stitch(self, images):
        w = sum(img.width for img in images)
        h = max(img.height for img in images)
        res = Image.new("RGB", (w, h), (255,255,255))
        x = 0
        for img in images:
            res.paste(img, (x, 0))
            x += img.width
        return res

    def vertical_stitch(self, images):
        w = max(img.width for img in images)
        h = sum(img.height for img in images)
        res = Image.new("RGB", (w, h), (255,255,255))
        y = 0
        for img in images:
            res.paste(img, (0, y))
            y += img.height
        return res

    def sanitize_filename(self, name):
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def recommend_layout_from_image_size(self):
        cw, ch = self.canvas_size
        try:
            mt = int(self.entry_margin_top.get())
            mb = int(self.entry_margin_bottom.get())
            ml = int(self.entry_margin_left.get())
            mr = int(self.entry_margin_right.get())
        except ValueError:
            messagebox.showwarning("输入错误", "请设置有效的边距")
            return

        avail_w = cw - ml - mr
        avail_h = ch - mt - mb
        if avail_w <= 0 or avail_h <= 0:
            messagebox.showerror("错误", "边距过大，可用区域无效")
            return

        h_gap = 30
        v_gap = 30
        img_w, img_h = None, None

        if self.resize_var.get():
            try:
                img_w = int(self.entry_width.get())
                img_h = int(self.entry_height.get())
            except ValueError:
                messagebox.showwarning("输入错误", "请设置有效的目标图片尺寸")
                return
            if img_w <= 0 or img_h <= 0:
                messagebox.showwarning("无效尺寸", "目标图片尺寸必须大于0")
                return
        else:
            if not self.image_paths:
                messagebox.showinfo("提示", "请先导入至少一张图片")
                return
            first_img = None
            for path in self.image_paths:
                try:
                    with Image.open(path) as img:
                        first_img = img.copy()
                        break
                except Exception:
                    continue
            if first_img is None:
                messagebox.showerror("错误", "无法读取任何有效图片")
                return
            img_w, img_h = first_img.size

        if img_w <= 0 or img_h <= 0:
            messagebox.showerror("无效图片尺寸", "图片尺寸异常")
            return

        max_cols = max(1, (avail_w + h_gap) // (img_w + h_gap))
        max_rows = max(1, (avail_h + v_gap) // (img_h + v_gap))

        self.entry_cols.delete(0, tk.END)
        self.entry_cols.insert(0, str(max_cols))
        self.entry_rows.delete(0, tk.END)
        self.entry_rows.insert(0, str(max_rows))
        self.entry_h_spacing.delete(0, tk.END)
        self.entry_h_spacing.insert(0, str(h_gap))
        self.entry_v_spacing.delete(0, tk.END)
        self.entry_v_spacing.insert(0, str(v_gap))

        mode = "目标" if self.resize_var.get() else "实际"
        messagebox.showinfo(
            "推荐完成",
            f"基于{mode}图片尺寸 {img_w}×{img_h}：\n"
            f"推荐 {max_rows} 行 × {max_cols} 列\n"
            f"默认间距：30px（水平/垂直）"
        )

    def recommend_image_size_from_layout(self):
        try:
            rows = int(self.entry_rows.get())
            cols = int(self.entry_cols.get())
            h_gap = int(self.entry_h_spacing.get())
            v_gap = int(self.entry_v_spacing.get())
            mt = int(self.entry_margin_top.get())
            mb = int(self.entry_margin_bottom.get())
            ml = int(self.entry_margin_left.get())
            mr = int(self.entry_margin_right.get())
            cw, ch = self.canvas_size
        except ValueError:
            messagebox.showwarning("输入错误", "请先设置有效的行、列、间距和边距")
            return

        if rows <= 0 or cols <= 0:
            messagebox.showwarning("无效行列", "行和列必须 ≥1")
            return

        avail_w = cw - ml - mr
        avail_h = ch - mt - mb

        if avail_w <= 0 or avail_h <= 0:
            messagebox.showerror("错误", "边距过大，可用区域无效")
            return

        total_h_gaps = h_gap * (cols - 1)
        total_v_gaps = v_gap * (rows - 1)

        if total_h_gaps >= avail_w or total_v_gaps >= avail_h:
            messagebox.showerror("空间不足", "间距过大，无法放置任何图片")
            return

        max_img_w = (avail_w - total_h_gaps) // cols
        max_img_h = (avail_h - total_v_gaps) // rows

        if max_img_w <= 0 or max_img_h <= 0:
            messagebox.showerror("空间不足", "剩余空间不足以放置图片")
            return

        self.entry_width.config(state="normal")
        self.entry_height.config(state="normal")
        self.entry_width.delete(0, tk.END)
        self.entry_width.insert(0, str(max_img_w))
        self.entry_height.delete(0, tk.END)
        self.entry_height.insert(0, str(max_img_h))
        self.resize_var.set(True)
        self.toggle_resize()

        messagebox.showinfo("推荐完成", f"推荐图片尺寸：{max_img_w} × {max_img_h} 像素\n（刚好填满设定布局）")

    def preview_stitch(self):
        if not self.image_paths:
            messagebox.showinfo("提示", "请先添加图片！")
            return
        
        self.status_var.set("正在预览...")
        self.root.update()
        
        # 创建后台线程处理预览
        def _preview_thread():
            try:
                config = get_current_config(self)
                results = process_image_batch(self.image_paths, config, preview_mode=True)
                
                if results:
                    img = results[0]
                    # 在主线程中更新UI
                    self.root.after(0, lambda: self._show_preview(img))
                else:
                    self.root.after(0, lambda: messagebox.showinfo("提示", "预览失败，没有生成图像！"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"预览失败：{e}"))
            finally:
                self.root.after(0, lambda: self.status_var.set("就绪"))
        
        # 启动后台线程
        import threading
        thread = threading.Thread(target=_preview_thread)
        thread.daemon = True
        thread.start()
    
    def _show_preview(self, img):
        """在主线程中显示预览"""
        win = tk.Toplevel(self.root)
        win.title("拼接预览")
        
        # 获取屏幕大小
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 计算最大允许的图片大小（屏幕的80%）
        max_width = int(screen_width * 0.4)
        max_height = int(screen_height * 0.4)
        
        # 检查图片是否需要缩放
        if img.width > max_width or img.height > max_height:
            # 计算缩放比例
            width_ratio = max_width / img.width
            height_ratio = max_height / img.height
            scale_ratio = min(width_ratio, height_ratio)
            
            # 计算新的图片大小
            new_width = int(img.width * scale_ratio)
            new_height = int(img.height * scale_ratio)
            
            # 缩放图片
            scaled_img = img.resize((new_width, new_height), Image.LANCZOS)
            photo = ImageTk.PhotoImage(scaled_img)
            
            # 设置窗口大小为缩放后的图片大小
            win.geometry(f"{new_width + 20}x{new_height + 20}")
            
            scaled_img.close()
        else:
            # 直接显示原始大小的图片
            photo = ImageTk.PhotoImage(img)
            win.geometry(f"{img.width + 20}x{img.height + 20}")
        
        label = tk.Label(win, image=photo)
        label.pack(padx=10, pady=10)
        win.photo = photo
        
        img.close()

    def stitch_images(self):
        if not self.image_paths:
            messagebox.showerror("错误", "无图片")
            return

        if self.layout_var.get() == LAYOUT_GRID and not self.resize_var.get():
            messagebox.showerror("配置错误", "网格模式下必须勾选“前置统一尺寸”并设置目标宽高！")
            return

        # 重置停止标志
        self.stop_flag.clear()

        # 先选择保存路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        layout = self.layout_var.get()
        suffix = {LAYOUT_HORIZONTAL: "horizontal", LAYOUT_VERTICAL: "vertical", LAYOUT_GRID: "grid"}[layout]

        has_reversed = self.gen_row_reversed_var.get() and (layout == LAYOUT_GRID)
        if has_reversed:
            suffix += "_with_reversed"

        base_name = f"{timestamp}_{suffix}"
        
        # 询问保存位置
        folder = filedialog.askdirectory(title="选择保存文件夹")
        if not folder:
            return

        output_folder = os.path.join(os.path.normpath(folder), self.sanitize_filename(base_name))
        os.makedirs(output_folder, exist_ok=True)

        # 禁用控件
        self._disable_controls(True)
        self.status_var.set("正在拼接...")

        # 启动后台线程，传入输出目录
        thread = threading.Thread(target=self._stitch_worker_with_save, args=(output_folder,), daemon=True)
        thread.start()
        
    def stop_stitch(self):
        """停止拼接操作"""
        if self.stop_flag.is_set():
            return
        
        self.stop_flag.set()
        self.status_var.set("正在停止拼接...")
        self.root.update_idletasks()

    def _stitch_worker_with_save(self, output_folder):
        """后台线程执行拼接并直接保存"""
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 记录开始内存使用
            log_memory("开始拼接")
            
            # 提前读取所有必要参数（避免跨线程访问 Tk 变量）
            resize_enabled = self.resize_var.get()
            target_w = int(self.entry_width.get()) if resize_enabled else None
            target_h = int(self.entry_height.get()) if resize_enabled else None
            enhance_enabled = self.enhance_var.get()
            brightness = self.brightness_val.get()
            contrast = self.contrast_val.get()
            sharpness = self.sharpness_val.get()
            layout = self.layout_var.get()
            total = len(self.image_paths)
            generate_reversed = self.gen_row_reversed_var.get()
            flip_mode = self.flip_mode.get()
            show_grid = self.show_grid_var.get()

            # 初始化已处理计数
            processed_count = 0
            total_steps = total * (2 if generate_reversed and layout == LAYOUT_GRID else 1)
            
            # 内存预分配
            if layout == LAYOUT_GRID:
                # 获取拼接配置
                cfg = self._get_config()
                rows, cols = cfg['rows'], cfg['cols']
                per_page = rows * cols
                
                # 预计算页面数量
                total_pages = (total + per_page - 1) // per_page
                
                # 预分配内存池
                from .memory_pool import memory_pool
                import numpy as np
                
                # 根据目标尺寸预分配内存
                if target_w and target_h:
                    # 预分配图像数组
                    for _ in range(min(10, total_pages)):
                        # 预分配图像数组
                        img_array = memory_pool.get((target_h, target_w, 3), dtype=np.uint8)
                        memory_pool.put(img_array)
                        
                        # 预分配增强后的图像数组
                        enhanced_array = memory_pool.get((target_h, target_w, 3), dtype=np.float32)
                        memory_pool.put(enhanced_array)

            # 如果是网格模式
            if layout == LAYOUT_GRID:
                # 获取拼接配置
                cfg = self._get_config()
                rows, cols = cfg['rows'], cfg['cols']
                per_page = rows * cols

                # 分页处理 - 使用路径驱动，而非图像驱动
                current_page = 1
                page_paths = []

                # 预计算所有页面
                total_pages = (len(self.image_paths) + per_page - 1) // per_page
                
                processed_count = 0
                
                for i, path in enumerate(self.image_paths):
                    # 检查是否需要停止
                    if self.stop_flag.is_set():
                        self.root.after(0, lambda: self.status_var.set("拼接已停止"))
                        return
                    
                    page_paths.append(path)

                    # 当页面满了或处理完所有图片时
                    if len(page_paths) >= per_page or i == len(self.image_paths) - 1:
                        if page_paths:
                            # 从margin元组中提取边距值
                            mt, mb, ml, mr = cfg['margin']
                            
                            # 为每个页面创建配置
                            # 映射翻转模式
                            flip_mode_map = {
                                'none': 0,
                                'vertical': 1,
                                'horizontal': 2
                            }
                            flip_mode_value = flip_mode_map.get(flip_mode, 0)
                            
                            page_config = {
                                'target_w': target_w,
                                'target_h': target_h,
                                'enhance_enabled': enhance_enabled,
                                'brightness': brightness,
                                'contrast': contrast,
                                'sharpness': sharpness,
                                'flip_mode': flip_mode_value,
                                'output_folder': output_folder,
                                'page_num': current_page,
                                'layout': 'grid',  # 添加布局类型
                                'rows': rows,
                                'cols': cols,
                                'h_spacing': cfg['h_spacing'],
                                'v_spacing': cfg['v_spacing'],
                                'margin_top': mt,
                                'margin_bottom': mb,
                                'margin_left': ml,
                                'margin_right': mr
                            }
                            
                            # 使用流水线处理页面
                            pipeline_pool.add_task(page_paths.copy(), page_config)
                            
                            # 处理反转页面（如果需要）
                            if generate_reversed:
                                rev_page_config = page_config.copy()
                                rev_page_config['page_num'] = current_page  # 反转页面使用相同的页码
                                rev_page_config['is_reversed'] = True  # 添加反转标记
                                # 生成反转版路径
                                rev_paths = self._reverse_rows_in_page(page_paths, cols)
                                pipeline_pool.add_task(rev_paths, rev_page_config)
                            
                            # 保存页面路径长度
                            page_length = len(page_paths)
                            page_paths = []
                            current_page += 1
                            processed_count += page_length
                            if generate_reversed:
                                processed_count += page_length
                            
                            # 更新进度
                            progress = (processed_count / total_steps) * 100
                            self.root.after(0, lambda p=min(progress, 99): [
                                self.progress_var.set(p),
                                self.status_var.set(f"正在拼接... {processed_count}/{total_steps}")
                            ])
                
                # 等待一段时间，让流水线有时间处理任务
                # 使用 is_processing_complete 方法检查是否所有任务都已处理完成
                start_wait_time = time.time()
                max_wait_time = 300  # 最大等待时间，避免无限等待
                
                # 检查是否需要停止
                if self.stop_flag.is_set():
                    self.root.after(0, lambda: self.status_var.set("拼接已停止"))
                    return
                
                # 等待所有任务处理完成
                self.root.after(0, lambda: self.status_var.set("等待处理完成..."))
                
                while not self.stop_flag.is_set():
                    # 检查是否处理完成
                    if pipeline_pool.is_processing_complete():
                        break
                    # 检查是否超时
                    if time.time() - start_wait_time > max_wait_time:
                        self.root.after(0, lambda: self.status_var.set("等待处理完成超时"))
                        break
                    # 短暂睡眠后再次检查
                    time.sleep(0.5)

            else:  # 水平或垂直布局
                # 使用流水线处理水平或垂直布局
                # 为水平/垂直布局创建配置
                # 映射翻转模式
                flip_mode_map = {
                    'none': 0,
                    'vertical': 1,
                    'horizontal': 2
                }
                flip_mode_value = flip_mode_map.get(flip_mode, 0)
                
                layout_config = {
                    'target_w': target_w,
                    'target_h': target_h,
                    'enhance_enabled': enhance_enabled,
                    'brightness': brightness,
                    'contrast': contrast,
                    'sharpness': sharpness,
                    'flip_mode': flip_mode_value,
                    'output_folder': output_folder,
                    'page_num': 1,
                    'layout': layout
                }
                
                # 使用流水线处理所有图像
                pipeline_pool.add_task(self.image_paths, layout_config)
                
                # 等待一段时间，让流水线有时间处理任务
                # 使用 is_processing_complete 方法检查是否所有任务都已处理完成
                start_wait_time = time.time()
                max_wait_time = 300  # 最大等待时间，避免无限等待
                
                # 检查是否需要停止
                if self.stop_flag.is_set():
                    self.root.after(0, lambda: self.status_var.set("拼接已停止"))
                    return
                
                # 等待所有任务处理完成
                self.root.after(0, lambda: self.status_var.set("等待处理完成..."))
                
                while not self.stop_flag.is_set():
                    # 检查是否处理完成
                    if pipeline_pool.is_processing_complete():
                        break
                    # 检查是否超时
                    if time.time() - start_wait_time > max_wait_time:
                        self.root.after(0, lambda: self.status_var.set("等待处理完成超时"))
                        break
                    # 短暂睡眠后再次检查
                    time.sleep(0.5)

            # 等待所有异步保存任务完成
            async_saver.wait_completion()
            
            # 计算耗时
            elapsed_time = time.time() - start_time
            minutes, seconds = divmod(elapsed_time, 60)
            
            # 完成
            self.root.after(0, lambda: [
                self.progress_var.set(100),
                self.status_var.set(f"就绪 - 已处理 {processed_count}/{total_steps} (耗时: {int(minutes)}分{int(seconds)}秒)")
            ])

            # 显示完成消息
            self.root.after(0, lambda: messagebox.showinfo("成功", f"拼接完成！\n已保存到：{output_folder}\n处理图片：{processed_count}/{total_steps}\n耗时：{int(minutes)}分{int(seconds)}秒"))

        except Exception as e:
            # 错误也需在主线程弹窗
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("拼接失败", msg))
        finally:
            # 记录完成时的内存使用
            log_memory("拼接完成")
            
            # 清理内存
            gc.collect()
            
            # 恢复 UI
            if self.stop_flag.is_set():
                self.root.after(0, lambda: [
                    self.progress_var.set(0),
                    self.status_var.set("就绪 - 拼接已停止"),
                    self._disable_controls(False),
                    gc.collect()
                ])
            else:
                self.root.after(0, lambda: [
                    self.progress_var.set(0),
                    self.status_var.set("就绪"),
                    self._disable_controls(False),
                    gc.collect()
                ])
            
            # 重置停止标志
            self.stop_flag.clear()


if __name__ == "__main__":
    main()