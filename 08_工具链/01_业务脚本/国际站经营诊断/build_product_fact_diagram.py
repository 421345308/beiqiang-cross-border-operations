"""Editable product-fact layout; photographs are embedded unchanged and uncropped."""
from pathlib import Path
from html import escape
import base64,mimetypes,textwrap
from svg_photo_reference import photo_data_url

def text_lines(text,x,y,width=64,size=25,weight='400',colour='#445971'):
    return ''.join(f'<text x="{x}" y="{y+i*(size+10)}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{colour}">{escape(line)}</text>'for i,line in enumerate(textwrap.wrap(text,width=width,break_long_words=False,break_on_hyphens=False)))

def diagram(photo,paragraphs,main=False):
    assert 1<=len(paragraphs)<=4
    height=1000 if main else 1300;photo_y=145;photo_h=390 if main else 580
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1000" height="{height}" viewBox="0 0 1000 {height}">','<rect width="1000" height="100%" fill="white"/>',text_lines('Style & Construction',50,77,size=48,weight='700',colour='#092b50'),'<rect x="50" y="105" width="80" height="6" rx="3" fill="#f47720"/>']
    data=photo_data_url(str(photo))
    svg.append(f'<image x="50" y="{photo_y}" width="900" height="{photo_h}" preserveAspectRatio="xMidYMid meet" xlink:href="{data}"/>')
    y=photo_y+photo_h+35;available=height-y-40;block=available/len(paragraphs)
    for i,p in enumerate(paragraphs):
        title,sep,body=p.partition(':')
        if not sep:title='Construction'if i==0 else'Everyday wear';body=p
        body=body.strip();assert len(title)<75
        lines=textwrap.wrap(body,width=65,break_long_words=False,break_on_hyphens=False);assert 44+len(lines)*32<=block,(title,lines,block)
        svg.extend([f'<rect x="50" y="{y-10}" width="900" height="{block-12}" rx="12" fill="#f4f7fa"/>',f'<rect x="50" y="{y-10}" width="6" height="{block-12}" rx="3" fill="#f47720"/>',text_lines(title,76,y+23,width=59,size=28,weight='700',colour='#092b50'),text_lines(body,76,y+62,width=65,size=24)])
        y+=block
    svg.append('</svg>');return ''.join(svg)
