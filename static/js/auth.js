/**
 * AROMA CAFE — AUTHENTICATION & PATRON ONBOARDING CONTROLLER
 * Strict Indian Mobile (10 Digits starting 6-9) & Password only (NO EMAIL).
 */

let currentAuthMode = 'signin';
let verifiedResetMobile = '';

function setAuthMode(mode) {
  currentAuthMode = mode;
  const isSignup = mode === 'signup';

  // Toggle button styling
  document.getElementById('modeBtn-signin')?.classList.toggle('btn-pill-primary', !isSignup);
  document.getElementById('modeBtn-signin')?.classList.toggle('btn-pill-secondary', isSignup);
  document.getElementById('modeBtn-signup')?.classList.toggle('btn-pill-primary', isSignup);
  document.getElementById('modeBtn-signup')?.classList.toggle('btn-pill-secondary', !isSignup);

  // Toggle signup fields
  document.getElementById('authField-name')?.classList.toggle('hidden', !isSignup);
  document.getElementById('authField-confirm')?.classList.toggle('hidden', !isSignup);
  document.getElementById('passwordStrengthBox')?.classList.toggle('hidden', !isSignup);

  // Update text
  const heading = document.getElementById('authHeading');
  const subheading = document.getElementById('authSubheading');
  const btnLabel = document.getElementById('authBtnLabel');

  if (isSignup) {
    if (heading) heading.textContent = 'Join Patron Circle';
    if (subheading) subheading.textContent = 'Create your account with your mobile number to access dining rewards and table receipts.';
    if (btnLabel) btnLabel.textContent = 'Complete Registration';
  } else {
    if (heading) heading.textContent = 'Welcome Back';
    if (subheading) subheading.textContent = 'Sign in with your mobile number to view past orders and tables.';
    if (btnLabel) btnLabel.textContent = 'Sign In to Sanctuary';
  }

  // Clear alerts
  clearAllErrors();
}

function togglePasswordVisibility(inputId, iconId) {
  const input = document.getElementById(inputId);
  const icon = document.getElementById(iconId);
  if (!input) return;

  if (input.type === 'password') {
    input.type = 'text';
    if (icon) {
      icon.innerHTML = `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>`;
    }
  } else {
    input.type = 'password';
    if (icon) {
      icon.innerHTML = `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>`;
    }
  }
}

function checkPasswordStrength(val) {
  const bar1 = document.getElementById('strengthBar1');
  const bar2 = document.getElementById('strengthBar2');
  const bar3 = document.getElementById('strengthBar3');
  const label = document.getElementById('strengthText');
  if (!bar1 || !label) return;

  let score = 0;
  if (val.length >= 8) score++;
  if (val.length >= 10 && /[0-9]/.test(val) && /[a-zA-Z]/.test(val)) score++;
  if (val.length >= 12 && /[^a-zA-Z0-9]/.test(val)) score++;

  bar1.style.backgroundColor = '#E5E7EB';
  bar2.style.backgroundColor = '#E5E7EB';
  bar3.style.backgroundColor = '#E5E7EB';

  if (score === 1) {
    bar1.style.backgroundColor = '#EF4444';
    label.textContent = 'Fair — min 8 characters';
    label.style.color = '#EF4444';
  } else if (score === 2) {
    bar1.style.backgroundColor = '#F59E0B';
    bar2.style.backgroundColor = '#F59E0B';
    label.textContent = 'Good strength';
    label.style.color = '#F59E0B';
  } else if (score >= 3) {
    bar1.style.backgroundColor = '#10B981';
    bar2.style.backgroundColor = '#10B981';
    bar3.style.backgroundColor = '#10B981';
    label.textContent = 'Strong password';
    label.style.color = '#10B981';
  } else {
    label.textContent = 'Minimum 8 characters required';
    label.style.color = '#78716C';
  }
}

function clearAllErrors() {
  const alert = document.getElementById('authAlert');
  if (alert) alert.className = 'hidden';
  ['name', 'mobile', 'password', 'confirm'].forEach(f => {
    const err = document.getElementById(`authError-${f}`);
    if (err) err.className = 'form-error hidden';
  });
}

function showFieldError(field, msg) {
  const err = document.getElementById(`authError-${field}`);
  if (err) {
    err.textContent = msg;
    err.classList.remove('hidden');
  }
}

function showTopAlert(msg, type = 'error') {
  const alert = document.getElementById('authAlert');
  if (!alert) return;
  alert.textContent = msg;
  if (type === 'error') {
    alert.style.backgroundColor = '#FEF2F2';
    alert.style.border = '1px solid #FCA5A5';
    alert.style.color = '#991B1B';
  } else {
    alert.style.backgroundColor = '#ECFDF5';
    alert.style.border = '1px solid #A7F3D0';
    alert.style.color = '#065F46';
  }
  alert.classList.remove('hidden');
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  clearAllErrors();

  const mobileInput = document.getElementById('authInput-mobile')?.value.trim();
  const password = document.getElementById('authInput-password')?.value;
  const submitBtn = document.getElementById('authSubmitBtn');

  // Normalize mobile
  let cleanMobile = mobileInput.replace(/[\s\-\(\)\.]/g, '');
  if (cleanMobile.startsWith('+91')) cleanMobile = cleanMobile.substring(3);
  if (cleanMobile.startsWith('91') && cleanMobile.length === 12) cleanMobile = cleanMobile.substring(2);
  if (cleanMobile.startsWith('0') && cleanMobile.length === 11) cleanMobile = cleanMobile.substring(1);

  if (!/^[6-9]\d{9}$/.test(cleanMobile)) {
    showFieldError('mobile', 'Please enter a valid 10-digit Indian mobile number (starts 6-9).');
    return;
  }

  if (!password || password.length < 8) {
    showFieldError('password', 'Password must be at least 8 characters long.');
    return;
  }

  if (currentAuthMode === 'signup') {
    const name = document.getElementById('authInput-name')?.value.trim();
    const confirm = document.getElementById('authInput-confirm')?.value;

    if (!name || name.length < 2) {
      showFieldError('name', 'Full Name must be at least 2 characters.');
      return;
    }
    if (password !== confirm) {
      showFieldError('confirm', 'Passwords do not match.');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Registering patron account...';

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, mobile: cleanMobile, password, confirm_password: confirm })
      });
      const data = await res.json();
      if (data.success) {
        showTopAlert('Welcome to Aroma Cafe! Redirecting...', 'success');
        const nextUrl = new URLSearchParams(window.location.search).get('next') || '/account';
        setTimeout(() => window.location.href = nextUrl, 1000);
      } else {
        showTopAlert(data.error || 'Registration failed.', 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Complete Registration';
      }
    } catch (err) {
      showTopAlert('Network error during registration.', 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Complete Registration';
    }

  } else {
    // SIGN IN
    submitBtn.disabled = true;
    submitBtn.textContent = 'Authenticating...';

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mobile: cleanMobile, password })
      });
      const data = await res.json();

      if (data.success) {
        showTopAlert('Authenticated successfully. Redirecting...', 'success');
        const nextUrl = new URLSearchParams(window.location.search).get('next') || '/account';
        setTimeout(() => window.location.href = nextUrl, 800);
      } else {
        showTopAlert(data.error || 'Authentication rejected.', 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In to Sanctuary';
      }
    } catch (err) {
      showTopAlert('Network error during sign in.', 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Sign In to Sanctuary';
    }
  }
}

// -------------------------------------------------------------
// FORGOT PASSWORD (STUB MOBILE OTP MODAL)
// -------------------------------------------------------------
function openForgotPasswordModal() {
  document.getElementById('forgotPasswordModal')?.classList.remove('hidden');
  document.getElementById('forgotStep1')?.classList.remove('hidden');
  document.getElementById('forgotStep2')?.classList.add('hidden');
  const alert1 = document.getElementById('forgotAlert1');
  if (alert1) alert1.className = 'hidden';
}

function closeForgotPasswordModal() {
  document.getElementById('forgotPasswordModal')?.classList.add('hidden');
}

async function sendMobileOTP() {
  const rawMobile = document.getElementById('forgotInput-mobile')?.value.trim();
  const alert1 = document.getElementById('forgotAlert1');
  const btn = document.getElementById('sendOtpBtn');

  let clean = rawMobile.replace(/[\s\-\(\)\.]/g, '');
  if (clean.startsWith('+91')) clean = clean.substring(3);
  if (!/^[6-9]\d{9}$/.test(clean)) {
    alert1.textContent = 'Please enter a valid 10-digit mobile number.';
    alert1.className = 'form-error';
    alert1.style.color = '#991B1B';
    alert1.classList.remove('hidden');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Dispatching OTP...';

  try {
    const res = await fetch('/api/auth/forgot-password/send-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mobile: clean })
    });
    const data = await res.json();

    if (data.success) {
      verifiedResetMobile = clean;
      document.getElementById('forgotStep1')?.classList.add('hidden');
      document.getElementById('forgotStep2')?.classList.remove('hidden');
      
      const alert2 = document.getElementById('forgotAlert2');
      if (alert2) {
        alert2.innerHTML = `<strong>Verification Code Dispatched!</strong><br/>Demo Stub OTP: <span style="font-family:monospace;font-size:14px;color:#065F46;">${data.stub_otp}</span>`;
        alert2.style.backgroundColor = '#ECFDF5';
        alert2.style.border = '1px solid #A7F3D0';
        alert2.style.color = '#065F46';
        alert2.classList.remove('hidden');
      }
    } else {
      alert1.textContent = data.error || 'Failed to dispatch OTP.';
      alert1.style.color = '#991B1B';
      alert1.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'Dispatch Verification Code →';
    }
  } catch (e) {
    alert1.textContent = 'Network communication error.';
    alert1.style.color = '#991B1B';
    alert1.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Dispatch Verification Code →';
  }
}

async function verifyOtpAndReset() {
  const otp = document.getElementById('forgotInput-otp')?.value.trim();
  const new_password = document.getElementById('forgotInput-newPassword')?.value;
  const confirm_password = document.getElementById('forgotInput-confirmPassword')?.value;
  const alert2 = document.getElementById('forgotAlert2');
  const btn = document.getElementById('verifyResetBtn');

  if (!otp || otp.length < 6) {
    alert2.textContent = 'Please enter the 6-digit OTP.';
    alert2.style.color = '#991B1B';
    alert2.classList.remove('hidden');
    return;
  }

  if (!new_password || new_password.length < 8) {
    alert2.textContent = 'New password must be at least 8 characters long.';
    alert2.style.color = '#991B1B';
    alert2.classList.remove('hidden');
    return;
  }

  if (new_password !== confirm_password) {
    alert2.textContent = 'Passwords do not match.';
    alert2.style.color = '#991B1B';
    alert2.classList.remove('hidden');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Saving password...';

  try {
    const res = await fetch('/api/auth/forgot-password/verify-reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mobile: verifiedResetMobile,
        otp,
        new_password,
        confirm_password
      })
    });
    const data = await res.json();

    if (data.success) {
      alert(data.message || 'Password reset successfully! Please sign in with your new password.');
      closeForgotPasswordModal();
      setAuthMode('signin');
      const mobileField = document.getElementById('authInput-mobile');
      if (mobileField) mobileField.value = verifiedResetMobile;
    } else {
      alert2.textContent = data.error || 'Password reset failed.';
      alert2.style.color = '#991B1B';
      alert2.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'Save New Password & Sign In';
    }
  } catch (e) {
    alert2.textContent = 'Network communication error.';
    alert2.style.color = '#991B1B';
    alert2.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Save New Password & Sign In';
  }
}
