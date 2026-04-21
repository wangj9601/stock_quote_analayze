import { test, expect } from '@playwright/test';
import { authenticatedPage } from '../src/fixtures/auth.fixture.js';

test('debug users page logs', async ({ page }) => {
    // 转发浏览器日志到终端
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
    page.on('pageerror', err => console.error('BROWSER ERROR:', err.message));

    console.log('🚀 导航到登录页...');
    await page.goto('/login');
    
    console.log('🔐 执行登录...');
    await page.fill('input[placeholder="用户名"]', 'admin');
    await page.fill('input[placeholder="密码"]', '123456');
    await page.click('button:has-text("登录")');
    
    console.log('⏳ 等待跳转...');
    await expect(page).toHaveURL(/dashboard/);
    
    console.log('🚀 导航到 /users...');
    await page.goto('/users');
    
    console.log('⏳ 等待 5 秒观察日志...');
    await page.waitForTimeout(5000);
    
    const title = await page.title();
    console.log('当前页面标题:', title);
    
    const screenshot = await page.screenshot({ path: 'scratch/final_debug.png' });
    console.log('截图已保存');
});
