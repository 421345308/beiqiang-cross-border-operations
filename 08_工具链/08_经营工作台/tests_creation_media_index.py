import tempfile
import unittest
import os
import subprocess
from pathlib import Path

from creation import Creation


class CreationMediaIndexTests(unittest.TestCase):
    def test_finished_video_paths_are_normalized_and_checked_by_media_service(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            base=root/'05_内容与视频'
            project=base/'01_贝强商品视频'/'example'
            finished=base/'成片'
            project.mkdir(parents=True)
            finished.mkdir()
            (base/'README.md').write_text('[项目](01_贝强商品视频/example/PROJECT.md)',encoding='utf8')
            (finished/'clip.mp4').write_bytes(b'\0\0\0\x18ftypisom'+b'data')
            (finished/'bad.mp4').write_bytes(b'not a video')
            (finished/'.local').mkdir()
            (finished/'.local'/'private.mp4').write_bytes(b'\0\0\0\x18ftypisom')
            (root/'outside.mp4').write_bytes(b'\0\0\0\x18ftypisom')
            (project/'PROJECT.md').write_text(
                '# 项目\n[有效](../../成片/clip.mp4)\n[伪造](../../成片/bad.mp4)\n'
                '[私有](../../成片/.local/private.mp4)\n[越界](../../../outside.mp4)\n'
                '[空字节](invalid%00.mp4)\n[盘符](C%3A/file.mp4)',encoding='utf8')
            catalog=Creation(root)
            detail=catalog.get_project(catalog.list_projects()[0]['id'])
            self.assertEqual([x['path'] for x in detail['assets']],['05_内容与视频/成片/clip.mp4'])

    def test_finished_root_junction_and_nested_escape(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as external:
            root=Path(folder)
            base=root/'05_内容与视频'
            project=base/'01_贝强商品视频'/'example'
            project.mkdir(parents=True)
            outside=Path(external)
            (outside/'clip.mp4').write_bytes(b'\0\0\0\x18ftypisom')
            links=[]
            try:
                for link,target in ((base/'成片',outside),(outside/'escape',project)):
                    if os.name=='nt':
                        result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True)
                        if result.returncode:self.skipTest('Creating directory junctions unavailable')
                    else:
                        link.symlink_to(target,target_is_directory=True)
                    links.append(link)
                (project/'secret.mp4').write_bytes(b'\0\0\0\x18ftypisom')
                (base/'README.md').write_text('[项目](01_贝强商品视频/example/PROJECT.md)',encoding='utf8')
                (project/'PROJECT.md').write_text('# 项目\n[有效](../../成片/clip.mp4)\n[逃逸](../../成片/escape/secret.mp4)',encoding='utf8')
                catalog=Creation(root)
                detail=catalog.get_project(catalog.list_projects()[0]['id'])
                self.assertEqual([x['path'] for x in detail['assets']],['05_内容与视频/成片/clip.mp4'])
            finally:
                for link in reversed(links):
                    if os.name=='nt':os.rmdir(link)
                    else:link.unlink()


if __name__=='__main__':unittest.main()
