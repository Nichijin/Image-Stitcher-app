# Image Stitcher

[中文（默认）](./README.md#chinese-version) | [English](./README.en.md)

A one-stop image stitching solution for Windows.

[Features](#en-features) • [System Requirements](#en-system-requirements) • [Quick Start](#en-quick-start) • [Installation](#en-installation) • [Usage Guide](#en-usage-guide)

<a id="en-toc"></a>
## Table of Contents

- [Features](#en-features)
- [System Requirements](#en-system-requirements)
- [Quick Start](#en-quick-start)
- [Installation](#en-installation)
- [Usage Guide](#en-usage-guide)
- [Configuration](#en-configuration)
- [Image Optimization](#en-image-optimization)
- [Architecture](#en-architecture)
- [File Structure](#en-file-structure)
- [FAQ](#en-faq)

<a id="en-features"></a>
## Features

- Multiple layouts: Horizontal, Vertical, Grid
- Image enhancement: Brightness, Contrast, Sharpness
- Batch processing with pagination
- Global flip modes and row-reversed generation (grid)
- Grid line overlay for alignment/debugging
- A4 mode presets for print workflows
- Multi-threaded processing pipeline and async save

<a id="en-system-requirements"></a>
## System Requirements

- OS: Windows 10/11
- Python: 3.8+
- RAM: 4GB+ recommended
- Display: 1280x720+ recommended

<a id="en-quick-start"></a>
## Quick Start

1. Add images (file picker or folder).
2. Select layout (Horizontal / Vertical / Grid).
3. Configure size, spacing, margins, and optional enhancement.
4. Click **Start Stitching** and choose an output folder.

<a id="en-installation"></a>
## Installation

### Option 1: EXE

Run `dist/ImageStitcher.exe`.

### Option 2: Source

```bash
pip install -r requirements.txt
python run.py
```

<a id="en-usage-guide"></a>
## Usage Guide

- Import images and manage the list (add/remove/clear).
- Configure layout and grid parameters (`rows`, `cols`, `h_spacing`, `v_spacing`).
- Configure margins and output canvas size.
- Optionally enable enhancement and tune values.
- Enable multi-page mode for large input sets.
- Export stitched images to the selected folder.

<a id="en-configuration"></a>
## Configuration

Runtime config file:

- `image_stitcher_config.json`

Scheme folder:

- `schemes/`

<a id="en-image-optimization"></a>
## Image Optimization

The app uses staged optimization:

- Parallel loading / preprocessing / stitching / saving
- Memory monitoring and adaptive worker sizing
- Efficient resize and optional enhancement pipelines
- Asynchronous output saving

<a id="en-architecture"></a>
## Architecture

Main modules:

- `run.py`: application entrypoint
- `image_stitcher/app.py`: Tkinter UI and orchestration
- `image_stitcher/pipeline_pool.py`: multi-pipeline scheduler
- `image_stitcher/pipeline.py`: worker stages
- `image_stitcher/image_processor.py`: image load/resize/enhance/stitch logic
- `image_stitcher/async_saver.py`: async saving
- `image_stitcher/resource_monitor.py`: resource heuristics

<a id="en-file-structure"></a>
## File Structure

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

<a id="en-faq"></a>
## FAQ

- Out of memory: reduce image count or output size, disable enhancement.
- Slow processing: lower target resolution and reduce enhancement usage.
- Slow saving: prefer SSD and reduce JPEG quality if needed.
