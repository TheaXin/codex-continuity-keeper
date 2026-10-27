# Codex Continuity Keeper

**让 Codex 长任务有断点、有进度，重开会话后可以继续；检测到低额度时优先交付已有成果。**

当前版本：**2.2.1**。包含完整 Skill、文件快照脚本、额度守卫、安装器、部署自检、升级与卸载工具、测试，以及参考项目和提示词。

- **继续**：先核对磁盘文件和 Git 差异，汇报进度，再继续原任务。
- **只看进度**：仅查询，不修改文件、不继续实现。
- **额度剩余 ≤5%**：保存文件快照与应急索引，提醒模型更新进度并尽快交付。

> 它减少中断造成的成果丢失，但不会增加或绕过额度。程序可以保存文件、检测额度和发送提示；语义进度与最终回复仍由模型执行，不能保证任意模型必定服从。

## 目录

1. [它怎么工作](#它怎么工作)
2. [适用环境与前提](#适用环境与前提)
3. [安装：从下载到可用](#安装从下载到可用)
4. [验证安装是否真的生效](#验证安装是否真的生效)
5. [日常使用](#日常使用)
6. [5% 额度守卫的具体行为](#5-额度守卫的具体行为)
7. [保存位置与文件恢复](#保存位置与文件恢复)
8. [升级与卸载](#升级与卸载)
9. [常见问题](#常见问题)
10. [测试、源码与参考资料](#测试源码与参考资料)

## 它怎么工作

本项目分为两层，避免把“有备份”误认为“任务已完成”。

| 层 | 谁负责 | 保存内容 |
| --- | --- | --- |
| 文件保护 | Python 脚本 | 实际落盘文件的内容去重快照、文件清单、额度状态、应急恢复索引 |
| 任务交接 | Codex 模型 | 原始目标、已验证成果、未完成/未验证内容、验收证据、下一步 |

典型工作流程：

```text
初始化项目并建立初始检查点
        ↓
完成一个可验证的小单元 → 写入真实文件 → 更新进度 → 保存检查点
        ↓
中断 / 上下文压缩 / 重开会话
        ↓
在原项目说“继续” → 核对真实状态 → 先汇报 → 再执行
```

不依赖 SessionEnd 或额度耗尽前的最后一次执行机会。已经写盘的成果及平时的检查点，才是主要保护。

## 适用环境与前提

| 项目 | 要求与说明 |
| --- | --- |
| Python | **3.11+**，安装及运行脚本不需要额外 pip 依赖 |
| Codex | 已安装官方 Codex CLI，实际版本需支持相关 Hooks，并能找到 `codex` 命令 |
| 平台 | macOS/Linux；另已加入 Windows 文件锁、UTF-8 和 Hook 命令适配，实际兼容性以对应 CI 结果及本机验证为准 |
| Git | 用于查看差异；项目不是 Git 仓库时仍可建立文件检查点，只是没有 Git 差异证据 |
| 额度查询 | 需要登录账户及当前服务支持官方额度读取；API Key、第三方模型或离线环境可能没有这类额度数据 |
| 网络 | 文件快照是本地操作；官方额度读取需要网络 |
| 云端/远程 | 必须在**真正执行任务的主机**安装。本地命令 Hooks 不代表云端编排会执行它们 |

开发时本机验证的 Codex CLI 为 `0.164.0-alpha.11.1`。不承诺所有历史/未来版本、账户及企业策略均支持相同事件和接口。

## 安装：从下载到可用

### 第一步：下载源码并查看脚本

macOS / Linux：

```bash
git clone https://github.com/TheaXin/codex-continuity-keeper.git
cd codex-continuity-keeper
python3 --version
codex --version
```

Windows PowerShell：

```powershell
git clone https://github.com/TheaXin/codex-continuity-keeper.git
cd codex-continuity-keeper
py -3 --version
codex --version
```

没有 Git 时，也可以使用 GitHub 的 **Code → Download ZIP**，解压后在项目目录打开终端。

安装前先阅读 `SKILL.md` 与 `scripts/install.py`、`scripts/keeper.py`、`scripts/quota.py`。本项目没有要求执行远程 `curl | sh` 安装命令。

### 第二步：安装 Skill 和额度守卫

macOS / Linux：

```bash
python3 scripts/install.py
```

Windows PowerShell：

```powershell
py -3 -X utf8 scripts/install.py
```

**额度守卫会一起安装，不需要第二次安装，也不需要单独的 OpenAI API Key。** 它尝试使用 Codex 现有账户支持的只读额度接口；接口不可用时明确降级为“未知”。

默认安装位置：

```text
~/.codex/skills/codex-continuity-keeper/
~/.codex/hooks.json
~/.codex/AGENTS.md
```

如果设置了 `CODEX_HOME`，使用该目录代替 `~/.codex`。在 Windows，`~` 表示当前用户主目录。

安装器会：

- 安装完整 Skill 和脚本，包括额度守卫。
- 合并本项目的五类 Hook，追加带标记的长期规则。
- 备份已有 Hooks 和 AGENTS 文件，保留不相关内容。
- 保持 `config.toml` 不变，不伪造 Hooks 信任记录。
- 遇到已有不同版本、用户修改、非法配置或内联 Hook 冲突时安全拒绝，而不是覆盖。

### 第三步：在 Codex 中审阅并信任 Hooks

打开一个新的本地 Codex 会话，输入：

```text
/hooks
```

审阅本项目的命令，并按 Codex 界面信任对应定义。仅安装文件不代表 Hooks 已运行。

应检查的事件：

| 事件 | 本项目用途 |
| --- | --- |
| SessionStart | 首次任务轮次前保存文件状态、读取额度、注入恢复提示 |
| UserPromptSubmit | 收到任务时检查状态与额度；识别“只看进度” |
| PostToolUse | Bash / apply_patch 等受支持工具操作完成后，保存去重快照并检查额度 |
| PreCompact | 上下文压缩前保存文件状态 |
| Stop | 任务轮次结束时保存文件状态，不强制开启下一轮 |

`SessionStart` 不一定在刚打开空会话时就执行，可能延后到首个任务轮次。Hooks 的定义或 Python 路径变化后，通常需要重新审阅。

### 第四步：在你的实际项目中初始化

进入你要工作的项目目录，在该目录的 Codex 会话中说：

```text
使用 $codex-continuity-keeper 初始化这个长任务：
[写出你的真实任务和验收要求]
先建立初始检查点，再按可验证的小单元开始执行。
```

它会读取现有项目内容，创建或安全采用：

```text
你的项目/
├── PROGRESS.md
├── CONTINUITY_TASKS.md
└── .continuity-keeper/
```

已有同名进度文件不会被安装器覆盖；模型需要阅读后合并。**Hooks 不会在每个路过的目录自动初始化项目。** 新项目需要一次明确初始化。

## 验证安装是否真的生效

### 1. 运行部署自检

在下载的仓库目录中执行：

```bash
python3 scripts/doctor.py
```

Windows：

```powershell
py -3 -X utf8 scripts/doctor.py
```

自检应显示 `skill_installed`、`quota_guard_installed`、`hooks_configured` 为 `true`。但它会把信任状态标为 **NOT VERIFIED**：这是有意的，必须在真实 Codex `/hooks` 中确认，不能仅凭配置文件存在判定已启用。

### 2. 做一次实际文件检查点测试

在已初始化项目的 Codex 会话中说：

```text
创建一个只用于验证的 continuity-demo.txt，写入 hello。
确认文件进入检查点，并汇报检查点 ID。不要修改其他业务文件。
```

也可以从下载的仓库目录手工执行：

```bash
python3 scripts/keeper.py --root /path/to/your-project list
python3 scripts/keeper.py --root /path/to/your-project status
```

Windows 示例：

```powershell
py -3 -X utf8 scripts/keeper.py --root "C:\Projects\your-project" list
py -3 -X utf8 scripts/keeper.py --root "C:\Projects\your-project" status
```

把示例路径替换为真实项目目录，不要直接复制占位路径。

### 3. 验证额度接口

```bash
python3 scripts/keeper.py --root /path/to/your-project quota --refresh
```

Windows 使用 `py -3 -X utf8` 替换 `python3`。

- `status: known`：获得有效额度窗口；查看 `windows` 内的 `remainingPercent`。
- `status: unknown`：接口、登录、网络、权限或账户能力未满足，**不能声称5%保护已正常工作**。
- `status: disabled`：该目录尚未初始化。

`quota` 命令会写额度状态，不属于“只看进度”的只读操作。它不重置额度，也不调用远程模型生成内容。

## 日常使用

### 正常推进

直接提出原始任务即可。Skill 会要求 Codex 按小单元写文件、验证、更新进度并保存检查点。进度记录服务于实际工作，不应变成繁重的额外流程。

### 关闭后再继续

在**同一个真实项目目录**打开 Codex，输入：

```text
继续
```

先汇报以下五项，再继续已授权的未完成任务：

```text
已完成
正在进行
未完成
阻碍
下一步
```

新开一个完全不同目录的聊天，不会自动拥有原项目文件。换电脑或换远程主机，也不会凭空同步本地检查点。

### 只查询，不执行

```text
只看进度
```

只读检查进度、任务清单、相关文件和 Git 差异；不初始化、不更新记录、不运行有副作用的验证、不继续实现。

### 主动交接

```text
保存当前断点，告诉我已有成果、未完成/未验证内容和下一步。
```

## 5% 额度守卫的具体行为

额度守卫遍历服务返回的所有有效额度桶和 `primary` / `secondary` 窗口：

```text
剩余百分比 = 100 - usedPercent
任一有效窗口剩余百分比 <= 5 → 发出低额度收尾指令
```

例如，`usedPercent = 95` 才表示剩余5%；`usedPercent = 5` 表示还剩95%。空值和接口失败都不是“额度充足”。

自动检查发生在会话开始、提交任务和受支持的工具操作后，默认缓存 **30秒**。Skill 另要求模型在昂贵操作前检查。

触发后的分工：

| 程序自动做 | 模型收到指令后做 |
| --- | --- |
| 保存真实文件快照 | 不再启动新实现单元、长测试或额外调研 |
| 保存标准化额度状态 | 简短更新已验证进度与未完成/未验证项 |
| 创建 `QUOTA_HANDOFF.md` 应急索引 | 保存最终检查点 |
| 注入 `LOW_QUOTA_HANDOFF` 提示 | 立即交付成果路径、剩余任务与恢复方法 |

不会自动使用重置券、购买额度、绕过限制或无限重试。若读取失败，提示模型使用可用的原生额度工具回退；没有可用接口就明确未知。

**不能保证的情况：**一次很长的模型生成或工具操作可能跨过5%并直接耗尽额度；此时不保证还有机会输出最终回复。任意模型也可能未完全遵循收尾提示。因此，平时的小单元落盘和检查点仍不可省略。

## 保存位置与文件恢复

所有项目状态保存在各自项目中，不集中混入其他项目：

```text
你的项目/
├── PROGRESS.md                       # 模型维护的语义进度
├── CONTINUITY_TASKS.md               # 任务与验收状态
└── .continuity-keeper/
    ├── project.json                 # 项目元数据
    ├── latest.json                  # 最新快照清单
    ├── snapshots/                   # 历史清单
    ├── objects/                     # 内容哈希去重对象
    ├── policy.json                  # 可选排除规则
    ├── quota.json                   # 额度窗口状态
    └── QUOTA_HANDOFF.md              # 低额度时生成的应急索引
```

`QUOTA_HANDOFF.md` 是机械索引，不是任务完成证明。正常恢复优先使用当前真实文件，而不是自动覆盖为旧快照。

文件损坏或丢失时，先列出快照，再导出到**项目外的全新目录**：

```bash
python3 scripts/keeper.py --root /path/to/project list
python3 scripts/keeper.py --root /path/to/project export CHECKPOINT_ID /new/recovery-directory
```

对比后选择性合并。脚本不会自动删除现场文件，也不会执行 Git reset / clean。

### 默认备份范围

- 仅快照符合过滤规则的文本常规文件；排除符号链接、二进制、凭据、依赖和常见缓存。
- 单文件上限 **2 MiB**；每次扫描上限 **64 MiB / 10,000个候选文件**。
- 保留初始检查点与最近50个变化快照；**128 MiB是软预算**，初始与最新快照受到保护。
- 内容不变不新增快照；旧快照淘汰后回收无引用对象。
- 启发式过滤不能识别所有私人信息；超限、被排除或不稳定文件不受保护。
- 快照不加密，不应提交到公开仓库。不要用全量暂存命令顺带上传本地状态。

额外排除项目私人目录，可在 `.continuity-keeper/policy.json` 写入：

```json
{"exclude": ["private/**", "customers/**"]}
```

## 升级与卸载

### 升级：先审阅旧安装，再生成基线

在新版本仓库目录中执行：

```bash
python3 scripts/manifest.py > previous-installation.json
python3 scripts/install.py --upgrade-from previous-installation.json
```

Windows：

```powershell
py -3 -X utf8 scripts/manifest.py | Out-File -Encoding utf8 previous-installation.json
py -3 -X utf8 scripts/install.py --upgrade-from previous-installation.json
```

基线记录旧安装的相对路径与 SHA-256；它不是来源信任证明。先审阅旧安装，安装器才会在哈希匹配时备份并升级。换解释器可能改变 Hook 命令，需要重新审阅 `/hooks`。

### 卸载：默认预览，确认后执行

```bash
python3 scripts/uninstall.py
python3 scripts/uninstall.py --apply
```

卸载移除精确匹配的本项目 Hooks 和未被编辑的规则，把旧 Skill **归档到备份**。不会删除各项目的检查点，也不会修改不相关 Hooks 或信任记录。

## 常见问题

| 问题 | 检查与处理 |
| --- | --- |
| 安装成功却没反应 | 在新会话运行 `/hooks` 审阅/信任；在实际项目明确调用 Skill 初始化 |
| 找不到 codex / Python | 安装官方工具；检查 PATH。安装 Hooks 使用的 Python 必须在后续仍可用 |
| 额度一直 unknown | 检查登录、网络、账户接口与运行权限；API Key/第三方模型不一定暴露订阅额度。不要伪造 known |
| API额度不可用，还能使用吗 | 文件快照与进度交接可以使用；低额度阈值功能必须明确标为不可用/未知 |
| 企业策略禁止 Hooks | 遵循策略，使用手工 checkpoint；不能宣称自动 Hooks 已启用 |
| 使用云端、WSL或容器 | 在真正执行工具的环境部署。主机路径、Python和登录不会自动迁移；本地命令 Hooks 不代表云端支持 |
| 已有内联 Hooks / 用户修改版本 | 安装器拒绝覆盖；先审阅并合并配置或准备已审阅的升级基线 |
| 出现磁盘满或快照失败 | 保留磁盘现有成果，报告失败，检查空间和过滤清单；之前的有效检查点仍可读 |
| 进度和实际文件不一致 | 以实际文件和验证结果为准，先重新核验再更新记录，不能仅信任旧摘要 |
| Windows有中文路径或乱码 | 使用 Python 3.11+ 与 `-X utf8`；检查 Hooks 的 Windows 命令。CI结果与实机测试仍是必要证据 |

## 测试、源码与参考资料

### 自动测试

在仓库根目录运行：

```bash
python3 scripts/test_keeper.py
python3 scripts/test_quota.py
python3 scripts/test_deployment.py
```

发布版 **21项测试在开发者的 macOS 环境通过**。仓库配置了 Linux / macOS / Windows × Python 3.11 / 3.12 / 3.13 的 GitHub Actions。其他平台的实际结果应查看 Actions，不能把本机成功当作远程矩阵已通过。

### 可选真实宿主测试

在 macOS/Linux 安装并信任当前版本 Hooks 后：

```bash
python3 scripts/integration_quota.py
```

使用临时项目、真实 Codex app-server 和本地确定性模型夹具，验证实际文件写入、模拟低额度、收尾提示和最终检查点。需要正常 Codex 运行权限及本地回环监听；诊断输出保存在 `work/`。不请求远程模型、不改变真实账户额度。该夹具面向 POSIX shell，不代表 Windows 宿主测试已通过。

### 源码结构

```text
SKILL.md                        # 模型工作流程、恢复与低额度收尾规则
agents/openai.yaml              # Skill 展示与触发元数据
scripts/install.py              # 安装、配置合并、校验升级
scripts/keeper.py               # 初始化、快照、状态、导出、Hooks入口
scripts/quota.py                # 官方额度读取、缓存、阈值与提示
scripts/doctor.py               # 只读部署自检
scripts/manifest.py             # 升级前生成旧安装哈希清单
scripts/uninstall.py            # 预览与安全归档卸载
scripts/test_*.py               # 单元与部署测试
scripts/integration_quota.py    # 可选真实宿主集成夹具
references/operations.md        # 运维、过滤、保留与环境边界
DESIGN_AND_PROMPTS.zh-CN.md      # 参考项目与完整提示词合集
```

### 设计参考与许可证

完整来源与提示词见 **[参考项目与提示词合集](DESIGN_AND_PROMPTS.zh-CN.md)**。

参考：[agent-rollback](https://github.com/Nainish-Rai/agent-rollback)、[resume-project-context](https://github.com/howtimeschange/codex-skills/tree/main/skills/resume-project-context)、[codex-session-handoff](https://github.com/lifang336/codex-session-handoff)、[agent-handoff](https://github.com/tjs0/agent-handoff)、[ralph](https://github.com/wiggumdev/ralph)。这些是设计参考，不是运行依赖；未运行其安装脚本，也不宣称完整审计了全部上游源码。

官方接口依据：[Hooks](https://learn.chatgpt.com/docs/hooks)、[App Server](https://learn.chatgpt.com/docs/app-server)。

本项目采用 **[MIT License](LICENSE)**。

### Windows 符号链接修复

早期发布的 Windows CI 发现 `O_NOFOLLOW` 不可用时可能跟随文件符号链接。现已增加跨平台 `lstat`、Windows reparse-point 检查与文件身份复核，并使用二进制读取保留 CRLF。Windows reparse-point 文件按保守策略排除；没有降低或跳过原过滤测试要求。跨平台通过情况以最新 Actions 为准。
