"""Codex CLI process adapter for the local agent runtime.

It translates one CLI stream into small runtime events. Business context,
task state, authorization and result publication remain with the caller.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

MODEL = 'gpt-6.1-sol'
TOKEN_FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')


class CodexBackend:
    """Default backend; this adapter does not imply another provider exists."""

    def __init__(self, executable_resolver=None):
        self.executable_resolver=executable_resolver or (lambda:shutil.which('codex'))

    def resolve_executable(self):
        return self.executable_resolver()

    @staticmethod
    def command(exe, folder, final, *, root, state, object_id, session_id=None, mode='draft', schema_path=None):
        mcp_args=[str(Path(__file__).with_name('desk_mcp.py').resolve()),'--root',str(Path(root).resolve()),
                  '--state',str(Path(state).resolve()),'--object-id',object_id,'--audit',str(folder/'source-reads.jsonl')]
        extraction = mode in ('mail_draft', 'customer_analysis')
        if extraction:
            mcp_args.append('--read-only')
        command = [exe, '--ask-for-approval', 'never', '-s', 'read-only' if extraction else 'workspace-write', '-C', str(Path(root).resolve())]
        if not extraction:
            command.append('--search')
        command.append('exec')
        if session_id:
            command += ['resume', session_id]
        features = (['--ignore-user-config', '--disable', 'multi_agent', '--disable', 'apps', '--disable', 'plugins', '--disable', 'remote_plugin']
                    if extraction else ['--enable', 'multi_agent', '-c', 'sandbox_workspace_write.network_access=true'])
        result=command + features + [
                '-c','mcp_servers.beiqiang_business.command='+json.dumps(sys.executable),
                '-c','mcp_servers.beiqiang_business.args='+json.dumps(mcp_args,ensure_ascii=False),
                '-m', MODEL, '--skip-git-repo-check', '--json', '-o', str(final), '-']
        if schema_path is not None:result[-1:-1]=['--output-schema',str(schema_path)]
        return result

    @staticmethod
    def spawn(command, *, env, flags):
        return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                errors='replace', env=env, **flags)

    @staticmethod
    def parse_event(line):
        """Map a Codex JSON line without returning commands or tool outputs."""
        try:
            event=json.loads(line)
        except (ValueError, TypeError):
            return None
        if not isinstance(event,dict):return None
        kind=event.get('type')
        if kind=='thread.started' and isinstance(event.get('thread_id'),str):
            try:return {'kind':'session','session_id':str(uuid.UUID(event['thread_id']))}
            except ValueError:return None
        if kind=='turn.completed':
            value=event.get('usage')
            usage={key:value[key] for key in TOKEN_FIELDS
                   if isinstance(value,dict) and type(value.get(key)) is int and value[key]>=0}
            return {'kind':'completed','usage':usage or None}
        if kind=='turn.failed':return {'kind':'failed'}
        if kind=='error':return {'kind':'reconnecting'}
        if kind not in ('item.started','item.completed'):return None
        item=event.get('item')
        if not isinstance(item,dict):return None
        item_type=item.get('type')
        if item_type in ('command_execution','tool_call','mcp_tool_call','web_search'):
            if kind=='item.completed':return {'kind':'progress','event':'tool.completed','text':'一项资料工具步骤已结束。'}
            if item_type=='web_search':return {'kind':'progress','event':'search','text':'正在检索公开资料。'}
            if re.search(r'\brg\b|\bgrep\b|select-string|findstr',str(item.get('command','')),re.I):
                return {'kind':'progress','event':'search','text':'正在项目资料中检索依据。'}
            if item_type=='command_execution':return {'kind':'progress','event':'read','text':'正在读取和核对项目资料。'}
            return {'kind':'progress','event':'tool','text':'正在调用资料工具。'}
        if item_type=='agent_message' and kind=='item.completed':
            return {'kind':'message','text':item.get('text','')}
        return None
