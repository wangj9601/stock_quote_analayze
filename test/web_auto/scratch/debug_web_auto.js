import { chromium } from '@playwright/test';
import fs from 'fs';
import path from 'path';

async function debug() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // 监听控制台日志
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    
    try {
        console.log('🚀 导航到登录页...');
        await page.goto('http://127.0.0.1:8001/login');
        
        console.log('🔐 尝试执行登录...');
        await page.fill('input[placeholder="请输入用户名"]', 'admin');
        await page.fill('input[placeholder="请输入密码"]', '123456');
        await page.click('button:has-text("登录")');
        
        console.log('⏳ 等待跳转到 dashboard...');
        await page.waitForURL(/dashboard/, { timeout: 15000 });
        console.log('✅ 登录成功，当前URL:', page.url());
        
        console.log('🚀 导航到用户管理页...');
        await page.goto('http://127.0.0.1:8001/users');
        await page.waitForLoadState('networkidle');
        
        console.log('📸 截图记录状态...');
        await page.screenshot({ path: 'scratch/users_debug.png' });
        
        const content = await page.content();
        fs.writeFileSync('scratch/users_page_content.txt', content);
        
        console.log('🔍 检查搜素框是否存在...');
        const searchInput = await page.getByPlaceholder('搜索用户名或邮箱').isVisible();
        console.log('搜素框可见性:', searchInput);
        
    } catch (err) {
        console.error('❌ 调试脚本发生错误:', err.message);
        await page.screenshot({ path: 'scratch/error_screenshot.png' });
    } finally {
        await browser.close();
    }
}

debug();
