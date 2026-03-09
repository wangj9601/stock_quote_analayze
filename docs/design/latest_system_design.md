# 股票分析系统最新设计文档（2025-11-07）

## 1. 系统概览

整个股票分析平台由四个核心子系统组成：

- `frontend`：面向终端投资者的静态站点，使用原生 HTML/CSS/JavaScript 搭配模块化脚本，负责行情展示、自选股、资讯浏览等交互。
- `admin`：基于 Vue 3 + Element Plus 的管理后台，提供用户、行情、日志、公告等运营工具。
- `backend_api`：FastAPI 服务层，整合认证、行情、资讯、交易笔记等 REST 接口，并为前端与后台提供统一的数据访问入口。
- `backend_core`：数据采集与分析引擎，负责对接第三方数据源、调度任务、生成报表，并与 API 层共享 PostgreSQL 数据库。

除上述模块外，系统还包含一套公共配置（如 `deploy_config.json`、Nginx 模板、批处理脚本），用于生产部署与一键启动。

## 2. 管理后台（`admin`）

### 2.1 技术栈与入口

后台采用 Vite 打包，组合 Vue 3、Pinia、Vue Router、Element Plus 以及 Tailwind PostCSS 风格工具。应用入口会注册所有 Element 图标并挂载到 `#app`。

```2:21:admin/src/main.ts
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import './style.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
```

### 2.2 路由布局与导航

应用通过嵌套路由实现登录页与主布局分离。`AdminLayout` 提供侧边栏导航、面包屑和注销流程，子路由覆盖仪表板、日志、用户、行情、数据采集等模块。

```4:70:admin/src/router/index.ts
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/views/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'logs', name: 'Logs', component: () => import('@/views/LogsView.vue') },
      { path: 'users', name: 'Users', component: () => import('@/views/UsersView.vue') },
      { path: 'quotes', name: 'Quotes', component: () => import('@/views/QuotesView.vue') },
      { path: 'datasource', name: 'DataSource', component: () => import('@/views/DataSourceView.vue') },
      { path: 'datacollect', name: 'DataCollect', component: () => import('@/views/DataCollectView.vue') },
      { path: 'monitoring', name: 'Monitoring', component: () => import('@/views/MonitoringView.vue') },
      { path: 'models', name: 'Models', component: () => import('@/views/ModelsView.vue') },
      { path: 'content', name: 'Content', component: () => import('@/views/ContentView.vue') },
      { path: 'announcements', name: 'Announcements', component: () => import('@/views/AnnouncementsView.vue') }
    ]
  }
]
```

### 2.3 认证与状态管理

Pinia `useAuthStore` 负责认证状态生命周期，包括本地 token 恢复、后端校验、登出清理。Vue Router 守卫会等待 `initAuth` 完成后再继续导航，确保刷新后仍保持会话。

```6:118:admin/src/stores/auth.ts
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const user = ref<UserInfo | null>(null)
  const isInitialized = ref(false)

  const isAuthenticated = computed(() => {
    if (!isInitialized.value) return false
    return !!token.value
  })

  const initAuth = async () => {
    const savedToken = localStorage.getItem('admin_token')
    const savedUser = localStorage.getItem('admin_user')
    if (savedToken && savedUser) {
      try {
        const response = await authService.verifyToken()
        if (response.valid) {
          token.value = savedToken
          user.value = JSON.parse(savedUser)
        } else {
          localStorage.removeItem('admin_token')
          localStorage.removeItem('admin_user')
        }
      } catch (err) {
        localStorage.removeItem('admin_token')
        localStorage.removeItem('admin_user')
      }
    }
    isInitialized.value = true
  }

  return { token, user, isInitialized, isAuthenticated, initAuth, login, logout }
})
```

### 2.4 API 封装

`apiService` 基于 Axios，对请求追加 Bearer Token、处理 401 自动登出，并允许独立传入 baseURL（兼容 `.env` 与环境配置）。模块化服务（如 `auth.service.ts`、`users.service.ts`）都通过该实例发起请求。

```1:74:admin/src/services/api.ts
class ApiService {
  private api: AxiosInstance
  private isLoggingOut = false

  constructor() {
    this.api = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL || getCurrentEnvConfig().apiBaseUrl,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' }
    })

    this.api.interceptors.request.use((config) => {
      const token = localStorage.getItem('admin_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })

    this.api.interceptors.response.use(
      (response) => response.data,
      (error) => {
        if (error.response?.status === 401 && !this.isLoggingOut) {
          localStorage.removeItem('admin_token')
          localStorage.removeItem('admin_user')
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }
}
```

### 2.5 典型业务页面

- **仪表板**：以统计卡片、快捷操作、时间线展示系统概况，可在真实数据未接入时回退到模拟数据。
- **用户管理**：整合 Pinia 与 Element 表格，支持分页、筛选、批量操作、密码重置等高级操作。

```118:217:admin/src/views/UsersView.vue
<el-table
  :data="filteredUsers"
  :loading="loading"
  stripe
  style="width: 100%"
  :max-height="tableHeight"
>
  <el-table-column prop="username" label="用户名" />
  <el-table-column label="角色">
    <template #default="{ row }">
      <el-tag :type="getRoleTagType(row.role)">
        {{ getRoleText(row.role) }}
      </el-tag>
    </template>
  </el-table-column>
  <el-table-column label="操作">
    <template #default="{ row }">
      <el-button size="small" @click="editUser(row)">编辑</el-button>
      <el-dropdown @command="(action) => handleUserAction(action, row)">
        <el-button size="small" type="primary">更多</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="change_password">修改密码</el-dropdown-item>
            <el-dropdown-item command="reset_password">初始化密码</el-dropdown-item>
            <el-dropdown-item command="disable">禁用</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>
  </el-table-column>
</el-table>
```

## 3. 公共站点前端（`frontend`）

### 3.1 配置与全局工具

静态站点通过 `Config` 动态判断环境并拼接 API 地址，`CommonUtils` 封装认证、搜索、格式化、Toast 等功能，同时提供 `authFetch` 自动附加 token 与 401 兜底逻辑。

```1:63:frontend/js/config.js
const Config = {
    getEnvironment() {
        const hostname = window.location.hostname;
        if (hostname === 'www.icemaplecity.com' || hostname === 'icemaplecity.com' || hostname === 'erp.icemaplecity.com') {
            return 'production';
        }
        if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.')) {
            return 'development';
        }
        return 'development';
    },
    getApiBaseUrl() {
        const environment = this.getEnvironment();
        switch (environment) {
            case 'production':
                return '';
            case 'development':
            default:
                return 'http://localhost:5000';
        }
    }
};
```

```4:171:frontend/js/common.js
async function authFetch(url, options = {}) {
    const token = localStorage.getItem('access_token');
    options.headers = options.headers || {};
    if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
    }
    const response = await fetch(url, options);
    if (response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('userInfo');
        if (!window.location.pathname.includes('login.html')) {
            CommonUtils.showToast('登录已过期，请重新登录', 'error');
            window.location.href = 'login.html';
        }
    }
    return response;
}

const CommonUtils = {
    auth: {
        async checkLogin() {
            const response = await authFetch(`${API_BASE_URL}/api/auth/status`);
            const result = await response.json();
            if (result.success && result.logged_in) {
                return result.user;
            }
            if (!window.location.pathname.includes('login.html')) {
                window.location.href = 'login.html';
            }
            return null;
        },
        logout() {
            localStorage.clear();
            window.location.replace('login.html');
        }
    }
};
```

### 3.2 页面逻辑

各功能页通过 `DOMContentLoaded` 时序调用多个 API，并在失败时切换到模拟数据，保证 demo 可用性。例如首页并行加载指数、自选股、板块、涨幅榜和新闻，细粒度控制 UI 更新与后备数据。

```27:176:frontend/js/home.js
document.addEventListener('DOMContentLoaded', function() {
    loadRealData();
});

async function loadMarketIndices() {
    const response = await authFetch(`${API_BASE_URL}/api/market/indices`);
    const result = await response.json();
    if (result.success && result.data) {
        updateIndexDisplay(result.data);
    } else {
        updateIndexDisplay(fallbackData);
    }
}

async function loadWatchlist() {
    const response = await authFetch(`${API_BASE_URL}/api/watchlist`);
    const result = await response.json();
    if (result.success && result.data) {
        updateWatchlistDisplay(result.data.slice(0, 3));
    } else {
        updateWatchlistDisplay(mockStocks);
    }
}
```

## 4. 后端 API 层（`backend_api`）

### 4.1 FastAPI 入口与跨域

`main.py` 创建 FastAPI 应用、注册请求日志中间件，并集中引入认证、后台、行情、资讯等子路由。CORS 放行本地开发、内网以及生产域名，方便前后端分离调试。

```26:110:backend_api/main.py
app = FastAPI(title="股票分析系统API", version="1.0.0")
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://www.icemaplecity.com", "https://icemaplecity.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(market_router)
app.include_router(stock_router)
app.include_router(quotes_router)
app.include_router(trading_notes_router)
app.include_router(news_channel_router)
```

### 4.2 配置与数据库

系统默认连接 PostgreSQL（含池化与超时参数），并暴露 `get_db` 依赖给各路由使用。JWT 配置集中于 `config.py`，确保认证逻辑取自统一密钥。

```20:48:backend_api/config.py
DATABASE_CONFIG = {
    "url": "postgresql+psycopg2://postgres:qidianspacetime@localhost:5446/stock_analysis",
    "pool_size": 5,
    "max_overflow": 10,
    "echo": False
}

JWT_CONFIG = {
    "secret_key": "your-secret-key-here",
    "algorithm": "HS256",
    "access_token_expire_minutes": 1440
}
```

```15:36:backend_api/database.py
engine = create_engine(
    DATABASE_CONFIG["url"],
    pool_size=DATABASE_CONFIG["pool_size"],
    max_overflow=DATABASE_CONFIG["max_overflow"],
    echo=DATABASE_CONFIG["echo"]
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
         yield db
    finally:
         db.close()
```

### 4.3 认证

`auth_routes` 提供登录、状态查询与登出接口，集成请求日志、密码迁移与 token 验证。`auth.py` 支持 bcrypt 与旧 SHA256 哈希共存，并在登录成功后自动迁移密码。

```121:246:backend_api/auth_routes.py
@router.post("/login", response_model=Token)
async def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    access_token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer", "user": UserInDB.from_orm(user)}
```

### 4.4 管理接口

后台接口与前端路由一一对应，例如用户管理支持分页搜索、状态切换、密码重置与统计汇总。所有接口均通过 `get_current_active_user` 进行管理员权限校验。

```29:209:backend_api/admin/users.py
@router.get("", response_model=UsersResponse)
async def get_users(skip: int = 0, limit: int = 20, search: Optional[str] = None, current_user = Depends(get_current_active_user), db: Session = Depends(get_db)):
    query = db.query(User)
    if search:
        query = query.filter(or_(User.username.contains(search), User.email.contains(search)))
    total = query.count()
    users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    return UsersResponse(data=users, total=total, page=(skip // limit) + 1, pageSize=limit)

@router.post("/{user_id}/password/reset")
async def reset_user_password(user_id: int, current_user = Depends(get_current_active_user), db: Session = Depends(get_db)):
    DEFAULT_PASSWORD = "bingfengtang$91"
    db_user = db.query(User).filter(User.id == user_id).first()
    db_user.password_hash = get_password_hash(DEFAULT_PASSWORD)
    db.commit()
    return {"message": "密码已重置为默认值", "default": DEFAULT_PASSWORD}
```

### 4.5 行情与资讯

`quotes_routes` 针对实时股票、指数、板块行情提供分页查询、排序、数据清洗（空值处理）等能力。通过 SQLAlchemy + Pandas 混合查询最大化灵活性。

```165:350:backend_api/quotes_routes.py
@router.get("/stocks")
async def get_stock_quotes(page: int = 1, page_size: int = 20, keyword: Optional[str] = None, market: Optional[str] = None, sort_by: Optional[str] = "change_percent"):
    db = next(get_db())
    latest_date_result = pd.read_sql_query("""
        SELECT MAX(trade_date) as latest_date 
        FROM stock_realtime_quote 
        WHERE change_percent IS NOT NULL AND change_percent != 0
    """, db.bind)
    latest_trade_date = latest_date_result.iloc[0]['latest_date']
    query = db.query(StockRealtimeQuote).filter(StockRealtimeQuote.trade_date == latest_trade_date)
    if keyword:
        query = query.filter((StockRealtimeQuote.code.contains(keyword)) | (StockRealtimeQuote.name.contains(keyword)))
    total = query.count()
    data = query.offset((page - 1) * page_size).limit(page_size).all()
    formatted_data = format_quotes_data(data, "stocks")
    return {"success": True, "data": formatted_data, "total": total, "page": page, "page_size": page_size}
```

其他模块如 `trading_notes_routes`、`news_channel_routes`、`market_routes` 则扩展个股笔记、资讯频道与市场概览接口，与前端脚本调用保持一致路径规范。

## 5. 核心引擎（`backend_core`）

### 5.1 配置中心

核心模块统一使用 `backend_core/config/config.py` 定义数据源 token、日志目录、数据库路径与代理设置，并在启动时确保关键目录存在。

```1:52:backend_core/config/config.py
ROOT_DIR = Path(__file__).parent.parent.parent
DB_DIR = ROOT_DIR / 'database'
DB_DIR.mkdir(parents=True, exist_ok=True)

DATA_COLLECTORS = {
    'tushare': {
        'max_retries': 3,
        'retry_delay': 5,
        'timeout': 30,
        'log_dir': str(ROOT_DIR / 'backend_core' / 'logs'),
        'db_file': str(DB_DIR / 'stock_analysis.db'),
        'token': TUSHARE_CONFIG['token']
    },
    'akshare': {
        'max_retries': 3,
        'retry_delay': 5,
        'timeout': 30,
        'log_dir': str(ROOT_DIR / 'backend_core' / 'logs'),
        'db_file': str(DB_DIR / 'stock_analysis.db'),
        'proxy_pool': [],
        'random_delay_range': (1, 3),
        'ssl_verify': False,
        'use_fallback_sources': True
    }
}
```

### 5.2 数据采集调度

`data_collectors/main.py` 基于 APScheduler 注册多项任务：

- AKShare 实时行情（工作日交易时段每 30 分钟）
- Tushare 历史行情（每日固定时刻）
- 行业板块、公告、换手率、自选股历史、新闻采集
- 新闻热度更新与老数据清理

```19:246:backend_core/data_collectors/main.py
ak_collector = AkshareRealtimeQuoteCollector(...)
tushare_hist_collector = HistoricalQuoteCollector(...)
news_collector = NewsCollector()

scheduler.add_job(collect_akshare_realtime, 'cron', day_of_week='mon-fri', hour='9-11,13-16', minute='23,53')
scheduler.add_job(collect_tushare_historical, 'cron', hour='10', minute='25')
scheduler.add_job(collect_akshare_index_realtime, 'cron', day_of_week='mon-fri', hour='9-11,13-16', minute='58')
scheduler.add_job(collect_akshare_stock_notices, 'interval', minutes=180)
scheduler.add_job(run_watchlist_history_collection, 'cron', minute='*/5')
scheduler.add_job(collect_market_news, 'interval', minutes=50)
scheduler.add_job(update_hot_news, 'interval', hours=1)
scheduler.add_job(cleanup_old_news, 'cron', hour=2, minute=0)
```

### 5.3 资讯采集与清洗

`NewsCollector` 使用 Akshare 拉取市场新闻/个股新闻，自动分类、提取摘要、写入数据库，并提供热门资讯标记与旧数据清理。

```19:394:backend_core/data_collectors/news_collector.py
class NewsCollector:
    def collect_market_news(self) -> List[Dict]:
        news_df = ak.stock_news_main_cx()
        for _, row in news_df.iterrows():
            news_item = {
                'title': str(row.get('tag', '')).strip(),
                'content': str(row.get('summary', '')).strip(),
                'publish_time': publish_time,
                'source': '财新网',
                'category_id': self._classify_news(title, content),
                'summary': self._extract_summary(content),
                'tags': self._extract_tags(title, content)
            }
            news_list.append(news_item)

    def collect_and_save_market_news(self) -> Dict:
        news_list = self.collect_market_news()
        saved_count = self.save_news_to_db(news_list)
        self.update_hot_news()
        return {"success": True, "collected": len(news_list), "saved": saved_count}
```

### 5.4 数据库与模型

核心引擎直接连接 PostgreSQL，并在 `models` 目录中定义历史行情、自选股、采集日志等 ORM 模型，与 API 层共享同一数据表，实现“采集-服务”解耦。

```8:33:backend_core/database/db.py
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "options": "-c deadlock_timeout=1s -c lock_timeout=5s -c statement_timeout=30s"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

```1:27:backend_core/models/historical_quotes.py
class HistoricalQuotes(Base):
    __tablename__ = 'historical_quotes'
    code = Column(String, primary_key=True)
    ts_code = Column(String)
    name = Column(String)
    market = Column(String)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Integer)
    amount = Column(Float)
    change_percent = Column(Float)
    collected_date = Column(DateTime, default=datetime.now)
```

### 5.5 报表与通知

`reports/csv_report_generator.py` 为企业用户生成 CSV/Excel 自选股报表，`wechat/wechat_service.py` 负责企业微信推送，`scheduler/daily_report_scheduler.py` 通过 `schedule` 每日两次触发报告发送。

```8:175:backend_core/reports/csv_report_generator.py
class CSVReportGenerator:
    def generate_summary_report(self, user_id: int) -> str:
        watchlist = self.get_user_watchlist(user_id)
        summary_data = []
        for stock in watchlist:
            summary = self.get_stock_summary_data(stock['stock_code'])
            summary_data.append({ '股票代码': stock['stock_code'], '当前价格': summary.get('current_price', 0) })
        df = pd.DataFrame(summary_data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return filepath
```

```1:98:backend_core/scheduler/daily_report_scheduler.py
class DailyReportScheduler:
    def send_daily_report(self):
        users = self.get_active_users()
        for user in users:
            report_file = self.report_generator.generate_summary_report(user_id)
            success = self.wechat_service.send_file_message(
                user_ids=[wechat_user_id],
                file_path=report_file,
                file_name=f"每日股票报告_{datetime.now().strftime('%Y%m%d')}.csv"
            )
```

## 6. 数据流与系统协同

1. **数据采集层**：`backend_core` 定时从 Akshare、Tushare 拉取行情、新闻、公告等数据，写入 PostgreSQL。热数据（实时行情）在 `stock_realtime_quote` 等表中滚动更新。
2. **服务层**：`backend_api` 使用共享数据库连接读取同一数据表，为前端提供 REST 接口；部分接口直接调用 `backend_core` 产生的结果（例如资讯、行情、报表）。
3. **前端消费**：
   - `frontend` 通过原生 `fetch` 调用 `/api/market/*`、`/api/watchlist` 等接口展示数据。
   - `admin` 通过 Axios 服务访问 `/api/admin/*` 与 `/api/quotes/*` 等，配合 Pinia 实现状态同步。
4. **通知链路**：当需要发送每日自选股报告时，调度器生成 CSV 并调用企业微信 API 下发给绑定用户。

整体架构如下：

```
第三方数据源 ──► backend_core (采集/调度/报表) ──► PostgreSQL
                                    ▲                                     │
                                    │                                     ▼
                              后端 API (FastAPI) ◄───── 认证/业务逻辑 ──► 管理后台 (Vue)
                                                                             │
                                                                             ▼
                                                          终端前端站点 (静态页面)
```

## 7. 运维与部署要点

- 开发阶段建议通过 `.env` / `VITE_API_BASE_URL` 控制管理端 API 地址；静态前端则依赖 `Config.getApiBaseUrl` 自动适配。
- FastAPI 服务默认监听 `0.0.0.0:5000`，若部署在生产，可配合 `nginx_complete.conf` 实现反向代理与静态资源托管。
- 数据采集脚本使用 BlockingScheduler，如需与 FastAPI 同机运行，应采用独立进程或使用 `BackgroundScheduler` 嵌入服务进程。
- 企业微信、Tushare Token 等敏感信息应通过环境变量或加密配置注入。

## 8. 演进建议

- **统一数据库配置**：目前 `backend_api` 与 `backend_core` 各自维护连接 URL，可考虑集中到共享配置或服务发现机制。
- **身份与权限**：前端公共站点的登录状态依赖 LocalStorage，建议引入刷新 token 与单点注销机制，降低盗用风险。
- **监控与告警**：为采集任务增加失败回调（如飞书/微信告警），并对 APScheduler 任务执行情况进行可视化统计。
- **测试覆盖**：完善 `docs` 与 `test` 目录下的集成测试，确保新增接口能被前端正确消费。

---

本设计文档将随代码结构调整持续更新，以保障业务方与开发团队对系统架构的统一认知。


