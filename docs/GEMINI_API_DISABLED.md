# 股票详情页 Gemini API 调用屏蔽说明

## 问题描述

在访问股票详情页时，后端 API `/api/analysis/stock/{stock_code}` 会调用 Gemini AI 进行深度分析。由于 Gemini API 配额超限（每分钟请求限制为 0），导致以下错误：

```
429 Quota exceeded for quota metric 'Generate Content API requests per minute' 
and limit 'GenerateContent request limit per minute for a region' 
of service 'generativelanguage.googleapis.com' for consumer 'project_number:773331463739'.
```

错误发生位置：
- `backend_api/stock/stock_analysis.py` 第 772 行
- `backend_api/stock/stock_analysis.py` 第 786 行

## 解决方案

### 修改文件
- **文件路径**: `backend_api/stock/stock_analysis.py`
- **修改位置**: `StockAnalysisService.get_stock_analysis()` 方法（第 844-850 行）

### 修改内容

**修改前**:
```python
# AI 深度分析 (Gemini) - 使用超时保护，失败不影响其他结果
try:
    ai_insight = self._get_gemini_analysis(stock_code, historical_data, technical_indicators)
except Exception as e:
    logger.warning(f"AI分析失败，使用默认值: {str(e)}")
    ai_insight = "AI 分析服务暂不可用"
```

**修改后**:
```python
# AI 深度分析 (Gemini) - 已屏蔽，避免配额超限
# try:
#     ai_insight = self._get_gemini_analysis(stock_code, historical_data, technical_indicators)
# except Exception as e:
#     logger.warning(f"AI分析失败，使用默认值: {str(e)}")
#     ai_insight = "AI 分析服务暂不可用"
ai_insight = ""  # 暂时屏蔽 Gemini 分析，避免配额超限
```

## 影响范围

### 不受影响的功能
✅ 技术指标计算（RSI、MACD、KDJ、布林带）
✅ 价格预测
✅ 交易建议
✅ 关键价位分析（支撑位、阻力位）
✅ 股票详情页的其他所有功能

### 受影响的功能
❌ AI 深度分析（Gemini）- 现在返回空字符串

## 后续建议

如果需要重新启用 Gemini AI 分析，可以考虑以下方案：

1. **增加配额**: 向 Google Cloud 申请提高 API 配额限制
2. **添加配置开关**: 在配置文件中添加开关，控制是否启用 Gemini 分析
3. **实现缓存机制**: 对分析结果进行缓存，减少 API 调用频率
4. **限流控制**: 实现请求限流，避免超过配额限制

## 验证方法

访问股票详情页（例如：`http://127.0.0.1:14780/api/analysis/stock/000721`），应该：
- ✅ 不再出现 429 配额超限错误
- ✅ 正常返回技术指标、价格预测、交易建议等数据
- ✅ `ai_insight` 字段为空字符串

## 修改时间
2026-02-02 14:00
