from acptest4 import AgentInstance
import asyncio
# --- 调度中心使用示例 ---
async def main():
    # 1. 调度中心初始化时，直接开启多个子进程实例
    claw = AgentInstance("claw_test2", "openclaw", ["acp", "--session", "agent:test2:main", "--no-prefix-cwd"])
    # 你可以同时开启另一个实例，比如 Codex
    # coder = AgentInstance("codex_main", "npx", ["@zed-industries/codex-acp"])

    await claw.start()
    # await coder.start()

    try:
        # 2. 在程序的任何地方，直接调用实例的 send 方法
        print("\n[调度中心] 下达指令 A...")
        res1 = await claw.send("你好，连接测试")
        print(f"回复 A: {res1.strip()}")

        print("\n[调度中心] 下达指令 B...")
        res2 = await claw.send("连接测试2")
        print(f"回复 B: {res2.strip()}")

    finally:
        # 3. 调度中心退出时，统一清理
        await claw.stop()

if __name__ == "__main__":
    asyncio.run(main())