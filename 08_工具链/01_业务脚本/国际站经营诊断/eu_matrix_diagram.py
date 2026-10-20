"""Native EU-only selection diagram; no foot measurements or size conversions."""
from html import escape
import math

def diagram(matrix):
    sizes=sorted({size for values in matrix.values()for size in values},key=int);assert 1<=len(sizes)<=16 and 1<=len(matrix)<=10
    rowh=68;top=205;height=top+(len(matrix)+1)*rowh+125;labelw=255;cell=(900-labelw)/len(sizes)
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}">','<rect width="1000" height="100%" fill="white"/>','<text x="50" y="75" font-family="Arial,sans-serif" font-size="43" font-weight="700" fill="#092b50">European Size Selection</text>','<rect x="50" y="101" width="80" height="6" rx="3" fill="#f47720"/>','<text x="50" y="153" font-family="Arial,sans-serif" font-size="24" fill="#526277">Choose the colour and EU size for your assortment.</text>']
    for i,(colour,values)in enumerate([('Colour',sizes)]+list(matrix.items())):
        y=top+i*rowh;header=i==0;fill='#092b50'if header else'#f1f5f9'if i%2 else'#fafbfd';ink='white'if header else'#092b50'
        out.extend([f'<rect x="50" y="{y}" width="900" height="{rowh-4}" rx="7" fill="{fill}"/>',f'<text x="66" y="{y+41}" font-family="Arial,sans-serif" font-size="{20 if len(colour)>21 else 24}" font-weight="700" fill="{ink}">{escape(colour)}</text>'])
        for j,size in enumerate(sizes):
            x=50+labelw+(j+.5)*cell
            if header:out.append(f'<text x="{x}" y="{y+41}" text-anchor="middle" font-family="Arial,sans-serif" font-size="22" font-weight="700" fill="white">{size}</text>')
            elif size in values:out.append(f'<circle cx="{x}" cy="{y+32}" r="6" fill="#f47720"/>')
            else:out.append(f'<path d="M{x-5},{y+32}h10" stroke="#b6c3d0" stroke-width="2"/>')
    end=top+(len(matrix)+1)*rowh
    out.extend([f'<circle cx="62" cy="{end+46}" r="6" fill="#f47720"/>',f'<text x="82" y="{end+54}" font-family="Arial,sans-serif" font-size="22" fill="#526277">Listed colour and EU size combination</text>','</svg>'])
    return ''.join(out)
