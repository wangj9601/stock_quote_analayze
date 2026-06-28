"""GMS 信号追溯：策略版本分标签相关单元测试"""

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend_api.stock.gms_trace_routes import _config_display_name


class TestGmsTraceConfigDisplay:
    def test_config_display_name_with_label(self):
        row = SimpleNamespace(id=1, name="default", version_label="标准版·双模块阶梯", is_default=True)
        assert "标准版" in _config_display_name(row)

    def test_config_display_name_name_only(self):
        row = SimpleNamespace(id=2, name="gms_penalty", version_label="", is_default=False)
        assert _config_display_name(row) == "gms_penalty"

    def test_config_display_name_missing_row(self):
        assert _config_display_name(None) == "未知版本"
