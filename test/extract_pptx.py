import zipfile
import re
from xml.etree import ElementTree as ET

pptx_path = '逻辑证伪应对系统_现代简约浅色版.pptx'
with zipfile.ZipFile(pptx_path, 'r') as z:
    slides = sorted(
        [f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')],
        key=lambda x: int(re.search(r'slide(\d+)', x).group(1))
    )
    lines = [f'Total slides: {len(slides)}']
    for slide_path in slides:
        slide_num = re.search(r'slide(\d+)', slide_path).group(1)
        xml_content = z.read(slide_path)
        root = ET.fromstring(xml_content)
        texts = []
        for t in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
            if t.text:
                texts.append(t.text)
            if t.tail:
                texts.append(t.tail)
        lines.append(f'\n=== Slide {slide_num} ===')
        lines.append(''.join(texts))

with open('test/pptx_content.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('Done, written to test/pptx_content.txt')
