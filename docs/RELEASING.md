# 发布 Windows 便携版（CI）

仓库已配置 GitHub Actions：`.github/workflows/release-windows.yml`。

## 一键发版（推荐）

在 `main` 上打版本 tag 并推送：

```powershell
cd D:\New_god\tool\codex-profile
git checkout main
git pull
# 如有需要先改版本号：desktop/package.json、desktop/src-tauri/tauri.conf.json、Cargo.toml
git tag v1.0.4
git push origin v1.0.4
```

Actions 会在 `windows-latest` 上：

1. `npm ci` + `tauri build --no-bundle`
2. 打包 `ProfileIsolator.exe` 与 `ProfileIsolator-windows-portable.zip`
3. 创建/更新 GitHub Release，并上传上述文件

## 仅构建、不发版

GitHub → Actions → **Release Windows** → **Run workflow**  
（可不填 tag；产物在 Artifact `ProfileIsolator-windows-portable`）

若要挂到已有 Release，在 `tag` 填入如 `v1.0.3` 再运行。

## 本地等价命令

```powershell
cd desktop
npm ci
npm run tauri build -- --no-bundle
# 输出：src-tauri/target/release/ai_cli_profile_isolator.exe
```

## 说明

- **免安装**：单文件 exe 即可运行（需 WebView2）
- zip 内含 `README-PORTABLE.txt` 简短说明
- 安装包（NSIS）可在 `tauri.conf.json` 的 `bundle.targets` 中启用；CI 当前为加快构建使用 `--no-bundle`
- CI 日志会打印 `sha256 exe=...` / `sha256 zip=...`，发版后可对照校验下载完整性
- 应用内 **More → About** 显示当前 `CARGO_PKG_VERSION`（与 `desktop/src-tauri/Cargo.toml` 一致）
