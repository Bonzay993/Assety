const { setupSearch } = require('./search');
const flush = async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); };

describe('asset search suggestions', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div class="search-bar"><input class="search-input"><button class="search-icon"></button><ul class="search-suggestions"></ul></div>';
    global.fetch = jest.fn();
    setupSearch();
  });
  afterEach(() => { delete global.fetch; });
  function type(query) {
    const input = document.querySelector('input');
    input.value = query;
    input.dispatchEvent(new Event('input'));
  }
  test('uses the actual JSON endpoint and renders text safely', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => [{ asset_tag: '<b>Laptop</b>', id: '123' }] });
    type('Laptop[');
    await flush();
    expect(fetch).toHaveBeenCalledWith('/search_assets?q=Laptop%5B');
    expect(document.querySelector('li').textContent).toBe('<b>Laptop</b>');
    expect(document.querySelector('li b')).toBeNull();
  });
  test('ignores older responses after a new search', async () => {
    let resolveOld;
    fetch.mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve; }));
    fetch.mockResolvedValueOnce({ ok: true, json: async () => [{ asset_tag: 'New', id: '2' }] });
    type('Old'); type('New');
    await flush();
    resolveOld({ ok: true, json: async () => [{ asset_tag: 'Old', id: '1' }] });
    await flush();
    expect(document.querySelector('li').textContent).toBe('New');
  });
  test('clearing the input cancels pending suggestions', async () => {
    let resolve;
    fetch.mockReturnValue(new Promise(done => { resolve = done; }));
    type('Laptop'); type('');
    resolve({ ok: true, json: async () => [{ asset_tag: 'Laptop', id: '1' }] });
    await flush();
    expect(document.querySelectorAll('li')).toHaveLength(0);
  });
});
