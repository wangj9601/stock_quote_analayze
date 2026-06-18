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
try:
    import sys
    import os
    import importlib.util
    
    # 获取 backend_api 目录路径
    backend_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_py_path = os.path.join(backend_api_dir, 'models.py')
    
    # 使用 importlib 直接加载 models.py 文件
    if os.path.exists(models_py_path):
        spec = importlib.util.spec_from_file_location("backend_api_models", models_py_path)
        models_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(models_module)
        
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
        MeanFrequencyResonanceIndicators = getattr(models_module, 'MeanFrequencyResonanceIndicators', None)
        GMSSignalTrace = getattr(models_module, 'GMSSignalTrace', None)
        VolumeShrinkBreakoutSignal = getattr(models_module, 'VolumeShrinkBreakoutSignal', None)
        VsbObserveStock = getattr(models_module, 'VsbObserveStock', None)
        GmsTradeObserveStock = getattr(models_module, 'GmsTradeObserveStock', None)
        GmsTradeObserveHistory = getattr(models_module, 'GmsTradeObserveHistory', None)
        TripleVolumeTradeObserveStock = getattr(models_module, 'TripleVolumeTradeObserveStock', None)
        GMSStrategyVersion = getattr(models_module, 'GMSStrategyVersion', None)
        GMSStrategyVersionStock = getattr(models_module, 'GMSStrategyVersionStock', None)
        GMSStrategyConfig = getattr(models_module, 'GMSStrategyConfig', None)
        GMSRuntimeConfig = getattr(models_module, 'GMSRuntimeConfig', None)
        GMSBacktestTask = getattr(models_module, 'GMSBacktestTask', None)
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
    else:
        raise ImportError(f"找不到 models.py 文件: {models_py_path}")
    
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
    MeanFrequencyResonanceIndicators = None
    GMSSignalTrace = None
    VolumeShrinkBreakoutSignal = None
    VsbObserveStock = None
    GmsTradeObserveStock = None
    GmsTradeObserveHistory = None
    TripleVolumeTradeObserveStock = None
    GMSStrategyVersion = None
    GMSStrategyVersionStock = None
    GMSRuntimeConfig = None
    GMSBacktestTask = None
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
    'MeanFrequencyResonanceIndicators',
    'GMSSignalTrace',
    'VolumeShrinkBreakoutSignal',
    'VsbObserveStock',
    'GmsTradeObserveStock',
    'GmsTradeObserveHistory',
    'TripleVolumeTradeObserveStock',
    'GMSStrategyVersion',
    'GMSStrategyVersionStock',
    'GMSRuntimeConfig',
    'GMSBacktestTask',
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
