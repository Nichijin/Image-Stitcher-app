import json
import os
from typing import Dict, Any
from .constants import (
    DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT,
    DEFAULT_TARGET_WIDTH, DEFAULT_TARGET_HEIGHT,
    DEFAULT_ROWS, DEFAULT_COLS, DEFAULT_H_SPACING, DEFAULT_V_SPACING,
    DEFAULT_MARGIN
)

SCHEMES_DIR = "schemes"
os.makedirs(SCHEMES_DIR, exist_ok=True)


def get_current_config(self) -> Dict[str, Any]:
    """获取当前配置"""
    cfg = {
        "a4_mode": self.a4_mode_var.get(),
        "landscape": self.landscape_var.get(),
        "canvas_width": int(self.entry_canvas_width.get()) if not self.a4_mode_var.get() else DEFAULT_CANVAS_WIDTH,
        "canvas_height": int(self.entry_canvas_height.get()) if not self.a4_mode_var.get() else DEFAULT_CANVAS_HEIGHT,

        "resize": self.resize_var.get(),
        "target_width": int(self.entry_width.get()) if self.resize_var.get() else DEFAULT_TARGET_WIDTH,
        "target_height": int(self.entry_height.get()) if self.resize_var.get() else DEFAULT_TARGET_HEIGHT,

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


def save_config(config: Dict[str, Any], filename: str) -> bool:
    """保存配置到文件"""
    try:
        filepath = os.path.join(SCHEMES_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False


def load_config(filename: str) -> Dict[str, Any]:
    """从文件加载配置"""
    try:
        filepath = os.path.join(SCHEMES_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"加载配置失败: {e}")
        return {}


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """校验配置并补充默认值"""
    defaults = {
        "a4_mode": False,
        "landscape": False,
        "canvas_width": DEFAULT_CANVAS_WIDTH,
        "canvas_height": DEFAULT_CANVAS_HEIGHT,
        "resize": True,
        "target_width": DEFAULT_TARGET_WIDTH,
        "target_height": DEFAULT_TARGET_HEIGHT,
        "layout": "水平",
        "rows": DEFAULT_ROWS,
        "cols": DEFAULT_COLS,
        "h_spacing": DEFAULT_H_SPACING,
        "v_spacing": DEFAULT_V_SPACING,
        "multi_page": True,
        "gen_row_reversed": False,
        "margin_top": DEFAULT_MARGIN,
        "margin_bottom": DEFAULT_MARGIN,
        "margin_left": DEFAULT_MARGIN,
        "margin_right": DEFAULT_MARGIN,
        "flip_mode": "无",
        "show_grid": False,
        "enhance_enabled": False,
        "brightness": 1.0,
        "contrast": 1.0,
        "sharpness": 1.0,
    }
    for key, default in defaults.items():
        if key not in config:
            config[key] = default
    return config