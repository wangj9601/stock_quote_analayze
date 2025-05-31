import tushare as ts
from pathlib import Path
import logging
from ...config.config import DATA_COLLECTORS

class TushareCollector:
    """Tushare数据采集器基类"""
    def __init__(self, config=None):
        ts.set_token('9701deb356e76d8d9918d797aff060ce90bd1a24339866c02444014f')
        self.config = config or DATA_COLLECTORS.get('tushare', {})
        log_dir = Path(self.config.get('log_dir', 'backend_core/logs'))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f'tushare_{self.__class__.__name__.lower()}.log'
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
