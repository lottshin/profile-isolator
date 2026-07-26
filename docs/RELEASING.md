# 发布 Windows 包（CI）

仓库：`.github/workflows/release-windows.yml`。

## 一键发版（推荐）

在 `main` 上打版本 tag 并推送：

```powershell
cd D:\New_god\tool\codex-profile
git checkout main
git pull
# 改版本号：desktop/package.json、desktop/src-tauri/tauri.conf.json、Cargo.toml
git tag v1.0.6
git push origin v1.0.6
```

Actions（`windows-latest`）会：

1. `npm ci` + `tauri build --bundles nsis`（便携 exe + **NSIS 安装包**）
2. 打包：
   - `ProfileIsolator.exe` — 免安装
   - `ProfileIsolator-windows-portable.zip` — exe + 说明
   - `ProfileIsolator-setup.exe` — 安装包（开始菜单 / 卸载）
   - `SHA256SUMS.txt` — 校验和
3. 创建/更新 GitHub Release，**Release 正文含 SHA256**

## 仅构建、不发版

GitHub → Actions → **Release Windows** → **Run workflow**

- 不填 tag → 产物在 Artifact `ProfileIsolator-windows`
- 填已有 tag → 上传到该 Release
- `with_installer` 可关（只打便携包，更快）

## 校验下载

```powershell
Get-FileHash .\ProfileIsolator.exe -Algorithm SHA256
# 与 Release 中 SHA256SUMS.txt 或说明里的哈希对照（不区分大小写）
```

## 本地等价命令

```powershell
cd desktop
npm ci
# 便携 exe only
npm run tauri build -- --no-bundle
# 含 NSIS 安装包
npm run tauri build -- --bundles nsis
# exe:  src-tauri/target/release/ai_cli_profile_isolator.exe
# nsis: src-tauri/target/release/bundle/nsis/*.exe
```

## 说明

- **免安装**：单文件 exe（需 WebView2）
- **安装包**：可选，适合希望开始菜单/卸载的用户
- 应用内 **More → About** 显示 `CARGO_PKG_VERSION`
