
# 2025/07/10
## 股票数据分析软件相关工作
    - sqlite 数据转换到 postgreSQL；
    - backend_core 目录 数据库访问切换到postgreSQL， 数据库访问架构都改为 sqlalchemy；
    - 数据采集相关代码改造后的相关调试工作。
## 东航数字升舱相关工作
    - 跟进首都机场小程序需求相关讨论。

# 2025/07/11
## 股票数据分析软件相关工作
    - 继续调试数据采集相关改造代码；
    - 参考backend_core 目录，backend_api 目录相关程序代码数据库访问切换到postgreSQL， 数据库访问架构都改为 sqlalchemy。

# 2025/07/14
## 股票数据分析软件相关工作
    - 新增自选股历史行情采集任务相关处理，每天凌晨2点执行一次， 数据库访问架构都改为 sqlalchemy。
    - 自选股历史行情采集任务相关处理代码调试。

# 2025/07/15
## 股票数据分析软件相关工作
    - 继续自选股历史行情采集任务相关处理代码调试。
    - 自选股历史行情前端页面显示效果调整。

# 2025/07/16
## 股票数据分析软件相关工作
    - utf-8 codec can't decode byte 0xd6 in position 60: invalid continuation byte 的报错， 修改以下配置文件pg_hba.conf。
    -   # "local" is for Unix domain socket connections only
        local   all             all                                     scram-sha-256
        # IPv4 local connections:
        #host    all             all             127.0.0.1/32            scram-sha-256
        host    all             all             127.0.0.1/32            trust
        host    all             all             192.168.31.237/32            trust
        你的问题是：

    - 同样的数据库连接字符串，只要把 192.168.31.237 换成 localhost，就不会报 utf-8 解码错误。用 IP 地址就报错，用 localhost 就没问题。
        这个现象的本质原因
        1. “localhost” 和 “IP地址” 连接方式底层实现不同
            localhost 连接时，PostgreSQL 客户端（psycopg2）优先用 Unix 域套接字（socket）（在 Windows 下用本地 TCP，但有时走的代码路径不同），
            IP 地址 连接时，一定用 TCP/IP。两种方式在底层数据传输、认证、环境变量、甚至编码协商上，可能会有差异。
        2. 数据库服务端的 client_encoding 协商机制
            PostgreSQL 支持多种编码协商方式，连接时会协商客户端和服务端的编码。
            用 localhost 时，可能协商出来的编码和用 IP 时不一样，比如：
            用 localhost，client_encoding 被设置成了 UTF-8（或你本地的默认编码）。
            用 IP，client_encoding 被设置成了 SQL_ASCII 或其他非 UTF-8 编码，导致遇到非 UTF-8 字节时报错。

# 2025/07/22

## 股票数据分析软件相关工作
    - tushare A股历史数据采集程序修改；
    - 个股历史数据查询导出功能前后台代码修改调整。

## 联航信息化系统需求调研
    - 联航信息化调研。