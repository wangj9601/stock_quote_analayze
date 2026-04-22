import { test, expect } from '../src/fixtures/auth.fixture.js'

test('debug users page logs', async ({ authenticatedPage }) => {
    // 转发浏览器日志到终端
    authenticatedPage.on('console', msg => console.log('BROWSER LOG:', msg.text()))
    authenticatedPage.on('pageerror', err => console.error('BROWSER ERROR:', err.message))

    // 复用登录夹具，避免硬编码账号导致卡在 /login
    await expect(authenticatedPage).toHaveURL(/dashboard/)

    console.log('🚀 导航到 /users...')
    await authenticatedPage.goto('/users')

    console.log('⏳ 等待 5 秒观察日志...')
    await authenticatedPage.waitForTimeout(5000)

    const title = await authenticatedPage.title()
    console.log('当前页面标题:', title)

    await authenticatedPage.screenshot({ path: 'scratch/final_debug.png' })
    console.log('截图已保存')
})
