const { setupInactivityTimer } = require('./inactivity');

describe('inactivity timeout', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    document.body.innerHTML = '<div id="inactivity-modal" style="display:none"><div id="modal-content"><span id="countdown">30</span><button id="stay-logged-in">Stay</button></div></div>';
    global.fetch = jest.fn().mockResolvedValue({ ok: true });
  });
  afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); delete global.fetch; });

  test('staying logged in resets the full idle period', () => {
    setupInactivityTimer(1);
    jest.advanceTimersByTime(60000);
    expect(document.getElementById('inactivity-modal').style.display).toBe('flex');
    document.getElementById('stay-logged-in').click();
    jest.advanceTimersByTime(59000);
    expect(document.getElementById('inactivity-modal').style.display).toBe('none');
    jest.advanceTimersByTime(1000);
    expect(document.getElementById('inactivity-modal').style.display).toBe('flex');
  });

  test('expires once after the warning countdown', async () => {
    setupInactivityTimer(1);
    jest.advanceTimersByTime(90000);
    await Promise.resolve();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith('/logout', { method: 'POST' });
    expect(document.getElementById('modal-content').textContent).toContain('You have been logged out');
    jest.advanceTimersByTime(90000);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
