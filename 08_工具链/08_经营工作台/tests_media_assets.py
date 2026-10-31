import io
from pathlib import Path
import tempfile
import unittest
from media_assets import MediaAssets,MediaError,parse_range

PNG=b'\x89PNG\r\n\x1a\n'+bytes(range(100))
class FakeHandler:
    def __init__(self,range_value=None):self.headers={} if range_value is None else {'Range':range_value};self.wfile=io.BytesIO();self.sent={}
    def send_response(self,status):self.status=status
    def send_header(self,key,value):self.sent[key]=value
    def end_headers(self):pass

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.media=self.root/'01_产品资产';self.media.mkdir()
        (self.media/'实物图.png').write_bytes(PNG)
        self.assets=MediaAssets(self.root)

    def test_resolve_returns_relative_same_origin_metadata(self):
        value=self.assets.resolve('01_产品资产\\实物图.png')
        self.assertEqual(value['path'],'01_产品资产/实物图.png');self.assertEqual(value['kind'],'image')
        self.assertEqual(value['mime_type'],'image/png');self.assertEqual(value['size'],len(PNG))
        self.assertTrue(value['url'].startswith('/api/media/file?path='));self.assertNotIn(str(self.root),str(value))

    def test_traversal_absolute_private_and_unapproved_roots_are_denied(self):
        for path in ['../secret.png','/etc/photo.png','C:\\auth.png','01_产品资产/../secret.png',
                     '08_工具链/file.png','01_产品资产/.local/auth.png','01_产品资产/private/image.png',
                     '01_产品资产/image.png:secret','01_产品资产/file\n.png']:
            with self.subTest(path=path),self.assertRaises(MediaError):self.assets.resolve(path)

    def test_extension_and_magic_are_both_required(self):
        for name,body in [('bad.png',b'<html>secret</html>'),('code.svg',b'<svg/>'),('token.json',PNG)]:
            (self.media/name).write_bytes(body)
            with self.assertRaises(MediaError) as caught:self.assets.resolve('01_产品资产/'+name)
            self.assertEqual(caught.exception.status,415)

    def test_real_mp4_and_audio_headers(self):
        for name,header,kind in [('clip.mp4',b'\0\0\0\x18ftypisom','video'),('song.wav',b'RIFF0000WAVE','audio')]:
            (self.media/name).write_bytes(header+b'payload')
            self.assertEqual(self.assets.resolve('01_产品资产/'+name)['kind'],kind)

    def test_ranges_and_head_use_exact_lengths(self):
        for value,start,end in [('bytes=8-15',8,15),('bytes=100-',100,len(PNG)-1),('bytes=-7',len(PNG)-7,len(PNG)-1),('bytes=0-999',0,len(PNG)-1)]:
            handler=FakeHandler(value);self.assets.serve(handler,'01_产品资产/实物图.png')
            self.assertEqual(handler.status,206);self.assertEqual(handler.wfile.getvalue(),PNG[start:end+1])
            self.assertEqual(handler.sent['Content-Length'],str(end-start+1))
        handler=FakeHandler();self.assets.serve(handler,'01_产品资产/实物图.png',head=True)
        self.assertEqual(handler.status,200);self.assertEqual(handler.wfile.getvalue(),b'')

    def test_unsatisfiable_or_multi_ranges_return_416(self):
        for value in ['bytes=999-','bytes=3-1','bytes=-0','bytes=0-1,4-5','bogus','bytes=-','bytes='+('9'*5000)+'-']:
            handler=FakeHandler(value);self.assets.serve(handler,'01_产品资产/实物图.png')
            self.assertEqual(handler.status,416);self.assertEqual(handler.sent['Content-Range'],f'bytes */{len(PNG)}')
            self.assertEqual(handler.wfile.getvalue(),b'')

    def test_missing_and_directories_are_not_exposed(self):
        for path in ['01_产品资产/no.png','01_产品资产']:
            with self.assertRaises(MediaError) as caught:self.assets.resolve(path)
            self.assertEqual(caught.exception.status,404)

    def test_known_root_junction_works_but_nested_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            outer=Path(external);(outer/'safe.png').write_bytes(PNG)
            link=self.root/'05_内容与视频'
            try:link.symlink_to(outer,target_is_directory=True)
            except OSError:self.skipTest('Creating directory links unavailable')
            assets=MediaAssets(self.root)
            self.assertEqual(assets.resolve('05_内容与视频/safe.png')['size'],len(PNG))
            nested=outer/'escape';nested.symlink_to(self.media,target_is_directory=True)
            with self.assertRaises(MediaError) as caught:assets.resolve('05_内容与视频/escape/实物图.png')
            self.assertEqual(caught.exception.status,403)

if __name__=='__main__':unittest.main()
