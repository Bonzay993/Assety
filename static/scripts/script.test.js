const { passwordValidator } = require('./script');

describe('passwordValidator', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <form>
        <div class="sign-up-form-group">
          <input id="password" />
        </div>
        <div class="sign-up-form-group">
          <input id="confirm-password" />
        </div>
        <button type="submit"></button>
      </form>
    `;
  });

  test('adds validation container only once', () => {
    passwordValidator();
    passwordValidator();
    expect(document.querySelectorAll('.password-validation').length).toBe(1);
  });

  test('enables submit button when criteria met', () => {
    passwordValidator();
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm-password');
    const submitButton = document.querySelector("button[type='submit']");

    passwordInput.value = 'pass';
    confirmInput.value = 'pass';
    passwordInput.dispatchEvent(new Event('input', { bubbles: true }));
    confirmInput.dispatchEvent(new Event('input', { bubbles: true }));
    expect(submitButton.disabled).toBe(true);

    passwordInput.value = 'Password';
    confirmInput.value = 'Password';
    passwordInput.dispatchEvent(new Event('input', { bubbles: true }));
    confirmInput.dispatchEvent(new Event('input', { bubbles: true }));
    expect(submitButton.disabled).toBe(false);
  });

  test('hides validation messages before typing', () => {
    passwordValidator();
    const rules = Array.from(document.querySelectorAll('.password-validation p'));
    expect(rules.length).toBe(3);
    rules.forEach(rule => {
      expect(rule.style.display).toBe('none');
    });
  });

  test('shows validation rules on password focus', () => {
    passwordValidator();
    const passwordInput = document.getElementById('password');
    passwordInput.dispatchEvent(new Event('focus', { bubbles: true }));
    const rules = Array.from(document.querySelectorAll('.password-validation p'));
    rules.forEach(rule => {
      expect(rule.style.display).toBe('block');
    });
  });

  test('shows mismatch message when passwords differ', () => {
    passwordValidator();
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm-password');
    passwordInput.value = 'Password1';
    confirmInput.value = 'Password2';
    passwordInput.dispatchEvent(new Event('input', { bubbles: true }));
    confirmInput.dispatchEvent(new Event('input', { bubbles: true }));
    const matchRule = document.getElementById('match');
    expect(matchRule.innerHTML).toContain('❌');
    expect(matchRule.style.color).toBe('red');
  });
});
