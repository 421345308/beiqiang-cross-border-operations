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

    def observation(self, *, minutes=0, status='ok', thread_id='thread-one', host_id='local', metadata=None):
        value={'host_id':host_id,'thread_id':thread_id,
               'observed_at':(datetime.now(timezone.utc)-timedelta(minutes=minutes)).isoformat(),
               'status':status,'source_tool':'mcp__codex_app__wait_threads'}
        if metadata is not None:value['metadata']=metadata
        elif status=='ok':value['metadata']={'status':'active'}
        return value

    def test_individual_observation_has_own_scope_and_does_not_mutate_full_snapshot(self):
        full=self.service.import_snapshot(self.payload(minutes=11))
        raw_before=self.service._stored()['threads']
        item=self.observation(metadata={'status':'active','updatedAt':1794370380})
        reply=self.service.import_observation(item)
        current=self.service.read();row=current['threads'][0]
        self.assertEqual(reply['scope'],'individual')
        self.assertEqual(current['state'],'stale')
        self.assertEqual(current['snapshot_observed_at'],full['snapshot_observed_at'])
        self.assertEqual(self.service._stored()['threads'],raw_before)
        self.assertEqual(row['status'],'active')
        self.assertEqual(row['individual_observation']['state'],'ok')
        self.assertEqual(row['individual_observation']['source'],'mcp__codex_app__wait_threads')
        self.assertEqual(row['individual_observation']['value_scope'],'individual')
        self.assertFalse(reply['automatic_refresh'])

    def test_individual_failure_preserves_last_value_and_marks_only_that_source(self):
        self.service.import_snapshot(self.payload([self.thread(),self.thread(id='other')],minutes=5))
        success=self.service.import_observation(self.observation(minutes=2))
        failed=self.service.import_observation(self.observation(status='unavailable'))
        current=self.service.read();first,second=current['threads']
        self.assertEqual(current['state'],'ok')
        self.assertEqual(first['status'],'active')
        self.assertEqual(first['individual_observation']['state'],'unavailable')
        self.assertEqual(first['individual_observation']['observed_at'],success['individual_observation']['observed_at'])
        self.assertNotEqual(first['individual_observation']['attempted_at'],first['individual_observation']['observed_at'])
        self.assertNotIn('individual_observation',second)
        self.assertEqual(failed['full_snapshot_observed_at'],current['snapshot_observed_at'])

    def test_individual_duplicate_is_idempotent_and_old_or_ambiguous_rejected(self):
        from workspaces import WorkspaceConflict
        self.service.import_snapshot(self.payload(minutes=3))
        item=self.observation(minutes=1)
        first=self.service.import_observation(item)
        stored=self.service._stored()
        self.assertEqual(first,self.service.import_observation(item))
        self.assertEqual(stored,self.service._stored())
        with self.assertRaises(WorkspaceConflict):self.service.import_observation(self.observation(minutes=2))
        changed={**item,'metadata':{'status':'idle'}}
        with self.assertRaises(WorkspaceConflict):self.service.import_observation(changed)
        with self.assertRaises(ValueError):self.service.import_observation(self.observation(thread_id='unknown'))
        with self.assertRaises(ValueError):self.service.import_observation({**item,'source_tool':'untrusted'})
        with self.assertRaises(ValueError):self.service.import_observation({**item,'source_tool':[]})
        with self.assertRaises(ValueError):self.service.import_observation({**item,'metadata':{'status':'active','summary':'not allowed'}})
        with self.assertRaises(ValueError):self.service.import_observation({**item,'status':'unavailable','metadata':{'status':'idle'}})
        with self.assertRaises(ValueError):self.service.import_observation({**item,'metadata':{'status':'active','updatedAt':'not-a-date'}})
        self.assertEqual(stored,self.service._stored())

    def test_individual_old_observation_loses_cross_connection_race(self):
        from workspaces import WorkspaceConflict
        database=Path(self.temp.name)/'individual.sqlite3'
        connections=[sqlite3.connect(database,check_same_thread=False,timeout=3) for _ in range(2)]
        services=[DesktopSnapshot(SimpleNamespace(root=self.root,db=db,lock=threading.RLock())) for db in connections]
        services[0].import_snapshot(self.payload(minutes=3))
        claimed,second_started,release=[threading.Event() for _ in range(3)]
        original=services[0]._stored
        def first_read():
            if claimed.is_set():return original()
            value=original();claimed.set()
            if not release.wait(3):raise RuntimeError('test synchronization timeout')
            return value
        services[0]._stored=first_read
        errors=[]
        def run(index,payload):
            try:
                if index==1:second_started.set()
                services[index].import_observation(payload)
            except BaseException as error:errors.append(error)
        workers=[threading.Thread(target=run,args=(0,self.observation())),
                 threading.Thread(target=run,args=(1,self.observation(minutes=1,metadata={'status':'idle'})))]
        try:
            workers[0].start();self.assertTrue(claimed.wait(3))
            workers[1].start();self.assertTrue(second_started.wait(3));release.set()
            for worker in workers:worker.join(4)
            self.assertFalse(any(worker.is_alive() for worker in workers))
            self.assertEqual(len(errors),1);self.assertIsInstance(errors[0],WorkspaceConflict)
            self.assertEqual(services[0].read()['threads'][0]['status'],'active')
        finally:
            release.set()
            for worker in workers:
                if worker.ident:worker.join(4)
            for connection in connections:connection.close()

    def test_individual_failure_before_any_success_keeps_complete_snapshot_value(self):
        full=self.service.import_snapshot(self.payload([self.thread(status='notLoaded')],minutes=2))
        value=self.service.import_observation(self.observation(status='unavailable'))
        row=self.service.read()['threads'][0]
        self.assertEqual(row['status'],'notLoaded')
        self.assertEqual(value['individual_observation']['state'],'unavailable')
        self.assertEqual(value['individual_observation']['observed_at'],full['snapshot_observed_at'])
        self.assertEqual(value['individual_observation']['value_scope'],'complete_snapshot')

    def test_individual_and_mapping_survive_full_source_failure(self):
        self.service.import_snapshot(self.payload(minutes=3))
        self.service.import_observation(self.observation(minutes=1))
        self.service.link_workstream({'workstream':'alibaba','host_id':'local','thread_id':'thread-one','source_note':'explicit mapping'})
        failed=self.payload([]);failed['status']='unavailable'
        value=self.service.import_snapshot(failed)
        self.assertEqual(value['state'],'unavailable')
        self.assertEqual(value['threads'][0]['status'],'active')
        self.assertEqual(value['threads'][0]['individual_observation']['state'],'ok')
        self.assertEqual(value['workstream_links'][0]['workstream'],'alibaba')

    def test_individual_success_does_not_clear_global_failure(self):
        self.service.import_snapshot(self.payload(minutes=3))
        failed=self.payload([]);failed['status']='unavailable'
        failed['observed_at']=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()
        self.service.import_snapshot(failed)
        self.service.import_observation(self.observation(minutes=1))
        value=self.service.read()
        self.assertEqual(value['state'],'unavailable')
        self.assertTrue(value['stale'])
        self.assertEqual(value['threads'][0]['individual_observation']['state'],'ok')
        self.assertEqual(value['threads'][0]['status'],'active')

    def test_full_refresh_keeps_newer_individual_and_newer_full_replaces_older_one(self):
        self.service.import_snapshot(self.payload(minutes=5))
        self.service.import_observation(self.observation(minutes=1))
        middle=self.service.import_snapshot(self.payload([self.thread(status='idle')],minutes=2))
        self.assertEqual(middle['threads'][0]['status'],'active')
        self.assertEqual(middle['threads'][0]['individual_observation']['state'],'ok')
        latest=self.service.import_snapshot(self.payload([self.thread(status='notLoaded')]))
        self.assertEqual(latest['threads'][0]['status'],'notLoaded')
        self.assertNotIn('individual_observation',latest['threads'][0])

    def test_full_snapshot_rebases_value_under_newer_failed_individual_attempt(self):
        self.service.import_snapshot(self.payload(minutes=5))
        self.service.import_observation(self.observation(minutes=4))
        self.service.import_observation(self.observation(minutes=1,status='unavailable'))
        full=self.service.import_snapshot(self.payload([self.thread(status='idle')],minutes=2))
        row=full['threads'][0]
        self.assertEqual(row['status'],'idle')
        self.assertEqual(row['individual_observation']['state'],'unavailable')
        self.assertEqual(row['individual_observation']['value_scope'],'complete_snapshot')
        self.assertEqual(row['individual_observation']['observed_at'],full['snapshot_observed_at'])

    def test_workstream_links_are_explicit_unique_idempotent_and_survive_full_refresh(self):
        from workspaces import WorkspaceConflict
        self.service.import_snapshot(self.payload([self.thread(),self.thread(id='thread-two')],minutes=3))
        link={'workstream':'tools','host_id':'local','thread_id':'thread-one','source_note':'explicit user mapping'}
        first=self.service.link_workstream(link)
        self.assertEqual(first['registration_state'],'present_in_snapshot')
        self.assertEqual(first['control'],'reference_only')
        self.assertEqual(first,self.service.link_workstream(link))
        with self.assertRaises(WorkspaceConflict):self.service.link_workstream({**link,'thread_id':'thread-two'})
        with self.assertRaises(WorkspaceConflict):self.service.link_workstream({**link,'workstream':'website'})
        with self.assertRaises(ValueError):self.service.link_workstream({**link,'workstream':'unknown'})
        with self.assertRaises(ValueError):self.service.link_workstream({**link,'workstream':[]})
        with self.assertRaises(ValueError):self.service.link_workstream({**link,'workstream':'website','thread_id':'missing'})
        with self.assertRaises(ValueError):self.service.link_workstream({**link,'source_note':' '})
        with self.assertRaises(ValueError):self.service.link_workstream({**link,'summary':'not allowed'})
        updated=self.service.import_snapshot(self.payload([self.thread(id='thread-two')]))
        self.assertEqual(updated['workstream_links'][0]['registration_state'],'not_in_latest_snapshot')
        self.assertEqual(updated['workstream_links'][0]['thread_id'],'thread-one')
        self.assertEqual(self.service.link_workstream(link)['registration_state'],'not_in_latest_snapshot')

    def test_workstream_links_conflict_across_independent_connections(self):
        from workspaces import WorkspaceConflict
        database=Path(self.temp.name)/'links.sqlite3'
        connections=[sqlite3.connect(database,check_same_thread=False,timeout=3) for _ in range(2)]
        services=[DesktopSnapshot(SimpleNamespace(root=self.root,db=db,lock=threading.RLock())) for db in connections]
        services[0].import_snapshot(self.payload([self.thread(),self.thread(id='other')]))
        gate=threading.Barrier(2);errors=[]
        def run(index,thread_id):
            try:
                gate.wait(timeout=3)
                services[index].link_workstream({'workstream':'tools','host_id':'local','thread_id':thread_id,'source_note':'explicit mapping'})
            except BaseException as error:errors.append(error)
        workers=[threading.Thread(target=run,args=(0,'thread-one')),threading.Thread(target=run,args=(1,'other'))]
        try:
            for worker in workers:worker.start()
            for worker in workers:worker.join(4)
            self.assertFalse(any(worker.is_alive() for worker in workers))
            self.assertEqual(len(errors),1);self.assertIsInstance(errors[0],WorkspaceConflict)
            self.assertEqual(len(services[0].read()['workstream_links']),1)
        finally:
            for worker in workers:
                if worker.ident:worker.join(4)
            for connection in connections:connection.close()

    def test_workstream_replacement_requires_expected_identity_and_preserves_history(self):
        from workspaces import WorkspaceConflict
        self.service.import_snapshot(self.payload([self.thread(),self.thread(id='thread-two'),self.thread(id='other')],minutes=3))
        original={'workstream':'tools','host_id':'local','thread_id':'thread-one','source_note':'user specified first'}
        old=self.service.link_workstream(original)
        replacement={'workstream':'tools','host_id':'local','thread_id':'thread-two','source_note':'user specified replacement',
                     'expected_host_id':'local','expected_thread_id':'thread-one','expected_linked_at':old['linked_at']}
        before=self.service._stored()
        with self.assertRaises(WorkspaceConflict):
            self.service.link_workstream({k:v for k,v in replacement.items() if not k.startswith('expected_')})
        with self.assertRaises(ValueError):
            self.service.link_workstream({k:v for k,v in replacement.items() if k!='expected_thread_id'})
        with self.assertRaises(WorkspaceConflict):
            self.service.link_workstream({**replacement,'expected_thread_id':'stale'})
        with self.assertRaises(ValueError):
            self.service.link_workstream({**replacement,'thread_id':'missing'})
        self.assertEqual(before,self.service._stored())
        updated=self.service.link_workstream(replacement)
        self.assertEqual(updated['thread_id'],'thread-two')
        self.assertEqual(updated['control'],'reference_only')
        history=self.service.read()['workstream_link_history']
        self.assertEqual(len(history),1)
        self.assertEqual(history[0]['thread_id'],'thread-one')
        self.assertEqual(history[0]['source_note'],'user specified first')
        self.assertEqual(history[0]['linked_at'],old['linked_at'])
        self.assertTrue(history[0]['replaced_at'])
        with self.assertRaises(WorkspaceConflict):self.service.link_workstream(replacement)
        self.assertEqual(len(self.service.read()['workstream_link_history']),1)
        self.assertEqual(updated,self.service.link_workstream({k:v for k,v in replacement.items() if not k.startswith('expected_')}))
        refreshed=self.service.import_snapshot(self.payload([self.thread(id='other')]))
        self.assertEqual(refreshed['workstream_links'][0]['registration_state'],'not_in_latest_snapshot')
        self.assertEqual(refreshed['workstream_link_history'][0]['thread_id'],'thread-one')

    def test_replacement_rejects_destination_owned_by_another_workstream(self):
        from workspaces import WorkspaceConflict
        self.service.import_snapshot(self.payload([self.thread(),self.thread(id='thread-two')]))
        old=self.service.link_workstream({'workstream':'tools','host_id':'local','thread_id':'thread-one','source_note':'first'})
        self.service.link_workstream({'workstream':'website','host_id':'local','thread_id':'thread-two','source_note':'second'})
        with self.assertRaises(WorkspaceConflict):
            self.service.link_workstream({'workstream':'tools','host_id':'local','thread_id':'thread-two','source_note':'new',
                'expected_host_id':'local','expected_thread_id':'thread-one','expected_linked_at':old['linked_at']})
        self.assertEqual(len(self.service.read().get('workstream_link_history',[])),0)

    def test_replacement_detects_aba_even_when_clock_does_not_advance(self):
        from unittest.mock import patch
        from workspaces import WorkspaceConflict
        self.service.import_snapshot(self.payload([self.thread(),self.thread(id='two'),self.thread(id='three')]))
        def payload(target,note,previous=None):
            value={'workstream':'tools','host_id':'local','thread_id':target,'source_note':note}
            if previous:
                value.update(expected_host_id=previous['host_id'],expected_thread_id=previous['thread_id'],
                             expected_linked_at=previous['linked_at'])
            return value
        with patch('desktop_snapshot.stamp',return_value='2026-01-01T00:00:00+00:00'):
            first=self.service.link_workstream(payload('thread-one','first'))
            second=self.service.link_workstream(payload('two','second',first))
            third=self.service.link_workstream(payload('thread-one','third',second))
        self.assertLess(first['linked_at'],second['linked_at'])
        self.assertLess(second['linked_at'],third['linked_at'])
        before=self.service._stored()
        with self.assertRaises(WorkspaceConflict):self.service.link_workstream(payload('three','stale',first))
        self.assertEqual(before,self.service._stored())
        self.assertEqual(self.service.read()['workstream_links'][0]['thread_id'],'thread-one')
        self.assertEqual(len(self.service.read()['workstream_link_history']),2)

    def test_two_replacements_with_same_expected_identity_only_one_succeeds(self):
        from workspaces import WorkspaceConflict
        database=Path(self.temp.name)/'replace.sqlite3'
        connections=[sqlite3.connect(database,check_same_thread=False,timeout=3) for _ in range(2)]
        services=[DesktopSnapshot(SimpleNamespace(root=self.root,db=db,lock=threading.RLock())) for db in connections]
        services[0].import_snapshot(self.payload([self.thread(),self.thread(id='two'),self.thread(id='three')]))
        old=services[0].link_workstream({'workstream':'tools','host_id':'local','thread_id':'thread-one','source_note':'first'})
        gate=threading.Barrier(2);errors=[]
        def run(index,thread_id):
            try:
                gate.wait(timeout=3)
                services[index].link_workstream({'workstream':'tools','host_id':'local','thread_id':thread_id,'source_note':'replacement',
                    'expected_host_id':'local','expected_thread_id':'thread-one','expected_linked_at':old['linked_at']})
            except BaseException as error:errors.append(error)
        workers=[threading.Thread(target=run,args=(0,'two')),threading.Thread(target=run,args=(1,'three'))]
        try:
            for worker in workers:worker.start()
            for worker in workers:worker.join(4)
            self.assertFalse(any(worker.is_alive() for worker in workers))
            self.assertEqual(len(errors),1);self.assertIsInstance(errors[0],WorkspaceConflict)
            result=services[0].read()
            self.assertIn(result['workstream_links'][0]['thread_id'],('two','three'))
            self.assertEqual(len(result['workstream_link_history']),1)
            self.assertEqual(result['workstream_link_history'][0]['thread_id'],'thread-one')
        finally:
            for worker in workers:
                if worker.ident:worker.join(4)
            for connection in connections:connection.close()

    def test_workstream_link_history_is_bounded(self):
        self.service.import_snapshot(self.payload([self.thread(),self.thread(id='thread-two')]))
        previous='thread-one'
        linked=self.service.link_workstream({'workstream':'tools','host_id':'local','thread_id':previous,'source_note':'initial'})
        for n in range(105):
            current='thread-two' if previous=='thread-one' else 'thread-one'
            linked=self.service.link_workstream({'workstream':'tools','host_id':'local','thread_id':current,'source_note':f'explicit change {n}',
                'expected_host_id':'local','expected_thread_id':previous,'expected_linked_at':linked['linked_at']})
            previous=current
        history=self.service.read()['workstream_link_history']
        self.assertEqual(len(history),100)
        self.assertEqual(history[0]['source_note'],'explicit change 4')

    def test_cli_can_link_and_observe_without_creating_jobs(self):
        import subprocess,sys
        database=Path(self.temp.name)/'runs.sqlite3'
        connection=sqlite3.connect(database)
        service=DesktopSnapshot(SimpleNamespace(root=self.root,db=connection,lock=threading.RLock()))
        service.import_snapshot(self.payload(minutes=2));connection.close()
        script=Path(__file__).with_name('desktop_snapshot.py')
        prefix=[sys.executable,'-X','utf8',str(script),'--root',str(self.root),'--state',self.temp.name]
        link={'workstream':'website','host_id':'local','thread_id':'thread-one','source_note':'explicit mapping'}
        def run(option,payload):
            p=subprocess.run(prefix+[option,'-'],input=json.dumps(payload)+'\n',text=True,encoding='utf8',capture_output=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            return json.loads(p.stdout)
        self.assertEqual(run('--link-input',link)['control'],'reference_only')
        self.assertEqual(run('--observation-input',self.observation())['scope'],'individual')
        connection=sqlite3.connect(database)
        try:
            service=DesktopSnapshot(SimpleNamespace(root=self.root,db=connection,lock=threading.RLock()))
            self.assertEqual(service.read()['threads'][0]['status'],'active')
            self.assertEqual(service.read()['workstream_links'][0]['workstream'],'website')
            tables={row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
            self.assertEqual(tables,{'desktop_observation'})
        finally:connection.close()
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
