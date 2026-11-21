# SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
# SPDX-License-Identifier: BSL-1.0
"""Validate the exact generated firmware bitmaps; optionally render a preview.

python test_font.py [test_subtitle.exe preview.png]
The optional preview uses the firmware bidi helper's output, not Pillow bidi.
"""
import pathlib
import re
import subprocess
import sys

source = (pathlib.Path(__file__).parents[2] / 'fonts/hebrew_font.cpp').read_text()
sizes = {}
for size, panel_height in ((12, 22), (24, 40)):
    bitmap = bytes(int(v, 16) for v in re.findall(r'0x([0-9a-f]+)',
        re.search(rf'bitmap_{size}\[\] = \{{(.*?)\}};', source, re.S)[1]))
    glyphs = {}
    for record, cp in re.findall(r'\{([\d, -]+)\}, // U\+([0-9A-F]+)',
            re.search(rf'glyphs_{size}\[\] = \{{(.*?)\}};', source, re.S)[1]):
        glyphs[int(cp, 16)] = tuple(map(int, record.split(',')))
    required = list(range(0x20, 0x7F)) + list(range(0x5D0, 0x5EB))
    required += [0x5BE, 0x5F3, 0x5F4, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x20AA]
    for cp in required:
        assert cp in glyphs, f'Missing U+{cp:04X} at {size}px'
        offset, w, h, advance, x, y = glyphs[cp]
        assert offset + (w*h + 7)//8 <= len(bitmap)
        if cp != 0x20:
            assert any(bitmap[offset:offset + (w*h + 7)//8]), f'Empty U+{cp:04X}'
    top = min(g[5] for g in glyphs.values())
    bottom = max(g[5] + g[2] for g in glyphs.values())
    assert bottom - top <= panel_height - 4, (size, top, bottom, panel_height)
    sizes[size] = bitmap, glyphs, top, bottom
    print(f'{size}px: {len(glyphs)} glyphs, {len(bitmap)} bitmap bytes; height {bottom-top}/{panel_height}px')

if len(sys.argv) == 3:
    from PIL import Image, ImageDraw
    executable, output = sys.argv[1:]
    assert not pathlib.Path(output).exists(), 'Refusing to overwrite existing preview'
    examples = [('Hebrew', 'שלום עולם!'), ('Mixed Latin and numbers', 'שלום (Hello 123)'),
                ('Time and punctuation', 'השעה 12:34 — שלום!'),
                ('Hebrew final letters', 'כמנפצ ךםןףץ')]
    preview = Image.new('RGB', (960, len(examples)*230 + 70), '#e5e7eb')
    draw = ImageDraw.Draw(preview)
    draw.text((24, 15), 'Firmware subtitle bitmap preview (exact 24px / 12px data, enlarged 3x)', fill='black')
    for row, (label, logical) in enumerate(examples):
        visual = subprocess.check_output([executable, '--stdin'], input=logical.encode('utf-8')).decode('utf-8')
        draw.text((24, 55+row*230), label, fill='black')
        for size, width, height, destx, desty in ((24,320,40,0,75+row*230), (12,128,22,10,202+row*230)):
            bitmap, glyphs, top, bottom = sizes[size]
            panel = Image.new('RGB', (width,height), 'black')
            pd = ImageDraw.Draw(panel)
            pd.rounded_rectangle((4,0,width-5,height-1), 10, fill='white', outline='black')
            tw = sum(glyphs[ord(c)][3] for c in visual)
            x = (width-tw)//2
            baseline = (height-(bottom-top))//2-top
            for c in visual:
                offset,w,h,advance,xoff,yoff = glyphs[ord(c)]
                for yy in range(h):
                    for xx in range(w):
                        bit=yy*w+xx
                        px,py=x+xoff+xx,baseline+yoff+yy
                        if 12 <= px < width-12 and 0 <= py < height and bitmap[offset+bit//8] & (128>>(bit%8)):
                            pd.point((px,py),fill='black')
                x+=advance
            preview.paste(panel.resize((width*3,height*3),Image.Resampling.NEAREST),(destx,desty))
    preview.save(output)
    print('Saved',output)
