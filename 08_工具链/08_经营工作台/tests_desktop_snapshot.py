import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from desktop_snapshot import DesktopSnapshot, SOURCE
from task_workspace import TaskWorkspace


class DesktopSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'workspace'
        self.root.mkdir()
        self.app=SimpleNamespace(root=self.root,db=sqlite3.connect(':memory:'),lock=threading.RLock())
        self.service=DesktopSnapshot(self.app)
    def tearDown(self):
        self.app.db.close();self.temp.cleanup()
    def payload(self, threads=None, minutes=0):
        return {'observed_at':(datetime.now(timezone.utc)-timedelta(minutes=minutes)).isoformat(),
                'status':'ok','truncated':False,'threads':threads if threads is not None else [self.thread()]}
    def thread(self, **updates):
        return {'id':'thread-one','hostId':'local','cwd':str(self.root),'title':'Synthetic title',
                'updatedAt':1794370380,'status':'notLoaded','projectId':None,**updates}
    def test_independent_connections_serialize_compare_and_commit(self):
        from workspaces import WorkspaceConflict
        database=Path(self.temp.name)/'observations.sqlite3'
        connections=[sqlite3.connect(database,check_same_thread=False,timeout=3) for _ in range(2)]
        services=[DesktopSnapshot(SimpleNamespace(root=self.root,db=db,lock=threading.RLock())) for db in connections]
        first_selected, second_started, second_selected, release = [threading.Event() for _ in range(4)]
        original_first, original_second = services[0]._stored, services[1]._stored
        def first_read():
            if first_selected.is_set():return original_first()
            self.assertTrue(connections[0].in_transaction)
            value=original_first();first_selected.set()
            if not release.wait(3):raise RuntimeError('test synchronization timeout')
            return value
        def second_read():
            second_selected.set();return original_second()
        services[0]._stored=first_read;services[1]._stored=second_read
        errors=[]
        old=self.payload(minutes=1);new=self.payload([self.thread(title='New observation')])
        def run(index,payload):
            try:
                if index==1:second_started.set()
                services[index].import_snapshot(payload)
            except BaseException as error:errors.append(error)
        workers=[threading.Thread(target=run,args=(0,old)),threading.Thread(target=run,args=(1,new))]
        try:
            workers[0].start();self.assertTrue(first_selected.wait(3))
            workers[1].start();self.assertTrue(second_started.wait(3))
            self.assertFalse(second_selected.wait(.1))
            release.set()
            for worker in workers:worker.join(4)
            self.assertFalse(any(worker.is_alive() for worker in workers))
            # import_snapshot returns a post-commit read, so restore the read hook first.
            services[0]._stored=original_first
            self.assertEqual(errors,[])
            self.assertEqual(services[0].read()['threads'][0]['title'],'New observation')
            with self.assertRaises(WorkspaceConflict):services[0].import_snapshot(old)
            self.assertFalse(connections[0].in_transaction)
        finally:
            release.set()
            for worker in workers:
                if worker.ident:worker.join(4)
            for connection in connections:connection.close()

    def test_failed_insert_rolls_back_previous_snapshot(self):
        self.service.import_snapshot(self.payload())
        self.app.db.execute("CREATE TRIGGER reject_snapshot BEFORE INSERT ON desktop_observation BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        self.app.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.import_snapshot(self.payload([self.thread(title='Must not persist')]))
        self.assertFalse(self.app.db.in_transaction)
        self.assertEqual(self.service.read()['threads'][0]['title'],'Synthetic title')

    def test_title_whitespace_preserved_but_controls_and_other_fields_rejected(self):
        title='Synthetic\r\nTitle\t<script>literal</script>'
        value=self.service.import_snapshot(self.payload([self.thread(title=title)]))
        self.assertEqual(value['threads'][0]['title'],title)
        for control in ('\x00','\x1b','\x7f','\x85','\u202e'):
            with self.subTest(control=repr(control)):
                with self.assertRaises(ValueError):
                    self.service.import_snapshot(self.payload([self.thread(title='Synthetic'+control)]))
        for key in ('id','hostId','cwd','kind','status','projectId'):
            for control in ('\r','\n','\t'):
                with self.subTest(key=key,control=repr(control)):
                    with self.assertRaises(ValueError):
                        self.service.import_snapshot(self.payload([self.thread(**{key:'Synthetic'+control})]))
        self.assertEqual(self.service.read()['threads'][0]['title'],title)

    def test_missing_scope_and_no_other_project_persisted(self):
        self.assertEqual(self.service.read()['state'],'missing')
        value=self.service.import_snapshot(self.payload([self.thread(),self.thread(id='outside',cwd=str(self.root.parent/'personal')),
            self.thread(id='relative',cwd='workspace'),self.thread(id='escape',cwd=str(self.root/'..'/'elsewhere'))]))
        self.assertEqual(len(value['threads']),1)
        self.assertEqual(value['excluded_count'],3)
        stored=self.app.db.execute('SELECT data FROM desktop_observation').fetchone()[0]
        self.assertNotIn('personal',stored)
        self.assertNotIn('outside',stored)
        self.assertIn('+00:00',value['threads'][0]['updatedAt'])
    def test_durable_mapping_requires_exact_host_and_workspace_tail(self):
        prefix='/tmp/codex-cloud-agent-abc/app_servers/threads/xyz/workspace/'
        value=self.service.import_snapshot(self.payload([
            self.thread(hostId='durable',cwd=prefix+str(self.root)),
            self.thread(id='wronghost',cwd=prefix+str(self.root)),
            self.thread(id='bad-tail',hostId='durable',cwd=prefix+str(self.root)+'-private'),
            self.thread(id='contains',hostId='durable',cwd='/tmp/other/'+str(self.root))]))
        self.assertEqual(len(value['threads']),1)
        self.assertEqual(value['threads'][0]['workspace_cwd'],str(self.root))
        self.assertEqual(value['threads'][0]['cwd'],prefix+str(self.root))
    def test_real_thread_service_mapping_keeps_strict_workspace_boundary(self):
        prefix='/tmp/codex-cloud-agent-abc/app_servers/thread_service/workspace/'
        value=self.service.import_snapshot(self.payload([
            self.thread(id='real',hostId='durable',cwd=prefix+str(self.root)),
            self.thread(id='child',hostId='durable',cwd=prefix+str(self.root/'child')),
            self.thread(id='wrong-host',hostId='local',cwd=prefix+str(self.root)),
            self.thread(id='wrong-prefix',hostId='durable',cwd='/tmp/untrusted/app_servers/thread_service/workspace/'+str(self.root)),
            self.thread(id='different-root',hostId='durable',cwd=prefix+str(self.root)+'-personal'),
            self.thread(id='traversal',hostId='durable',cwd=prefix+str(self.root/'..'/'personal')),
            self.thread(id='similar-service',hostId='durable',cwd='/tmp/codex-cloud-agent-abc/app_servers/thread_service_extra/workspace/'+str(self.root)),
            self.thread(id='nested-marker',hostId='durable',cwd=prefix+'fake/workspace/'+str(self.root))]))
        self.assertEqual([row['id'] for row in value['threads']],['real','child'])
        self.assertEqual(value['excluded_count'],6)
        self.assertEqual(value['threads'][0]['cwd'],prefix+str(self.root))
        self.assertEqual(value['threads'][1]['workspace_cwd'],str(self.root/'child'))

    def test_expiry_unavailable_retains_last_observation_and_metadata_only(self):
        value=self.service.import_snapshot(self.payload(minutes=11))
        self.assertEqual(value['state'],'stale')
        self.assertFalse(value['automatic_refresh'])
        unavailable=self.payload([]);unavailable['status']='unavailable'
        value=self.service.import_snapshot(unavailable)
        self.assertEqual(value['state'],'unavailable')
        self.assertEqual(len(value['threads']),1)
        self.assertTrue(value['stale'])
        for extra in ('summary','history','messages'):
            with self.assertRaises(ValueError):
                self.service.import_snapshot(self.payload([self.thread(**{extra:'forbidden'})]))

    def test_partial_refresh_does_not_replace_last_complete_snapshot(self):
        previous=self.service.import_snapshot(self.payload([self.thread(id='old')],minutes=1))
        partial=self.payload([self.thread(id='partial')]);partial['truncated']=True
        value=self.service.import_snapshot(partial)
        self.assertEqual(value['state'],'unavailable')
        self.assertTrue(value['stale'])
        self.assertTrue(value['attempt_truncated'])
        self.assertEqual(value['snapshot_observed_at'],previous['snapshot_observed_at'])
        self.assertEqual([item['id'] for item in value['threads']],['old'])

    def test_first_partial_refresh_does_not_masquerade_as_complete(self):
        partial=self.payload([self.thread(id='partial')]);partial['truncated']=True
        value=self.service.import_snapshot(partial)
        self.assertEqual(value['state'],'unavailable')
        self.assertEqual(value['threads'],[])
        self.assertTrue(value['attempt_truncated'])
        with self.assertRaises(ValueError):self.service.import_snapshot(self.payload([self.thread()]*501))
    def test_overview_read_only_not_loaded_unknown_no_title_association(self):
        self.service.import_snapshot(self.payload())
        self.app.desktop_snapshot=self.service
        self.app.agent_jobs=SimpleNamespace(list_jobs=lambda:[])
        self.app.business=SimpleNamespace(list_objects=lambda:[{'id':'product:one','title':'Synthetic title','kind':'product'}])
        self.app.cloud_review=SimpleNamespace(workspace_status=lambda:{'runs':[]})
        overview=TaskWorkspace(self.app).overview()
        row=overview['tasks'][0]
        self.assertEqual(row['origin'],'desktop')
        self.assertEqual(row['status'],'unknown')
        self.assertIsNone(row['object_id'])
        self.assertEqual(row['conversation_scope'],'reference_only')
        self.assertFalse(row['capabilities']['adjust'])
        self.assertFalse(row['capabilities']['external_conversation_control'])
        self.assertEqual(row['source'],SOURCE)
        self.assertIsNone(row['priority'])
        self.assertEqual(row['priority_basis'],'unregistered')
        self.assertIn('非实时',overview['scope'])
        self.assertEqual(TaskWorkspace(self.app).overview({'executor':'codex_cli'})['tasks'],[])
        self.assertEqual(overview['sources']['desktop']['state'],'ok')


class DesktopSnapshotHTTPTests(unittest.TestCase):
    from tests_desk_http import DeskHTTPTests as Fixture
    setUp=Fixture.setUp
    tearDown=Fixture.tearDown
    request=Fixture.request
    write=Fixture.write
    def test_import_uses_existing_csrf_and_never_creates_job(self):
        payload={'observed_at':datetime.now(timezone.utc).isoformat(),'status':'ok','truncated':False,
                 'threads':[{'id':'test','hostId':'local','cwd':str(self.root),'status':'notLoaded','title':'Fixture'}]}
        try: denied=self.request('/api/desk/desktop-snapshot',payload,token=False)[0]
        except (ConnectionAbortedError,ConnectionResetError):denied=0
        self.assertIn(denied,(0,403))
        self.assertEqual(self.app.desktop_snapshot.read()['state'],'missing')
        status,value=self.request('/api/desk/desktop-snapshot',payload)
        self.assertEqual(status,200)
        self.assertFalse(value['truncated'])
        self.assertEqual(self.app.agent_jobs.list_jobs(),[])
        self.assertEqual(self.request('/api/desk/desktop-snapshot')[0],200)
