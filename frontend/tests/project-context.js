// Run through Playwright MCP browser_run_code_unsafe. All API responses are mocked.
async (page) => {
  const context = await page.context().browser().newContext();
  const testPage = await context.newPage();
  const check = (value, message) => { if (!value) throw new Error(message); };
  let empty = false;
  const requests = [];
  try {
    await testPage.route('http://127.0.0.1:8000/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/ai/chat') {
        requests.push(route.request().postDataJSON());
        return route.fulfill({json:{answer:'**Sample answer**'}});
      }
      if (path === '/projects') return route.fulfill({json:empty ? [] : [
        {id:101,name:'Naples Medical Center',status:'active',rfis:[]},
        {id:202,name:'Synthetic context test project',status:'active',rfis:[]},
      ]});
      if (path.endsWith('/summary')) return route.fulfill({json:{project_name:'Sample',total_rfis:0,critical_rfis:0,blocking_rfis:0}});
      return route.fulfill({json:[]});
    });
    await testPage.goto('http://localhost:5173');
    const select = testPage.getByRole('combobox', {name:'Select project'});
    const input = testPage.getByRole('textbox', {name:'Your project question'});
    await select.waitFor();
    for (const id of [101, 202]) {
      await select.selectOption(String(id));
      await input.fill('Which RFIs are critical?');
      await input.press('Enter');
      await testPage.locator('.markdown strong').waitFor();
      check(requests.at(-1).project_id === id, 'Chat must use current selection');
      check(requests.at(-1).message === 'Which RFIs are critical?', 'User text must remain unchanged');
    }
    empty = true;
    await testPage.reload();
    await testPage.getByRole('heading', {name:'No projects available',exact:true}).waitFor();
    await input.fill('Which RFIs are critical?');
    await input.press('Enter');
    await testPage.locator('.markdown strong').waitFor();
    check(!Object.hasOwn(requests.at(-1), 'project_id'), 'No selection must not invent a project');
    return ['Selected 101 passed', 'Changed selection 202 passed', 'No selection omitted context'];
  } finally {
    await context.close();
  }
}
