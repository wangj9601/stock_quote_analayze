# 板块分析 PDF 中文字体

## 文件

- `NotoSansSC-Subset.ttf`：Noto Sans SC（思源黑体 / Noto CJK Sans）简体子集，供 jsPDF 嵌入。

## 来源与许可

- 上游：Google Fonts **Noto Sans SC**（[@fontsource/noto-sans-sc](https://www.npmjs.com/package/@fontsource/noto-sans-sc) 的 `chinese-simplified-400-normal` 字形集）
- 许可：[SIL Open Font License 1.1](https://scripts.sil.org/OFL)（可商用、可嵌入；保留许可声明即可）
- 本仓库由 WOFF 转为 TTF，便于 jsPDF `addFont` 使用；未修改字形设计。

## 重新生成

```bash
python scripts/build_board_pdf_font.py
```

脚本会从 jsDelivr 拉取 fontsource 的 WOFF，转换为 TTF 并写入本目录。

## 运行时加载策略

`board_analysis_pdf.js` 优先请求本地 `assets/fonts/NotoSansSC-Subset.ttf`，成功后写入 IndexedDB 缓存；本地失败时再尝试 CDN 上的 NotoSansSC OTF（jsPDF 不能直接嵌入 WOFF）。首次导出可能稍慢，之后走缓存。部署时请务必带上本目录 TTF。
