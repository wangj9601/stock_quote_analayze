# 前端 UI 本地字体

替代原先 `fonts.googleapis.com` / `fonts.gstatic.com` 的公网加载，避免国内访问不稳定。

## 文件

| 字体 | 字重 | 子集 |
|------|------|------|
| Barlow Condensed | 500 / 600 / 700 | latin |
| Noto Sans SC | 400 / 500 / 600 / 700 | latin + chinese-simplified |

声明见 `css/fonts-local.css`，由 `css/design-tokens.css` 引入。

## 来源与许可

- 上游：[fontsource](https://fontsource.org/) 打包的 Google Fonts（`@fontsource/barlow-condensed@5.3.0`、`@fontsource/noto-sans-sc@5.3.1`）
- 许可：SIL Open Font License 1.1（`OFL-BarlowCondensed.txt`、`OFL-NotoSansSC.txt`）

## 重新拉取

```powershell
# 在临时目录 npm pack 后，将所需 .woff2 复制到本目录，并保留 OFL 文本
npm pack @fontsource/barlow-condensed@5.3.0 @fontsource/noto-sans-sc@5.3.1
```

PDF 导出用的嵌入字体仍在 `assets/fonts/NotoSansSC-Subset.ttf`，与本目录无关。
