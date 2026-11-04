"""Reuse existing product media in an existing creation canvas, without copies."""
from pathlib import PurePosixPath
from uuid import uuid4


class ProductCreation:
    def __init__(self, app):
        self.app = app

    def _product(self, product_id):
        if not isinstance(product_id, str) or not product_id.startswith('product:'):
            raise ValueError('请选择商品')
        product = self.app.business.get_object(product_id)
        if product.get('kind') != 'product':
            raise ValueError('请选择商品')
        return product

    def options(self, product_id):
        product = self._product(product_id)
        assets = []
        for item in product.get('assets', []):
            try:
                media = self.app.media.resolve(item.get('path'))
            except ValueError:
                continue
            assets.append({**media, 'label': item.get('label') or media['name']})
        projects = [{k: row.get(k) for k in ('id', 'title', 'source')}
                    for row in self.app.creation.list_projects()]
        return {'product_id': product_id, 'assets': assets, 'projects': projects,
                'notice': '素材来自该商品已有索引；选择项目不表示商品与项目已经关联，原文件不会被复制或覆盖。'}

    def add_to_canvas(self, product_id, project_id, path, version):
        product = self._product(product_id)
        if not isinstance(path, str) or path not in {item.get('path') for item in product.get('assets', [])}:
            raise ValueError('请选择该商品已有素材')
        media = self.app.media.resolve(path)
        if not isinstance(project_id, str) or not project_id.startswith('creation:'):
            raise ValueError('请选择已有创作项目')
        canvas = self.app.creation_canvas.get(project_id)
        if canvas['version'] != version:
            from workspaces import WorkspaceConflict
            raise WorkspaceConflict('这份画布已被其他页面更新，请重新打开')
        if any(node.get('type') == 'asset' and node.get('data', {}).get('media_path') == path for node in canvas['nodes']):
            return {'canvas': canvas, 'added': False, 'notice': '该素材已在项目画布中'}
        node = {'id': 'asset-' + uuid4().hex, 'type': 'asset',
                'position': {'x': 420 + (len(canvas['nodes']) % 3) * 260,
                             'y': 80 + (len(canvas['nodes']) // 3) * 200},
                'data': {'title': PurePosixPath(path).name, 'media_path': path,
                         'kind': media['kind'], 'product_id': product_id}}
        saved = self.app.creation_canvas.save({**canvas, 'nodes': [*canvas['nodes'], node]})
        return {'canvas': saved, 'added': True, 'notice': '已在画布引用商品素材；原文件未改动'}
