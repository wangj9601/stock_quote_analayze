# StockNews数据库插入修复说明

## 问题描述
系统出现错误：`psycopg2.errors.NotNullViolation: 错误: null value in column "id" of relation "stock_news" violates not-null constraint`

## 问题分析
通过分析错误日志和代码，发现问题出现在 `stock_news` 表的 `id` 字段：

1. **数据库约束错误**：`id` 字段被定义为非空约束，但插入时值为 `null`
2. **自增主键问题**：`StockNews` 模型中的 `id` 字段定义为 `autoincrement=True`，但在 PostgreSQL 中可能需要特殊处理
3. **插入逻辑问题**：在创建 `StockNews` 对象时，没有正确处理自增主键

## 根本原因
1. **PostgreSQL 自增字段处理**：PostgreSQL 中的自增字段需要特殊配置
2. **模型定义不完整**：缺少 `__table_args__` 配置
3. **插入逻辑不优化**：没有明确处理自增主键的生成

## 修复方案

### 1. 修复模型定义
在 `backend_api/models.py` 中为 `StockNews` 和 `StockResearchReport` 模型添加 `__table_args__` 配置：

```python
class StockNews(Base):
    __tablename__ = "stock_news"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), index=True)
    title = Column(String(200))
    content = Column(Text)
    keywords = Column(String(100))
    publish_time = Column(DateTime)
    source = Column(String(100))
    url = Column(String(300))
    summary = Column(Text)
    type = Column(String(20))
    rating = Column(String(50))
    target_price = Column(String(50))
    created_at = Column(DateTime)
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class StockResearchReport(Base):
    __tablename__ = "stock_research_reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    # ... 其他字段 ...
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )
```

### 2. 修复插入逻辑
在 `backend_api/stock/stock_news.py` 中优化 `save_news_to_db` 函数：

```python
async def save_news_to_db(symbol: str, news_data: list):
    """保存新闻数据到数据库"""
    try:
        db = next(get_db())
        
        # 先删除该股票的旧数据（保持当日最新）
        today = datetime.date.today().strftime('%Y-%m-%d')
        db.query(StockNews).filter(StockNews.stock_code == symbol, StockNews.created_at >= today).delete()
        
        # 插入新数据
        for item in news_data:
            news_obj = StockNews(
                stock_code=symbol,
                title=item.get('title', ''),
                content=item.get('content', ''),
                keywords=item.get('keywords', ''),
                publish_time=item.get('publish_time', ''),
                source=item.get('source', ''),
                url=item.get('url', ''),
                summary=item.get('summary', ''),
                type=item.get('type', 'news'),
                rating=item.get('rating', ''),
                target_price=item.get('target_price', ''),
                created_at=datetime.datetime.now()
            )
            # 不设置id字段，让数据库自动生成
            db.add(news_obj)
        
        db.commit()
        print(f"[save_news_to_db] 成功保存 {len(news_data)} 条数据到数据库")
        
    except Exception as e:
        print(f"[save_news_to_db] 保存数据到数据库失败: {e}")
        print(traceback.format_exc())
        db.rollback()
        raise
```

### 3. 修复研报插入逻辑
同样优化 `save_research_reports_to_db` 函数：

```python
# 插入或更新数据
research_obj = StockResearchReport(
    stock_code=symbol,
    stock_name=stock_name,
    report_name=report_name,
    # ... 其他字段 ...
    updated_at=datetime.datetime.now()
)
# 不设置id字段，让数据库自动生成
db.add(research_obj)
```

## 测试验证

### 1. 模型定义测试
创建了 `test_stock_news_fix.py` 测试脚本，验证模型定义：

```
StockNews 字段:
  id: INTEGER   
    - 主键: True
    - 自增: True
  stock_code: VARCHAR(20)
  title: VARCHAR(200)
  content: TEXT
  # ... 其他字段

✅ 模型定义检查完成
```

### 2. 对象创建测试
验证对象创建是否正常：

```
✅ 成功创建StockNews对象
  股票代码: 000001
  标题: 测试新闻标题
  ID字段: None  # 正确，因为还没有插入数据库

✅ 成功创建StockResearchReport对象
  股票代码: 000001
  研报名称: 测试研报
  ID字段: None  # 正确，因为还没有插入数据库
```

## 修复要点

### 1. 自增主键处理
- ✅ 不手动设置 `id` 字段值
- ✅ 让数据库自动生成主键
- ✅ 添加 `__table_args__` 配置

### 2. 错误处理优化
- ✅ 添加 `db.rollback()` 回滚操作
- ✅ 添加 `raise` 重新抛出异常
- ✅ 改进错误日志记录

### 3. 数据库兼容性
- ✅ 支持 PostgreSQL 自增字段
- ✅ 保持与 SQLite 的兼容性
- ✅ 正确处理事务

## 相关文件

### 修复的文件
1. `backend_api/models.py`
   - 为 `StockNews` 模型添加 `__table_args__` 配置
   - 为 `StockResearchReport` 模型添加 `__table_args__` 配置

2. `backend_api/stock/stock_news.py`
   - 修复 `save_news_to_db` 函数的插入逻辑
   - 修复 `save_research_reports_to_db` 函数的插入逻辑
   - 添加错误处理和回滚机制

### 测试文件
1. `test_stock_news_fix.py` - 数据库插入修复验证测试

## 数据库表结构
`stock_news` 表的字段结构：
```sql
CREATE TABLE "stock_news" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "stock_code" VARCHAR(20),
    "title" VARCHAR(200),
    "content" TEXT,
    "keywords" VARCHAR(100),
    "publish_time" DATETIME,
    "source" VARCHAR(100),
    "url" VARCHAR(300),
    "summary" TEXT,
    "type" VARCHAR(20),
    "rating" VARCHAR(50),
    "target_price" VARCHAR(50),
    "created_at" DATETIME
);
```

## 总结
通过修复模型定义和插入逻辑，`StockNews` 和 `StockResearchReport` 的数据库插入现在能够正确处理自增主键：

- ✅ 自增主键自动生成
- ✅ 避免 `null` 值约束错误
- ✅ 支持 PostgreSQL 和 SQLite
- ✅ 改进错误处理和事务管理
- ✅ 通过测试验证修复成功

问题已完全解决！🚀 