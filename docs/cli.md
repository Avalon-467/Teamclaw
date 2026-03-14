# TeamClaw CLI 命令大全

> 最后更新：2026-03-14

## 运行方式

**使用项目根目录作为工作目录，通过 `uv run` 直接执行：**

```bash
cd /data/workspace/mini_timebot   # 进入项目根目录
uv run scripts/cli.py [参数...]
```

> ⚠️ **不需要** 额外安装 `teamclaw` 命令或设置 alias。直接在项目目录下用 `uv run` 即可，它会自动解析项目依赖并执行。

## 概览

```bash
uv run scripts/cli.py [-u USER] <子命令> [参数...]
```

**全局参数：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-u`, `--user` | 用户名（通过 `X-User-Id` header 传递给后端） | 环境变量 `CLI_USER`，兜底 `admin` |

> 💡 `-u` 对所有走 front.py 的命令生效（internal-agents / teams / visual / openclaw-snapshot 等）。

---

## 目录

1. [chat](#1-chat) — 发送消息
2. [sessions](#2-sessions) — 会话列表
3. [sessions-status](#3-sessions-status) — 所有会话忙碌状态
4. [session-status](#4-session-status) — 单个会话状态
5. [history](#5-history) — 会话历史
6. [delete-session](#6-delete-session) — 删除会话
7. [settings](#7-settings) — 查看/修改设置
8. [tools](#8-tools) — 可用工具
9. [tts](#9-tts) — 文字转语音
10. [cancel](#10-cancel) — 取消当前生成
11. [restart](#11-restart) — 重启 Agent
12. [groups](#12-groups) — 群组管理
13. [openclaw](#13-openclaw) — OpenClaw Agent 管理
14. [openclaw-snapshot](#14-openclaw-snapshot) — OpenClaw 快照管理
15. [visual](#15-visual) — 可视化编排管理
16. [internal-agents](#16-internal-agents) — 内部 Agent CRUD
17. [teams](#17-teams) — Team 管理
18. [topics](#18-topics) — OASIS 话题管理
19. [experts](#19-experts) — 专家列表
20. [workflows](#20-workflows) — Workflow 查看
21. [tunnel](#21-tunnel) — Cloudflare Tunnel 管理
22. [status](#22-status) — 服务状态检查

---

## 1. chat

**发送消息（流式输出）**

```bash
# 基本用法（-s 必填）
uv run scripts/cli.py -u Avalon_01 chat "你好" -s mysession

```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `message` | 消息内容（位置参数） | ✅ | — |
| `-s`, `--session` | 会话 ID | ✅ | — |

---

## 2. sessions

**查看会话列表**

```bash
uv run scripts/cli.py -u Avalon_01 sessions
```

无额外参数。

---

## 3. sessions-status

**查看所有会话忙碌状态**

```bash
uv run scripts/cli.py sessions-status
```

无额外参数。

---

## 4. session-status

**查看单个会话状态**

```bash
uv run scripts/cli.py session-status -s mysession
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `-s`, `--session` | 会话 ID | ❌ | `default` |

---

## 5. history

**查看会话历史**

```bash
# 查看完整历史
uv run scripts/cli.py -u Avalon_01 history -s mysession

# 最近 5 条
uv run scripts/cli.py -u Avalon_01 history -s mysession -n 5

# 不截断长消息
uv run scripts/cli.py -u Avalon_01 history -s mysession --full
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `-s`, `--session` | 会话 ID | ❌ | `default` |
| `-n`, `--limit` | 最近 N 条 | ❌ | 全部 |
| `--full` | 不截断长消息 | ❌ | `False` |

---

## 6. delete-session

**删除会话**

```bash
uv run scripts/cli.py -u Avalon_01 delete-session mysession
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `session` | 会话 ID（位置参数） | ✅ | — |

---

## 7. settings

**查看/修改设置**

```bash
# 查看基本设置
uv run scripts/cli.py settings

# 查看完整设置（含高级项）
uv run scripts/cli.py settings --full

# 修改设置
uv run scripts/cli.py settings --set model gpt-4o
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `--full` | 显示完整设置 | ❌ | `False` |
| `--set KEY VALUE` | 修改设置项 | ❌ | — |

---

## 8. tools

**查看可用工具**

```bash
# 完整工具列表
uv run scripts/cli.py tools

# 仅显示名称
uv run scripts/cli.py tools --brief
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `--brief` | 仅显示工具名称 | ❌ | `False` |

---

## 9. tts

**文字转语音**

```bash
uv run scripts/cli.py tts "你好世界" -o hello.mp3 --voice alloy
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `text` | 要转换的文本（位置参数） | ✅ | — |
| `-o`, `--output` | 输出文件 | ❌ | `tts_output.mp3` |
| `--voice` | 语音角色 | ❌ | — |

---

## 10. cancel

**取消当前生成**

```bash
uv run scripts/cli.py cancel -s mysession
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `-s`, `--session` | 会话 ID | ❌ | `default` |

---

## 11. restart

**重启 Agent 服务**

本地操作，写入 `.restart_flag` 文件触发 launcher 重启。

```bash
uv run scripts/cli.py restart
```

无额外参数，无 HTTP 请求。

---

## 12. groups

**群组管理**

```bash
# 列出群组
uv run scripts/cli.py groups
uv run scripts/cli.py groups list

# 创建群组
uv run scripts/cli.py groups create --name "测试群" --data '{"members":["bot1","bot2"]}'

# 查看群组详情
uv run scripts/cli.py groups get --group-id abc123

# 更新群组
uv run scripts/cli.py groups update --group-id abc123 --data '{"name":"新名字"}'

# 删除群组
uv run scripts/cli.py groups delete --group-id abc123

# 查看消息
uv run scripts/cli.py groups messages --group-id abc123
uv run scripts/cli.py groups messages --group-id abc123 --after-id msg_100

# 发送消息
uv run scripts/cli.py groups send --group-id abc123 --message "大家好"

# 静音/取消静音
uv run scripts/cli.py groups mute --group-id abc123
uv run scripts/cli.py groups unmute --group-id abc123
uv run scripts/cli.py groups mute-status --group-id abc123

# 群组会话
uv run scripts/cli.py groups sessions --group-id abc123
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `list` |
| `--group-id` | 群组 ID | 视操作而定 | — |
| `--name` | 群组名称 | create 时 | — |
| `--message` | 消息内容 | send 时 | — |
| `--data` | JSON 数据 | ❌ | — |
| `--after-id` | 增量消息起点 | ❌ | — |



---

## 13. openclaw

**OpenClaw Agent 管理**

```bash
# 列出 OpenClaw 会话
uv run scripts/cli.py openclaw
uv run scripts/cli.py openclaw sessions --filter keyword

# 添加 Agent
uv run scripts/cli.py openclaw add --data '{"name":"mybot","api_url":"..."}'

# 查看 Agent 详情
uv run scripts/cli.py openclaw detail --name mybot

# 查看工作区
uv run scripts/cli.py openclaw default-workspace
uv run scripts/cli.py openclaw workspace-files --workspace /path
uv run scripts/cli.py openclaw workspace-file-read --workspace /path --filename main.py

# 保存文件
uv run scripts/cli.py openclaw workspace-file-save --data '{"workspace":"/path","filename":"main.py","content":"..."}'

# 技能与工具
uv run scripts/cli.py openclaw skills --agent mybot
uv run scripts/cli.py openclaw tool-groups

# 频道与绑定
uv run scripts/cli.py openclaw channels
uv run scripts/cli.py openclaw bindings --agent mybot
uv run scripts/cli.py openclaw bind --data '{"agent":"mybot","channel":"ch1"}'

# 更新配置
uv run scripts/cli.py openclaw update-config --data '{"name":"mybot","config":{...}}'

# 移除 Agent
uv run scripts/cli.py openclaw remove --name mybot
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `sessions` |
| `--filter` | 过滤关键词 | ❌ | — |
| `--name` | Agent 名称 | 视操作 | — |
| `--agent` | Agent 名称 | 视操作 | — |
| `--workspace` | 工作区路径 | 视操作 | — |
| `--filename` | 文件名 | 视操作 | — |
| `--data` | JSON 数据 | 视操作 | — |


---

## 14. openclaw-snapshot

**OpenClaw 快照管理**

```bash
# 获取快照列表
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot get --team myteam

# 导出单个快照
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot export --team myteam --agent-name "Agent全名" --short-name "显示名"

# 导出全部
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot export-all --team myteam

# 同步全部
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot sync-all --team myteam

# 恢复单个
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot restore --team myteam --short-name "显示名" --target-name "目标Agent"

# 恢复全部
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot restore-all --team myteam
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `get` |
| `--team` | Team 名称 | ✅ | — |
| `--agent-name` | Agent 全名 | export 时 | — |
| `--short-name` | 显示名 | export/restore 时 | — |
| `--target-name` | 恢复目标 Agent 名 | restore 时 | — |


---

## 15. visual

**可视化编排管理**

```bash
# 专家列表
uv run scripts/cli.py -u Avalon_01 visual experts --team myteam

# 添加/删除自定义专家
uv run scripts/cli.py -u Avalon_01 visual add-expert --data '{"tag":"myexpert","name":"我的专家","prompt":"..."}' --team myteam
uv run scripts/cli.py -u Avalon_01 visual delete-expert --tag myexpert --team myteam

# 生成 YAML
uv run scripts/cli.py -u Avalon_01 visual generate-yaml --data '{"nodes":[...],"edges":[...]}' --team myteam
uv run scripts/cli.py -u Avalon_01 visual agent-generate-yaml --data '{"prompt":"..."}' --team myteam

# 布局管理
uv run scripts/cli.py -u Avalon_01 visual save-layout --data '{"name":"myflow","nodes":[...],"edges":[...]}' --team myteam
uv run scripts/cli.py -u Avalon_01 visual load-layouts --team myteam
uv run scripts/cli.py -u Avalon_01 visual load-layout --name myflow --team myteam
uv run scripts/cli.py -u Avalon_01 visual load-yaml-raw --name myflow --team myteam
uv run scripts/cli.py -u Avalon_01 visual delete-layout --name myflow --team myteam

# 上传 YAML
uv run scripts/cli.py -u Avalon_01 visual upload-yaml --data '{"name":"myflow","yaml_content":"..."}' --team myteam

# 编排会话状态
uv run scripts/cli.py -u Avalon_01 visual sessions-status
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `experts` |
| `--team` | Team 名称 | ❌ | — |
| `--tag` | 专家 tag | delete-expert 时 | — |
| `--name` | 布局名称 | load/delete 时 | — |
| `--data` | JSON 数据 | 视操作 | — |

---

## 16. internal-agents

**内部 Agent CRUD**

```bash
# 列出
uv run scripts/cli.py -u Avalon_01 internal-agents list --team myteam

# 添加
uv run scripts/cli.py -u Avalon_01 internal-agents add --team myteam --data '{"session":"s1","meta":{"name":"bot","tag":"assistant"}}'
uv run scripts/cli.py -u Avalon_01 internal-agents add --team myteam --session s1 --data '{"meta":{"name":"bot"}}'

# 更新（--sid 必填）
uv run scripts/cli.py -u Avalon_01 internal-agents update --sid s1 --team myteam --data '{"meta":{"name":"new_name"}}'

# 删除（--sid 必填）
uv run scripts/cli.py -u Avalon_01 internal-agents delete --sid s1 --team myteam
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `list` |
| `--team` | Team 名称 | ❌ | — |
| `--sid` | Session ID | update/delete ✅ | — |
| `--session` | Session ID（add 时自动补入 data） | ❌ | — |
| `--data` | JSON 数据 | add/update 时 | — |

---

## 17. teams

**Team 管理**

```bash
# 团队列表
uv run scripts/cli.py -u Avalon_01 teams

# 🆕 一次性查看 team 完整信息（聚合成员、专家、workflows、话题等）
uv run scripts/cli.py -u Avalon_01 teams info --team-name team2

# 创建 / 删除团队
uv run scripts/cli.py -u Avalon_01 teams create --team-name newteam --data '{"description":"..."}'
uv run scripts/cli.py -u Avalon_01 teams delete --team-name oldteam

# 成员管理
uv run scripts/cli.py -u Avalon_01 teams members --team-name myteam
uv run scripts/cli.py -u Avalon_01 teams add-ext-member --team-name myteam --data '{"user_id":"bob","role":"member"}'
uv run scripts/cli.py -u Avalon_01 teams update-ext-member --team-name myteam --data '{"user_id":"bob","role":"admin"}'
uv run scripts/cli.py -u Avalon_01 teams delete-ext-member --team-name myteam --data '{"user_id":"bob"}'

# 团队专家管理
uv run scripts/cli.py -u Avalon_01 teams experts --team-name myteam
uv run scripts/cli.py -u Avalon_01 teams add-expert --team-name myteam --data '{"tag":"myexpert","name":"...","prompt":"..."}'
uv run scripts/cli.py -u Avalon_01 teams update-expert --team-name myteam --tag myexpert --data '{"name":"..."}'
uv run scripts/cli.py -u Avalon_01 teams delete-expert --team-name myteam --tag myexpert

# 团队快照
uv run scripts/cli.py -u Avalon_01 teams snapshot-download --team-name myteam -o snapshot.zip
uv run scripts/cli.py -u Avalon_01 teams snapshot-upload --team-name myteam --file snapshot.zip
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 (`list`, `info`, `create`, `delete`, `members`, ...) | ❌ | `list` |
| `--team-name` | Team 名称 | 视操作 | — |
| `--tag` | 专家 tag | update/delete-expert 时 | — |
| `--data` | JSON 数据 | 视操作 | — |
| `-o`, `--output` | 输出文件路径 | ❌ | `team_{name}_snapshot.zip` |
| `--file` | 上传文件路径 | snapshot-upload 时 | — |

> 💡 **`info` 命令**：一次性聚合调用多个 API（成员、专家、workflows、话题、OpenClaw 快照），美化输出该 team 的完整信息快照，不直接对应单个接口。

---

## 18. topics

**OASIS 话题管理**

```bash
# 列出话题
uv run scripts/cli.py topics
uv run scripts/cli.py topics list

# 查看话题详情（美化输出：时间线 + 发言记录 + 结论）
uv run scripts/cli.py topics show --topic-id t123
uv run scripts/cli.py topics show --topic-id t123 --full    # 不截断长发言
uv run scripts/cli.py topics show --topic-id t123 --raw     # 输出原始 JSON

# 实时跟踪讨论过程（SSE 流式输出，Ctrl+C 退出）
uv run scripts/cli.py topics watch --topic-id t123

# 取消讨论
uv run scripts/cli.py topics cancel --topic-id t123

# 清除话题
uv run scripts/cli.py topics purge --topic-id t123

# 删除全部话题
uv run scripts/cli.py topics delete-all
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 (`list`, `show`, `watch`, `cancel`, `purge`, `delete-all`) | ❌ | `list` |
| `--topic-id` | 话题 ID | show/watch/cancel/purge 时 ✅ | — |
| `--raw` | 输出原始 JSON (show 时) | ❌ | `False` |
| `--full` | 不截断长发言内容 (show 时) | ❌ | `False` |

> 💡 **三种查看方式的区别：**
> - `show` — 一次性获取话题的完整快照（时间线 + 所有发言 + 结论），适合话题结束后回顾
> - `watch` — 实时流式输出讨论进展（连接后端 SSE），适合启动 workflow 后实时跟踪
> - `conclusion` (在 workflows 子命令中) — 阻塞等待直到讨论结束并返回结论


## 19. experts

**OASIS 专家管理**

```bash
# 列出专家
uv run scripts/cli.py -u Avalon_01 experts
uv run scripts/cli.py -u Avalon_01 experts list
uv run scripts/cli.py -u Avalon_01 experts list --team team2

# 添加自定义专家
uv run scripts/cli.py -u Avalon_01 experts add --tag my_analyst --expert-name "数据分析师" --persona "你是资深数据分析专家"
uv run scripts/cli.py -u Avalon_01 experts add --tag my_lawyer --expert-name "法律顾问" --persona "你是法律专家" --team team2

# 更新专家
uv run scripts/cli.py -u Avalon_01 experts update --tag my_analyst --persona "你是AI数据分析专家，擅长深度学习"

# 删除专家
uv run scripts/cli.py -u Avalon_01 experts delete --tag my_analyst
uv run scripts/cli.py -u Avalon_01 experts delete --tag my_lawyer --team team2
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `list` |
| `--tag` | 专家标签（唯一标识） | add/update/delete 时 ✅ | — |
| `--expert-name` | 专家显示名称 | add 时 ✅ | — |
| `--persona` | 专家人设描述 | ❌ | — |
| `--temperature` | 温度参数 (0-2) | ❌ | 0.7 |
| `--team` | Team 名称 | ❌ | — |

---

## 20. workflows

**OASIS Workflow 管理**

```bash
# 列出所有 workflow
uv run scripts/cli.py -u Avalon_01 workflows
uv run scripts/cli.py -u Avalon_01 workflows list

# 按 team 过滤
uv run scripts/cli.py -u Avalon_01 workflows list --team team2

# 查看 YAML 内容
uv run scripts/cli.py -u Avalon_01 workflows show --name creative_critical_workflow
uv run scripts/cli.py -u Avalon_01 workflows show --name test2flow --team team2

# 保存 workflow（从文件）
uv run scripts/cli.py -u Avalon_01 workflows save --name my_flow --yaml-file /path/to/flow.yaml --description "我的工作流"
uv run scripts/cli.py -u Avalon_01 workflows save --name my_flow --yaml-file /path/to/flow.yaml --team team2

# 保存 workflow（直接传 YAML）
uv run scripts/cli.py -u Avalon_01 workflows save --name quick_flow --yaml 'version: 2
plan:
  - id: s1
    expert: creative#temp#1
  - id: s2
    expert: critical#temp#1
edges:
  - [s1, s2]'

# 运行 workflow（使用已保存的文件名）
uv run scripts/cli.py -u Avalon_01 workflows run --name creative_critical_workflow --question "分析AI发展趋势"
uv run scripts/cli.py -u Avalon_01 workflows run --name test2flow --team team2 --question "讨论产品策略"

# 运行 workflow（从 YAML 文件）
uv run scripts/cli.py -u Avalon_01 workflows run --yaml-file /path/to/flow.yaml --question "分析数据"

# 运行选项
uv run scripts/cli.py -u Avalon_01 workflows run --name my_flow --question "问题" --max-rounds 10 --discussion true
uv run scripts/cli.py -u Avalon_01 workflows run --name my_flow --question "问题" --early-stop

# 获取结论（阻塞等待直到讨论结束）
uv run scripts/cli.py -u Avalon_01 workflows conclusion --topic-id abc12345
uv run scripts/cli.py -u Avalon_01 workflows conclusion --topic-id abc12345 --timeout 600
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `list` |
| `--team` | Team 名称 | ❌ | — |
| `--name` | Workflow 文件名（可省略 `.yaml` 后缀） | show/save 时 ✅, run 时可选 | — |
| `--yaml` | 直接传入 YAML 内容 | save/run 时可选（与 `--yaml-file` 二选一） | — |
| `--yaml-file` | YAML 文件路径 | save/run 时可选（与 `--yaml`/`--name` 二选一） | — |
| `--description` | Workflow 描述 | ❌ | — |
| `--question` | 讨论问题/任务 | run 时 ✅ | — |
| `--max-rounds` | 最大讨论轮数 (1-20) | ❌ | 5 |
| `--discussion` | 讨论模式 (true=讨论, false=执行) | ❌ | YAML 中设定 |
| `--early-stop` | 提前终止 | ❌ | false |
| `--topic-id` | 话题 ID | conclusion 时 ✅ | — |
| `--timeout` | 等待超时秒数 | ❌ | 300 |

> `show` 直接读取本地 YAML 文件（`data/user_files/{user}/[teams/{team}/]oasis/yaml/{name}.yaml`），不走 HTTP。
>
> `run` 返回 `topic_id`，用 `conclusion` 或 `topics show` 查看结果。

---

## 21. tunnel

**Cloudflare Tunnel 管理**

本地进程操作，通过 `scripts/tunnel.py` 和 pid 文件管理。

```bash
# 查看状态
uv run scripts/cli.py tunnel
uv run scripts/cli.py tunnel status

# 启动 / 停止
uv run scripts/cli.py tunnel start
uv run scripts/cli.py tunnel stop
```

| 参数 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| `action` | 操作 | ❌ | `status` |

无 HTTP 请求。

---

## 22. status

**检查各服务状态**

同时探测三个核心服务的健康状态。

```bash
uv run scripts/cli.py status
```

无额外参数。

---

## 常用组合示例

```bash
# 检查服务是否正常
uv run scripts/cli.py status

# 以 Avalon_01 身份管理 team2
uv run scripts/cli.py -u Avalon_01 teams members --team-name team2
uv run scripts/cli.py -u Avalon_01 internal-agents list --team team2
uv run scripts/cli.py -u Avalon_01 workflows list --team team2
uv run scripts/cli.py -u Avalon_01 workflows show --name test2flow --team team2

# 聊天
uv run scripts/cli.py -u Avalon_01 chat "帮我分析这段数据" -s analysis_session

# 查看聊天历史（最近 10 条，完整输出）
uv run scripts/cli.py -u Avalon_01 history -s analysis_session -n 10 --full

# 可视化编排：查看布局 → 查看 YAML → 查看会话状态
uv run scripts/cli.py -u Avalon_01 visual load-layouts --team myteam
uv run scripts/cli.py -u Avalon_01 visual load-yaml-raw --name myflow --team myteam
uv run scripts/cli.py -u Avalon_01 visual sessions-status

# OpenClaw 快照：导出全部 → 恢复全部
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot export-all --team myteam
uv run scripts/cli.py -u Avalon_01 openclaw-snapshot restore-all --team myteam

```
