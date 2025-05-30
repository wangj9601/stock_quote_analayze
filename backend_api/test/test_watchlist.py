import unittest
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class TestWatchlist(unittest.TestCase):
    def setUp(self):
        # 这里假设有 app/test_client/test_user 的初始化方式，需根据实际项目调整
        from backend_api.main import app
        self.client = app.test_client()
        self.test_user = {
            'username': 'testuser1',
            'password': 'password123'
        }

    def test_06b_delete_watchlist_by_code(self):
        """测试根据股票代码删除自选股接口"""
        print("\n🗑️ 测试自选股按股票代码删除...")

        # 先登录
        response = self.client.post('/api/auth/login',
            json=self.test_user,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        user_id = json.loads(response.data)['user']['id']

        # 添加一只自选股，便于后续删除
        stock_data = {
            'user_id': user_id,
            'stock_code': '000002',
            'stock_name': '万科A',
            'group_name': '地产股'
        }
        response = self.client.post('/api/watchlist',
            json=stock_data,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])

        # 正确参数删除（应成功）
        response = self.client.post('/api/watchlist/delete_by_code',
            data={'stock_code': '000002'}
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('删除成功', data['message'])

        # 再次删除同一只（应返回404）
        response = self.client.post('/api/watchlist/delete_by_code',
            data={'stock_code': '000002'}
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('自选股不存在', data['detail'])

        # 缺少参数（应返回422）
        response = self.client.post('/api/watchlist/delete_by_code', data={})
        self.assertEqual(response.status_code, 422)
        print("✅ 自选股按股票代码删除接口测试通过")

if __name__ == '__main__':
    unittest.main()