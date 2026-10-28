# 从公开 Release 到安装验收

验收分为两个层次，避免把“离线脚本通过”当作真实账户和 Hooks 已启用。

## A. 离线、隔离安装验收

要求 Python 3.11+。不需要 Codex 登录，不联网，不调用远程模型，不修改真实 CODEX_HOME。

1. 从 [Releases](https://github.com/TheaXin/codex-continuity-keeper/releases) 下载同一版本 ZIP、SHA256SUMS.txt、release-manifest.json。
2. 解压前核对 ZIP 的 SHA-256：

```bash
# macOS：比较输出与 SHA256SUMS.txt 的 ZIP 行
shasum -a 256 codex-continuity-keeper-2.3.0.zip
# Linux：同时检查 ZIP 和 manifest
sha256sum -c SHA256SUMS.txt
```

Windows PowerShell：

```powershell
Get-FileHash .\codex-continuity-keeper-2.3.0.zip -Algorithm SHA256
```

校验文件应来自同一 Release。校验提供完整性检查，不等于独立签名认证。

3. 解压，在版本目录打开终端，审阅源码，再逐文件验证：

```bash
python3 scripts/verify_release.py ../codex-continuity-keeper-2.3.0.zip --manifest ../release-manifest.json
```

Windows 用 `py -3 -X utf8` 替换 `python3`；按实际下载位置调整路径。

4. 执行隔离验收：

```bash
python3 scripts/acceptance.py --report acceptance.json
```

Windows：

```powershell
py -3 -X utf8 scripts/acceptance.py --report acceptance.json
```

报告文件必须是新路径；重复运行换文件名。预期顶层 `status` 和所有 `steps[].status` 均为 `PASS`。

### 检查内容

- 向临时 Codex home 安装完整包，验证安装源码哈希、额度守卫和原配置保护。
- 使用**安装后的 CLI**创建项目与初始检查点。
- 写入成果并检查对象存储中的字节，相同内容不新增快照。
- 新 OS 进程读取进度，只读查询不改变文件内容。
- 仅在测试目录模拟文件丢失，导出到新目录，不自动覆盖现场。
- 选择性恢复后用新进程继续任务，验证结果，再保存进度和最终检查点。
- 隔离模拟95%已用，检查5%剩余警报；缺失数据仍标为 unknown。

报告不含账户信息或临时用户名路径。语义进度由测试夹具依据实际结果填写，不是远程模型自由生成。

## B. 真实用户环境验收

离线验收通过后再安装到真实用户目录：

```bash
python3 scripts/install.py
python3 scripts/doctor.py
```

Windows 改为 `py -3 -X utf8`。接着在**实际执行主机**检查：

| 项目 | 通过标准 | 未通过时 |
| --- | --- | --- |
| Skill和守卫 | doctor对应installed字段为true | 检查CODEX_HOME及解释器 |
| Hooks配置 | 五类事件已配置 | 检查安装输出和已有冲突 |
| Hooks权限 | Codex `/hooks` 中已审阅、信任并启用 | 先在官方界面审阅，不伪造信任 |
| 项目初始化 | 进度、任务清单和初始快照存在 | 明确调用Skill初始化原任务 |
| 文件变化 | 测试文件真实内容进入检查点 | 检查过滤、空间、支持工具与Hook错误 |
| 真实额度 | `quota --refresh`返回known和有效窗口 | 明确unknown，使用可用原生工具回退 |
| 自然语言恢复 | 新会话在原目录说继续，先核对汇报再执行 | 检查Skill加载及目录 |

doctor 的信任说明 `NOT VERIFIED` 是有意的，配置存在不能证明执行。API Key、第三方模型、云端编排、企业策略或离线环境可能不满足自动化前提，文件保护与额度能力要分别验收。

## 跨平台证据

CI 对 Linux/macOS/Windows × Python 3.11/3.12/3.13 运行单元测试和相同隔离验收。正式 Release 只有九组报告全部 PASS 才发布，并附 `acceptance-evidence.zip`。

这证明对应平台的安装与恢复逻辑，不证明所有账户都可读取额度，也不保证真实断电或额度耗尽后仍能生成最后一次回复。
