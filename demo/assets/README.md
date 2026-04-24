# 离线底图替换说明

将你的园区底图文件放在本目录，推荐文件名：

- `park_basemap.png`（优先）
- `park_basemap.jpg`
- `park_basemap.jpeg`
- `park_basemap.webp`

Demo 在离线模式下会自动尝试加载上述文件；如果都不存在，会回退到默认离线样式底图。

也可通过 URL 指定文件，例如：

- `digital_twin_demo.html?offlineBasemap=./assets/my_park_map.png`
