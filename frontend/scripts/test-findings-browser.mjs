import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';

// Uses mocked network responses: no demo-user posts are written to the backend.
const browser = await chromium.launch({ headless: true, executablePath: process.env.BROWSER_EXE ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' });
try {
  const context = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
  let post = null;
  const comments = [];
  const bands = ['starlight', 'hydrogen', 'helium', 'water-ice', 'co2-ice', 'co-ice', 'organic-dust', 'methane', 'warm-glow'];
  const area = { id: '10.00000_20.00000', name: 'Test region', center: { ra: 10, dec: 20 }, extentDeg: .2187, sizePx: 128,
    pixelScaleArcsec: 6.15, minFovDeg: .06, maxFovDeg: .98, layers: [],
    levels: [{ level: 0, extentDeg: .2187, sizePx: 128, pixelScaleArcsec: 6.15 }],
    epochs: [0, 1, 2, 3].map((i) => ({ id: `epoch${i}`, date: `2025-07-0${i+1}T00:00:00Z`, bands: [i < 2 ? 'starlight' : 'co2-ice'] })),
    bands: bands.map((id) => ['starlight', 'co2-ice'].includes(id) ? { id, state: 'ok', empty: null } : { id, state: 'no-coverage', reason: 'No observation' }) };
  await context.addInitScript(() => sessionStorage.setItem('pulsr.share-draft', JSON.stringify({
    areaName: 'Test region', box: { ra: 10, dec: 20, width: .005, height: .005 },
    bands: ['co2-ice'], epochs: ['epoch2', 'epoch3'], spectrum: null, mover: null,
    view: { ra: 10, dec: 20, fov: .2 }, viewUrl: 'http://localhost:3000/explore?ra=10&dec=20',
  })));
  await context.route('**/api/explore/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/explore', '');
    let json;
    if (path === '/session') json = { account: { id: 'alex-rivera', name: 'Alex Rivera', mode: 'demo' }, ai_available: false };
    else if (path === '/area') json = area;
    else if (path.includes('/frames/')) return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==', 'base64') });
    else if (path === '/findings/match') json = { finding: post };
    else if (path === '/findings' && request.method() === 'POST') {
      const draft = request.postDataJSON();
      post = { ...draft, author: 'Alex Rivera', id: 'browser-test-post', status: 'suspected-motion', created_at: new Date().toISOString(), evidence: { bands: draft.bands, epochs: draft.epochs, track: draft.track, view: draft.view } };
      json = { created: true, finding: post };
    } else if (path.endsWith('/comments')) {
      comments.push({ ...request.postDataJSON(), author: 'Alex Rivera', id: 'comment1', created_at: new Date().toISOString() });
      json = comments.at(-1);
    } else if (path === '/findings/browser-test-post') json = { finding: post, comments };
    else if (path === '/markers') json = { markers: [
      { id: 'known', ra: 10.03, dec: 20, name: 'Known star', kind: 'identified', basis: 'catalog', epoch: 'all', source: 'Test catalog' },
      ...(post ? [{ id: post.id, ra: 10, dec: 20, name: post.title, kind: 'finding' }] : []),
    ] };
    else json = {};
    await route.fulfill({ json });
  });
  const page = await context.newPage();
  await page.goto('http://localhost:3000/explore?ra=10&dec=20&fov=.2');
  const co2 = page.getByRole('switch').filter({ hasText: 'CO₂-ice region' });
  await co2.waitFor();
  await co2.click();
  await page.waitForFunction(() => [...document.querySelectorAll('[role="switch"]')].some((el) => el.textContent.includes('CO₂-ice region') && el.getAttribute('aria-checked') === 'true'));
  assert.equal(await co2.getAttribute('aria-checked'), 'true');
  await page.getByRole('button', { name: 'Catalog match: Known star', exact: true }).waitFor();
  await page.goto('http://localhost:3000/share');
  await page.getByLabel('Title', { exact: true }).fill('Possible motion in this region');
  await page.getByLabel('What changed between observations?').fill('The source shifts between the selected observations while background sources stay aligned.');
  assert.equal(await page.getByRole('textbox', { name: /^Display name/ }).count(), 0);
  await page.getByRole('button', { name: 'Create discussion post' }).click();
  await page.waitForURL('**/findings/browser-test-post');
  await page.getByRole('heading', { name: 'Possible motion in this region' }).waitFor();
  assert.equal(await page.getByRole('textbox', { name: /^Display name/ }).count(), 0);
  await page.getByLabel('Add evidence or discuss').fill('Compare the nearby stars to rule out alignment drift.');
  await page.getByRole('button', { name: 'Post comment' }).click();
  await page.getByText('Compare the nearby stars to rule out alignment drift.', { exact: true }).waitFor();
  await page.goto('http://localhost:3000/share');
  await page.getByRole('link', { name: 'Possible motion in this region' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Create discussion post' }).count(), 0);
  await page.goto('http://localhost:3000/explore?ra=10&dec=20&fov=.2');
  await page.getByRole('button', { name: 'Discussion: Possible motion in this region', exact: true }).click();
  await page.getByRole('dialog', { name: 'Discussion preview' }).waitFor();
  assert.match(page.url(), /\/explore\?/);
  const discussionsSwitch = page.getByRole('switch', { name: 'Show discussion posts', exact: true });
  await discussionsSwitch.click();
  assert.equal(await discussionsSwitch.getAttribute('aria-checked'), 'false');
  assert.equal(await page.getByRole('dialog', { name: 'Discussion preview' }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Discussion: Possible motion in this region', exact: true }).count(), 0);
  await page.getByRole('button', { name: 'Catalog match: Known star', exact: true }).waitFor();
  await discussionsSwitch.click();
  await page.getByRole('button', { name: 'Discussion: Possible motion in this region', exact: true }).click();
  await page.getByRole('dialog', { name: 'Discussion preview' }).waitFor();
  await page.getByRole('button', { name: 'Open discussion', exact: true }).click();
  await page.waitForURL('**/findings/browser-test-post');
  console.log('PASS: isolated window switch, known marker, current account, create finding, comment, duplicate lookup, preview card before navigation');
} finally {
  await browser.close();
}
