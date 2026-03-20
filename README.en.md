收到，之前的翻译为了保持简洁，对“图片生成优化”、“技术架构细节”以及部分代码示例和详细对比表格进行了概括。

以下是完整无删减的英文版本，包含了所有的代码块、详细的性能对比数据、完整的配置项说明以及所有的优化策略细节。

<a id="english-version"></a>
🖼️ Smart Image Stitcher (Image Stitcher)

[中文（默认）](./README.md#chinese-version) | [English](#english-version)

🎉 One-stop image stitching solution - Easily combine multiple photos into beautiful collages.

Features • System Requirements • Quick Start • Installation • Usage Guide

💡 First time user? Check out the Quick Start section to get up and running in 3 minutes!

📚 Table of Contents

Quick Start - 🚀 Quick getting started guide
Features - 🎯 Core and advanced features
Installation - 📦 EXE and Source Code methods
Usage Guide - 🎓 Detailed operation instructions
Configuration - ⚙️ Config files and scheme management
Image Optimization - 🚀 Detailed optimization strategies
Architecture - 🏗️ Architecture principles and source structure
File Structure - 📁 Project directory layout
FAQ - ❓ Frequently asked questions
Changelog - 📝 Version history
Contributing - 🤝 How to contribute
License - 📄 License info
Acknowledgements - 🙏 Credits

Quick Navigation

Need to get started quickly? Jump directly to the Quick Start section.
Encountering technical issues? Check the FAQ section.

🎯 Features

Core Features

✅ Multiple Layouts: Supports horizontal, vertical, and grid layouts.
✅ Image Enhancement: Adjust brightness, contrast, and sharpness.
✅ Batch Processing: Supports automatic pagination for large numbers of images.
✅ Image Flipping: Vertical flip, horizontal flip.
✅ Reversed Version Generation: Row reversal effect in grid layout.
✅ Grid Line Display: Visual aid feature.
✅ A4 Paper Mode: Preset A4 paper sizes and orientations.

Advanced Features

✅ Multi-threading: Asynchronous loading, preprocessing, stitching, and saving.
✅ Memory Optimization: Automatic garbage collection and memory monitoring.
✅ Config Persistence: Automatically saves and loads user configurations.
✅ Scheme Management: Supports saving and loading stitching schemes.
✅ Progress Monitoring: Real-time processing progress display.

🖥️ System Requirements

OS: Windows 10/11
Python Version: 3.8+
RAM: Recommended 4GB+ (for processing large batches)
Screen Resolution: Recommended 1280x720+

🚀 Quick Start

⚡ 3-Minute Quick Start - The most concise beginner's guide

🎯 Simplest Workflow (3 Steps)

Select Images 📂
    Click the "Select Images" button.
    Or drag and drop images directly into the list.
Set Layout 📐
    Choose layout: Horizontal / Vertical / Grid.
    Set rows and columns (for Grid mode).
Start Stitching ▶️
    Click the "Start Stitching" button.
    Wait for processing to complete.
    View the result.

💡 Typical Scenarios
Scenario   Recommended Settings   Description
Simple Stitch   Horizontal/Vertical   2-10 images, quick stitch

Photo Wall   Grid Layout   4-20 images, 2-4 rows, 2-4 cols

Batch Print   A4 Mode   Preset print size, precise layout

📊 Performance Reference
Image Count   Processing Time   Memory Usage   Recommended Settings
1-10   

📦 Installation

Method 1: Using Packaged EXE (Recommended)

Download the dist/ImageStitcher.exe file.
Double-click to run; no Python installation required.

Method 2: Running from Source

Clone or download the project locally.
Install dependencies:

pip install -r requirements.txt

Run the application:

python run.py

Dependencies
Package   Purpose   Required?
Pillow (PIL)   Image Processing   ✅ Yes

numpy   Numerical Computing   ✅ Yes

psutil   System Monitoring   🟡 Optional

🚀 Usage Guide

Launch Application

Run ImageStitcher.exe or python run.py to start.

Basic Workflow

Select Images
    Click "Select Images".
    Supports multi-select.
    Or drag and drop images into the list.
Configure Parameters
    Set layout (Horizontal/Vertical/Grid).
    Configure grid parameters (Rows, Cols, Spacing).
    Set image size and enhancement parameters.
    Configure margins and flip modes.
Start Stitching
    Click "Start Stitching".
    Wait for completion.
    View results.

Detailed Operations

Select Images

Add Images: Click "Select Images" to choose files.
Clear List: Click "Clear List" to remove all.
Delete Selected: Select images in the list and click "Delete Selected".

Configure Layout

Horizontal Layout
Images arranged in a single row.
Ideal for banners or long strips.

Vertical Layout
Images arranged in a single column.
Ideal for vertical compositions.

Grid Layout
Images arranged in rows and columns.
Supports custom rows and columns.
Supports automatic pagination for large batches.

Image Enhancement

Available when "Uniform Size Pre-processing" is checked:

Target Width/Height: Uniformly resize images.
Brightness: Adjust (-100 ~ +100).
Contrast: Adjust (-100 ~ +100).
Sharpness: Adjust (-100 ~ +100).

Flip Mode

None: No flip.
Vertical Flip: Flip vertically.
Horizontal Flip: Flip horizontally.

Reversed Version Generation

In Grid Layout, checking "Generate Reversed Version" will:

Reverse the order of images in each row.
Empty slots participate in the reversal.
Generate files with a _reversed suffix.

A4 Paper Mode

Preset A4 size (210mm x 297mm).
Supports Landscape and Portrait.
Convenient for printing and layout.

Practical Tips

Batch Processing Large Numbers of Images

Set appropriate rows/cols (e.g., 2 rows, 4 cols).
Check "Multi-page Stitching".
The program automatically paginates.
Can generate reversed versions simultaneously.

Creating Special Effects

Combine "Horizontal Flip" with "Reversed Version" for mirror effects.
Adjust brightness/contrast to improve visual consistency.
Enable "Show Grid Lines" to help align images.

⚙️ Configuration

📁 Config File Location

Saved in the project root directory: image_stitcher_config.json

💡 Tip: Configurations are saved automatically and loaded on the next startup.

🔧 Configuration Items
Key   Type   Default   Description
a4_mode   boolean   false   A4 Mode (auto-sets canvas size)

landscape   boolean   false   Landscape Mode (A4 horizontal)

canvas_width   integer   800   Canvas Width (pixels)

canvas_height   integer   600   Canvas Height (pixels)

resize   boolean   true   Uniform Size Pre-processing

target_width   integer   800   Target Width (pixels)

target_height   integer   600   Target Height (pixels)

layout   string   "Horizontal"   Layout: Horizontal/Vertical/Grid

rows   integer   2   Grid Rows

cols   integer   4   Grid Columns

h_spacing   integer   30   Horizontal Spacing (pixels)

v_spacing   integer   30   Vertical Spacing (pixels)

multi_page   boolean   true   Multi-page Stitching (Auto-pagination)

gen_row_reversed   boolean   false   Generate Row Reversed Version

margin_top   integer   0   Top Margin (pixels)

margin_bottom   integer   0   Bottom Margin (pixels)

margin_left   integer   0   Left Margin (pixels)

margin_right   integer   0   Right Margin (pixels)

flip_mode   string   "None"   Flip: None/Vertical/Horizontal

show_grid   boolean   false   Show Grid Lines (Debug)

enhance_enabled   boolean   false   Image Enhancement Enabled

brightness   integer   0   Brightness (-100~100)

contrast   integer   0   Contrast (-100~100)

sharpness   integer   0   Sharpness (0~100)

📝 JSON Configuration Example

{
    "a4_mode": false,
    "landscape": false,
    "canvas_width": 800,
    "canvas_height": 600,
    
    "resize": true,
    "target_width": 800,
    "target_height": 600,
    
    "layout": "Grid",
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
    
    "flip_mode": "None",
    "show_grid": false,
    
    "enhance_enabled": false,
    "brightness": 0,
    "contrast": 0,
    "sharpness": 0
}

Scheme Management

Save Scheme: Save current config as a .json file.
Load Scheme: Load a previously saved scheme.

🚀 Image Generation Optimization

💡 Goal: Maximize processing speed and minimize memory usage while maintaining high-quality output.

This tool employs a multi-layer optimization strategy to ensure high performance even with large image batches.
Optimization Type   Description   Effect
🔄 Parallel Processing   Multi-threaded pipeline utilizing CPU resources   Speed ↑ 62.5%

💾 Memory Management   Auto GC, monitoring, dynamic adjustment   Memory ↓ 52%

⚡ Algorithm Optimization   Efficient image processing algorithms & data structures   CPU Utilization ↑ 58%

📤 I/O Optimization   Async saving, batch processing, smart caching   File Size ↓ 10%

🌊 1. Multi-threaded Pipeline Processing

📊 Pipeline Architecture Diagram

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Image Load │ →  │   Resize    │ →  │ Enhancement │ →  │ Grid Stitch │
│ (Multi-thread)│  │ (Multi-thread)│  │ (Multi-thread)│  │ (Multi-thread)│
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
        ↓                    ↓                    ↓                    ↓
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Post-Process│ →  │ Async Save  │    │             │    │             │
│  (Flip etc) │    │ (Multi-thread)│    │             │    │             │
└─────────────┘    └─────────────┘    │             │    │             │
                                      └─────────────┘    └─────────────┘

⚙️ Pipeline Stage Details
Stage   Function   Optimization Measures   Performance Gain
Stage 1 📦 Load   Parallel loading of multiple images   Lazy loading, format support   67%

Stage 2 📐 Resize   Resize images to target size   LANCZOS/BICUBIC algorithms   68%

Stage 3 🎨 Enhance   Apply brightness, contrast, sharpness   ImageEnhance module   -

Stage 4 🧩 Stitch   Efficient stitching using NumPy   Canvas pre-allocation, vectorization   75%

Stage 5 🔄 Post   Apply flips and reversal effects   Batch processing   -

Stage 6 💾 Save   Asynchronous saving   JPEG optimization, batch save   51%

💾 2. Memory Management Optimization

🧹 Automatic Garbage Collection

import gc

def process_batch(images):
    """Process image batch and trigger garbage collection"""
    # Process images
    results = [process_single(img) for img in images]
    
    # Clean up temporary objects
    gc.collect()
    
    return results

Optimization Measures:
✅ Regular cleanup of temporary objects.
✅ Release unused image objects.
✅ Reduce memory fragmentation.
✅ Prevent memory leaks.

📈 Memory Monitoring

import psutil

def monitor_memory():
    """Real-time memory usage monitoring"""
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory Usage: {mem_mb:.1f} MB")
    
    if mem_mb > 2048:  # Warning if over 2GB
        print("⚠️ Warning: Memory usage exceeds 2GB")
        gc.collect()

Monitoring Features:
📊 Real-time memory usage tracking.
⚠️ Warnings when thresholds are exceeded.
🔄 Automatic strategy adjustment.
📝 Logging of memory usage history.

🎛️ Dynamic Pipeline Length Adjustment

import os
from concurrent.futures import ThreadPoolExecutor

def calculate_thread_pool_sizes():
    """Dynamically adjust thread pool size based on system resources"""
    cpu_count = os.cpu_count() or 4
    mem_gb = psutil.virtual_memory().total / (1024**3)
    
    # Dynamically adjust based on CPU cores and RAM
    load_threads = min(8, max(2, cpu_count))
    save_threads = min(4, max(1, cpu_count // 2))
    
    return {
        'load': load_threads,
        'save': save_threads
    }

Adjustment Strategy:
Resource   Adjustment Method   Description
CPU Cores   Threads = min(8, cpu_count)   Maximize CPU utilization

RAM Size   Threads = min(4, cpu_count // 2)   Prevent out-of-memory errors

Load   Dynamic Adjustment   Adjust based on real-time load

Monitoring   Real-time Monitoring   Ensure system stability

🖼️ 3. Image Processing Optimization

📏 Fast Resizing

from PIL import Image

def fast_load_and_resize(path, target_w, target_h):
    """High-quality scaling using LANCZOS algorithm"""
    img = Image.open(path)
    img = img.resize((target_w, target_h), Image.LANCZOS)
    return img

Scaling Algorithm Comparison:
Algorithm   Speed   Quality   Best For   Recommendation
🥇 LANCZOS   Medium   ⭐⭐⭐⭐⭐   Downscaling   ⭐⭐⭐⭐⭐

🥈 BICUBIC   Medium   ⭐⭐⭐⭐   General Use   ⭐⭐⭐⭐⭐

🥉 BILINEAR   Fast   ⭐⭐⭐   Upscaling   ⭐⭐⭐⭐

NEAREST   Fast   ⭐⭐   Indexed Images   ⭐⭐

Algorithm Selection Advice:
📉 Downscaling: Use LANCZOS (Highest quality).
↔️ General: Use BICUBIC (Balance of quality/speed).
📈 Upscaling: Use BILINEAR (Fast speed).
📑 Indexed: Use NEAREST (For indexed images).

📦 Batch Processing

from concurrent.futures import ThreadPoolExecutor

def process_image_batch(image_paths, target_size, enhance_params):
    """Batch process images to reduce context switching"""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_single, path, target_size, enhance_params) 
            for path in image_paths
        ]
        results = [f.result() for f in futures]
    return results

Optimization Advantages:
⚡ Reduced thread creation overhead.
🚀 Improved CPU utilization.
💾 Lower peak memory usage.
⏱️ Faster processing speed.

🗃️ Smart Caching

Cache processed images
cache = {}
cache_limit = 100

def get_processed_image(path, params):
    """Get processed image, use cache to avoid re-processing"""
    key = (path, tuple(sorted(params.items())))
    
    if key in cache:
        return cache[key]
    
    # Process image
    img = process_single(path, params)
    
    # Cache result (limit cache size)
    if len(cache) >= cache_limit:
        cache.pop(next(iter(cache)))
    cache[key] = img
    
    return img

Caching Strategy:
🔄 Avoid re-processing.
💾 Reduce disk reads.
⏱️ Improve processing speed.
📏 Limit cache size.

🧩 4. Grid Stitching Optimization

🚀 NumPy Acceleration

import numpy as np
from PIL import Image

def stitch_grid_numpy(images, rows, cols, h_spacing, v_spacing, margins, target_w, target_h):
    """Grid stitching using NumPy - Efficient vectorized operations"""
    margin_top, margin_bottom, margin_left, margin_right = margins
    
    # Calculate canvas size
    canvas_width = margin_left + margin_right + cols * target_w + (cols - 1) * h_spacing
    canvas_height = margin_top + margin_bottom + rows * target_h + (rows - 1) * v_spacing
    
    # Create canvas
    canvas = np.full((canvas_height, canvas_width, 3), 255, dtype=np.uint8)
    
    # Stitch images
    for idx, img in enumerate(images[:rows * cols]):
        if img is None:
            continue
        row, col = divmod(idx, cols)
        x = margin_left + col * (target_w + h_spacing)
        y = margin_top + row * (target_h + v_spacing)
        
        # Convert to NumPy array
        img_np = np.array(img)
        h, w = img_np.shape[:2]
        
        # Paste to canvas
        canvas[y:y+h, x:x+w] = img_np
    
    return Image.fromarray(canvas)

NumPy Advantages:
Feature   Description   Effect
🚀 Vectorization   Uses NumPy array operations   10-100x faster

🎯 Less Python Loops   Avoids Python-level loops   Reduced overhead

📦 Contiguous Memory   Arrays stored contiguously   Cache friendly

🧮 Multi-dimensional   Supports multi-dim arrays   Flexible & Efficient

📐 Canvas Pre-allocation

Pre-calculate canvas size
canvas_width = margin_left + margin_right + cols * width + (cols-1) * spacing
canvas_height = margin_top + margin_bottom + rows * height + (rows-1) * spacing
canvas = Image.new('RGB', (canvas_width, canvas_height), (255, 255, 255))

Pre-allocation Advantages:
Feature   Description   Effect
🎯 One-time Alloc   Pre-calculate required memory   Avoids dynamic expansion

💾 Less Fragmentation   Allocate memory once   Reduces fragmentation

🚀 Faster Access   Contiguous memory access   Improves access speed

🛠️ Memory Optimization Tricks

Use uint8 type to reduce memory usage
canvas = np.zeros((height, width, 3), dtype=np.uint8)

Avoid unnecessary copies
img_np = np.array(img, copy=False)

Use views instead of copies
sub_canvas = canvas[y:y+h, x:x+w]

Trick Explanations:
📉 Use uint8: Reduces memory by 50% (from float64 to uint8).
🔄 Avoid Copy: Use copy=False to avoid unnecessary memory copying.
👁️ Use Views: Use slicing to create views instead of copying.

💾 5. Asynchronous Saving Optimization

🔄 Multi-threaded Saving

from concurrent.futures import ThreadPoolExecutor
import queue

class AsyncSaver:
    """Async Saver - Does not block main thread"""
    
    def init(self, max_workers=4):
        self.save_queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = False
        
    def save(self, image, path, format="JPEG", **kwargs):
        """Asynchronously save image"""
        if self._shutdown:
            # If shutdown, save synchronously
            image.save(path, format, **kwargs)
            return
        
        # Async save
        self.save_queue.put((image, path, format, kwargs))
        
    def _save_worker(self):
        """Save worker thread"""
        while not self._shutdown:
            try:
                image, path, format, kwargs = self.save_queue.get(timeout=1)
                image.save(path, format, **kwargs)
                self.save_queue.task_done()
            except queue.Empty:
                continue

Multi-threading Advantages:
Feature   Description   Effect
🚫 Non-blocking   Saving happens in background   Smooth UI

📦 Parallel Save   Multiple images saved simultaneously   Reduced wait time

📈 Throughput   Continuous processing of save tasks   Higher efficiency

📷 JPEG Optimization

img.save(path, "JPEG", 
         quality=90,        # Quality 90, balance size/quality
         optimize=True,     # Optimize encoding
         progressive=True)  # Progressive loading

Parameter Explanation:
Parameter   Recommended   Description   File Size Impact
quality   90   90% quality   ⭐⭐⭐⭐⭐

optimize   True   Optimize Huffman coding   ⭐⭐⭐⭐

progressive   True   Progressive JPEG   ⭐⭐

Quality Comparison:
Quality   File Size   Image Quality   Recommendation
50   📉 Small   ⭐⭐ Poor   ❌ Not Recommended

75   📊 Medium   ⭐⭐⭐ Fair   ⭐⭐⭐

90   📈 Moderate   ⭐⭐⭐⭐ Good   ⭐⭐⭐⭐⭐ Recommended

95   📉 Large   ⭐⭐⭐⭐⭐ Excellent   ⭐⭐⭐⭐

100   📉 Very Large   ⭐⭐⭐⭐⭐ Best   ⭐⭐

📦 Batch Saving

def save_batch(images, paths, format="JPEG", quality=90):
    """Batch save images - Reduce disk I/O"""
    for img, path in zip(images, paths):
        img.save(path, format, quality=quality, optimize=True)

Batch Advantages:
Feature   Description   Effect
📉 Less I/O   Batch processing reduces I/O calls   Faster speed

🚀 Throughput   Continuous writing to disk   Less waiting

💾 Less Overhead   Reduced filesystem overhead   Higher efficiency

⚡ 6. Practical Optimization Tips

📊 Batch Processing Recommendations
Count   Mode   Resolution   Enhancement   Reversed
1-10   Single Page   High   ✅ On   ✅ On

10-100   Multi-page   Medium   ⚠️ Low   ✅ On

100+   Multi-page   Low   ❌ Off   ❌ Off

Advice:
📝 Small Batch: Quality first, enable enhancement and reversal.
📦 Medium Batch: Balance quality/speed, lower params slightly.
🚀 Large Batch: Speed first, disable enhancement and reversal.

⚙️ Performance Tuning Parameters
Parameter   Recommended   Description   Impact
Target Size   800x600   Balance quality/speed   ⭐⭐⭐⭐⭐

Brightness/Contrast   0   Disable enhancement   ⭐⭐⭐⭐

JPEG Quality   90   Best quality/size ratio   ⭐⭐⭐⭐⭐

Thread Count   Auto   Based on CPU cores   ⭐⭐⭐⭐

💻 Memory Optimization Advice

Low Memory Systems (8GB):
📈 Can process more images.
✅ Enable image enhancement.
📐 Use higher resolution.
📦 Batch processing.
✅ Enable reversed versions.

📈 7. Performance Benchmarks

🧪 Test Environment
Component   Configuration
CPU   Intel Core i7-10700 (8 Cores, 16 Threads)

RAM   16GB DDR4

OS   Windows 11

Images   100 JPEGs (4000x3000)

Target Size   800x600

Layout   2 Rows x 4 Columns Grid

📊 Before vs After Optimization
Metric   Before   After   Improvement
Processing Time   120s   45s   🚀 62.5% Faster ⬇️

Peak Memory   2.5GB   1.2GB   💾 52% Less ⬇️

File Size   50MB   45MB   📦 10% Smaller ⬇️

CPU Utilization   60%   95%   ⚡ 58% Higher ⬆️

⏱️ Stage-by-Stage Time Comparison
Stage   Before   After   Improvement
📦 Load   30s   10s   🚀 67% Faster ⬇️

📏 Resize   25s   8s   🚀 68% Faster ⬇️

🧩 Stitch   20s   5s   🚀 75% Faster ⬇️

💾 Save   45s   22s   🚀 51% Faster ⬇️

🎯 8. Best Practices

📋 Quick Processing Workflow

Step 1: Prepare Images 📂
✅ Unify image formats (JPEG recommended).
✅ Resize original images (recommended max 2000x2000).
✅ Remove unwanted images.
✅ Check image quality.

Step 2: Configure Parameters ⚙️
✅ Set appropriate grid dimensions.
✅ Enable "Uniform Size Pre-processing".
✅ Set target size to 800x600 or 1024x768.
✅ Configure margins and spacing.

Step 3: Start Processing ▶️
✅ Preview effect.
✅ Adjust parameters.
✅ Start stitching.
✅ Monitor progress.

Step 4: Check Results ✅
✅ View stitched result.
✅ Adjust parameters (if needed).
✅ Re-process (if needed).
✅ Save final result.

❓ Common Performance Issues

Issue 1: Slow Processing ⏱️
Causes:
📏 Image size too large.
🎨 Image enhancement enabled.
🧵 Insufficient threads.
💾 Disk I/O bottleneck.
Solutions:
📉 Lower resolution.
❌ Disable enhancement.
🧵 Increase thread count.
🚀 Use SSD.

Issue 2: Out of Memory 💾
Causes:
📦 Too many images processed simultaneously.
🎨 Image enhancement consumes memory.
🗃️ Cache too large.
Solutions:
📉 Reduce simultaneous image count.
📦 Process in batches.
❌ Disable enhancement.
📈 Increase virtual memory.

Issue 3: High CPU Usage ⚡
Causes:
🧵 Too many threads.
🎨 Image enhancement uses CPU.
📱 Other programs using CPU.
Solutions:
📉 Reduce thread count.
❌ Disable enhancement.
📱 Close other programs.

Issue 4: Slow Saving 💾
Causes:
💾 Disk I/O bottleneck.
📷 JPEG quality too high.
📦 Improper save format.
Solutions:
📉 Lower JPEG quality.
🚀 Use SSD.
📦 Batch saving.

✅ Performance Tuning Checklist

[ ] Are image sizes appropriate?
[ ] Is image enhancement necessary?
[ ] Are thread counts reasonable?
[ ] Is memory usage normal?
[ ] Is CPU usage normal?
[ ] Is disk I/O a bottleneck?
[ ] Is JPEG quality appropriate?

🚀 9. Advanced Optimization Techniques

📦 Batch Processing Optimization

def batch_process(images, batch_size=10):
    """Batch processing optimization - Control peak memory"""
    results = []
    for i in range(0, len(images), batch_size):
        batch = images[i:i+batch_size]
        results.extend(process_batch(batch))
    return results

Advantages:
📉 Controls peak memory.
📊 Balances load.
🔄 Easy to manage.

🗃️ Memory Pool Optimization

class MemoryPool:
    """Memory pool optimization - Avoid frequent alloc/free"""
    
    def init(self, max_size=100):
        self.pool = []
        self.max_size = max_size
        
    def get(self):
        """Get object from pool"""
        if self.pool:
            return self.pool.pop()
        return None
        
    def put(self, obj):
        """Return object to pool"""
        if len(self.pool) 

🏗️ Technical Architecture

🏢 Core Component Architecture

image_stitcher/
├── app.py                  # 🖥️ Main App Interface (Tkinter GUI)
├── config.py               # ⚙️ Config Management (Save/Load/Validate)
├── image_processor.py      # 🖼️ Core Image Processing (PIL/OpenCV/libvips)
├── pipeline_pool.py        # 🌊 Pipeline Pool Manager (Dynamic parallelism)
├── pipeline.py             # 📋 Single Pipeline Implementation
├── async_saver.py          # 💾 Async Saver (Background Thread Pool)
├── exporters.py            # 📤 Export Functions
├── constants.py            # 📌 Constant Definitions
├── utils.py                # 🛠️ Utility Functions
├── resource_monitor.py     # 📊 System Resource Monitoring
└── memory_pool.py          # 🗃️ Memory Pool Management (NumPy Array Reuse)

🔄 Pipeline Architecture Diagram

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Image Load │ →  │   Resize    │ →  │ Enhancement │ →  │ Grid Stitch │
│ (Multi-thread)│  │  (OpenCV)   │    │   (PIL)     │    │  (NumPy)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
        ↓                    ↓                    ↓                    ↓
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Post-Process│ →  │ Async Save  │    │             │    │             │
│  (Flip etc) │    │ (Thread Pool)│    │             │    │             │
└─────────────┘    └─────────────┘    │             │    │             │
                                      └─────────────┘    └─────────────┘

🎯 Three-Layer Processing Optimization
Layer   Component   Optimization Tech   Effect
Image Layer   image_processor.py   libvips → OpenCV → PIL Fallback   Best Performance

Pipeline Layer   pipeline_pool.py   Dynamic Parallel Pipelines   Smart Load Balancing

Memory Layer   memory_pool.py   NumPy Array Reuse   Reduced GC Pressure

Pipeline Architecture Detail
(See diagram above)

Thread Pool Management

import os
import psutil
from concurrent.futures import ThreadPoolExecutor

def calculate_thread_pool_sizes():
    """Dynamically adjust thread pool size based on system resources"""
    cpu_count = os.cpu_count() or 4
    mem_gb = psutil.virtual_memory().total / (1024**3)
    
    # Dynamically adjust based on CPU cores and RAM
    load_threads = min(8, max(2, cpu_count))
    save_threads = min(4, max(1, cpu_count // 2))
    
    return {
        'load': load_threads,
        'save': save_threads
    }

Adjustment Strategy:
Resource   Adjustment Method   Description
CPU Cores   Threads = min(8, cpu_count)   Maximize CPU utilization

RAM Size   Threads = min(4, cpu_count // 2)   Prevent out-of-memory

Load   Dynamic Adjustment   Adjust based on real-time load

Monitoring   Real-time Monitoring   Ensure system stability

📁 File Structure

project_root/
├── dist/                      # Packaged executables
│   ├── ImageStitcher.exe     # Main Program
│   └── image_stitcher_config.json
├── build/                     # Build temporary files
├── schemes/                   # Saved schemes
├── image_stitcher/            # Source Code
│   ├── init.py
│   ├── app.py
│   ├── config.py
│   ├── image_processor.py
│   ├── pipeline_pool.py
│   ├── async_saver.py
│   ├── exporters.py
│   ├── constants.py
│   ├── utils.py
│   └── resource_monitor.py
├── run.py                    # Entry Script
├── build_exe.py              # Packaging Script
├── requirements.txt          # Dependency List
└── README.md                 # This File

❓ FAQ

Q1: How to package as EXE?

python build_exe.py

The packaged file will be in the dist/ directory.

Q2: What to do if out of memory when processing many images?

Reduce the number of images processed simultaneously.
Turn off image enhancement features.
Increase system virtual memory.
Process images in batches.

Q3: Why are there black or white borders in the result?

Adjust margin parameters.
Check if image sizes are consistent.
Adjust grid parameters.

Q4: How to generate reversed versions?

Select "Grid Layout".
Set rows and columns.
Check "Generate Reversed Version".
Start stitching.

The reversed version will reverse the order of images in each row, including empty slots.

Q5: Where is the configuration file?

The configuration file is saved in the project root directory: image_stitcher_config.json.

Q6: How to save stitching schemes?

Click the "Save Scheme" button to save the current configuration as a scheme file.

📝 Changelog

v1.0.0

Initial release.
Support for multiple stitching layouts.
Image enhancement support.
Support for flipping and reversed versions.
Multi-threaded processing.
Configuration saving and loading.

🤝 Contributing

Issues and Pull Requests are welcome!

📄 License

MIT License

🙏 Acknowledgements

Python & Tkinter
Pillow (PIL)
NumPy

Last Updated: 2026-03-19
