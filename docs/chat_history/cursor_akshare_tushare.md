https://www.tradingview.com/symbols/SSE-601919/

# 收集akshare和tushare接口列表
_Exported on 2025/6/13 at GMT+8 15:35:37 from Cursor (1.1.2)_

---

**User**

@/backend_api @/backend_core 帮我搜集所有通过akshare， tushare的接口，并列表显示。

---

**Cursor**

根据你的代码库，以下是所有通过 **akshare** 和 **tushare** 的接口调用整理列表（仅列出主要API调用点和方法，便于你快速定位和理解）：

---

## 一、akshare接口调用汇总

### 1. `backend_api/market_routes.py`
- `ak.stock_zh_index_spot_em(symbol="沪深重要指数")` 获取沪深重要指数
- `ak.stock_zh_index_spot_em(symbol="上证系列指数")` 获取上证系列指数
- `ak.stock_zh_index_spot_em(symbol="深证系列指数")` 获取深证系列指数
- `ak.stock_board_industry_name_em()` 获取行业板块行情

### 2. `backend_api/watchlist_manage.py`
- `ak.stock_bid_ask_em(symbol=code)` 获取自选股盘口实时行情

### 3. `backend_api/stock/stock_manage.py`
- `ak.stock_bid_ask_em(symbol=code)` 获取单只股票盘口实时行情
- `ak.stock_zh_a_spot_em()` 获取A股全部实时行情

### 4. `backend_api/stock/stock_fund_flow.py`
- `ak.stock_individual_fund_flow_rank(indicator='今日')` 查询个股资金流向排名
- `ak.stock_individual_fund_flow(stock=code, market='sh/sz/bj')` 查询个股资金流向（上交所/深交所/北交所）

### 5. `backend_api/admin/quotes.py`
- 主要用于数据导出，实际行情采集见上面相关API

### 6. `backend_core/data_collectors/akshare/base.py` 及相关采集器
- `ak.stock_zh_a_spot_em()` 获取A股列表/实时行情
- `ak.stock_zh_a_hist(symbol, period, start_date, end_date, adjust)` 获取历史行情
- `ak.stock_financial_analysis_indicator(symbol)` 获取财务指标
- `ak.stock_individual_info_em(symbol)` 获取公司概况
- `ak.stock_a_lg_indicator(symbol)` 获取估值指标

---

## 二、tushare接口调用汇总

### 1. `backend_core/data_collectors/tushare/base.py`
- `ts.set_token(...)` 设置tushare token

### 2. `backend_core/data_collectors/tushare/historical.py`
- `pro.daily(trade_date=date_str)` 获取指定日期的A股历史行情（Tushare Pro接口）

### 3. `backend_core/data_collectors/tushare/realtime.py`
- `pro.stock_basic(exchange='', list_status='L')` 获取股票基础信息
- `ts.get_realtime_quotes(stocks['ts_code'].tolist())` 获取实时行情

### 4. `backend_core/data_collectors/tushare/index.py`
- 继承自`TushareCollector`，具体接口调用方式类似

---

## 典型接口调用举例

| 文件 | 主要akshare/tushare接口 | 说明 |
|------|------------------------|------|
| backend_api/market_routes.py | ak.stock_zh_index_spot_em, ak.stock_board_industry_name_em | 指数、板块行情 |
| backend_api/watchlist_manage.py | ak.stock_bid_ask_em | 自选股盘口 |
| backend_api/stock/stock_manage.py | ak.stock_bid_ask_em, ak.stock_zh_a_spot_em | 批量/单只股票实时行情 |
| backend_api/stock/stock_fund_flow.py | ak.stock_individual_fund_flow_rank, ak.stock_individual_fund_flow | 个股资金流向 |
| backend_core/data_collectors/akshare/base.py | ak.stock_zh_a_spot_em, ak.stock_zh_a_hist, ak.stock_financial_analysis_indicator, ak.stock_individual_info_em, ak.stock_a_lg_indicator | 采集器基类，封装多种akshare接口 |
| backend_core/data_collectors/tushare/historical.py | pro.daily | 历史行情采集 |
| backend_core/data_collectors/tushare/realtime.py | pro.stock_basic, ts.get_realtime_quotes | 实时行情采集 |

---

如需详细到每个API的参数和返回结构，可进一步展开具体函数实现。你可以指定某个文件或接口，我可以帮你详细解读。

如需导出为表格或文档，也可告知！

---

如需继续，请输入你的补充指令，或输入 `TASK_COMPLETE` 结束本次交互。

