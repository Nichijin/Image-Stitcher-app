from PIL import Image, ImageEnhance
import numpy as np
from typing import List, Tuple, Optional
from .utils import OPENCV_AVAILABLE
from .memory_pool import memory_pool

# 检查libvips是否可用
LIBVIPS_AVAILABLE = False
try:
    import pyvips
    # 测试是否能实际使用libvips
    # 尝试创建一个简单的图像来验证libvips是否正常工作
    test_img = pyvips.Image.black(10, 10)
    LIBVIPS_AVAILABLE = True
except Exception as e:
    print(f"libvips 初始化失败: {e}")
    LIBVIPS_AVAILABLE = False

if OPENCV_AVAILABLE:
    import cv2

def get_optimal_interpolation(src_size, dst_size):
    """根据源尺寸和目标尺寸选择最佳插值方法"""
    src_area = src_size[0] * src_size[1]
    dst_area = dst_size[0] * dst_size[1]
    scale = dst_area / src_area
    
    if scale < 0.1:
        # 大幅缩小，速度优先
        return cv2.INTER_NEAREST
    elif scale < 0.5:
        # 中度缩小，平衡速度和质量
        return cv2.INTER_LINEAR
    elif scale < 2.0:
        # 小幅缩放，质量优先
        return cv2.INTER_CUBIC
    else:
        # 放大，高质量
        return cv2.INTER_LANCZOS4

def multi_level_resize(img, target_w: int, target_h: int) -> np.ndarray:
    """多级缩放，提高大图像缩放速度"""
    import cv2
    import numpy as np
    
    h, w = img.shape[:2]
    
    # 计算当前尺寸与目标尺寸的比例
    scale = min(target_w / w, target_h / h)
    
    # 如果需要大幅缩小，使用多级缩放
    if scale < 0.5:
        # 第一级缩放到中间尺寸
        mid_w = int(w * 0.5)
        mid_h = int(h * 0.5)
        mid_resized = cv2.resize(img, (mid_w, mid_h), interpolation=cv2.INTER_LINEAR)
        
        # 第二级缩放到目标尺寸
        # 根据中间尺寸和目标尺寸选择插值方法
        final_interpolation = get_optimal_interpolation(
            (mid_w, mid_h),
            (target_w, target_h)
        )
        final_resized = cv2.resize(mid_resized, (target_w, target_h), interpolation=final_interpolation)
        return final_resized
    else:
        # 直接缩放到目标尺寸
        interpolation = get_optimal_interpolation(
            (w, h),
            (target_w, target_h)
        )
        return cv2.resize(img, (target_w, target_h), interpolation=interpolation)


# 实现简单的缓存机制
# 由于PIL Image对象不能被直接缓存，我们使用一个字典来缓存处理结果
_image_cache = {}
_cache_max_size = 100  # 缓存最大数量

# 生成缓存键
def _get_cache_key(path: str, target_w: int, target_h: int) -> str:
    """生成缓存键"""
    import os
    # 使用绝对路径以确保一致性
    abs_path = os.path.abspath(path)
    return f"{abs_path}_{target_w}_{target_h}"

def fast_load_and_resize(path: str, target_w: int, target_h: int) -> Image.Image:
    """快速加载并缩放图像，优先使用 libvips，其次 OpenCV，最后 PIL"""
    import os
    # 检查文件是否存在
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在: {path}")
    
    # 检查文件是否为有效文件
    if not os.path.isfile(path):
        raise ValueError(f"不是有效文件: {path}")
    
    # 如果目标尺寸为 None，返回原始尺寸
    if target_w is None or target_h is None:
        im = Image.open(path)
        img = im.convert("RGB")
        return img
    
    # 检查缓存
    cache_key = _get_cache_key(path, target_w, target_h)
    if cache_key in _image_cache:
        # 从缓存中获取
        img_np = _image_cache[cache_key]
        return Image.fromarray(img_np)
    
    # 如果 libvips 可用，优先使用 libvips 加载和缩放
    if LIBVIPS_AVAILABLE:
        try:
            import pyvips
            
            # 使用 libvips 打开图像
            img = pyvips.Image.new_from_file(path, access='sequential')
            
            # 计算缩放比例
            scale_x = target_w / img.width
            scale_y = target_h / img.height
            scale = min(scale_x, scale_y)
            
            # 缩放图像
            # 使用 lanczos3 插值，质量高且速度快
            resized = img.resize(scale, kernel='lanczos3')
            
            # 确保图像是 RGB 格式
            if resized.bands == 4:
                # 如果是 RGBA，转换为 RGB
                resized = resized.flatten()
            elif resized.bands == 1:
                # 如果是灰度，转换为 RGB
                resized = resized.bandjoin([resized, resized, resized])
            
            # 直接转换为 PIL Image，避免中间 numpy 数组
            # 获取图像数据
            data = resized.write_to_memory()
            # 创建 PIL Image
            img = Image.frombuffer(
                'RGB',
                [resized.width, resized.height],
                data,
                'raw',
                'RGB',
                0,
                1
            )
            
            # 更新缓存
            cache_key = _get_cache_key(path, target_w, target_h)
            img_np = np.array(img)
            # 检查缓存大小
            if len(_image_cache) >= _cache_max_size:
                # 移除最旧的缓存项
                oldest_key = next(iter(_image_cache))
                del _image_cache[oldest_key]
            _image_cache[cache_key] = img_np
            
            return img
        except Exception as e:
            print(f"libvips 处理失败: {e}")
            pass
    
    # 如果 OpenCV 可用，使用 OpenCV 加载和缩放
    if OPENCV_AVAILABLE:
        try:
            import cv2
            import numpy as np
            from .memory_pool import memory_pool
            
            # 直接使用 imdecode 支持中文路径
            try:
                # 使用 np.fromfile 读取文件内容
                img_array = np.fromfile(path, dtype=np.uint8)
                # 使用 cv2.imdecode 解码图像
                img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if img_bgr is not None:
                    # 使用内存池进行图像处理
                    from .memory_pool import memory_pool
                    
                    # 从内存池获取数组用于存储缩放结果
                    resized_shape = (target_h, target_w, 3)
                    resized = memory_pool.get(resized_shape, dtype=np.uint8)
                    
                    try:
                        # 使用多级缩放提高速度
                        # 注意：这里我们需要修改multi_level_resize函数以支持输出数组
                        # 为了保持兼容性，我们先使用原始实现，然后将结果复制到内存池数组
                        temp_resized = multi_level_resize(img_bgr, target_w, target_h)
                        resized[:] = temp_resized
                    except Exception as e:
                        print(f"内存池使用失败: {e}")
                        # 回退到原始方法
                        resized = multi_level_resize(img_bgr, target_w, target_h)
                
                # 转为 RGB 格式 (PIL 需要)
                from .memory_pool import memory_pool
                rgb_shape = (target_h, target_w, 3)
                resized_rgb = memory_pool.get(rgb_shape, dtype=np.uint8)
                
                try:
                    cv2.cvtColor(resized, cv2.COLOR_BGR2RGB, dst=resized_rgb)
                except Exception as e:
                    print(f"颜色转换失败: {e}")
                    # 回退到原始方法
                    resized_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                
                # 转回 PIL Image 用于粘贴
                result = Image.fromarray(resized_rgb)
                
                # 更新缓存
                cache_key = _get_cache_key(path, target_w, target_h)
                img_np = np.array(result)
                # 检查缓存大小
                if len(_image_cache) >= _cache_max_size:
                    # 移除最旧的缓存项
                    oldest_key = next(iter(_image_cache))
                    del _image_cache[oldest_key]
                _image_cache[cache_key] = img_np
                
                # 归还内存池数组
                try:
                    memory_pool.put(resized)
                    memory_pool.put(resized_rgb)
                except Exception as e:
                    print(f"内存池归还失败: {e}")
                
                return result
            except Exception as e:
                print(f"OpenCV 处理失败: {e}")
                pass
            
            # 回退到 PIL
            pass
        except Exception as e:
            print(f"OpenCV 不可用: {e}")
            # 回退到 PIL
            pass
    
    # 回退到 PIL 缩放
    with Image.open(path) as im:
        if im.format == 'JPEG':
            # 使用 draft 方法加速 JPEG 加载
            im.draft("RGB", (target_w, target_h))
        img = im.convert("RGB")
        # 根据目标尺寸选择合适的 resize 方法
        if target_w * target_h < 1000000:
            resized_img = img.resize((target_w, target_h), Image.BILINEAR)
        else:
            resized_img = img.resize((target_w, target_h), Image.LANCZOS)
        
        # 更新缓存
        cache_key = _get_cache_key(path, target_w, target_h)
        img_np = np.array(resized_img)
        # 检查缓存大小
        if len(_image_cache) >= _cache_max_size:
            # 移除最旧的缓存项
            oldest_key = next(iter(_image_cache))
            del _image_cache[oldest_key]
        _image_cache[cache_key] = img_np
        
        return resized_img


def create_canvas_numpy(width: int, height: int) -> np.ndarray:
    """创建白色画布 (H, W, C)"""
    return np.full((height, width, 3), 255, dtype=np.uint8)


def paste_tile_numpy(canvas_np: np.ndarray, tile_img: Image.Image, x: int, y: int) -> None:
    """直接将 PIL 图像粘贴到 NumPy 画布"""
    tile_np = np.array(tile_img)  # (H, W, 3)
    h, w = tile_np.shape[:2]
    canvas_np[y:y+h, x:x+w] = tile_np


def apply_enhancements(img: Image.Image, brightness: float = 0, contrast: float = 0, sharpness: float = 0) -> Image.Image:
    """应用图像增强（PS风格参数）
    
    Args:
        img: 输入图像
        brightness: 亮度调整 (-100 到 100)
        contrast: 对比度调整 (-100 到 100)
        sharpness: 锐化调整 (0 到 100)
        
    Returns:
        增强后的图像
    """
    # 如果不需要增强，直接返回
    if brightness == 0 and contrast == 0 and sharpness == 0:
        return img
    
    # 转换为 NumPy 数组进行快速处理
    img_np = np.array(img, dtype=np.float32)
    
    # 应用亮度增强（PS风格：-100到100映射到0到2）
    if brightness != 0:
        brightness_factor = 1.0 + (brightness / 100.0)
        img_np *= brightness_factor
    
    # 应用对比度增强（PS风格：-100到100映射到0到2）
    if contrast != 0:
        contrast_factor = 1.0 + (contrast / 100.0)
        img_np = (img_np - 128) * contrast_factor + 128
    
    # 应用锐度增强（PS风格：0到100映射到0到3）
    if sharpness != 0:
        # 确保图像是 uint8 类型
        img_np_uint8 = np.clip(img_np, 0, 255).astype(np.uint8)
        
        # 计算锐化因子（0到100映射到0到3）
        sharpness_factor = 1.0 + (sharpness / 50.0)
        
        # 使用更高效的锐化方法
        if sharpness_factor > 1.0:
            # 锐化增强
            # 使用简单的锐化 kernel
            kernel = np.array([[-1, -1, -1],
                              [-1, 9, -1],
                              [-1, -1, -1]])
            
            # 直接使用 NumPy 进行卷积，避免 scipy 依赖
            from .memory_pool import memory_pool
            result_shape = img_np_uint8.shape
            result = memory_pool.get(result_shape, dtype=np.uint8)
            
            # 手动实现简单的卷积（对于小 kernel 更高效）
            h, w = img_np_uint8.shape[:2]
            for i in range(1, h-1):
                for j in range(1, w-1):
                    if len(img_np_uint8.shape) == 3:
                        # 彩色图像
                        for c in range(3):
                            result[i, j, c] = np.sum(img_np_uint8[i-1:i+2, j-1:j+2, c] * kernel)
                    else:
                        # 灰度图像
                        result[i, j] = np.sum(img_np_uint8[i-1:i+2, j-1:j+2] * kernel)
            
            # 混合原始图像和锐化图像
            blend_factor = (sharpness_factor - 1.0) / 2.0
            img_np = img_np_uint8 * (1.0 - blend_factor) + result * blend_factor
            
            # 归还内存
            memory_pool.put(result)
        else:
            # 锐化减弱（模糊）
            from .memory_pool import memory_pool
            result_shape = img_np_uint8.shape
            result = memory_pool.get(result_shape, dtype=np.uint8)
            
            # 简单的均值模糊
            h, w = img_np_uint8.shape[:2]
            for i in range(1, h-1):
                for j in range(1, w-1):
                    if len(img_np_uint8.shape) == 3:
                        # 彩色图像
                        for c in range(3):
                            result[i, j, c] = np.mean(img_np_uint8[i-1:i+2, j-1:j+2, c])
                    else:
                        # 灰度图像
                        result[i, j] = np.mean(img_np_uint8[i-1:i+2, j-1:j+2])
            
            # 混合原始图像和模糊图像
            blend_factor = 1.0 - sharpness_factor
            img_np = img_np_uint8 * (1.0 - blend_factor) + result * blend_factor
            
            # 归还内存
            memory_pool.put(result)
    
    # 确保值在有效范围内并转换回 PIL Image
    img_np = np.clip(img_np, 0, 255).astype(np.uint8)
    result = Image.fromarray(img_np)
    # 释放临时数组
    from .memory_pool import memory_pool
    memory_pool.put(img_np)
    return result


def load_and_enhance_image(path: str, target_w: int, target_h: int, brightness: float = 0, contrast: float = 0, sharpness: float = 0) -> Image.Image:
    """加载并增强图像
    
    Args:
        path: 图像路径
        target_w: 目标宽度
        target_h: 目标高度
        brightness: 亮度调整 (-100 到 100)
        contrast: 对比度调整 (-100 到 100)
        sharpness: 锐化调整 (0 到 100)
        
    Returns:
        处理后的图像
    """
    img = fast_load_and_resize(path, target_w, target_h)
    img = apply_enhancements(img, brightness, contrast, sharpness)
    return img


def stitch_horizontal(images: List[str], target_width: int, target_height: int, enhance_enabled: bool, brightness: float, contrast: float, sharpness: float) -> Image.Image:
    """水平拼接图像"""
    # 过滤掉无法读取的图片和None占位符
    valid_images = []
    for path in images:
        # 跳过None占位符
        if path is None:
            continue
        try:
            if enhance_enabled:
                img = load_and_enhance_image(path, target_width, target_height, brightness, contrast, sharpness)
            else:
                img = fast_load_and_resize(path, target_width, target_height)
            valid_images.append(img)
        except Exception as e:
            print(f"跳过 {path}: {e}")
    
    if not valid_images:
        raise ValueError("没有有效的图片可以拼接")
    
    total_width = len(valid_images) * target_width
    max_height = target_height
    canvas = Image.new('RGB', (total_width, max_height), (255, 255, 255))
    
    x_offset = 0
    for img in valid_images:
        canvas.paste(img, (x_offset, 0))
        x_offset += target_width
    return canvas


def stitch_vertical(images: List[str], target_width: int, target_height: int, enhance_enabled: bool, brightness: float, contrast: float, sharpness: float) -> Image.Image:
    """垂直拼接图像"""
    # 过滤掉无法读取的图片和None占位符
    valid_images = []
    for path in images:
        # 跳过None占位符
        if path is None:
            continue
        try:
            if enhance_enabled:
                img = load_and_enhance_image(path, target_width, target_height, brightness, contrast, sharpness)
            else:
                img = fast_load_and_resize(path, target_width, target_height)
            valid_images.append(img)
        except Exception as e:
            print(f"跳过 {path}: {e}")
    
    if not valid_images:
        raise ValueError("没有有效的图片可以拼接")
    
    max_width = target_width
    total_height = len(valid_images) * target_height
    canvas = Image.new('RGB', (max_width, total_height), (255, 255, 255))
    
    y_offset = 0
    for img in valid_images:
        canvas.paste(img, (0, y_offset))
        y_offset += target_height
    return canvas


def stitch_grid(
    images: List[str],
    rows: int,
    cols: int,
    target_width: int,
    target_height: int,
    h_spacing: int,
    v_spacing: int,
    margin_top: int,
    margin_bottom: int,
    margin_left: int,
    margin_right: int,
    enhance_enabled: bool,
    brightness: float,
    contrast: float,
    sharpness: float,
    show_grid: bool = False,
    flip_mode: str = "无"
) -> Image.Image:
    """网格拼接图像"""
    # 过滤掉无法读取的图片和处理None占位符
    valid_images = []
    for path in images:
        # 处理None占位符
        if path is None:
            valid_images.append(None)
            continue
        try:
            if enhance_enabled:
                img = load_and_enhance_image(path, target_width, target_height, brightness, contrast, sharpness)
            else:
                img = fast_load_and_resize(path, target_width, target_height)
            valid_images.append(img)
        except Exception as e:
            print(f"跳过 {path}: {e}")
            valid_images.append(None)
    
    # 检查是否有有效图像（非None）
    valid_count = sum(1 for img in valid_images if img is not None)
    if valid_count == 0:
        raise ValueError("没有有效的图片可以拼接")
    
    # 计算画布大小
    canvas_width = margin_left + margin_right + cols * target_width + (cols - 1) * h_spacing
    canvas_height = margin_top + margin_bottom + rows * target_height + (rows - 1) * v_spacing
    canvas = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))
    
    # 绘制网格线（如果需要）
    if show_grid:
        from PIL import ImageDraw
        draw = ImageDraw.Draw(canvas)
        # 垂直线
        for i in range(cols + 1):
            x = margin_left + i * (target_width + h_spacing)
            draw.line([(x, margin_top), (x, canvas_height - margin_bottom)], fill=(0, 0, 0), width=1)
        # 水平线
        for i in range(rows + 1):
            y = margin_top + i * (target_height + v_spacing)
            draw.line([(margin_left, y), (canvas_width - margin_right, y)], fill=(0, 0, 0), width=1)
    
    # 粘贴图像
    idx = 0
    for row in range(rows):
        for col in range(cols):
            if idx >= len(valid_images):
                break
            # 跳过None占位符
            if valid_images[idx] is None:
                idx += 1
                continue
            x = margin_left + col * (target_width + h_spacing)
            y = margin_top + row * (target_height + v_spacing)
            img = valid_images[idx]
            canvas.paste(img, (x, y))
            idx += 1
    
    # 应用翻转
    if flip_mode == "上下翻转":
        canvas = canvas.transpose(Image.FLIP_TOP_BOTTOM)
    elif flip_mode == "左右翻转":
        canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)
    
    return canvas


def process_image_batch(
    image_paths: List[str],
    config: dict,
    progress_callback: Optional[callable] = None,
    preview_mode: bool = False
) -> List[Image.Image]:
    """批量处理图像并返回拼接结果"""
    results = []
    layout = config.get("layout")
    target_width = config.get("target_width", 800)
    target_height = config.get("target_height", 600)
    
    enhance_enabled = config.get("enhance_enabled", False)
    brightness = config.get("brightness", 1.0)
    contrast = config.get("contrast", 1.0)
    sharpness = config.get("sharpness", 1.0)
    
    if layout == "水平":
        result = stitch_horizontal(image_paths, target_width, target_height, enhance_enabled, brightness, contrast, sharpness)
        results.append(result)
    elif layout == "垂直":
        result = stitch_vertical(image_paths, target_width, target_height, enhance_enabled, brightness, contrast, sharpness)
        results.append(result)
    elif layout == "网格":
        rows = config.get("rows", 2)
        cols = config.get("cols", 2)
        h_spacing = config.get("h_spacing", 30)
        v_spacing = config.get("v_spacing", 30)
        margin_top = config.get("margin_top", 0)
        margin_bottom = config.get("margin_bottom", 0)
        margin_left = config.get("margin_left", 0)
        margin_right = config.get("margin_right", 0)
        show_grid = config.get("show_grid", False)
        flip_mode = config.get("flip_mode", "无")
        
        # 计算页数
        total_cells = rows * cols
        pages = (len(image_paths) + total_cells - 1) // total_cells
        
        # 预览模式下只处理第一页
        max_pages = 1 if preview_mode else pages
        
        for i in range(max_pages):
            start = i * total_cells
            end = min(start + total_cells, len(image_paths))
            page_images = image_paths[start:end]
            
            result = stitch_grid(
                page_images, rows, cols, target_width, target_height,
                h_spacing, v_spacing, margin_top, margin_bottom,
                margin_left, margin_right, enhance_enabled,
                brightness, contrast, sharpness, show_grid, flip_mode
            )
            results.append(result)
            
            # 生成反向版本（如果需要）
            if config.get("gen_row_reversed", False) and not preview_mode:
                reversed_result = stitch_grid(
                    page_images, rows, cols, target_width, target_height,
                    h_spacing, v_spacing, margin_top, margin_bottom,
                    margin_left, margin_right, enhance_enabled,
                    brightness, contrast, sharpness, show_grid, flip_mode
                )
                # 这里可以添加行反转逻辑
                results.append(reversed_result)
    
    return results