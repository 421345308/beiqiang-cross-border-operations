"""Read-only, scoped local media resolution and HTTP byte-range serving."""
from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote, urlencode

DEFAULT_ROOTS = ('01_产品资产', '05_内容与视频',
    '05_内容与视频/01_贝强商品视频', '05_内容与视频/03_通用AI视频实验',
    '05_内容与视频/成片', '99_临时区/工作台应用验收')
TYPES = {'.jpg':('image','image/jpeg'),'.jpeg':('image','image/jpeg'),
    '.png':('image','image/png'),'.gif':('image','image/gif'),'.webp':('image','image/webp'),
    '.bmp':('image','image/bmp'),'.avif':('image','image/avif'),
    '.mp4':('video','video/mp4'),'.m4v':('video','video/mp4'),'.mov':('video','video/quicktime'),
    '.webm':('video','video/webm'),'.mp3':('audio','audio/mpeg'),'.wav':('audio','audio/wav'),
    '.ogg':('audio','audio/ogg'),'.flac':('audio','audio/flac'),'.m4a':('audio','audio/mp4'),'.aac':('audio','audio/aac')}
PRIVATE = {'node_modules','__pycache__','cache','caches','private','credentials','secrets','auth','logs','backups'}

class MediaError(ValueError):
    def __init__(self,message,status=400,code='INVALID_MEDIA_PATH'):
        super().__init__(message);self.status=status;self.code=code

def _private(parts):
    return any(p.startswith('.') or p.casefold() in PRIVATE or 'private' in p.casefold() or '凭证' in p or '登录态' in p for p in parts)

def _magic(extension,header):
    if extension in ('.jpg','.jpeg'):return header.startswith(b'\xff\xd8\xff')
    if extension=='.png':return header.startswith(b'\x89PNG\r\n\x1a\n')
    if extension=='.gif':return header.startswith((b'GIF87a',b'GIF89a'))
    if extension=='.webp':return header[:4]==b'RIFF' and header[8:12]==b'WEBP'
    if extension=='.bmp':return header.startswith(b'BM')
    if extension in ('.mp4','.m4v','.m4a','.mov','.avif'):
        return header[4:8]==b'ftyp' and (extension!='.avif' or b'avif' in header[8:40] or b'avis' in header[8:40])
    if extension=='.webm':return header.startswith(b'\x1aE\xdf\xa3')
    if extension=='.mp3':return header.startswith(b'ID3') or len(header)>1 and header[0]==255 and header[1]&224==224
    if extension=='.wav':return header[:4]==b'RIFF' and header[8:12]==b'WAVE'
    if extension=='.ogg':return header.startswith(b'OggS')
    if extension=='.flac':return header.startswith(b'fLaC')
    if extension=='.aac':return len(header)>1 and header[0]==255 and header[1]&246==240
    return False

def parse_range(value,size):
    """Return an inclusive single-byte interval, or None for no Range header."""
    if value is None:return None
    if not isinstance(value,str) or len(value)>200:raise MediaError('请求的媒体范围无效',416,'INVALID_RANGE')
    match=re.fullmatch(r'bytes=([0-9]*)-([0-9]*)',value.strip())
    if not match or not any(match.groups()) or size<=0:raise MediaError('请求的媒体范围无效',416,'INVALID_RANGE')
    start,end=match.groups()
    if not start:
        length=int(end)
        if length<=0:raise MediaError('请求的媒体范围无效',416,'INVALID_RANGE')
        return max(0,size-length),size-1
    start=int(start);end=min(int(end),size-1) if end else size-1
    if start>=size or end<start:raise MediaError('请求的媒体范围无效',416,'INVALID_RANGE')
    return start,end

@dataclass(frozen=True)
class _Root:
    relative: PurePosixPath
    lexical: Path
    real: Path

class MediaAssets:
    def __init__(self,root,allowed_roots=None):
        self.root=Path(root).resolve(strict=True)
        self.roots=[]
        for value in DEFAULT_ROOTS if allowed_roots is None else allowed_roots:
            relative=PurePosixPath(value)
            if relative.is_absolute() or '..' in relative.parts or _private(relative.parts):raise ValueError('Invalid configured media root')
            lexical=self.root.joinpath(*relative.parts)
            if lexical.is_dir():self.roots.append(_Root(relative,lexical,lexical.resolve(strict=True)))
        self.roots.sort(key=lambda item:len(item.relative.parts),reverse=True)

    def _locate(self,value):
        if not isinstance(value,str) or not value or len(value)>2000 or any(ord(c)<32 for c in value) or ':' in value:
            raise MediaError('请填写项目内的相对媒体文件路径')
        relative=PurePosixPath(value.replace('\\','/'))
        if relative.is_absolute() or '..' in relative.parts or _private(relative.parts):raise MediaError('媒体路径不在允许范围',403,'MEDIA_FORBIDDEN')
        normalized=relative.as_posix()
        selected=next((entry for entry in self.roots if relative.is_relative_to(entry.relative)),None)
        if not selected:raise MediaError('仅可预览项目业务媒体目录中的文件',403,'MEDIA_FORBIDDEN')
        try:
            if selected.lexical.resolve(strict=True)!=selected.real:raise MediaError('媒体根目录已改变，请重新检查配置',403,'MEDIA_FORBIDDEN')
            candidate=self.root.joinpath(*relative.parts).resolve(strict=True)
        except (OSError,RuntimeError):raise MediaError('找不到这份本地媒体文件',404,'MEDIA_NOT_FOUND')
        if not candidate.is_relative_to(selected.real) or _private(candidate.relative_to(selected.real).parts):
            raise MediaError('媒体链接超出已核实的目录边界',403,'MEDIA_FORBIDDEN')
        if not candidate.is_file():raise MediaError('请选择媒体文件而不是目录',404,'MEDIA_NOT_FOUND')
        extension=relative.suffix.lower()
        if extension not in TYPES:raise MediaError('暂不支持该媒体格式（不支持SVG或网页）',415,'UNSUPPORTED_MEDIA')
        return candidate,normalized,extension

    def _open(self,value):
        candidate,relative,extension=self._locate(value)
        try:
            stream=candidate.open('rb')
            if not _magic(extension,stream.read(64)):
                stream.close();raise MediaError('文件内容与媒体扩展名不匹配',415,'UNSUPPORTED_MEDIA')
            stream.seek(0)
            return stream,relative,TYPES[extension]
        except OSError:raise MediaError('无法读取这份本地媒体文件',404,'MEDIA_NOT_FOUND')

    def resolve(self,path):
        stream,relative,(kind,mime)=self._open(path)
        with stream:size=os.fstat(stream.fileno()).st_size
        return {'path':relative,'name':PurePosixPath(relative).name,'kind':kind,'mime_type':mime,
            'size':size,'url':'/api/media/file?'+urlencode({'path':relative})}

    def serve(self,handler,path,head=False):
        stream,relative,(_,mime)=self._open(path)
        with stream:
            size=os.fstat(stream.fileno()).st_size
            try:interval=parse_range(handler.headers.get('Range'),size)
            except MediaError as error:
                handler.send_response(error.status);handler.send_header('Content-Range',f'bytes */{size}')
                handler.send_header('Content-Length','0');handler.send_header('Cache-Control','no-store');handler.end_headers();return
            start,end=interval if interval is not None else (0,size-1)
            length=end-start+1
            handler.send_response(206 if interval is not None else 200)
            handler.send_header('Content-Type',mime);handler.send_header('Content-Length',str(length))
            handler.send_header('Accept-Ranges','bytes');handler.send_header('Cache-Control','private, no-store')
            handler.send_header('X-Content-Type-Options','nosniff')
            handler.send_header('Content-Disposition',"inline; filename*=UTF-8''"+quote(PurePosixPath(relative).name,safe=''))
            if interval is not None:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            handler.end_headers()
            if head:return
            stream.seek(start);remaining=length
            try:
                while remaining:
                    chunk=stream.read(min(256*1024,remaining))
                    if not chunk:break
                    handler.wfile.write(chunk);remaining-=len(chunk)
            except (BrokenPipeError,ConnectionResetError):return
