import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from PIL import Image, ImageDraw, ImageTk, ImageEnhance
import os
import glob
import re
import gc
from datetime import datetime
import json
import threading  # <<< 新增：用于多线程
import io  # <<< 新增：用于PDF导出

# 尝试导入OpenCV以进行性能优化
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("警告: 未安装opencv-python，将使用PIL进行图像处理。安装opencv-python可获得更快的处理速度。")

def fast_load_and_resize(path, target_w, target_h):
    """使用 OpenCV 快速加载并缩放图像"""
    if not OPENCV_AVAILABLE:
        # 如果OpenCV不可用，则回退到PIL
        with Image.open(path) as img:
            if img.format == 'JPEG':
                img.draft("RGB", (target_w * 2, target_h * 2))
            img = img.convert("RGB")
            return img.resize((target_w, target_h), Image.LANCZOS)
    
    # 1. 用 OpenCV 加载 (BGR 格式)
    img_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"无法读取图像: {path}")
    
    # 2. 转为 RGB (PIL 需要)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    
    # 3. 用 OpenCV 高质量缩放
    resized = cv2.resize(
        img_rgb, 
        (target_w, target_h), 
        interpolation=cv2.INTER_LANCZOS4  # 等同于 PIL.LANCZOS
    )
    
    # 4. 转回 PIL Image 用于粘贴
    return Image.fromarray(resized)

def create_canvas_numpy(width, height):
    """创建白色画布 (H, W, C)"""
    return np.full((height, width, 3), 255, dtype=np.uint8)

def paste_tile_numpy(canvas_np, tile_img, x, y):
    """直接将 PIL 图像粘贴到 NumPy 画布"""
    tile_np = np.array(tile_img)  # (H, W, 3)
    h, w = tile_np.shape[:2]
    canvas_np[y:y+h, x:x+w] = tile_np


try:
    import img2pdf
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


class ImageStitcher:
    def __init__(self, root):
        self.root = root
        self.root.title("智能图片拼接工具")
        self.root.geometry("700x920")

        # 创建 schemes 目录（用于保存方案）
        self.schemes_dir = "schemes"
        os.makedirs(self.schemes_dir, exist_ok=True)

        self.image_paths = []
        self.canvas_size = (800, 600)

        # 图像增强参数（默认关闭）
        self.enhance_var = tk.BooleanVar(value=False)
        self.brightness_val = tk.DoubleVar(value=1.0)
        self.contrast_val = tk.DoubleVar(value=1.0)
        self.sharpness_val = tk.DoubleVar(value=1.0)

        # 绑定窗口关闭事件以保存默认配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.setup_ui()
        self.load_config()  # 启动时加载上次默认配置

    def setup_ui(self):
        # === 图片选择区域 ===
        frame_select = tk.LabelFrame(self.root, text="图片管理", padx=10, pady=10)
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
        frame_canvas = tk.LabelFrame(self.root, text="输出设置", padx=10, pady=10)
        frame_canvas.pack(pady=10, fill="x", padx=20)

        dim_frame = tk.Frame(frame_canvas)
        dim_frame.pack(anchor="w", pady=2)
        tk.Label(dim_frame, text="画布尺寸:").pack(side="left")
        tk.Label(dim_frame, text="宽:").pack(side="left", padx=(10, 0))
        self.entry_canvas_width = tk.Entry(dim_frame, width=8)
        self.entry_canvas_width.insert(0, "800")
        self.entry_canvas_width.pack(side="left", padx=5)
        tk.Label(dim_frame, text="高:").pack(side="left", padx=(10, 0))
        self.entry_canvas_height = tk.Entry(dim_frame, width=8)
        self.entry_canvas_height.insert(0, "600")
        self.entry_canvas_height.pack(side="left", padx=5)
        tk.Button(dim_frame, text="应用", command=self.set_canvas_size, width=6).pack(side="left", padx=10)

        a4_frame = tk.Frame(frame_canvas)
        a4_frame.pack(anchor="w", pady=5)
        self.a4_mode_var = tk.BooleanVar()
        self.landscape_var = tk.BooleanVar()
        tk.Checkbutton(a4_frame, text="A4 打印 (300 DPI)", variable=self.a4_mode_var, command=self.toggle_a4).pack(side="left")
        tk.Checkbutton(a4_frame, text="横向", variable=self.landscape_var, command=self.toggle_a4).pack(side="left", padx=(10, 0))

        # === 拼接规则区域 ===
        frame_rules = tk.LabelFrame(self.root, text="拼接规则", padx=10, pady=10)
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
        self.layout_var = tk.StringVar(value="水平")
        combo = ttk.Combobox(layout_frame, textvariable=self.layout_var, values=["水平", "垂直", "网格"], state="readonly", width=10)
        combo.pack(side="left", padx=5)
        combo.bind('<<ComboboxSelected>>', lambda e: self.grid_frame.grid() if self.layout_var.get() == "网格" else self.grid_frame.grid_remove())

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
        self.flip_mode = tk.StringVar(value="无")
        flip_combo = ttk.Combobox(
            flip_frame,
            textvariable=self.flip_mode,
            values=["无", "上下翻转", "左右翻转"],
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
        frame_enhance = tk.LabelFrame(self.root, text="生成图像编辑", padx=10, pady=10)
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

        b_frame = tk.Frame(self.enhance_frame)
        b_frame.pack(anchor="w", pady=2)
        tk.Label(b_frame, text="亮度 (0.0–2.0):", width=18).pack(side="left")
        tk.Scale(b_frame, from_=0.0, to=2.0, resolution=0.1, orient="horizontal", variable=self.brightness_val, length=300).pack(side="left")

        c_frame = tk.Frame(self.enhance_frame)
        c_frame.pack(anchor="w", pady=2)
        tk.Label(c_frame, text="对比度 (0.0–2.0):", width=18).pack(side="left")
        tk.Scale(c_frame, from_=0.0, to=2.0, resolution=0.1, orient="horizontal", variable=self.contrast_val, length=300).pack(side="left")

        s_frame = tk.Frame(self.enhance_frame)
        s_frame.pack(anchor="w", pady=2)
        tk.Label(s_frame, text="锐化 (0.0–2.0):", width=18).pack(side="left")
        tk.Scale(s_frame, from_=0.0, to=2.0, resolution=0.1, orient="horizontal", variable=self.sharpness_val, length=300).pack(side="left")

        self.enhance_frame.pack_forget()  # 初始隐藏

        # === 进度与操作区域 ===
        frame_progress = tk.LabelFrame(self.root, text="状态", padx=10, pady=10)
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

        # === 操作按钮栏 ===
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)
        self.btn_stitch = tk.Button(btn_frame, text="开始拼接", command=self.stitch_images, bg="#4CAF50", fg="white", font=("Arial",10,"bold"), width=12)
        self.btn_stitch.pack(side="left", padx=5)
        self.btn_preview = tk.Button(btn_frame, text="🔍 预览拼接", command=self.preview_stitch, bg="#FFC107", fg="black", font=("Arial",10,"bold"), width=12)
        self.btn_preview.pack(side="left", padx=5)
        tk.Button(btn_frame, text="💾 保存当前为方案...", command=self.save_current_as_scheme, bg="#2196F3", fg="white", width=16).pack(side="left", padx=5)
        tk.Button(btn_frame, text="📂 加载方案...", command=self.load_scheme, bg="#FF9800", fg="white", width=12).pack(side="left", padx=5)

    # ========================
    #   新增：单张图实时预览（带增强）
    # ========================
    def preview_single_image(self, event=None):
        sel = self.listbox.curselection()
        if not sel or not self.image_paths:
            return
        idx = sel[0]
        path = self.image_paths[idx]
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                # 应用增强
                if self.enhance_var.get():
                    if self.brightness_val.get() != 1.0:
                        enhancer = ImageEnhance.Brightness(img)
                        img = enhancer.enhance(self.brightness_val.get())
                    if self.contrast_val.get() != 1.0:
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(self.contrast_val.get())
                    if self.sharpness_val.get() != 1.0:
                        enhancer = ImageEnhance.Sharpness(img)
                        img = enhancer.enhance(self.sharpness_val.get())

                win = tk.Toplevel(self.root)
                win.title(f"预览: {os.path.basename(path)}")
                ratio = min(600 / img.width, 600 / img.height, 1.0)
                preview = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
                photo = ImageTk.PhotoImage(preview)
                label = tk.Label(win, image=photo)
                label.pack(padx=10, pady=10)
                win.photo = photo  # 防止被回收
        except Exception as e:
            messagebox.showerror("预览失败", f"无法打开图片：{e}")

    # ========================
    #   方案保存与加载（已包含增强参数）
    # ========================

    def get_current_config(self):
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
        return cfg

    def apply_config(self, cfg):
        try:
            self.layout_var.set(cfg.get("layout", "水平"))
            if cfg.get("layout") == "网格":
                self.grid_frame.grid()
            else:
                self.grid_frame.grid_remove()

            self.a4_mode_var.set(cfg.get("a4_mode", False))
            self.landscape_var.set(cfg.get("landscape", False))

            if not cfg.get("a4_mode", False):
                self.entry_canvas_width.delete(0, tk.END)
                self.entry_canvas_width.insert(0, str(cfg.get("canvas_width", 800)))
                self.entry_canvas_height.delete(0, tk.END)
                self.entry_canvas_height.insert(0, str(cfg.get("canvas_height", 600)))
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
                entry.insert(0, str(cfg.get(attr, 0)))

            self.flip_mode.set(cfg.get("flip_mode", "无"))
            self.show_grid_var.set(cfg.get("show_grid", False))

            # 图像增强
            self.enhance_var.set(cfg.get("enhance_enabled", False))
            self.brightness_val.set(cfg.get("brightness", 1.0))
            self.contrast_val.set(cfg.get("contrast", 1.0))
            self.sharpness_val.set(cfg.get("sharpness", 1.0))
            if cfg.get("enhance_enabled", False):
                self.enhance_frame.pack(fill="x", pady=(10, 0))
            else:
                self.enhance_frame.pack_forget()

            if cfg.get("a4_mode", False):
                self.toggle_a4()

            self.update_status()
        except Exception as e:
            messagebox.showerror("加载失败", f"方案数据损坏或版本不兼容：{e}")

    def save_current_as_scheme(self):
        name = simpledialog.askstring("保存方案", "请输入方案名称：")
        if not name:
            return
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', name.strip())
        if not safe_name:
            messagebox.showwarning("无效名称", "方案名称不能为空或仅含非法字符")
            return

        filepath = os.path.join(self.schemes_dir, f"{safe_name}.json")
        if os.path.exists(filepath):
            if not messagebox.askyesno("覆盖确认", f"方案 '{safe_name}' 已存在，是否覆盖？"):
                return

        cfg = self.get_current_config()
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

    # ========================
    #   控件禁用/启用（防并发操作）
    # ========================
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

    # ========================
    #   原有功能（略作调整）
    # ========================

    def toggle_a4(self):
        if self.a4_mode_var.get():
            w, h = (3508, 2480) if self.landscape_var.get() else (2480, 3508)
            self.canvas_size = (w, h)
            self.entry_canvas_width.delete(0, tk.END); self.entry_canvas_width.insert(0, str(w)); self.entry_canvas_width.config(state="disabled")
            self.entry_canvas_height.delete(0, tk.END); self.entry_canvas_height.insert(0, str(h)); self.entry_canvas_height.config(state="disabled")
            for e in [self.entry_margin_top, self.entry_margin_bottom, self.entry_margin_left, self.entry_margin_right]:
                e.delete(0, tk.END); e.insert(0, "50")
            self.entry_h_spacing.delete(0, tk.END); self.entry_h_spacing.insert(0, "30")
            self.entry_v_spacing.delete(0, tk.END); self.entry_v_spacing.insert(0, "30")
            self.resize_var.set(False)
            self.toggle_resize()
        else:
            self.entry_canvas_width.config(state="normal")
            self.entry_canvas_height.config(state="normal")
            self.set_canvas_size()
        self.update_status()

    def set_canvas_size(self):
        try:
            w, h = int(self.entry_canvas_width.get()), int(self.entry_canvas_height.get())
            if w > 0 and h > 0:
                self.canvas_size = (w, h)
        except ValueError:
            pass
        self.update_status()

    def toggle_resize(self):
        state = "normal" if self.resize_var.get() else "disabled"
        self.entry_width.config(state=state)
        self.entry_height.config(state=state)

    def update_status(self):
        mode = "A4" if self.a4_mode_var.get() else "自定义"
        self.status_var.set(f"{len(self.image_paths)} 张图片 | {mode} | {self.canvas_size[0]}×{self.canvas_size[1]}")
        self.update_expected_pages()
    
    def _on_layout_changed(self, event=None):
        if self.layout_var.get() == "网格":
            self.grid_frame.grid()
        else:
            self.grid_frame.grid_remove()
        self.update_expected_pages()
    
    def _on_param_changed(self, *args):
        self.update_expected_pages()
    
    def update_expected_pages(self):
        # 只有在网格布局时才计算预计页数
        if self.layout_var.get() != "网格":
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

    def add_images(self):
        files = filedialog.askopenfilenames(filetypes=[("图片", "*.jpg *.jpeg *.png *.bmp *.gif *.jfif")])
        for f in files:
            if f not in self.image_paths:
                self.image_paths.append(f)
                self.listbox.insert("end", os.path.basename(f))
        self.update_status()

    def add_folder_images(self):
        folder = filedialog.askdirectory()
        if not folder: return
        exts = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.jfif']
        paths = [p for e in exts for p in glob.glob(os.path.join(folder, e)) + glob.glob(os.path.join(folder, e.upper()))]
        added = 0
        for p in paths:
            if p not in self.image_paths:
                self.image_paths.append(p)
                self.listbox.insert("end", os.path.basename(p))
                added += 1
        if added: messagebox.showinfo("成功", f"添加 {added} 张图片")
        self.update_status()

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            del self.image_paths[i]
            self.listbox.delete(i)
        self.update_status()

    def clear_list(self):
        self.image_paths.clear()
        self.listbox.delete(0, "end")
        self.update_status()

    def sanitize_filename(self, name):
        return re.sub(r'[<>:"/\\|?*]', '_', name)

    def load_config(self):
        try:
            with open("image_stitcher_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.apply_config(cfg)
        except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
            pass

    def save_config(self):
        cfg = self.get_current_config()
        try:
            with open("image_stitcher_config.json", "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception:
            pass

    def on_closing(self):
        self.save_config()
        self.root.destroy()

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

    def grid_stitch_from_paths(self, paths, rows, cols, h_spacing, v_spacing, margin, img_w, img_h, enhance_params=None, is_preview=True):
        """
        从图像路径列表流式拼接网格，极大降低内存占用。
        :param paths: 图像路径列表（最多 rows*cols 张）
        :param enhance_params: (brightness, contrast, sharpness) 或 None
        """
        mt, mb, ml, mr = margin
        cw, ch = self.canvas_size

        if img_w is None or img_h is None:
            raise ValueError("网格模式必须启用“前置统一尺寸”并设置目标宽高")

        # 创建输出画布
        result = Image.new("RGB", (cw, ch), (255, 255, 255))
        draw = ImageDraw.Draw(result) if self.show_grid_var.get() else None

        # 预计算位置参数
        for idx, path in enumerate(paths[:rows * cols]):
            try:
                with Image.open(path) as img:
                    img = img.convert("RGB")
                    
                    # --- 关键优化：使用 draft 减少解码内存 ---
                    # 仅对 JPEG 有效，且需在 convert 前调用
                    if hasattr(img, 'draft') and img.format == 'JPEG':
                        img.draft("RGB", (img_w * 2, img_h * 2))
                        img = img.convert("RGB")  # draft 后需重新 convert
                    
                    # 缩放到目标尺寸
                    resized = img.resize((img_w, img_h), Image.LANCZOS)
                    
                    # 应用增强（如果启用）
                    if enhance_params:
                        brightness, contrast, sharpness = enhance_params
                        if brightness != 1.0:
                            resized = ImageEnhance.Brightness(resized).enhance(brightness)
                        if contrast != 1.0:
                            resized = ImageEnhance.Contrast(resized).enhance(contrast)
                        if sharpness != 1.0:
                            resized = ImageEnhance.Sharpness(resized).enhance(sharpness)

                    # 计算位置并粘贴
                    row, col = divmod(idx, cols)
                    x = ml + col * (img_w + h_spacing)
                    y = mt + row * (img_h + v_spacing)
                    result.paste(resized, (x, y))
                    
                    # 绘制网格线（调试）
                    if draw:
                        draw.rectangle([x, y, x + img_w, y + img_h], outline="red", width=1)
                        
                    # resized 和 img 在此自动销毁（with 块结束 + 无引用）
                    
            except Exception as e:
                print(f"跳过 {path}: {e}")
        return result

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

    def multi_grid_stitch(self, images, cfg, is_preview=False):
        rows, cols = cfg['rows'], cfg['cols']
        per_page = rows * cols
        
        if not self.multi_page_var.get():
            return [self.grid_stitch(images[:per_page], **cfg)]
        
        # 如果是预览模式，只返回第一页
        if is_preview:
            return [self.grid_stitch(images[:min(per_page, len(images))], **cfg)]
        
        # 对于完整处理，逐页处理以减少内存使用
        results = []
        for i in range(0, len(images), per_page):
            page_images = images[i:i+per_page]
            page_result = self.grid_stitch(page_images, **cfg)
            results.append(page_result)
            
            # 释放已处理的图片对象，减少内存占用
            for img in page_images:
                del img
            gc.collect()
        
        return results

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

    def stitch_by_layout(self, images, is_preview=True):
        layout = self.layout_var.get()
        if layout == "水平":
            return [self.horizontal_stitch(images)]
        elif layout == "垂直":
            return [self.vertical_stitch(images)]
        else:
            cfg = self._get_config()
            return self.multi_grid_stitch(images, cfg)

    def generate_row_reversed_grids(self, original_images, cfg, is_preview=False):
        rows = cfg['rows']
        cols = cfg['cols']
        per_page = rows * cols
        multi_page = self.multi_page_var.get()

        if not multi_page:
            pages = [original_images[:per_page]]
        else:
            # 如果是预览模式，只处理第一页
            if is_preview:
                pages = [original_images[:min(per_page, len(original_images))]]
            else:
                pages = [original_images[i:i + per_page] for i in range(0, len(original_images), per_page)]

        reversed_pages = []
        for page_imgs in pages:
            reversed_list = []
            for r in range(rows):
                start = r * cols
                end = start + cols
                row_imgs = page_imgs[start:end]
                if len(row_imgs) > 0:  # 确保有图片才反转
                    reversed_list.extend(reversed(row_imgs))
            reversed_pages.append(self.grid_stitch(reversed_list, **cfg))
            
            # 清理临时列表以释放内存
            del reversed_list[:]
            del reversed_list
            gc.collect()
            
        return reversed_pages

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

    # ========================
    #   多线程拼接入口
    # ========================
    def stitch_images(self):
        if not self.image_paths:
            messagebox.showerror("错误", "无图片")
            return

        if self.layout_var.get() == "网格" and not self.resize_var.get():
            messagebox.showerror("配置错误", "网格模式下必须勾选“前置统一尺寸”并设置目标宽高！")
            return

        # 先选择保存路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        layout = self.layout_var.get()
        suffix = {"水平": "horizontal", "垂直": "vertical", "网格": "grid"}[layout]

        has_reversed = self.gen_row_reversed_var.get() and (layout == "网格")
        if has_reversed:
            suffix += "_with_reversed"

        base_name = f"{timestamp}_{suffix}"
        
        # 询问保存位置
        folder = filedialog.askdirectory(title="选择保存文件夹")
        if not folder:
            return

        output_folder = os.path.join(folder, self.sanitize_filename(base_name))
        os.makedirs(output_folder, exist_ok=True)

        # 禁用控件
        self._disable_controls(True)
        self.status_var.set("正在拼接...")

        # 启动后台线程，传入输出目录
        thread = threading.Thread(target=self._stitch_worker_with_save, args=(output_folder,), daemon=True)
        thread.start()

    def _stitch_worker_with_save(self, output_folder):
        """后台线程执行拼接并直接保存"""
        try:
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

            # 如果是网格模式，需要先处理所有图片，然后分页拼接
            if layout == "网格":
                # 获取拼接配置
                cfg = self._get_config()
                rows, cols = cfg['rows'], cfg['cols']
                per_page = rows * cols

                # 分页拼接并保存 - 流式处理
                saved_count = 0
                for i in range(0, len(self.image_paths), per_page):
                    # 当前页的图片路径
                    page_paths = self.image_paths[i:i+per_page]
                    
                    # 加载当前页的图片
                    page_images = []
                    for j, path in enumerate(page_paths):
                        try:
                            # 流式加载图片
                            img = Image.open(path).convert("RGB")
                            
                            if target_w and target_h:
                                img = img.resize((target_w, target_h), Image.LANCZOS)

                            # 应用增强
                            if enhance_enabled:
                                if brightness != 1.0:
                                    img = ImageEnhance.Brightness(img).enhance(brightness)
                                if contrast != 1.0:
                                    img = ImageEnhance.Contrast(img).enhance(contrast)
                                if sharpness != 1.0:
                                    img = ImageEnhance.Sharpness(img).enhance(sharpness)

                            page_images.append(img)
                        except Exception as e:
                            print(f"跳过 {path}: {e}")

                    if not page_images:
                        continue  # 跳过空页面
                    
                    # 拼接当前页
                    page_result = self.grid_stitch(page_images, **cfg)
                    
                    # 应用翻转
                    mode = self.flip_mode.get()
                    if mode == "上下翻转":
                        page_result = page_result.transpose(Image.FLIP_TOP_BOTTOM)
                    elif mode == "左右翻转":
                        page_result = page_result.transpose(Image.FLIP_LEFT_RIGHT)
                    
                    # 保存当前页
                    page_path = os.path.join(output_folder, f"page_{(i // per_page) + 1:02d}.jpg")
                    page_result.save(page_path, "JPEG", quality=95, optimize=True)
                    saved_count += 1
                    
                    # 释放当前页图片内存
                    del page_result
                    for img in page_images:
                        del img
                    gc.collect()

                    # 更新进度
                    page_progress = 50 + ((i + len(page_paths)) / total) * 40
                    self.root.after(0, lambda p=min(page_progress, 90): self.progress_var.set(p))

                # 如果需要生成反转版
                if self.gen_row_reversed_var.get():
                    # 重新处理一遍生成反转版
                    reversed_processed_images = []
                    for i, path in enumerate(self.image_paths):
                        try:
                            img = Image.open(path).convert("RGB")
                            
                            if target_w and target_h:
                                img = img.resize((target_w, target_h), Image.LANCZOS)

                            # 应用增强
                            if enhance_enabled:
                                if brightness != 1.0:
                                    img = ImageEnhance.Brightness(img).enhance(brightness)
                                if contrast != 1.0:
                                    img = ImageEnhance.Contrast(img).enhance(contrast)
                                if sharpness != 1.0:
                                    img = ImageEnhance.Sharpness(img).enhance(sharpness)

                            reversed_processed_images.append(img)
                        except Exception as e:
                            print(f"跳过 {path}: {e}")

                    # 生成反转版并保存
                    for i in range(0, len(reversed_processed_images), per_page):
                        page_images = reversed_processed_images[i:i+per_page]
                        
                        # 生成反转版网格
                        reversed_list = []
                        for r in range(rows):
                            start = r * cols
                            end = start + cols
                            row_imgs = page_images[start:end]
                            if len(row_imgs) > 0:
                                reversed_list.extend(reversed(row_imgs))
                        
                        if reversed_list:  # 确保有图片才处理
                            reversed_result = self.grid_stitch(reversed_list, **cfg)
                            
                            # 应用翻转
                            mode = self.flip_mode.get()
                            if mode == "上下翻转":
                                reversed_result = reversed_result.transpose(Image.FLIP_TOP_BOTTOM)
                            elif mode == "左右翻转":
                                reversed_result = reversed_result.transpose(Image.FLIP_LEFT_RIGHT)
                            
                            # 保存反转版
                            rev_path = os.path.join(output_folder, f"page_{(i // per_page) + 1:02d}_row_reversed.jpg")
                            reversed_result.save(rev_path, "JPEG", quality=95, optimize=True)
                            saved_count += 1
                            
                            # 释放反转版图片内存
                            del reversed_result

                        # 清理当前页的图片列表
                        for img in page_images:
                            del img
                        gc.collect()

                        # 更新进度
                        rev_progress = 90 + ((i + len(page_images)) / total) * 10
                        self.root.after(0, lambda p=min(rev_progress, 100): self.progress_var.set(p))

                    # 清理反转版处理的图片
                    for img in reversed_processed_images:
                        del img

            else:  # 水平或垂直布局
                # 对于非网格模式，一次处理所有图片
                processed_images = []
                for i, path in enumerate(self.image_paths):
                    try:
                        # 流式加载图片
                        img = Image.open(path).convert("RGB")
                        
                        if target_w and target_h:
                            img = img.resize((target_w, target_h), Image.LANCZOS)

                        # 应用增强
                        if enhance_enabled:
                            if brightness != 1.0:
                                img = ImageEnhance.Brightness(img).enhance(brightness)
                            if contrast != 1.0:
                                img = ImageEnhance.Contrast(img).enhance(contrast)
                            if sharpness != 1.0:
                                img = ImageEnhance.Sharpness(img).enhance(sharpness)

                        processed_images.append(img)
                    except Exception as e:
                        print(f"跳过 {path}: {e}")

                    # 更新进度
                    progress = (i / total) * 50
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))

                if not processed_images:
                    raise ValueError("无有效图片")

                # 拼接
                if layout == "水平":
                    result = self.horizontal_stitch(processed_images)
                else:  # 垂直
                    result = self.vertical_stitch(processed_images)

                # 应用翻转
                mode = self.flip_mode.get()
                if mode == "上下翻转":
                    result = result.transpose(Image.FLIP_TOP_BOTTOM)
                elif mode == "左右翻转":
                    result = result.transpose(Image.FLIP_LEFT_RIGHT)

                # 保存结果
                result_path = os.path.join(output_folder, "combined_image.jpg")
                result.save(result_path, "JPEG", quality=95, optimize=True)
                
                # 释放内存
                del result
                for img in processed_images:
                    del img

                self.root.after(0, lambda: self.progress_var.set(95))

            self.root.after(0, lambda: self.progress_var.set(100))

            # 显示完成消息
            self.root.after(0, lambda: messagebox.showinfo("成功", f"拼接完成！\n已保存到：{output_folder}"))

        except Exception as e:
            # 错误也需在主线程弹窗
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("拼接失败", msg))
        finally:
            # 清理加载的图片以释放内存
            if 'processed_images' in locals():
                for img in processed_images:
                    del img
            if 'reversed_processed_images' in locals():
                for img in reversed_processed_images:
                    del img
            if 'page_images' in locals():
                for img in page_images:
                    del img
            gc.collect()
            
            # 恢复 UI
            self.root.after(0, lambda: [
                self.progress_var.set(0),
                self.status_var.set("就绪"),
                self._disable_controls(False),
                gc.collect()
            ])

    def _show_preview_dialog(self, pil_img, is_preview=True):
        """显示预览对话框"""
        win = tk.Toplevel(self.root)
        if is_preview:
            win.title("预览 - 确认拼接效果")
        else:
            win.title("预览 - 确认保存")
        
        ratio = min(800/pil_img.width, 600/pil_img.height, 1.0)
        preview = pil_img.resize((int(pil_img.width*ratio), int(pil_img.height*ratio)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(preview)
        tk.Label(win, image=photo).pack(padx=10, pady=10)
        win.photo = photo

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)
        
        if is_preview:
            # 预览窗口：继续拼接 或 取消
            tk.Button(btn_frame, text="✅ 继续拼接", command=lambda: [win.destroy(), self._confirm_full_process()], bg="#4CAF50", fg="white").pack(side="left", padx=15)
            tk.Button(btn_frame, text="❌ 取消", command=win.destroy, bg="#f44336", fg="white").pack(side="left", padx=15)
        else:
            # 最终保存窗口：现在不再需要，因为保存是在拼接过程中完成的
            tk.Button(btn_frame, text="✅ 关闭", command=win.destroy, bg="#4CAF50", fg="white").pack(side="left", padx=15)

    def _confirm_full_process(self):
        """确认执行完整拼接流程"""
        # 重新执行完整拼接（会先选择保存路径）
        self.stitch_images()

    # ========================
    #   新增：预览拼接功能
    # ========================
    def preview_stitch(self):
        if not self.image_paths:
            messagebox.showerror("错误", "无图片")
            return

        if self.layout_var.get() == "网格" and not self.resize_var.get():
            messagebox.showerror("配置错误", "网格模式下必须勾选前置统一尺寸并设置目标宽高！")
            return

        # 禁用控件
        self._disable_controls(True)
        self.status_var.set("正在预览拼接...")

        # 启动后台线程
        thread = threading.Thread(target=self._preview_worker, daemon=True)
        thread.start()

    def _preview_worker(self):
        """后台线程执行预览拼接"""
        try:
            # 提前读取所有必要参数（避免跨线程访问 Tk 变量）
            resize_enabled = self.resize_var.get()
            target_w = int(self.entry_width.get()) if resize_enabled else None
            target_h = int(self.entry_height.get()) if resize_enabled else None
            enhance_enabled = self.enhance_var.get()
            brightness = self.brightness_val.get()
            contrast = self.contrast_val.get()
            sharpness = self.sharpness_val.get()
            layout = self.layout_var.get()
            total = min(len(self.image_paths), 10)  # 限制预览最多前10张图片

            # 预览拼接（只处理第一页或全部）
            self.root.after(0, lambda: self.progress_var.set(70))
            
            if layout == "网格":
                # 对于网格模式，只预览第一页 - 使用流式处理
                cfg = self._get_config()
                # 只取前几页的路径进行预览
                preview_paths = self.image_paths[:min(cfg['rows'] * cfg['cols'], total)]
                
                # 为了快速预览，可以选择性跳过增强处理
                enhance_params = (brightness, contrast, sharpness) if enhance_enabled else None
                preview_result = self.grid_stitch_from_paths(
                    preview_paths,
                    rows=cfg['rows'],
                    cols=cfg['cols'],
                    h_spacing=cfg['h_spacing'],
                    v_spacing=cfg['v_spacing'],
                    margin=cfg['margin'],
                    img_w=target_w,
                    img_h=target_h,
                    enhance_params=enhance_params
                )
            else:
                # 对于水平/垂直模式，使用原有方式，但限制数量
                # 流式加载图片，分批处理
                images = []
                for i in range(total):
                    path = self.image_paths[i]
                    try:
                        # 流式加载图片
                        with Image.open(path) as im:
                            img = im.convert("RGB")
                            
                            if target_w and target_h:
                                img = img.resize((target_w, target_h), Image.LANCZOS)

                            # 应用增强（如果启用）
                            if enhance_enabled:
                                if brightness != 1.0:
                                    img = ImageEnhance.Brightness(img).enhance(brightness)
                                if contrast != 1.0:
                                    img = ImageEnhance.Contrast(img).enhance(contrast)
                                if sharpness != 1.0:
                                    img = ImageEnhance.Sharpness(img).enhance(sharpness)

                            images.append(img)
                    except Exception as e:
                        print(f"跳过 {path}: {e}")

                    # 更新进度
                    progress = (i / total) * 50
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))

                if not images:
                    raise ValueError("无有效图片")

                preview_result = self.stitch_by_layout(images, is_preview=True)[0]
                
                # 清理临时图片
                for img in images:
                    del img
                gc.collect()

            self.root.after(0, lambda: self.progress_var.set(90))

            # 保存预览结果供后续使用
            self._preview_result = preview_result
            
            # 在主线程显示预览
            self.root.after(0, lambda: self._show_preview_dialog(preview_result, is_preview=True))

        except Exception as e:
            # 错误也需在主线程弹窗
            self.root.after(0, lambda msg=str(e): messagebox.showerror("预览失败", msg))
        finally:
            # 清理加载的图片以释放内存
            gc.collect()
            
            # 恢复 UI
            self.root.after(0, lambda: [
                self.progress_var.set(0),
                self.status_var.set("就绪"),
                self._disable_controls(False),
                gc.collect()
            ])

    # ========================
    #   新增：PDF导出功能
    # ========================
    def export_pdf(self):
        if not self.image_paths:
            messagebox.showerror("错误", "无图片")
            return

        if self.layout_var.get() == "网格" and not self.resize_var.get():
            messagebox.showerror("配置错误", "网格模式下必须勾选前置统一尺寸并设置目标宽高！")
            return

        if not PDF_SUPPORT:
            messagebox.showerror("错误", "未安装 img2pdf 模块，无法导出 PDF。请安装 img2pdf 模块。")
            return

        # 询问保存位置
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        layout = self.layout_var.get()
        suffix = {"水平": "horizontal", "垂直": "vertical", "网格": "grid"}[layout]

        has_reversed = self.gen_row_reversed_var.get() and (layout == "网格")
        if has_reversed:
            suffix += "_with_reversed"

        base_name = f"{timestamp}_{suffix}"
        default_filename = f"{base_name}.pdf"
        pdf_path = filedialog.asksaveasfilename(
            title="保存PDF",
            defaultextension=".pdf",
            initialfile=default_filename,
            filetypes=[("PDF 文件", "*.pdf")]
        )
        if not pdf_path:
            return

        # 禁用控件
        self._disable_controls(True)
        self.status_var.set("正在导出PDF...")

        # 启动后台线程
        thread = threading.Thread(target=self._export_pdf_worker, args=(pdf_path,), daemon=True)
        thread.start()

    def _export_pdf_worker(self, pdf_path):
        """后台线程执行PDF导出"""
        try:
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

            # 如果是网格模式，需要先处理所有图片，然后分页拼接
            if layout == "网格":
                # 获取拼接配置
                cfg = self._get_config()
                rows, cols = cfg['rows'], cfg['cols']
                per_page = rows * cols

                # 临时存储处理后的图片
                temp_images = []

                # 分页拼接并保存 - 流式处理
                for i in range(0, len(self.image_paths), per_page):
                    # 当前页的图片路径
                    page_paths = self.image_paths[i:i+per_page]
                    
                    # 直接流式拼接，不缓存图像
                    try:
                        enhance_params = (brightness, contrast, sharpness) if enhance_enabled else None
                        page_result = self.grid_stitch_from_paths(
                            page_paths,
                            rows=cfg['rows'],
                            cols=cfg['cols'],
                            h_spacing=cfg['h_spacing'],
                            v_spacing=cfg['v_spacing'],
                            margin=cfg['margin'],
                            img_w=target_w,
                            img_h=target_h,
                            enhance_params=enhance_params,
                            is_preview=False  # 标记为非预览模式（完整处理）
                        )
                    except Exception as e:
                        print(f"拼接页面失败: {e}")
                        continue

                    if page_result is None:
                        continue  # 跳过空页面
                    
                    # 应用翻转
                    mode = self.flip_mode.get()
                    if mode == "上下翻转":
                        page_result = page_result.transpose(Image.FLIP_TOP_BOTTOM)
                    elif mode == "左右翻转":
                        page_result = page_result.transpose(Image.FLIP_LEFT_RIGHT)
                    
                    # 保存到临时列表
                    temp_images.append(page_result)

                    # 释放当前页图片内存
                    del page_result
                    gc.collect()

                    # 更新进度
                    page_progress = 50 + ((i + len(page_paths)) / total) * 40
                    self.root.after(0, lambda p=min(page_progress, 90): self.progress_var.set(p))

                # 如果需要生成反转版
                if self.gen_row_reversed_var.get():
                    # 重新处理一遍生成反转版，使用流式处理
                    for i in range(0, len(self.image_paths), per_page):
                        # 当前页的图片路径
                        page_paths = self.image_paths[i:i+per_page]
                        
                        # 生成反转版网格
                        reversed_list = []
                        for r in range(rows):
                            start = r * cols
                            end = start + cols
                            row_paths = page_paths[start:end]
                            if len(row_paths) > 0:  # 确保有图片才反转
                                reversed_list.extend(reversed(row_paths))
                        
                        if reversed_list:  # 确保有图片才处理
                            try:
                                enhance_params = (brightness, contrast, sharpness) if enhance_enabled else None
                                reversed_result = self.grid_stitch_from_paths(
                                    reversed_list,
                                    rows=cfg['rows'],
                                    cols=cfg['cols'],
                                    h_spacing=cfg['h_spacing'],
                                    v_spacing=cfg['v_spacing'],
                                    margin=cfg['margin'],
                                    img_w=target_w,
                                    img_h=target_h,
                                    enhance_params=enhance_params,
                                    is_preview=False  # 标记为非预览模式（完整处理）
                                )
                            except Exception as e:
                                print(f"拼接反转页面失败: {e}")
                                continue
                            
                            # 应用翻转
                            mode = self.flip_mode.get()
                            if mode == "上下翻转":
                                reversed_result = reversed_result.transpose(Image.FLIP_TOP_BOTTOM)
                            elif mode == "左右翻转":
                                reversed_result = reversed_result.transpose(Image.FLIP_LEFT_RIGHT)
                            
                            # 保存到临时列表
                            temp_images.append(reversed_result)

                            # 释放反转版图片内存
                            del reversed_result

                        gc.collect()

                        # 更新进度
                        rev_progress = 90 + ((i + len(page_paths)) / total) * 10
                        self.root.after(0, lambda p=min(rev_progress, 100): self.progress_var.set(p))

                # 将所有图像转换为PDF
                temp_bytes_list = []
                for img in temp_images:
                    # 将图像转换为字节
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='JPEG', quality=95)
                    temp_bytes_list.append(img_byte_arr.getvalue())
                    del img  # 删除图像对象
                
                # 使用img2pdf将字节数据转换为PDF
                pdf_bytes = img2pdf.convert(temp_bytes_list)
                
                # 保存PDF文件
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)

                # 清理临时数据
                del temp_bytes_list[:]
                del temp_bytes_list
                gc.collect()

            else:  # 水平或垂直布局
                # 对于非网格模式，一次处理所有图片
                processed_images = []
                for i, path in enumerate(self.image_paths):
                    try:
                        # 使用快速加载函数（如果OpenCV可用）
                        if OPENCV_AVAILABLE and target_w and target_h:
                            img = fast_load_and_resize(path, target_w, target_h)
                        else:
                            # 流式加载图片（回退到原来的方法）
                            with Image.open(path) as im:
                                # JPEG 解码优化
                                if im.format == 'JPEG':
                                    im.draft("RGB", (target_w * 2 if target_w else 2000, target_h * 2 if target_h else 2000))
                                
                                img = im.convert("RGB")
                                
                                if target_w and target_h:
                                    img = img.resize((target_w, target_h), Image.LANCZOS)

                                # 应用增强
                                if enhance_enabled:
                                    if brightness != 1.0:
                                        img = ImageEnhance.Brightness(img).enhance(brightness)
                                    if contrast != 1.0:
                                        img = ImageEnhance.Contrast(img).enhance(contrast)
                                    if sharpness != 1.0:
                                        img = ImageEnhance.Sharpness(img).enhance(sharpness)

                        processed_images.append(img)
                    except Exception as e:
                        print(f"跳过 {path}: {e}")

                    # 更新进度
                    progress = (i / total) * 50
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))

                if not processed_images:
                    raise ValueError("无有效图片")

                # 拼接
                if layout == "水平":
                    result = self.horizontal_stitch(processed_images)
                else:  # 垂直
                    result = self.vertical_stitch(processed_images)

                # 应用翻转
                mode = self.flip_mode.get()
                if mode == "上下翻转":
                    result = result.transpose(Image.FLIP_TOP_BOTTOM)
                elif mode == "左右翻转":
                    result = result.transpose(Image.FLIP_LEFT_RIGHT)

                # 将拼接结果保存到PDF
                img_byte_arr = io.BytesIO()
                result.save(img_byte_arr, format='JPEG', quality=95)
                pdf_bytes = img2pdf.convert([img_byte_arr.getvalue()])
                
                # 保存PDF文件
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                
                # 释放内存
                del result
                for img in processed_images:
                    del img
                del img_byte_arr

            self.root.after(0, lambda: self.progress_var.set(100))

            # 显示完成消息
            self.root.after(0, lambda: messagebox.showinfo("成功", f"PDF生成完成！\n已保存到：{pdf_path}"))

        except Exception as e:
            # 错误也需在主线程弹窗
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("PDF生成失败", msg))
        finally:
            # 清理加载的图片以释放内存
            gc.collect()
            
            # 恢复 UI
            self.root.after(0, lambda: [
                self.progress_var.set(0),
                self.status_var.set("就绪"),
                self._disable_controls(False),
                gc.collect()
            ])

# === 启动 ===
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageStitcher(root)
    root.mainloop()