import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from creation_canvas import CreationCanvas
from workspaces import WorkspaceConflict


class CanvasConcurrencyTests(unittest.TestCase):
    def test_two_connections_cannot_overwrite_same_version(self):
        # Exercise both the first insert and an update of an existing canvas.
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as folder:
                database = Path(folder) / 'state.sqlite3'

                def open_canvas():
                    app = SimpleNamespace(
                        db=sqlite3.connect(database, timeout=10), lock=threading.RLock(),
                        creation=SimpleNamespace(get_project=lambda oid: {
                            'title': '项目', 'summary': '', 'assets': []}),
                    )
                    return app, CreationCanvas(app)

                app, canvas = open_canvas()
                try:
                    if existing:
                        canvas.save(canvas.get('creation:one'))
                finally:
                    app.db.close()

                barrier = threading.Barrier(2, timeout=10)

                def write(x):
                    app, canvas = open_canvas()
                    try:
                        body = canvas.get('creation:one')
                        body['nodes'][0]['position']['x'] = x
                        barrier.wait()
                        try:
                            return ('saved', canvas.save(body))
                        except WorkspaceConflict:
                            return ('conflict', None)
                    finally:
                        app.db.close()

                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(write, (101, 202)))
                self.assertEqual(sorted(result[0] for result in results), ['conflict', 'saved'])
                saved = next(result[1] for result in results if result[0] == 'saved')
                app, canvas = open_canvas()
                try:
                    self.assertEqual(canvas.get('creation:one'), saved)
                finally:
                    app.db.close()


if __name__ == '__main__':
    unittest.main()
