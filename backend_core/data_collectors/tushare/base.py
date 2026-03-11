import tushare as ts
from pathlib import Path
import logging
from ...config.config import DATA_COLLECTORS
from ...logging_utils import should_log_to_file

class TushareCollector:
    """Tushare数据采集器基类"""
    def __init__(self, config=None):
        ts.set_token('9701deb356e76d8d9918d797aff060ce90bd1a24339866c02444014f')
        self.config = config or DATA_COLLECTORS.get('tushare', {})
        log_dir = Path(self.config.get('log_dir', 'backend_core/logs'))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f'tushare_{self.__class__.__name__.lower()}.log'
        if should_log_to_file():
            logging.basicConfig(
                filename=log_file,
                level=logging.INFO,
                format='%(asctime)s %(levelname)s %(message)s',
                encoding='utf-8'
            )
        else:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s %(levelname)s %(message)s',
                handlers=[logging.StreamHandler()]
            )
        self.logger = logging.getLogger(self.__class__.__name__)
