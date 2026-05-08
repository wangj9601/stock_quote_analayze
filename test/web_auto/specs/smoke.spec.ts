import { test, expect } from '../src/fixtures/auth.fixture.js'
import { runSmokeScan } from '../src/runner/smoke-scanner.js'

test.describe('菜单冒烟扫描 @smoke', () => {
  test('登录后扫描主菜单并记录失败项 @smoke', async ({ authenticatedPage }) => {
    const results = await runSmokeScan(authenticatedPage)

    const failed = results.filter((x) => !x.ok)
    test.info().annotations.push({
      type: 'smoke-scan',
      description: JSON.stringify(results, null, 2)
    })

    expect(
      failed,
      `存在失败菜单项: ${failed.map((x) => `${x.menu} => ${x.error}`).join('; ')}`
    ).toHaveLength(0)
  })
})
