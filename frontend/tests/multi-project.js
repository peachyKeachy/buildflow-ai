// Playwright MCP browser_run_code_unsafe; actual project API, mocked chat (no paid calls).
async (page) => {
  const context = await page.context().browser().newContext();
  const tab = await context.newPage();
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const requests = [];
  try {
    await tab.route('http://127.0.0.1:8000/ai/chat', async route => {
      requests.push(route.request().postDataJSON());
      await route.fulfill({json:{answer:'**Synthetic sample response**'}});
    });
    await tab.goto('http://localhost:5173');
    const select = tab.getByRole('combobox',{name:'Select project'});
    await select.waitFor();
    check(await select.locator('option').count() === 3, 'Expected three project options');
    const results = [];
    for (const [id, name, total, critical, blocking] of [
      [101,'Naples Medical Center',3,2,2], [202,'Gulfshore Residential Tower',6,2,3],
      [303,'Southwest Logistics Center',5,1,2], [101,'Naples Medical Center',3,2,2],
    ]) {
      await select.selectOption(String(id));
      await tab.getByRole('heading',{name,exact:true}).waitFor();
      await tab.waitForFunction(expected => document.querySelectorAll('.rfi-table tbody tr').length === expected, total);
      await tab.getByRole('button',{name:'Critical only',exact:true}).click();
      check(await tab.locator('.rfi-table tbody tr').count() === critical, 'Critical count mismatch');
      await tab.getByRole('button',{name:'All RFIs',exact:true}).click();
      const metrics = await tab.locator('.metric-value').allTextContents();
      check(metrics[0].includes(String(total)) && metrics[1].includes(String(critical)) && metrics[2].includes(String(blocking)), 'KPI mismatch');
      await tab.getByRole('textbox',{name:'Your project question'}).fill('Which RFIs are critical?');
      await tab.getByRole('button',{name:'Send question'}).click();
      await tab.locator('.markdown strong').waitFor();
      check(requests.at(-1).project_id === id, 'Chat context did not follow selection');
      results.push(`Project ${id}: KPIs, RFIs, filtering, and chat context passed`);
    }
    return results;
  } finally { await context.close(); }
}
