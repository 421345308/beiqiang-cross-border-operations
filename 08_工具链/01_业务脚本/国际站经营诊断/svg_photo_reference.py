"""Embed original photo, losslessly decode unsupported WebP for SVG compatibility."""
from pathlib import Path
from functools import lru_cache
import base64,mimetypes,subprocess
NODE='C:/Users/spq/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'

@lru_cache(maxsize=256)
def photo_data_url(file):
    file=Path(file)
    if file.suffix.lower()=='.webp':
        return subprocess.check_output([NODE,str(Path(__file__).parent/'encode_svg_photo.cjs'),str(file)],text=True).strip()
    mime=mimetypes.guess_type(file.name)[0]or'image/jpeg'
    return 'data:'+mime+';base64,'+base64.b64encode(file.read_bytes()).decode()
