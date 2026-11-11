// Run with Playwright MCP browser_run_code_unsafe, filename: frontend/tests/browser-smoke.js.
// Chat is intercepted only in this test; the application always uses the real API.
async (page) => {
  const check = (value, message) => { if (!value) throw new Error(message); };
  const context = await page.context().browser().newContext();
  const testPage = await context.newPage();
  const results = [];
  try {
    await testPage.goto('http://localhost:5173');
    const input = testPage.getByRole('textbox', { name: 'Your project question' });
    await input.waitFor({ timeout: 5000 });
    await testPage.getByRole('heading', { name: 'Naples Medical Center', exact: true }).waitFor();
    check(await testPage.getByRole('button', { name: 'Send question' }).isDisabled(), 'Blank input must disable send');
    await input.fill('   ');
    check(await testPage.getByRole('button', { name: 'Send question' }).isDisabled(), 'Whitespace must disable send');
    results.push('Backend project data and blank validation');

    let calls = 0;
    let fail = false;
    await testPage.route('http://127.0.0.1:8000/ai/chat', async route => {
      calls++;
      check(route.request().method() === 'POST', 'Chat must use POST');
      check(typeof route.request().postDataJSON().message === 'string', 'Chat contract must include message');
      await new Promise(resolve => setTimeout(resolve, 350));
      if (fail) return route.abort('failed');
      await route.fulfill({ json: { answer: '**Sample answer**\n\n- Review open RFIs\n\n| RFI | Title |\n| --- | --- |\n| 1 | Electrical routing conflict |\n\n<script>window.unsafeMarkdown = true</script>' } });
    });
    await input.fill('Show me all RFIs for project 101.');
    await input.press('Enter');
    check(await testPage.getByRole('button', { name: 'Sending' }).isDisabled(), 'Send disabled during request');
    await input.press('Enter');
    await testPage.locator('.markdown strong').waitFor();
    check(calls === 1, 'Duplicate submit must not make another request');
    check(await testPage.locator('.markdown table').count() === 1, 'GFM table must render');
    check(await testPage.locator('.markdown li').count() === 1, 'Markdown list must render');
    check(await testPage.evaluate(() => !window.unsafeMarkdown), 'Raw HTML must not execute');
    await testPage.setViewportSize({width:375,height:900});
    check(await testPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Markdown table must stay inside mobile viewport');
    await testPage.setViewportSize({width:1440,height:900});
    results.push('Chat contract, loading, duplicate submit, safe Markdown bold/list/table');

    fail = true;
    await input.fill('Give me a summary of project 999.');
    await input.press('Enter');
    await testPage.getByRole('alert').waitFor();
    check(await testPage.locator('.markdown').count() === 0, 'Failed request must clear stale answer');
    check(await testPage.getByRole('button', { name: 'Send question' }).isEnabled(), 'Failure must reset loading');
    results.push('Network failure recovery and stale-answer clearing');

    await testPage.getByRole('button', { name: 'Critical only' }).click();
    check(await testPage.locator('.rfi-table tbody tr').count() === 2, 'Critical filter should show IDs 1 and 3');
    check((await testPage.locator('.rfi-table tbody').innerText()).includes('RFI-003'), 'Critical ID 3 missing');
    await testPage.getByRole('button', { name: 'All RFIs', exact: true }).click();
    check(await testPage.locator('.rfi-table tbody tr').count() === 3, 'All filter should show three RFIs');
    results.push('Backend critical IDs and RFI filtering');

    for (const width of [375, 768, 1440]) {
      await testPage.setViewportSize({ width, height: 900 });
      check(await testPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Page overflow at ${width}px`);
      if (width < 768) await testPage.getByRole('button', { name: 'Open navigation' }).click();
      await testPage.getByRole('link', { name: 'AI Assistant', exact: true }).click();
      check(new URL(testPage.url()).hash === '#assistant', 'Assistant navigation should reach section');
      await input.focus();
      check(await input.evaluate(el => el === document.activeElement), 'Question must be focusable');
    }
    results.push('375/768/1440 layouts, navigation and keyboard focus');

    await testPage.setViewportSize({width:375,height:900});
    await testPage.getByRole('button', {name:'Open navigation'}).click();
    await testPage.getByRole('button', {name:'Close navigation'}).focus();
    await testPage.keyboard.press('Shift+Tab');
    check(await testPage.getByRole('link', {name:'RFI Register',exact:true}).evaluate(el => el === document.activeElement), 'Drawer must contain keyboard focus');
    await testPage.keyboard.press('Escape');
    await testPage.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Open navigation');
    await testPage.getByRole('button', {name:'Open navigation'}).click();
    await testPage.setViewportSize({width:1440,height:900});
    await testPage.waitForFunction(() => !document.querySelector('.workspace').inert);
    results.push('Mobile drawer focus trap, Escape and desktop resize recovery');

    await testPage.route('http://127.0.0.1:8000/projects', route => route.fulfill({json:[{id:101,name:'Malformed sample',status:'active',rfis:[null]}]}));
    await testPage.reload();
    await testPage.getByRole('alert').waitFor({timeout:5000});
    results.push('Malformed project data produces a recoverable error');
    await testPage.unroute('http://127.0.0.1:8000/projects');
    await testPage.getByRole('button', {name:'Retry',exact:true}).click();
    await testPage.getByRole('heading', {name:'Naples Medical Center',exact:true}).waitFor();
    await testPage.route('http://127.0.0.1:8000/projects', route => route.fulfill({json:[]}));
    await testPage.reload();
    await testPage.getByRole('heading', {name:'No projects available',exact:true}).waitFor();
    check((await testPage.locator('.metric-value').first().innerText()).includes('Unavailable'), 'Empty dataset must not fabricate counts');
    results.push('Project retry and empty dataset');
    return results;
  } finally {
    await context.close();
  }
}
