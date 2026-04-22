import { test, expect } from '../src/fixtures/auth.fixture.js'
import { UsersPage } from '../src/pages/users.page.js'

test.describe('用户管理核心流程', () => {
  test('应该能成功搜索现有用户 @smoke', async ({ authenticatedPage }) => {
    const usersPage = new UsersPage(authenticatedPage)
    await usersPage.goto()
    
    // 默认列表应包含管理员（通常环境中有 admin）
    await usersPage.searchUser('admin')
    const exists = await usersPage.isUserInList('admin')
    expect(exists).toBeTruthy()
  })

  test('应该能成功填写新增用户表单并提交 @case', async ({ authenticatedPage }) => {
    const usersPage = new UsersPage(authenticatedPage)
    await usersPage.goto()
    
    const testUser = {
      username: `testuser_${Date.now()}`,
      email: `test_${Date.now()}@example.com`,
      password: 'Password123!',
      role: 'user' as const
    }
    
    await usersPage.createUser(testUser)
    
    // 创建成功提示与对话框关闭已在 page object 中校验，这里确认页面仍停留在用户管理
    await expect(authenticatedPage.getByRole('link', { name: '用户管理' })).toBeVisible()
  })
})
