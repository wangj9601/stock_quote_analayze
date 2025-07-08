PS E:\wangxw\股票分析软件\编码\stock_quote_analayze> python -m backend_core.data_collectors.tushare.main --type realtime

gemini api key:
AIzaSyD1PSWLXbmZM2mfXPXjQ5iPMv0hiaNUdg8

# git常规操作指令
## git 强制以远程的文件为准。
git reset --hard origin/main

# 安装 Git LFS：

git lfs install

git lfs track "*.psd"

git add .

git commit -m "Add large files"

git push origin main




# 数据采集主程序
 python -m backend_core.data_collectors.main

# 近期工作安排
## 1. 完成个股历史成交数据采集、分析、展现（成交明细【成交时间、成交价格、成交数量、成交金额】、成交统计、成交分布、成交趋势、成交分析）。
## 2. 完成阿里云部署（应用服务器、数据库服务器【冰封堂】）。

# 中期工作安排
## 1. 如何分析/模型。
## 2. 选股。

# 长期工作安排
## 1. 交易策略管理。
## 2. 策略回测。
