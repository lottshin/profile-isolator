# Profile Isolator

**中文** | [English](README.en.md)

<p align="center">
  <img src="docs/brand/icon-256.png" alt="Profile Isolator icon" width="120" />
</p>

<p align="center">
  <b>让不同的 Codex CLI / Claude Code 同时使用不同的供应商</b><br/>
  每个终端一套 API、模型、Key —— 互不串台
</p>

<p align="center">
  <img src="docs/screenshots/main-ui.png" alt="Profile Isolator 主界面（演示数据，已脱敏）" width="900" />
</p>

> 截图仅为界面示意：**profile 名 / 路径 / 接口地址均为示例**，不含真实 Key。

<p align="center">
  <a href="https://github.com/lottshin/profile-isolator/releases"><img src="https://img.shields.io/github/v/release/lottshin/profile-isolator?label=release" alt="release" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="license" /></a>
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey" alt="platform" />
</p>

## 解决什么问题

在 Windows 上并行使用多套 CLI 时，常见需求是：

| 场景 | 默认全局配置 | 使用本工具 |
|------|--------------|------------|
| 终端 A：Codex + 供应商 X | 修改 `~/.codex` | 启动 profile「供应商 X」 |
| 终端 B：Codex + 供应商 Y（同时） | 再改全局，终端 A 也被影响 | 启动 profile「供应商 Y」 |
| Claude Code 使用另一供应商 | 再改 `~/.claude` | 在 Claude 页同样按 profile 启动 |
| 同一项目在不同供应商间 `resume` | 会话目录容易对不齐 | 可选共享会话 + 相同工作目录 |

本工具为每个 profile 使用独立配置目录，启动时注入隔离环境变量；会话目录可选共享。

**目标：多个 Codex / Claude Code 进程并行运行，各自连接不同供应商，配置互不干扰。**

实现方式：

- **Codex**：每个 profile 独立目录，启动时设置 `CODEX_HOME`
- **Claude Code**：每个 profile 独立目录，启动时设置 `CLAUDE_CONFIG_DIR`

| CLI | 隔离环境变量 | 主配置 | 凭证 | 会话 |
|-----|-------------|--------|------|------|
| **Codex** | `CODEX_HOME` | `config.toml` | `auth.json` | `sessions/` |
| **Claude Code** | `CLAUDE_CONFIG_DIR` | `settings.json` | `.credentials.json`（主要 MCP OAuth） | `projects/` |

> Claude 的 API Key / Base URL / 模型在 **`settings.json` → `env`**（`ANTHROPIC_*`），不在 `.credentials.json`。

## 功能一览

- 为 **Codex / Claude Code** 分别管理多供应商 profile  
- **Launch**：带隔离环境启动 CLI（可同时开多个，互不影响）  
- 会话共享（junction 到默认 home），同一工作目录可跨供应商 `resume`  
- 新建 / 导入 / **重命名** / **复制** / 删除 / **拖动排序**  
- **工作目录按 profile 记忆**  
- Codex + Claude 配置树可**一起搬到其他盘**  
- 缓存查看 / 清理（不自动清会话）  
- 浅色 / 深色 / 跟随系统  

## 下载

- **Windows 预编译**：[Releases](https://github.com/lottshin/profile-isolator/releases)  
  直接运行 `ProfileIsolator-v*.exe`（需 WebView2，Win11 一般已自带）

## 快速使用（多供应商并行）

1. 打开应用 → 选 **Codex**（或 **Claude Code**）  
2. 为供应商 A 建一个 profile（或 Import 当前配置后再改）  
3. 在 Config / Auth 里填该供应商的 base_url、模型、Key → 保存  
4. 再复制或新建 profile，改成供应商 B 的配置  
5. 分别 **Launch** → 两个终端各自 `CODEX_HOME` / `CLAUDE_CONFIG_DIR` 不同，**同时使用不同供应商**  
6. 工作目录选同一项目时，配合会话共享可跨 profile `resume`  

默认路径：

```text
%USERPROFILE%\CodexProfiles\<name>
%USERPROFILE%\ClaudeProfiles\<name>
```

可在 **More → Cache & storage** 把两套树一起迁到例如 `F:\AI-Profiles\`。

本机设置：

```text
%USERPROFILE%\.profile-isolator\
```

## 从源码构建

```powershell
# 依赖：Node 18+、Rust stable、VS Build Tools (C++)
cd desktop
npm install
npm run tauri dev          # 开发
npm run tauri build -- --no-bundle   # 产出 exe
# desktop/src-tauri/target/release/ai_cli_profile_isolator.exe
```

可选：`python desktop/make_ios_icon.py` 重新生成图标。

## 安全提示

- **不要**把含真实 Key 的配置提交到仓库或发到公开截图  
- 分享配置前请脱敏  

## 项目结构

```text
├── desktop/          # 主程序：Tauri + React
├── app/              # 旧版 Python GUI（可选）
├── docs/
│   ├── brand/        # 应用图标
│   └── screenshots/  # README 截图
├── README.md         # 中文（默认）
└── README.en.md      # English
```

## 许可证

MIT — 见 [LICENSE](LICENSE)。
