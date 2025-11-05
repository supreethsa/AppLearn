// site.js
document.addEventListener('DOMContentLoaded', () => {
  // --- keep your existing non-auth code here (animations, etc.) ---
  try {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((e) => e.isIntersecting && e.target.classList.add('show'));
    });
    document.querySelectorAll('.hidden').forEach((el) => observer.observe(el));
  } catch (_) {}

  // ------- Auth UI toggle (simple inline welcome + logout) -------
const loginBtn  = document.getElementById('loginNavBtn');
const signupBtn = document.getElementById('signupNavBtn');
const logoutBtn = document.getElementById('logoutNavBtn');
const btnContainer = document.querySelector('.button-container');

let welcomeWrapper = document.getElementById('welcomeWrapper');
let welcomeSpan = document.getElementById('welcomeMsg');
let roleSpan = document.getElementById('welcomeRole');

if (btnContainer) {
  if (!welcomeWrapper) {
    welcomeWrapper = document.createElement('div');
    welcomeWrapper.id = 'welcomeWrapper';
    welcomeWrapper.className = 'welcome-wrapper';
    btnContainer.insertBefore(welcomeWrapper, logoutBtn || null);
  }
  if (!welcomeSpan) {
    welcomeSpan = document.createElement('span');
    welcomeSpan.id = 'welcomeMsg';
    welcomeWrapper.appendChild(welcomeSpan);
  }
  if (!roleSpan) {
    roleSpan = document.createElement('span');
    roleSpan.id = 'welcomeRole';
    welcomeWrapper.appendChild(roleSpan);
  }
}

function setLoggedOut() {
  if (welcomeSpan) welcomeSpan.textContent = '';
  if (roleSpan) roleSpan.textContent = '';
  if (logoutBtn)  logoutBtn.style.display = 'none';
  if (loginBtn)   loginBtn.style.display  = 'inline-block';
  if (signupBtn)  signupBtn.style.display = 'inline-block';
}

function formatRole(role) {
  if (!role) return '';
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function setLoggedIn(firstName, role) {
  if (welcomeSpan) welcomeSpan.textContent = firstName ? `Welcome, ${firstName}!` : 'Welcome!';
  if (roleSpan) roleSpan.textContent = formatRole(role);
  if (logoutBtn)  logoutBtn.style.display = 'inline-block';
  if (loginBtn)   loginBtn.style.display  = 'none';
  if (signupBtn)  signupBtn.style.display = 'none';
}

fetch('/api/me')
  .then(r => r.ok ? r.json() : Promise.reject())
  .then(me => me.authenticated ? setLoggedIn(me.first_name, me.role) : setLoggedOut())
  .catch(() => setLoggedOut());

if (logoutBtn) {
  logoutBtn.addEventListener('click', async () => {
    try { await fetch('/api/logout', { method: 'POST' }); }
    finally {
      setLoggedOut();
      window.location.href = 'Home.html';
    }
  });
}

  // ======== to here (end of new auth code) ========
});
