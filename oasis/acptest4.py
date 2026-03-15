# /// script
# dependencies = ["agent-client-protocol"]
# ///

import asyncio
import os
import sys
import json
from acp import PROTOCOL_VERSION, Client, connect_to_agent, text_block
from acp.schema import ClientCapabilities, Implementation, AgentMessageChunk

# --- 验证过的过滤器 ---
class SecureStreamReader(asyncio.StreamReader):
    def __init__(self, real_reader, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._real_reader = real_reader

    async def readline(self):
        while True:
            line = await self._real_reader.readline()
            if not line: return b""
            if line.strip().startswith(b'{'): return line
            continue

# --- 内部协议处理类 ---
class InternalClient(Client):
    def __init__(self):
        self.chunks = []

    async def session_update(self, session_id, update, **kwargs):
        if isinstance(update, AgentMessageChunk) and hasattr(update.content, 'text'):
            self.chunks.append(update.content.text)

    def get_and_clear_text(self):
        text = "".join(self.chunks)
        self.chunks = []
        return text

# --- 核心组件类：供调度中心直接使用 ---
class AgentInstance:
    """
    Agent 实例组件。
    由调度中心实例化，内部管理子进程的生命周期。
    """
    def __init__(self, name, cmd, args):
        self.name = name
        self.cmd = cmd
        self.args = args
        self.proc = None
        self.conn = None
        self.session_id = None
        self.client = InternalClient()

    async def start(self):
        """启动子进程并完成 ACP 初始化"""
        self.proc = await asyncio.create_subprocess_exec(
            self.cmd, *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=sys.stderr 
        )
        
        safe_stdout = SecureStreamReader(self.proc.stdout)
        self.conn = connect_to_agent(self.client, self.proc.stdin, safe_stdout)

        # 执行握手
        await self.conn.initialize(
            protocol_version=PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(),
            client_info=Implementation(name=f"orch-comp-{self.name}", version="1.0"),
        )
        session = await self.conn.new_session(mcp_servers=[], cwd=os.getcwd())
        self.session_id = session.session_id
        print(f"[*] Agent [{self.name}] 实例已启动并建立长连接。")
        return self

    async def send(self, prompt):
        """发送消息并获取回复，保持上下文"""
        if not self.conn:
            raise RuntimeError(f"Agent {self.name} 尚未启动")
        
        await self.conn.prompt(session_id=self.session_id, prompt=[text_block(prompt)])
        return self.client.get_and_clear_text()

    async def stop(self):
        if self.proc and self.proc.returncode is None:
            # 1. 关键：手动喂入 EOF，打破 SecureStreamReader 的读取循环
            self.proc.stdout.feed_eof() 
            
            # 2. 关闭输入流
            if self.proc.stdin:
                self.proc.stdin.close()
                
            # 3. 强力清理进程
            self.proc.terminate()
            try:
                # 只等 0.2 秒，不等它在那磨叽
                await asyncio.wait_for(self.proc.wait(), timeout=0.2)
            except asyncio.TimeoutError:
                self.proc.kill() # 还不走就直接强杀
                await self.proc.wait()

