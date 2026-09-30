# boom

[English](README.md) | [简体中文](README.zh-CN.md)

统一的 [Claude Code](https://claude.ai/code) 和 [Codex](https://github.com/openai/codex) 启动器。通过命名配置管理多个 API 账号、服务商或订阅方案，启动时指定名称即可切换。

## 功能

- **多配置管理**：按名称切换 API key、服务地址和模型。
- **公共设置**：Claude 配置共用 `common.json`，各配置可以覆盖公共设置。
- **额度查询**：`boom status` 查询 Claude（官方订阅及 MiniMax）和 Codex 的实时用量，显示各额度窗口。
- **Token 统计**：`boom usage` 扫描 Claude、Codex 和 Gemini 的本地会话文件，统计 token 用量。
- **原生权限默认值**：保留 CLI 自身的权限设置；只有显式指定 `--unsafe` 才会添加危险的权限绕过参数。兼容 `--safe`。
- **本地插件开发**：每个源码仓库注册一次，修改后的 skill 会在下次启动时同步到所选 CLI 环境。

## 环境要求

- **bash** 3.2+
- **node** 18+，用于合并 JSON 设置和通过内置 fetch 查询额度。
- **jq**，仅 `boom claude show` 需要。
- 单独安装 Claude Code CLI 和／或 Codex CLI。
- 注册本地插件同步适配器时，需要 Python 3.11+。

## 安装

```bash
git clone https://github.com/doublnt/boom.git
cd boom
bash install.sh
```

默认安装到 `~/.local/bin/boom`。可通过环境变量指定安装目录：

```bash
BOOM_INSTALL_DIR=/usr/local/bin bash install.sh
```

也可以直接把 `boom` 文件复制到 `PATH` 中的目录，并执行 `chmod +x` 赋予执行权限。

## 快速开始

```bash
# 添加 Claude 配置，服务商需支持 Claude Code 使用的 Anthropic 协议
boom claude add myplan

# 设为默认配置
boom claude default myplan

# 使用默认配置启动 Claude
boom claude

# 使用指定配置启动 Claude
boom claude myplan

# 查询各账号的额度
boom status

# 查看 token 用量统计
boom usage
```

## 配置

boom 的数据默认保存在 `~/.boom/`，可通过 `$BOOM_HOME` 修改根目录：

```text
~/.boom/
  claude/
    common.json          # 合并到所有 Claude 配置中的公共设置
    default              # 默认配置名称
    profiles/
      myplan.json        # 各配置的设置，如环境变量、模型等
  codex/
    default
    profiles/
      myaccount/         # 各配置独立的 Codex 主目录
        config.toml
        auth.json
    shared/
      sessions/          # 所有 Codex 配置共享的会话
      history.jsonl
```

### Claude 配置

`claude/profiles/` 下的每个文件都是 Claude Code 的设置 JSON。`env` 字段用于设置启动 Claude 时的环境变量：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://your-provider/v1",
    "ANTHROPIC_AUTH_TOKEN": "sk-...",
    "ANTHROPIC_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-sonnet-4-5",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-sonnet-4-5",
    "CLAUDE_CODE_SUBAGENT_MODEL": "claude-sonnet-4-5",
    "API_TIMEOUT_MS": "600000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
```

先对 `common.json` 进行深度合并，再由具体配置中的字段覆盖公共设置。

官方配置不含自定义服务商、API 凭据或 `apiKeyHelper`。boom 使用权限为 `0600` 的临时 `--settings` 文件，保留原生登录以及用户、项目设置，包括用户插件和 skill；不会覆盖 `~/.claude/settings.json`。公共设置中的服务商凭据和模型别名会被移除，继承的用户服务商设置会在临时文件中被屏蔽，支持 `CLAUDE_CONFIG_DIR`。配置中显式指定的模型仍会保留，受管理策略仍然生效。执行结束、出错或收到可处理的取消信号时会清理临时文件；`SIGKILL` 无法触发清理。

第三方配置同样使用临时 `--settings` 文件，应用其中显式指定的服务商设置。仅指定模型名称不会让配置变成第三方账号。这两种启动方式都不提供操作系统沙箱；`--safe` 表示 boom 不注入权限绕过参数，并不保证所有设置或插件都被隔离。

使用 `--no-profile` 可以继承原生 CLI 的登录和设置，不应用 boom 的公共或命名配置。这个参数不会切换账号或执行登录，原生 CLI 仍可能读取自己的配置。

### Codex 配置

`codex/profiles/` 下的每个目录都是独立的 `CODEX_HOME`。会话和历史记录通过符号链接指向共享目录，因此可以跨配置使用 `/resume`。

插件缓存也按配置独立保存，更新原生 Codex 的插件不会同步更新 boom 配置中的插件。请在实际启动的环境中检查：

```bash
boom c -- plugin list --json
boom x -- plugin list --json
```

手动刷新插件市场中的插件，可执行 `boom x -- plugin add NAME@MARKETPLACE`；指定配置时使用 `boom x PROFILE -- plugin add NAME@MARKETPLACE`。已注册的本地仓库会通过下方的开发模式在启动前同步。刷新后需要启动新的 CLI 会话。Claude skills 目录中的源码链接直接读取源文件，无需重新安装。

### 本地插件开发

先注册你信任的源码仓库，只需执行一次：

```bash
boom plugins add ~/plugins/any-agent-skills
boom plugins list
```

之后修改 skill 源码，正常启动 `boom c` 或 `boom x` 即可。boom 会在 CLI 启动前调用仓库中的 `scripts/sync-local-plugins.py --target claude|codex --ensure` 适配器。注册意味着允许后续启动时执行这个适配器；没有适配器的仓库会被拒绝。适配器需返回 JSON，包含 `schema_version: 1`、`status: "ready"`、`updated: boolean` 和 `version: string`。

Any Agent Skills 适配器会比较源码内容和实际安装的缓存。内容未变时，不执行原生安装命令；内容变化后，生成不可变快照，只更新本次启动的环境：Claude 使用 `CLAUDE_CONFIG_DIR`，Codex 使用所选配置的 `CODEX_HOME`，`--no-profile` 使用原生环境。账号、服务商设置和权限保持独立。并发同步会串行执行写入，旧快照和已有会话都会保留。

原生安装器可能删除旧版本缓存。适配器会保留其内容，在更新结束后恢复旧资源路径，更新失败时也会恢复。如果进程被强制中断，持久化日志会在下次启动时恢复未完成的操作。保留的缓存位于 `~/.local/share/any-agent-skills/retained-cache/`，按内容去重；这些缓存和快照会持续占用磁盘空间，直到显式删除。

更新提示写入 stderr，不影响 stdin 和原生 CLI 的 JSON stdout。同步失败会阻止启动；适配器有两分钟的执行时限，取消时会终止它拥有的进程组。版本／帮助、认证／登录、插件管理、MCP／app-server 命令，以及 Codex 带有 `--ignore-user-config` 的调用都会跳过同步。直接运行原生 CLI 不会经过这个同步入口。

```bash
boom x --no-plugin-sync -- exec "..."    # 本次启动跳过同步
boom plugins remove any-agent-skills     # 停止自动同步，保留已安装的副本
```

## 命令

```text
boom claude [name] [--safe|--unsafe] [--no-profile] [-- <claude args>]
boom c      [name] [...]

boom codex  [name] [--safe|--unsafe] [--no-profile] [-- <codex args>]
boom x      [name] [...]

boom plugins add <local-repository>
boom plugins list
boom plugins remove <plugin-name>
```

### Claude 管理命令

| 命令 | 说明 |
|---|---|
| `boom claude add <name>` | 交互式创建配置 |
| `boom claude edit [name]` | 编辑已有配置 |
| `boom claude show [name]` | 输出合并后的设置 JSON |
| `boom claude list` | 列出所有配置 |
| `boom claude default <name>` | 设置默认配置 |
| `boom claude remove <name>` | 删除配置 |
| `boom claude doctor` | 检查安装状态 |

### Codex 管理命令

| 命令 | 说明 |
|---|---|
| `boom codex add <name>` | 创建配置并执行 `codex login` |
| `boom codex edit [name]` | 重命名或重新登录 |
| `boom codex list` | 列出所有配置 |
| `boom codex default <name>` | 设置默认配置 |
| `boom codex remove <name>` | 删除配置 |
| `boom codex doctor` | 检查安装状态 |

### 其他命令

| 命令 | 说明 |
|---|---|
| `boom status` | 通过 Claude／Codex API 查询实时额度 |
| `boom status --claude --official` | 仅查询原生 Claude 订阅额度 |
| `boom status --codex --official` | 仅查询原生 Codex ChatGPT 登录账号的额度；设置了 `CODEX_HOME` 时使用该目录 |
| `boom usage` | 汇总本地会话文件中的 token 用量 |
| `boom clean --dry-run` | 预览选中的日志和 `.DS_Store` 清理项 |

额度窗口采用接口返回的时长，显示**剩余百分比**。缺失或格式错误的值显示为未知，不会被当作剩余 100%。Claude 返回的 `seven_day_*` 窗口按服务商提供的名称展示，不猜测模型对应关系。查询失败时返回非零退出码，但仍会展示其他服务商的结果。`status` 尽力通过订阅接口查询，不刷新认证、不购买或重置额度，也不调用模型。指定 `CLAUDE_CONFIG_DIR` 时，使用该目录中的凭据文件，不回退到默认钥匙串账号。

`usage` 是本地 token 用量估算，不代表剩余额度或实际费用。共享的 Codex 会话路径会先去重，再统计 token 和文件数量，保留 k／M／B 简写显示。

`clean` 默认排除备份和同步暂存文件。需要清理这些内容时，先停止相关 CLI 并确认备份是否还需要，再显式指定 `--include-backups`／`--include-staging`。`--yes` 只跳过确认提示，仍需自行完成这些检查。启动和查询额度时不会自动清理。

## CLI 兼容性检查（2026-09-29）

已检查 Claude Code **2.1.284** 和 Codex CLI **0.158.0**。这是当时检查的版本，并非强制升级要求。只读帮助／认证检查和模拟进程测试不能证明真实模型可用或沙箱完全隔离。

| 旧用法或易混淆用法 | 当前用法 |
|---|---|
| 认为直接运行 `boom c`／`boom x` 会绕过权限 | 默认采用原生权限；确实需要绕过时显式指定 `--unsafe` |
| `boom c profile list` | 已移除，使用 `boom c list`，Codex 使用 `boom x list` |
| `boom c -p "prompt"` | `--` 前的 `-p` 用于选择 boom 配置；打印模式使用 `boom c --no-profile -- -p "prompt"` |
| Claude `--permission-mode default` | 当时的本地帮助列出 `manual`；无人值守时拒绝权限提示可用 `dontAsk --permission-prompts none` |
| Codex `exec --full-auto` | 当时的解析器拒绝该参数；原生自动审批可用 `--approve-for-me`，但语义不同，脚本应明确设置沙箱和审批配置 |
| `codex sandbox macos -- …` | 当时的语法为 `codex sandbox -- COMMAND…` |
| Codex `preferred_auth_method` 配置 | 当前参考文档未列出该字段，boom 不再生成它；不会自动迁移已有账号配置 |
| 用 Claude `--bare` 精简订阅调用 | 当时的帮助说明 bare 不读取 OAuth／钥匙串；应使用合适的受限设置，避免改变计费途径 |

当时的本地帮助仍提供 Claude 的 `--restricted`、`--tools`、`--strict-mcp-config`、`--resume SESSION_ID`，以及 Codex 的 `exec --json`、`--ignore-user-config`、`exec resume SESSION_ID` 和 `app-server`。`--ignore-rules` 仍存在，但它跳过的是 execpolicy 规则，与 AGENTS.md 加载无关，boom 不要求使用它。

原生 CLI 参数应放在 `--` 后，避免其参数值被误认为配置名称。只读检查示例：

```bash
boom c --safe --no-profile -- --version
boom x --safe --no-profile -- --version
boom c --safe --no-profile -- auth status
boom x --safe --no-profile -- login status
python3 -m unittest discover -s tests -v
```

测试使用临时 HOME、模拟 CLI 和 HTTP 测试数据，不调用模型或修改真实账号设置。验证和回退说明见 [CHANGE_REPORT.md](CHANGE_REPORT.md)。参考文档：[Claude CLI](https://code.claude.com/docs/en/cli-reference)、[Claude 设置](https://code.claude.com/docs/en/settings)、[Codex 配置](https://learn.chatgpt.com/docs/config-file/config-reference)。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `BOOM_HOME` | `~/.boom` | boom 数据根目录 |
| `BOOM_REAL_CLAUDE` | 自动检测 | 原生 `claude` 可执行文件路径 |
| `BOOM_REAL_CODEX` | `/opt/homebrew/bin/codex` | 原生 `codex` 可执行文件路径 |

## 许可证

MIT
