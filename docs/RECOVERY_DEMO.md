# 可重复的中断恢复演示

## 一条命令

```bash
python3 scripts/demo_recovery.py
```

Windows PowerShell：

```powershell
py -3 -X utf8 scripts/demo_recovery.py
```

默认创建并清理临时工作区，不触碰真实项目、用户配置或账户额度。每步输出 PASS，最后输出JSON。

## 保留现场

指定**源码目录外且尚不存在**的新目录：

```bash
python3 scripts/demo_recovery.py --workspace ../continuity-recovery-demo --report recovery-report.json
```

Windows：

```powershell
py -3 -X utf8 scripts/demo_recovery.py --workspace ..\continuity-recovery-demo --report recovery-report.json
```

目录和报告均不能已存在，重跑时换名称。源码目录内的现场被拒绝，避免生成状态递归进入安装包。

```text
continuity-recovery-demo/
├── isolated codex home/    # 演示用完整安装及备份
├── demo project/
│   ├── result.json         # 最终total=5，两个阶段完成
│   ├── continue_demo.py    # 独立进程执行第二阶段
│   ├── PROGRESS.md
│   ├── CONTINUITY_TASKS.md
│   └── .continuity-keeper/
└── exported snapshot/      # 第一阶段导出，total=2
```

## 实际断点与证据

| 阶段 | 实际操作 |
| --- | --- |
| 初始化 | 调用隔离安装的CLI，建立初始检查点 |
| 第一阶段 | 写result.json，验证total=2，记录第二阶段未完成 |
| 保存 | 对象存储字节与成果一致，重复checkpoint不新增快照 |
| 新进程 | 全新OS进程读持久化进度，不依赖前一进程内存 |
| 模拟丢失 | 仅删除这个新演示工作区中的result.json |
| 安全导出 | 导出第一阶段到新目录，确认没有自动覆盖现场 |
| 继续 | 明确合并核对后的文件，用独立进程完成第二阶段 |
| 验收 | 读取并验证total=5，更新进度并保存最终检查点 |
| 额度边界 | 只在演示项目模拟剩5%，验证应急索引及收尾提示 |

这是文件持久化、独立进程及选择性恢复实验；不是物理断电实验，不改变真实额度，也不证明远程模型必定服从自然语言。

## 手工体验“继续”

先完成真实安装和 `/hooks` 审查，再在一个独立测试项目中说：

```text
使用 $codex-continuity-keeper 初始化两阶段任务：
第一阶段创建result.json，total=2，保存并记录第二阶段未完成。
第二阶段在我说继续后再加3，验证total=5。
本轮只执行第一阶段并交付断点。
```

关闭会话后在**同一项目目录**打开新会话，说“继续”。验收：先汇报五类状态，核对实际文件再继续；读取并验证最终值后更新进度。

不要故意耗尽真实额度，不要用业务项目模拟删除文件。
