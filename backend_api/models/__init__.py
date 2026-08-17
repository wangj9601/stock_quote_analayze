"""
Models package initialization
"""

from .pvfrs_enhanced import (
    PVFRSStrategyConfig,
    PVFRSBacktestTaskEnhanced,
    PVFRSBacktestResultEnhanced,
    PVFRSTradeRecordEnhanced,
    PVFRSEquityCurveEnhanced,
    PVFRSBacktestTask,
    PVFRSBacktestResult,
    PVFRSTradeRecord,
    PVFRSEquityCurve,
    PVFRSAlert,
    PVFRSMonitorMetric
)

# 导入原有模型以保持兼容性
# 注意：模型定义在 backend_api/models.py 文件中
# 由于存在 models 目录和 models.py 文件，需要使用特殊方式导入
_models_py_module = None

def _load_models_py_module(force_reload: bool = False):
    """加载 backend_api/models.py（与包名冲突，需 importlib）。"""
    global _models_py_module
    import os
    import importlib.util
    import sys

    if _models_py_module is not None and not force_reload:
        return _models_py_module

    backend_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_py_path = os.path.join(backend_api_dir, 'models.py')
    if not os.path.exists(models_py_path):
        raise ImportError(f"找不到 models.py 文件: {models_py_path}")

    module_name = "backend_api_models"
    if force_reload and module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, models_py_path)
    models_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = models_module
    spec.loader.exec_module(models_module)
    _models_py_module = models_module
    return models_module


try:
    models_module = _load_models_py_module()
    if models_module is not None:
        # 导入所有需要的模型
        User = getattr(models_module, 'User', None)
        Admin = getattr(models_module, 'Admin', None)
        AdminInDB = getattr(models_module, 'AdminInDB', None)
        Watchlist = getattr(models_module, 'Watchlist', None)
        WatchlistGroup = getattr(models_module, 'WatchlistGroup', None)
        WatchlistCreate = getattr(models_module, 'WatchlistCreate', None)
        WatchlistInDB = getattr(models_module, 'WatchlistInDB', None)
        WatchlistGroupCreate = getattr(models_module, 'WatchlistGroupCreate', None)
        WatchlistGroupInDB = getattr(models_module, 'WatchlistGroupInDB', None)
        Token = getattr(models_module, 'Token', None)
        TokenData = getattr(models_module, 'TokenData', None)
        UserInDB = getattr(models_module, 'UserInDB', None)
        UserCreate = getattr(models_module, 'UserCreate', None)
        UserUpdate = getattr(models_module, 'UserUpdate', None)
        FrontendRole = getattr(models_module, 'FrontendRole', None)
        FrontendPermission = getattr(models_module, 'FrontendPermission', None)
        RolePermission = getattr(models_module, 'RolePermission', None)
        FrontendRoleCreate = getattr(models_module, 'FrontendRoleCreate', None)
        FrontendRoleUpdate = getattr(models_module, 'FrontendRoleUpdate', None)
        FrontendRoleInDB = getattr(models_module, 'FrontendRoleInDB', None)
        FrontendPermissionInDB = getattr(models_module, 'FrontendPermissionInDB', None)
        PermissionTreeNode = getattr(models_module, 'PermissionTreeNode', None)
        RolePermissionsUpdate = getattr(models_module, 'RolePermissionsUpdate', None)
        UserPermissionsUpdate = getattr(models_module, 'UserPermissionsUpdate', None)
        UserPermissionsDetail = getattr(models_module, 'UserPermissionsDetail', None)
        UserPermission = getattr(models_module, 'UserPermission', None)
        UserRoleInfo = getattr(models_module, 'UserRoleInfo', None)
        PermissionsResponse = getattr(models_module, 'PermissionsResponse', None)
        MeanFrequencyResonanceIndicators = getattr(models_module, 'MeanFrequencyResonanceIndicators', None)
        GMSSignalTrace = getattr(models_module, 'GMSSignalTrace', None)
        GmsTraceRecomputeTask = getattr(models_module, 'GmsTraceRecomputeTask', None)
        VolumeShrinkBreakoutSignal = getattr(models_module, 'VolumeShrinkBreakoutSignal', None)
        VsbObserveStock = getattr(models_module, 'VsbObserveStock', None)
        GmsTradeObserveStock = getattr(models_module, 'GmsTradeObserveStock', None)
        GmsTradeObserveHistory = getattr(models_module, 'GmsTradeObserveHistory', None)
        GmsFormalTrade = getattr(models_module, 'GmsFormalTrade', None)
        UrtTradeObserveStock = getattr(models_module, 'UrtTradeObserveStock', None)
        UrtTradeObserveHistory = getattr(models_module, 'UrtTradeObserveHistory', None)
        UrtFormalTrade = getattr(models_module, 'UrtFormalTrade', None)
        TradeObserveStock = getattr(models_module, 'TradeObserveStock', None)
        TradeObserveHistory = getattr(models_module, 'TradeObserveHistory', None)
        FormalTrade = getattr(models_module, 'FormalTrade', None)
        TripleVolumeTradeObserveStock = getattr(models_module, 'TripleVolumeTradeObserveStock', None)
        GMSStrategyVersion = getattr(models_module, 'GMSStrategyVersion', None)
        GMSStrategyVersionStock = getattr(models_module, 'GMSStrategyVersionStock', None)
        GMSStrategyConfig = getattr(models_module, 'GMSStrategyConfig', None)
        URTStrategyConfig = getattr(models_module, 'URTStrategyConfig', None)
        URTSignalTrace = getattr(models_module, 'URTSignalTrace', None)
        UrtTraceRecomputeTask = getattr(models_module, 'UrtTraceRecomputeTask', None)
        URTBacktestTask = getattr(models_module, 'URTBacktestTask', None)
        GMSRuntimeConfig = getattr(models_module, 'GMSRuntimeConfig', None)
        GMSBacktestTask = getattr(models_module, 'GMSBacktestTask', None)
        SBBRStrategyConfig = getattr(models_module, 'SBBRStrategyConfig', None)
        SBBRSignalTrace = getattr(models_module, 'SBBRSignalTrace', None)
        SBBRTraceRecomputeTask = getattr(models_module, 'SBBRTraceRecomputeTask', None)
        SBBRReserveBox = getattr(models_module, 'SBBRReserveBox', None)
        SBBRTradeObserveStock = getattr(models_module, 'SBBRTradeObserveStock', None)
        SBBRFormalTrade = getattr(models_module, 'SBBRFormalTrade', None)
        SBBRBacktestTask = getattr(models_module, 'SBBRBacktestTask', None)
        RPEStrategyConfig = getattr(models_module, 'RPEStrategyConfig', None)
        RPESignalTrace = getattr(models_module, 'RPESignalTrace', None)
        RPETradeObserveStock = getattr(models_module, 'RPETradeObserveStock', None)
        RPETradeObserveHistory = getattr(models_module, 'RPETradeObserveHistory', None)
        RPEFormalTrade = getattr(models_module, 'RPEFormalTrade', None)
        RPEBacktestTask = getattr(models_module, 'RPEBacktestTask', None)
        RPEPrecomputeRun = getattr(models_module, 'RPEPrecomputeRun', None)
        RPETraceRecomputeTask = getattr(models_module, 'RPETraceRecomputeTask', None)
        EnvSyncServerConfig = getattr(models_module, 'EnvSyncServerConfig', None)
        EnvSyncClientConfig = getattr(models_module, 'EnvSyncClientConfig', None)
        EnvSyncAuditLog = getattr(models_module, 'EnvSyncAuditLog', None)
        StockBasicInfo = getattr(models_module, 'StockBasicInfo', None)
        StockBasicInfoHK = getattr(models_module, 'StockBasicInfoHK', None)
        StockPriceData = getattr(models_module, 'StockPriceData', None)
        StockTechnicalIndicators = getattr(models_module, 'StockTechnicalIndicators', None)
        StockRealtimeQuote = getattr(models_module, 'StockRealtimeQuote', None)
        StockRealtimeQuoteHK = getattr(models_module, 'StockRealtimeQuoteHK', None)
        FundBasicInfo = getattr(models_module, 'FundBasicInfo', None)
        FundRealtimeQuote = getattr(models_module, 'FundRealtimeQuote', None)
        FundHistoricalQuotes = getattr(models_module, 'FundHistoricalQuotes', None)
        HistoricalQuotes = getattr(models_module, 'HistoricalQuotes', None)
        HistoricalQuotesHK = getattr(models_module, 'HistoricalQuotesHK', None)
        IndexRealtimeQuotes = getattr(models_module, 'IndexRealtimeQuotes', None)
        IndustryBoardRealtimeQuotes = getattr(models_module, 'IndustryBoardRealtimeQuotes', None)
        IndustryBoardConstituent = getattr(models_module, 'IndustryBoardConstituent', None)
        ConceptBoardConstituent = getattr(models_module, 'ConceptBoardConstituent', None)
        HKIndexRealtimeQuotes = getattr(models_module, 'HKIndexRealtimeQuotes', None)
        HKIndexHistoricalQuotes = getattr(models_module, 'HKIndexHistoricalQuotes', None)
        StockNews = getattr(models_module, 'StockNews', None)
        MAIndicators = getattr(models_module, 'MAIndicators', None)
        MACDIndicators = getattr(models_module, 'MACDIndicators', None)
        KDJIndicators = getattr(models_module, 'KDJIndicators', None)
        RSIIndicators = getattr(models_module, 'RSIIndicators', None)
        BOLLIndicators = getattr(models_module, 'BOLLIndicators', None)
        MAVOLIndicators = getattr(models_module, 'MAVOLIndicators', None)
        InfiniteCostIndicators = getattr(models_module, 'InfiniteCostIndicators', None)
        QuoteData = getattr(models_module, 'QuoteData', None)
        QuoteDataCreate = getattr(models_module, 'QuoteDataCreate', None)
        QuoteDataInDB = getattr(models_module, 'QuoteDataInDB', None)
        DataCollectionRequest = getattr(models_module, 'DataCollectionRequest', None)
        DataCollectionResponse = getattr(models_module, 'DataCollectionResponse', None)
        DataCollectionStatus = getattr(models_module, 'DataCollectionStatus', None)
        TushareHistoricalCollectionRequest = getattr(models_module, 'TushareHistoricalCollectionRequest', None)
        RealtimeHistoricalCollectionRequest = getattr(models_module, 'RealtimeHistoricalCollectionRequest', None)
        FileHistoricalCollectionRequest = getattr(models_module, 'FileHistoricalCollectionRequest', None)
        HKFileHistoricalCollectionRequest = getattr(models_module, 'HKFileHistoricalCollectionRequest', None)
        RealtimeCollectionRequest = getattr(models_module, 'RealtimeCollectionRequest', None)
        RealtimeCollectionResponse = getattr(models_module, 'RealtimeCollectionResponse', None)
        Base = getattr(models_module, 'Base', None)
        
        # 导入系统监控模型
        SystemMonitorMetric = getattr(models_module, 'SystemMonitorMetric', None)
        SystemAlert = getattr(models_module, 'SystemAlert', None)
        SystemServiceStatus = getattr(models_module, 'SystemServiceStatus', None)
        SystemAlertRule = getattr(models_module, 'SystemAlertRule', None)
        SystemPerformanceReport = getattr(models_module, 'SystemPerformanceReport', None)
        
        # 导入微信推送相关模型
        UserPushConfig = getattr(models_module, 'UserPushConfig', None)
        PushRecord = getattr(models_module, 'PushRecord', None)
        EmailSenderConfig = getattr(models_module, 'EmailSenderConfig', None)
        EmailSendLog = getattr(models_module, 'EmailSendLog', None)
        TripleVolumeObserveStock = getattr(models_module, 'TripleVolumeObserveStock', None)
        # 交易笔记与模拟交易模型
        TradingNotes = getattr(models_module, 'TradingNotes', None)
        TradingJournalLog = getattr(models_module, 'TradingJournalLog', None)
        TradeExecutionLog = getattr(models_module, 'TradeExecutionLog', None)
        SimTradeAccount = getattr(models_module, 'SimTradeAccount', None)
        SimTradePosition = getattr(models_module, 'SimTradePosition', None)
        SimTradeOrder = getattr(models_module, 'SimTradeOrder', None)
        QuoteSyncTask = getattr(models_module, 'QuoteSyncTask', None)
        QuoteSyncTaskCreate = getattr(models_module, 'QuoteSyncTaskCreate', None)
        QuoteSyncTaskInDB = getattr(models_module, 'QuoteSyncTaskInDB', None)
        
        # 采集日历模型
        TradingCalendar = getattr(models_module, 'TradingCalendar', None)
        TradingCalendarCreate = getattr(models_module, 'TradingCalendarCreate', None)
        TradingCalendarInDB = getattr(models_module, 'TradingCalendarInDB', None)
        StockCodeTextPK = getattr(models_module, 'StockCodeTextPK', None)

except Exception as e:
    # 如果导入失败，创建占位符
    import traceback
    print(f"警告：导入模型失败: {e}")
    traceback.print_exc()
    User = None
    Admin = None
    AdminInDB = None
    Watchlist = None
    WatchlistGroup = None
    WatchlistCreate = None
    WatchlistInDB = None
    WatchlistGroupCreate = None
    WatchlistGroupInDB = None
    Token = None
    TokenData = None
    UserInDB = None
    UserCreate = None
    UserUpdate = None
    FrontendRole = None
    FrontendPermission = None
    RolePermission = None
    FrontendRoleCreate = None
    FrontendRoleUpdate = None
    FrontendRoleInDB = None
    FrontendPermissionInDB = None
    PermissionTreeNode = None
    RolePermissionsUpdate = None
    UserPermissionsUpdate = None
    UserPermissionsDetail = None
    UserPermission = None
    UserRoleInfo = None
    PermissionsResponse = None
    MeanFrequencyResonanceIndicators = None
    GMSSignalTrace = None
    GmsTraceRecomputeTask = None
    VolumeShrinkBreakoutSignal = None
    VsbObserveStock = None
    GmsTradeObserveStock = None
    GmsTradeObserveHistory = None
    GmsFormalTrade = None
    UrtTradeObserveStock = None
    UrtTradeObserveHistory = None
    UrtFormalTrade = None
    TradeObserveStock = None
    TradeObserveHistory = None
    FormalTrade = None
    TripleVolumeTradeObserveStock = None
    GMSStrategyVersion = None
    GMSStrategyVersionStock = None
    GMSStrategyConfig = None
    URTStrategyConfig = None
    URTSignalTrace = None
    UrtTraceRecomputeTask = None
    URTBacktestTask = None
    GMSRuntimeConfig = None
    GMSBacktestTask = None
    SBBRStrategyConfig = None
    SBBRSignalTrace = None
    SBBRTraceRecomputeTask = None
    SBBRReserveBox = None
    SBBRTradeObserveStock = None
    SBBRFormalTrade = None
    SBBRBacktestTask = None
    RPEStrategyConfig = None
    RPESignalTrace = None
    RPETradeObserveStock = None
    RPETradeObserveHistory = None
    RPEFormalTrade = None
    RPEBacktestTask = None
    RPEPrecomputeRun = None
    RPETraceRecomputeTask = None
    EnvSyncServerConfig = None
    EnvSyncClientConfig = None
    EnvSyncAuditLog = None
    StockCodeTextPK = None
    StockBasicInfo = None
    StockBasicInfoHK = None
    StockPriceData = None
    StockTechnicalIndicators = None
    StockRealtimeQuote = None
    StockRealtimeQuoteHK = None
    FundBasicInfo = None
    FundRealtimeQuote = None
    FundHistoricalQuotes = None
    HistoricalQuotes = None
    HistoricalQuotesHK = None
    IndexRealtimeQuotes = None
    IndustryBoardRealtimeQuotes = None
    IndustryBoardConstituent = None
    ConceptBoardConstituent = None
    HKIndexRealtimeQuotes = None
    HKIndexHistoricalQuotes = None
    StockNews = None
    MAIndicators = None
    MACDIndicators = None
    KDJIndicators = None
    RSIIndicators = None
    BOLLIndicators = None
    MAVOLIndicators = None
    InfiniteCostIndicators = None
    QuoteData = None
    QuoteDataCreate = None
    QuoteDataInDB = None
    DataCollectionRequest = None
    DataCollectionResponse = None
    DataCollectionStatus = None
    TushareHistoricalCollectionRequest = None
    RealtimeHistoricalCollectionRequest = None
    FileHistoricalCollectionRequest = None
    HKFileHistoricalCollectionRequest = None
    RealtimeCollectionRequest = None
    RealtimeCollectionResponse = None
    Base = None
    
    # 系统监控模型占位符
    SystemMonitorMetric = None
    SystemAlert = None
    SystemServiceStatus = None
    SystemAlertRule = None
    SystemPerformanceReport = None
    
    # 微信推送模型占位符
    UserPushConfig = None
    PushRecord = None
    EmailSenderConfig = None
    EmailSendLog = None
    TripleVolumeObserveStock = None
    # 交易笔记与模拟交易模型占位符
    TradingNotes = None
    TradingJournalLog = None
    TradeExecutionLog = None
    SimTradeAccount = None
    SimTradePosition = None
    SimTradeOrder = None
    QuoteSyncTask = None
    QuoteSyncTaskCreate = None
    QuoteSyncTaskInDB = None
    TradingCalendar = None
    TradingCalendarCreate = None
    TradingCalendarInDB = None

__all__ = [
    'PVFRSStrategyConfig',
    'PVFRSBacktestTaskEnhanced',
    'PVFRSBacktestResultEnhanced',
    'PVFRSTradeRecordEnhanced',
    'PVFRSEquityCurveEnhanced',
    'PVFRSBacktestTask',
    'PVFRSBacktestResult',
    'PVFRSTradeRecord',
    'PVFRSEquityCurve',
    'PVFRSAlert',
    'PVFRSMonitorMetric',
    'User',
    'Admin',
    'AdminInDB',
    'Watchlist',
    'WatchlistGroup',
    'WatchlistCreate',
    'WatchlistInDB',
    'WatchlistGroupCreate',
    'WatchlistGroupInDB',
    'Token',
    'TokenData',
    'UserInDB',
    'UserCreate',
    'UserUpdate',
    'FrontendRole',
    'FrontendPermission',
    'RolePermission',
    'FrontendRoleCreate',
    'FrontendRoleUpdate',
    'FrontendRoleInDB',
    'FrontendPermissionInDB',
    'PermissionTreeNode',
    'RolePermissionsUpdate',
    'UserPermissionsUpdate',
    'UserPermissionsDetail',
    'UserPermission',
    'UserRoleInfo',
    'PermissionsResponse',
    'MeanFrequencyResonanceIndicators',
    'GMSSignalTrace',
    'GmsTraceRecomputeTask',
    'VolumeShrinkBreakoutSignal',
    'VsbObserveStock',
    'GmsTradeObserveStock',
    'GmsTradeObserveHistory',
    'GmsFormalTrade',
    'UrtTradeObserveStock',
    'UrtTradeObserveHistory',
    'UrtFormalTrade',
    'TradeObserveStock',
    'TradeObserveHistory',
    'FormalTrade',
    'TripleVolumeTradeObserveStock',
    'GMSStrategyVersion',
    'GMSStrategyVersionStock',
    'GMSStrategyConfig',
    'URTStrategyConfig',
    'URTSignalTrace',
    'UrtTraceRecomputeTask',
    'URTBacktestTask',
    'GMSRuntimeConfig',
    'GMSBacktestTask',
    'SBBRStrategyConfig',
    'SBBRSignalTrace',
    'SBBRTraceRecomputeTask',
    'SBBRReserveBox',
    'SBBRTradeObserveStock',
    'SBBRFormalTrade',
    'SBBRBacktestTask',
    'RPEStrategyConfig',
    'RPESignalTrace',
    'RPETradeObserveStock',
    'RPETradeObserveHistory',
    'RPEFormalTrade',
    'RPEBacktestTask',
    'RPEPrecomputeRun',
    'RPETraceRecomputeTask',
    'EnvSyncServerConfig',
    'EnvSyncClientConfig',
    'EnvSyncAuditLog',
    'StockBasicInfo',
    'StockBasicInfoHK',
    'StockPriceData',
    'StockTechnicalIndicators',
    'StockRealtimeQuote',
    'StockRealtimeQuoteHK',
    'FundBasicInfo',
    'FundRealtimeQuote',
    'FundHistoricalQuotes',
    'HistoricalQuotes',
    'HistoricalQuotesHK',
    'IndexRealtimeQuotes',
    'IndustryBoardRealtimeQuotes',
    'IndustryBoardConstituent',
    'ConceptBoardConstituent',
    'HKIndexRealtimeQuotes',
    'HKIndexHistoricalQuotes',
    'StockNews',
    'MAIndicators',
    'MACDIndicators',
    'KDJIndicators',
    'RSIIndicators',
    'BOLLIndicators',
    'MAVOLIndicators',
    'InfiniteCostIndicators',
    'QuoteData',
    'QuoteDataCreate',
    'QuoteDataInDB',
    'DataCollectionRequest',
    'DataCollectionResponse',
    'DataCollectionStatus',
    'TushareHistoricalCollectionRequest',
    'RealtimeHistoricalCollectionRequest',
    'FileHistoricalCollectionRequest',
    'HKFileHistoricalCollectionRequest',
    'RealtimeCollectionRequest',
    'RealtimeCollectionResponse',
    'SystemMonitorMetric',
    'SystemAlert',
    'SystemServiceStatus',
    'SystemAlertRule',
    'SystemPerformanceReport',
    'UserPushConfig',
    'PushRecord',
    'EmailSenderConfig',
    'EmailSendLog',
    'TripleVolumeObserveStock',
    'TradingNotes',
    'TradingJournalLog',
    'TradeExecutionLog',
    'SimTradeAccount',
    'SimTradePosition',
    'SimTradeOrder',
    'QuoteSyncTask',
    'QuoteSyncTaskCreate',
    'QuoteSyncTaskInDB',
    'TradingCalendar',
    'TradingCalendarCreate',
    'TradingCalendarInDB',
    'StockCodeTextPK',
]


def __getattr__(name: str):
    """热重载/切分支后包缓存过期时，按需从 models.py 补齐缺失符号。"""
    if name.startswith('_'):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        mod = _load_models_py_module(force_reload=True)
        val = getattr(mod, name, None)
    except Exception as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    if val is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = val
    return val
