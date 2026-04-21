import { test, expect } from '../src/fixtures/auth.fixture.js'
import { QuotesPage } from '../src/pages/quotes.page.js'

test.describe('行情数据中心核心流程', () => {
  test('应该能在 A股/港股 市场间自由切换并保持数据加载 @smoke', async ({ authenticatedPage }) => {
    const quotesPage = new QuotesPage(authenticatedPage)
    await quotesPage.goto()
    
    // 验证 A股数据加载
    await expect(authenticatedPage.getByText('股票实时行情')).toBeVisible()
    
    // 切换到港股
    await quotesPage.switchToMarket('HK')
    await expect(authenticatedPage.getByText('港股实时行情')).toBeVisible()
    
    // 返回 A股
    await quotesPage.switchToMarket('A')
    await expect(authenticatedPage.getByText('股票实时行情')).toBeVisible()
  })

  test('应该能通过股票代码成功搜索单个股票 @case', async ({ authenticatedPage }) => {
    const quotesPage = new QuotesPage(authenticatedPage)
    await quotesPage.goto()
    
    const stockCode = '000001'
    await quotesPage.searchStock('A', stockCode)
    
    // 验证列表中仅存在目标代码（或包含该代码的行）
    const exists = await quotesPage.isStockInList(stockCode)
    expect(exists).toBeTruthy()
  })
})
