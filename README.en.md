# 🖼️ Image Stitcher

[中文（默认）](./README.md) | [English](./README.en.md)

> A one-stop image stitching solution for Windows. Stitch multiple photos into polished collages with grid, horizontal, and vertical layouts.

[Features](#features) • [System Requirements](#system-requirements) • [Quick Start](#quick-start) • [Installation](#installation) • [User Guide](#usage-guide)

<a id="toc"></a>
## 📚 Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Installation](#installation)
- [User Guide](#usage-guide)
- [Configuration](#configuration)
- [Image Generation Optimization](#image-optimization)
- [Architecture](#architecture)
- [Project Structure](#file-structure)
- [FAQ](#faq)
- [Changelog](#changelog)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

<a id="features"></a>
## 🎯 Features

### Core Features

- Multiple stitch layouts: Horizontal, Vertical, Grid
- Image enhancement: Brightness, Contrast, Sharpness
- Batch processing: Automatic pagination for large image sets
- Image flipping: Top-bottom / Left-right
- Reversed output generation for grid rows
- Grid line rendering for visual alignment/debugging
- A4 mode with portrait/landscape presets

### Advanced Features

- Multi-threaded processing pipeline (load, preprocess, stitch, postprocess, save)
- Memory optimization and resource monitoring
- Config persistence and reload
- Scheme save/load management
- Real-time progress and status updates

<a id="system-requirements"></a>
## 🖥️ System Requirements

- OS: Windows 10/11
- Python: 3.8+
- Memory: 4GB+ recommended for large batches
- Display: 1280x720+ recommended

---

<a id="quick-start"></a>
## 🚀 Quick Start

### Minimal 3-step workflow

1. Select images (multi-select or folder import).
2. Choose layout (Horizontal/Vertical/Grid).
3. Click **Start Stitching**, choose output folder, and wait for completion.

### Typical scenarios

| Scenario | Recommended Setup | Notes |
| --- | --- | --- |
| Quick merge | Horizontal/Vertical | Fast, small image sets |
| Photo wall | Grid (2-4 rows, 2-4 cols) | Good for collages |
| Print-ready output | A4 mode | Consistent page sizing |

### Performance references

| Image Count | Time Estimate | Memory | Recommendation |
| --- | --- | --- | --- |
| 1-10 | < 10s | < 500MB | Enable high quality |
| 10-50 | 10-30s | 0.5-1GB | Balanced setup |
| 50-100 | 30-60s | 1GB+ | Lower resolution |
| 100+ | 1-2 min | 2GB+ | Use paging |

<a id="installation"></a>
## 📦 Installation

### Option 1: Prebuilt EXE

1. Use `dist/ImageStitcher.exe`
2. Double-click to run (no Python install needed)

### Option 2: Run from source

```bash
pip install -r requirements.txt
python run.py
```

### Dependencies

- `Pillow` (PIL)
- `numpy`
- `psutil` (optional, resource monitor)

<a id="usage-guide"></a>
## 🚀 User Guide

### Start the app

Run `ImageStitcher.exe` or `python run.py`.

### Basic workflow

1. **Select images**
2. **Configure parameters**
3. **Start stitching**

### Layout modes

- **Horizontal**: one-row panorama style
- **Vertical**: one-column stack
- **Grid**: row/column matrix with spacing and margins

### Enhancement controls

When resizing is enabled, you can set:

- Target Width/Height
- Brightness (-100 ~ +100)
- Contrast (-100 ~ +100)
- Sharpness (-100 ~ +100)

### Flip modes

- None
- Vertical flip
- Horizontal flip

### Reversed version generation

In grid mode, row-reversed generation can:

- Reverse order inside each row
- Keep empty slots in reversal logic
- Output files with `_reversed` suffix

### A4 mode

- A4 preset dimensions (210mm x 297mm)
- Portrait/landscape support
- Better print layout consistency

<a id="configuration"></a>
## ⚙️ Configuration

### Config file

- `image_stitcher_config.json`

### Main config fields

```json
{
  "a4_mode": false,
  "landscape": false,
  "canvas_width": 800,
  "canvas_height": 600,
  "resize": true,
  "target_width": 800,
  "target_height": 600,
  "layout": "grid",
  "rows": 2,
  "cols": 4,
  "h_spacing": 30,
  "v_spacing": 30,
  "multi_page": true,
  "gen_row_reversed": false,
  "margin_top": 50,
  "margin_bottom": 50,
  "margin_left": 50,
  "margin_right": 50,
  "flip_mode": "none",
  "show_grid": false,
  "enhance_enabled": false,
  "brightness": 0,
  "contrast": 0,
  "sharpness": 0
}
```

### Schemes

- Save current options as a `.json` scheme
- Reload scheme files anytime

<a id="image-optimization"></a>
## 🚀 Image Generation Optimization

This project includes optimization across:

- Parallel processing pipeline
- Memory monitoring and adaptive workers
- Efficient resize/enhancement paths
- Async output save

Pipeline stages:

1. Load images
2. Resize / preprocess
3. Enhance (optional)
4. Stitch layout
5. Postprocess (flip/reverse)
6. Async save

<a id="architecture"></a>
## 🏗️ Architecture

Main modules:

- `run.py`: entry script
- `image_stitcher/app.py`: Tkinter UI and orchestration
- `image_stitcher/pipeline_pool.py`: multi-pipeline scheduling
- `image_stitcher/pipeline.py`: staged task workers
- `image_stitcher/image_processor.py`: load/resize/enhance/stitch helpers
- `image_stitcher/async_saver.py`: asynchronous saving
- `image_stitcher/resource_monitor.py`: runtime resource heuristics
- `image_stitcher/config.py`: config persistence

<a id="file-structure"></a>
## 📁 Project Structure

```text
image0/
├─ run.py
├─ README.md
├─ README.zh-CN.md
├─ README.en.md
├─ image_stitcher/
│  ├─ app.py
│  ├─ pipeline.py
│  ├─ pipeline_pool.py
│  ├─ image_processor.py
│  ├─ async_saver.py
│  ├─ resource_monitor.py
│  ├─ config.py
│  ├─ constants.py
│  └─ utils.py
└─ schemes/
```

<a id="faq"></a>
## ❓ FAQ

- **Out of memory**: Reduce image count, disable enhancement, lower output size.
- **Slow processing**: Reduce target size, use paging, and avoid excessive enhancements.
- **Slow saving**: Use SSD, reduce JPEG quality if needed.
- **UI freeze suspicion**: Check long-running task status and allow workers to complete.

<a id="changelog"></a>
## 📝 Changelog

- Added stable anchor links for reliable GitHub navigation
- Added bilingual documentation files
- Default README set to Chinese

<a id="contributing"></a>
## 🤝 Contributing

Issues and pull requests are welcome.

<a id="license"></a>
## 📄 License

Please follow repository license policy.

<a id="acknowledgements"></a>
## 🙏 Acknowledgements

Thanks to all contributors and users.
