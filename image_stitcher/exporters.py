import os
from typing import List, Optional
from PIL import Image
from .utils import PDF_SUPPORT

if PDF_SUPPORT:
    import img2pdf
    import io


def export_to_png(images: List[Image.Image], output_dir: str, base_name: str) -> List[str]:
    """导出为PNG文件"""
    outputs = []
    for i, img in enumerate(images):
        filename = f"{base_name}_{i+1}.png"
        filepath = os.path.join(output_dir, filename)
        img.save(filepath, "PNG", optimize=True)
        outputs.append(filepath)
    return outputs


def export_to_jpg(images: List[Image.Image], output_dir: str, base_name: str, quality: int = 95) -> List[str]:
    """导出为JPG文件"""
    outputs = []
    for i, img in enumerate(images):
        filename = f"{base_name}_{i+1}.jpg"
        filepath = os.path.join(output_dir, filename)
        img.save(filepath, "JPEG", quality=quality, optimize=True)
        outputs.append(filepath)
    return outputs


def export_to_pdf(images: List[Image.Image], output_path: str) -> Optional[str]:
    """导出为PDF文件"""
    if not PDF_SUPPORT:
        return None
    
    try:
        # 将图像转换为字节流
        pdf_bytes = []
        for img in images:
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            pdf_bytes.append(img_byte_arr.getvalue())
        
        # 生成PDF
        pdf_content = img2pdf.convert(pdf_bytes)
        with open(output_path, 'wb') as f:
            f.write(pdf_content)
        
        return output_path
    except Exception as e:
        print(f"PDF导出失败: {e}")
        return None


def export_images(
    images: List[Image.Image],
    output_dir: str,
    base_name: str,
    format: str = "PNG"
) -> List[str]:
    """根据格式导出图像"""
    os.makedirs(output_dir, exist_ok=True)
    
    if format == "PNG":
        return export_to_png(images, output_dir, base_name)
    elif format == "JPG":
        return export_to_jpg(images, output_dir, base_name)
    elif format == "PDF":
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
        result = export_to_pdf(images, pdf_path)
        return [result] if result else []
    else:
        return []