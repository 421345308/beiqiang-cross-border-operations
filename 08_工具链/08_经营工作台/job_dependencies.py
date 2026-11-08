"""Persistent relationships on AgentJobs, with explicit first execution only.

No scheduler or replay loop: callers inspect the graph and explicitly dispatch
ready plans. Existing records need no migration; absent links mean standalone.
All graph mutations and worker claims use AgentJobs' SQLite BEGIN IMMEDIATE.
"""
import os
import threading


class JobDependencies:
    def create_group(self, object_id, instruction, *, parent_job_id=None, idempotency_key=None, batch_id=None, context=None):
        """A non-executing container; graph aggregate reports child progress.

        The persisted group stays planned and never owns a worker. Adding a new
        child can reopen the computed aggregate without replaying older children.
        """
        return self.start(object_id, instruction, parent_job_id=parent_job_id,
                          idempotency_key=idempotency_key, batch_id=batch_id,
                          defer=True, task_kind='group', context=context)

    @staticmethod
    def _validate_plan_options(parent_job_id, depends_on, idempotency_key, defer):
        if parent_job_id is not None and (not isinstance(parent_job_id, str) or not parent_job_id):
            raise ValueError('父任务编号无效')
        if depends_on is not None and (not isinstance(depends_on, (list, tuple)) or
                len(depends_on) > 200 or any(not isinstance(v, str) or not v for v in depends_on)):
            raise ValueError('依赖应为最多200项任务编号')
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or
                not idempotency_key.strip() or len(idempotency_key) > 200):
            raise ValueError('去重键应为1至200字')
        if type(defer) is not bool:
            raise ValueError('defer 应为布尔值')

    def _existing_plan(self, job):
        key = job.get('idempotency_key')
        if key is None:
            return None
        for existing in self.list_jobs():
            if existing.get('idempotency_key') != key:
                continue
            fields = ('object_id', 'mode', 'batch_id', 'source_event', 'parent_job_id', 'task_kind', 'context')
            original_instruction = existing.get('initial_instruction', existing.get('instruction'))
            if (original_instruction != job.get('initial_instruction') or
                    any(existing.get(k) != job.get(k) for k in fields) or
                    set(existing.get('depends_on', [])) != set(job.get('depends_on', []))):
                raise ValueError('去重键已用于不同工作，请读取原任务')
            return existing
        return None

    def _validate_links(self, job):
        if job.get('parent_job_id'):
            if self.get_job(job['parent_job_id'])['status'] == 'cancelled':
                raise ValueError('已取消的父任务不能新增子任务')
        for dependency in job.get('depends_on', []):
            if self.get_job(dependency).get('task_kind') == 'group':
                raise ValueError('依赖必须指向实际工作，不能依赖动态分组')
        jobs = {row['id']: row for row in self.list_jobs()}
        jobs[job['id']] = job
        # Iterative traversal avoids a recursion limit on long imported graphs.
        visited = set()
        pending = list(job.get('depends_on', []))
        while pending:
            current = pending.pop()
            if current == job['id']:
                raise ValueError('任务依赖不能形成循环')
            if current in visited:
                continue
            visited.add(current)
            pending.extend(jobs[current].get('depends_on', []))

    def _check_dependencies(self, job):
        blocked = [key for key in job.get('depends_on', [])
                   if self.get_job(key)['status'] != 'completed']
        if blocked:
            raise ValueError('前置任务尚未完成，请先核对依赖任务：' + ', '.join(blocked))

    def _check_parent_available(self, job):
        parent = job.get('parent_job_id')
        seen = {job['id']}
        while parent:
            if parent in seen:
                raise ValueError('父任务关系无效')
            seen.add(parent)
            row = self.get_job(parent)
            if row['status'] == 'cancelled':
                raise ValueError('父任务已取消，不能启动子任务')
            parent = row.get('parent_job_id')

    def add_dependency(self, job_id, dependency_id):
        """Add a dependency before first dispatch; active inputs are immutable."""
        if not isinstance(dependency_id, str) or not dependency_id:
            raise ValueError('依赖任务编号无效')
        with self._write():
            job = self.get_job(job_id)
            if job['status'] != 'planned':
                raise ValueError('只可修改尚未执行的计划依赖')
            if job.get('task_kind') == 'group':
                raise ValueError('分组不执行，前置依赖请添加到实际子任务')
            links = job.setdefault('depends_on', [])
            if dependency_id not in links:
                if len(links) >= 200:
                    raise ValueError('每项任务最多200项依赖')
                links.append(dependency_id)
            self._validate_links(job)
            self._event(job, 'dependency', '已更新前置任务；未自动执行。')
            self._save(job)
        return job

    def get_graph(self, job_id):
        """Snapshot of a root and descendants, with external dependencies."""
        with self.app.lock:
            rows = {row['id']: row for row in self.list_jobs()}
        if job_id not in rows:
            raise ValueError('找不到这项工作')
        children = {}
        for row in rows.values():
            children.setdefault(row.get('parent_job_id'), []).append(row['id'])
        ids, pending = set(), [job_id]
        while pending:
            key = pending.pop()
            if key in ids:
                continue
            ids.add(key)
            pending.extend(children.get(key, []))
        jobs = []
        external = set()
        for key in sorted(ids):
            row = dict(rows[key])
            dependencies = row.get('depends_on', [])
            row['blocked_by'] = [dep for dep in dependencies if dep not in rows or rows[dep]['status'] != 'completed']
            row['ready'] = row['status'] == 'planned' and row.get('task_kind') != 'group' and not row['blocked_by']
            external.update(set(dependencies) - ids)
            jobs.append(row)
        work = [row for row in jobs if row.get('task_kind') != 'group']
        counts = {}
        for row in work:
            counts[row['status']] = counts.get(row['status'], 0) + 1
        state = ('empty' if not work else
                 'running' if any(row['status'] in ('queued', 'running') for row in work) else
                 'needs_attention' if any(row['status'] in ('failed', 'needs_input', 'cancelled') for row in work) else
                 'completed' if all(row['status'] == 'completed' for row in work) else
                 'ready' if any(row['ready'] for row in work) else 'blocked')
        return {'root_job_id': job_id, 'jobs': jobs,
                'aggregate': {'status': state, 'counts': counts, 'total': len(work)},
                'external_dependencies': [rows[key] for key in sorted(external) if key in rows]}

    def dispatch(self, job_id):
        """Explicitly execute an unattempted plan; never replay a prior attempt.

        Crash after claim is handled by existing owner recovery, never returned
        to planned. Retrying a failed/interrupted job requires explicit resume
        and reconciliation of its original session and side effects.
        """
        with self.lock:
            with self._write():
                self._recover_exited_owners()
                job = self.get_job(job_id)
                if job.get('task_kind') == 'group':
                    raise ValueError('分组只汇总子任务，不能启动执行器')
                if job['status'] != 'planned' or job.get('attempt', 0):
                    raise ValueError('只能显式启动尚未执行的计划；已执行工作不能自动重放')
                self._check_parent_available(job)
                self._check_dependencies(job)
                self._check_object_available(job['object_id'], exclude=job_id)
                obj = self.app.business.get_object(job['object_id'])
                if not isinstance(obj, dict) or obj.get('id') != job['object_id']:
                    raise ValueError('业务对象无效')
                parent = self.get_job(job['parent_job_id']) if job.get('parent_job_id') else None
                if (parent and (parent.get('context') or {}).get('type') == 'customer_batch_research'
                        and job.get('mode') == 'outreach_research'):
                    guard = getattr(self.app, 'batch_research', None)
                    if guard is None:
                        raise ValueError('客户批次检查不可用，请回到原批次核对')
                    guard.check_dispatch(job, obj)
                if job.get('mode') == 'customer_analysis':
                    profile = self.app.customer_workspace.profile(job['object_id'])
                    obj = {**obj, '_customer_profile': profile}
                    job.update(source_hash=profile['source_hash'], profile_revision=profile['revision'], profile_saved=False)
                job.update(status='queued', owner_pid=os.getpid(), owner_id=self.owner_id, worker_finished=False)
                self._event(job, 'queued', '计划已显式启动，前置任务已完成。')
                self._save(job)
            try:
                worker = threading.Thread(target=self._work, args=(job_id, obj), daemon=True,
                                          name='business-agent-' + job_id[:8])
                self.threads[job_id] = worker
                worker.start()
            except BaseException:
                self.threads.pop(job_id, None)
                with self._write():
                    current = self.get_job(job_id)
                    current.update(status='failed', worker_finished=True, error='工作线程未能启动；未自动重试。')
                    self._save(current)
                raise
        return job
