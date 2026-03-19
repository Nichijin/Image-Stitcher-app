# Image Stitcher

> Smart image stitching tool for Windows with grid/horizontal/vertical layouts, batch processing, enhancement, flipping, and A4 print mode.

[中文版本 (Chinese)](./README.zh-CN.md) | [English](./README.en.md)

<a id="quick-start"></a>
## Quick Start

1. Select images.
2. Choose layout (Horizontal / Vertical / Grid).
3. Set size, spacing, margins, and optional enhancement.
4. Click **Start Stitching** and choose output folder.

<a id="features"></a>
## Features

- Multiple layouts: Horizontal, Vertical, Grid
- Image enhancement: Brightness, Contrast, Sharpness
- Batch processing with pagination for large image sets
- Flip modes: Vertical / Horizontal
- Grid row-reversed output generation
- Optional grid line overlay for debugging/alignment
- A4 print mode (portrait/landscape)
- Multi-threaded pipeline and async save
- Config persistence and scheme management

<a id="requirements"></a>
## Requirements

- Windows 10/11
- Python 3.8+
- Recommended RAM: 4GB+

<a id="installation"></a>
## Installation

### Option 1: EXE

Run `dist/ImageStitcher.exe`.

### Option 2: Source

```bash
pip install -r requirements.txt
python run.py
```

<a id="usage"></a>
## Usage Guide

- Add images from file picker or folder.
- Configure layout and grid params (`rows`, `cols`, `h_spacing`, `v_spacing`).
- Configure margins and output canvas size.
- (Optional) Enable enhancement and adjust values.
- Enable multi-page mode for large input sets.
- Export stitched outputs to the selected folder.

<a id="configuration"></a>
## Configuration

Runtime config file:

- `image_stitcher_config.json`

Saved scheme folder:

- `schemes/`

<a id="architecture"></a>
## Architecture

Main modules:

- `run.py`: app entrypoint
- `image_stitcher/app.py`: Tkinter UI and orchestration
- `image_stitcher/pipeline_pool.py`: pipeline pool and scheduling
- `image_stitcher/pipeline.py`: staged processing pipeline
- `image_stitcher/image_processor.py`: loading, resize, enhancement, stitching
- `image_stitcher/async_saver.py`: async file save
- `image_stitcher/resource_monitor.py`: adaptive worker/resource heuristics

<a id="faq"></a>
## FAQ

- Out of memory: reduce image count or resolution, disable enhancement.
- Slow processing: lower resolution / reduce page size.
- Slow saving: prefer SSD and lower JPEG quality.

<a id="notes"></a>
## Notes

- For the complete Chinese documentation, see [README.zh-CN.md](./README.zh-CN.md).
