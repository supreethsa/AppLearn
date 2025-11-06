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
  initGameLaunchers();
  initVideoTracking();
});

function initGameLaunchers() {
  const buttons = Array.from(document.querySelectorAll('.game-launch-btn[data-video-id][data-game-url]'));
  if (!buttons.length) return;

  const statusByGame = new Map();
  document.querySelectorAll('.game-launch-status').forEach((el) => {
    const key = el.dataset.targetGame || el.dataset.targetVideo || el.dataset.targetId;
    if (key) {
      statusByGame.set(key, el);
    }
  });

  const state = { checkedAuth: false, loggedIn: false };
  const activeButtons = new Set();

  async function ensureAuth() {
    if (state.checkedAuth) {
      return state.loggedIn;
    }
    state.checkedAuth = true;
    try {
      const res = await fetch('/api/me', { credentials: 'include' });
      if (!res.ok) {
        state.loggedIn = false;
        return state.loggedIn;
      }
      const data = await res.json();
      state.loggedIn = !!(data && data.authenticated);
    } catch (_) {
      state.loggedIn = false;
    }
    return state.loggedIn;
  }

  const newSessionId = () => {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  };

  const formatTime = (seconds) => {
    const total = Math.max(0, Math.round(seconds));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  function showGamePrompt(message) {
    return new Promise(resolve => {
      const existing = document.querySelector('.game-confirm-backdrop');
      if (existing) {
        existing.remove();
      }

      const backdrop = document.createElement('div');
      backdrop.className = 'game-confirm-backdrop';
      const dialog = document.createElement('div');
      dialog.className = 'game-confirm-dialog';

      const heading = document.createElement('h3');
      heading.textContent = 'Ready to play?';

      const body = document.createElement('p');
      body.textContent = message || 'Please keep the game open and active to earn credit.';

      const buttonsWrap = document.createElement('div');
      buttonsWrap.className = 'game-confirm-buttons';

      const cancelBtn = document.createElement('button');
      cancelBtn.type = 'button';
      cancelBtn.className = 'game-confirm-cancel';
      cancelBtn.textContent = 'Not yet';

      const startBtn = document.createElement('button');
      startBtn.type = 'button';
      startBtn.className = 'game-confirm-start';
      startBtn.textContent = 'Start game';

      buttonsWrap.append(cancelBtn, startBtn);
      dialog.append(heading, body, buttonsWrap);
      backdrop.append(dialog);

      const activeElement = document.activeElement;

      function cleanup(result) {
        backdrop.classList.remove('is-visible');
        const removeBackdrop = () => {
          if (backdrop.parentNode) {
            backdrop.parentNode.removeChild(backdrop);
          }
        };
        backdrop.addEventListener('transitionend', removeBackdrop, { once: true });
        window.setTimeout(removeBackdrop, 220);
        document.removeEventListener('keydown', handleKey);
        if (activeElement && typeof activeElement.focus === 'function') {
          activeElement.focus();
        }
        resolve(result);
      }

      function handleKey(evt) {
        if (evt.key === 'Escape') {
          evt.preventDefault();
          cleanup(false);
        }
      }

      cancelBtn.addEventListener('click', () => cleanup(false));
      startBtn.addEventListener('click', () => cleanup(true));
      backdrop.addEventListener('click', (evt) => {
        if (evt.target === backdrop) {
          cleanup(false);
        }
      });

      document.addEventListener('keydown', handleKey);

      document.body.appendChild(backdrop);
      window.setTimeout(() => {
        backdrop.classList.add('is-visible');
        startBtn.focus();
      }, 10);
    });
  }

  async function postAttempt(gameId, sessionId) {
    const payload = {
      video_id: gameId,
      session_id: sessionId,
      attempt: 1,
      seconds_delta: 0,
      position: 0,
      duration: 0,
    };
    const res = await fetch('/api/video/progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    if (res.status === 401) {
      state.loggedIn = false;
      throw new Error('Not authenticated');
    }
    if (!res.ok) {
      throw new Error(`Attempt tracking failed with status ${res.status}`);
    }
  }

  async function postCompletion(videoId, sessionId, seconds) {
    const payload = {
      video_id: videoId,
      session_id: sessionId,
      seconds_delta: seconds,
      position: seconds,
      duration: seconds,
      completed: 1,
    };
    const res = await fetch('/api/video/progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    });
    if (res.status === 401) {
      state.loggedIn = false;
      throw new Error('Not authenticated');
    }
    if (!res.ok) {
      throw new Error(`Progress update failed with status ${res.status}`);
    }
  }

  function clearButtonTimer(btn, { message = '', isError = false } = {}) {
    if (!btn) return;
    if (btn.__gameTimeout) {
      window.clearTimeout(btn.__gameTimeout);
    }
    if (btn.__countdownInterval) {
      window.clearInterval(btn.__countdownInterval);
    }
    btn.__gameTimeout = null;
    btn.__countdownInterval = null;
    btn.disabled = false;
    delete btn.__remainingSeconds;
    activeButtons.delete(btn);
    const statusEl = statusByGame.get(btn.dataset.gameId || btn.dataset.videoId);
    if (statusEl) {
      statusEl.textContent = message;
      if (isError) {
        statusEl.classList.add('is-error');
      } else {
        statusEl.classList.remove('is-error');
      }
    }
  }

  function resetAllTimers(messageFactory) {
    if (!activeButtons.size) return;
    activeButtons.forEach((btn) => {
      const requiredSeconds = Number(btn.dataset.gameSeconds) || 10;
      const remaining = typeof btn.__remainingSeconds === 'number'
        ? Math.max(0, Math.round(btn.__remainingSeconds))
        : requiredSeconds;
      const text = typeof messageFactory === 'function'
        ? messageFactory(requiredSeconds, remaining)
        : (messageFactory || '');
      clearButtonTimer(btn, { message: text, isError: false });
    });
    activeButtons.clear();
  }

  const resetMessage = (secondsRequired, remaining) => {
    const remainingText = formatTime(remaining);
    const requiredText = formatTime(secondsRequired);
    return `Timer reset with ${remainingText} remaining. You must complete the full ${requiredText} in one session to receive credit.`;
  };

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      resetAllTimers(resetMessage);
    }
  });
  window.addEventListener('pagehide', () => resetAllTimers(resetMessage));
  window.addEventListener('beforeunload', () => resetAllTimers(resetMessage));
  window.addEventListener('pageshow', (evt) => {
    if (evt.persisted) {
      resetAllTimers(resetMessage);
    }
  });

  buttons.forEach((btn) => {
    const videoId = btn.dataset.videoId;
    const gameId = btn.dataset.gameId || videoId;
    const statusEl = statusByGame.get(gameId) || null;

    btn.addEventListener('click', async (evt) => {
      evt.preventDefault();
      const url = btn.dataset.gameUrl;
      if (!url) return;

      const canTrack = await ensureAuth();
      if (!canTrack) {
        if (statusEl) {
          statusEl.textContent = 'Sign in to track this game.';
          statusEl.classList.add('is-error');
        }
        return;
      }

      const promptMessage = btn.dataset.gamePrompt
        || 'Please keep the game open and active for 5 minutes to receive credit. Ready to start?';
      const confirmed = await showGamePrompt(promptMessage);
      if (!confirmed) {
        if (statusEl) {
          statusEl.classList.remove('is-error');
          statusEl.textContent = 'Launch cancelled. Click Play Game when you are ready.';
        }
        return;
      }

      const targetWindow = window.open(url, '_blank');
      if (targetWindow && typeof targetWindow === 'object') {
        try {
          targetWindow.opener = null;
        } catch (_) {}
      } else {
        if (statusEl) {
          statusEl.textContent = 'Pop-up blocked. Please allow pop-ups for AppLearn or open the link manually.';
          statusEl.classList.add('is-error');
        }
        return;
      }

      clearButtonTimer(btn);

      const rawSeconds = parseInt(btn.dataset.gameSeconds, 10);
      const durationSeconds = Number.isFinite(rawSeconds) && rawSeconds > 0 ? rawSeconds : 10;
      const sessionId = newSessionId();
      let attemptLogged = true;
      try {
        await postAttempt(gameId, sessionId);
      } catch (err) {
        console.warn('Failed to record game attempt', err);
        if (statusEl) {
          statusEl.textContent = 'Attempt not logged. Timer running anyway.';
          statusEl.classList.add('is-error');
        }
        attemptLogged = false;
      }

      let remaining = durationSeconds;
      const startedAt = Date.now();
      btn.disabled = true;
      activeButtons.add(btn);
      btn.__remainingSeconds = durationSeconds;
      if (statusEl && attemptLogged) {
        statusEl.classList.remove('is-error');
        statusEl.textContent = `Tracking game time: ${formatTime(remaining)} remaining`;
      }

      btn.__countdownInterval = window.setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        remaining = Math.max(0, durationSeconds - elapsed);
        btn.__remainingSeconds = remaining;
        if (statusEl) {
          const baseText = attemptLogged
            ? 'Tracking game time'
            : 'Timer running (attempt not logged)';
          statusEl.textContent = `${baseText}: ${formatTime(remaining)} remaining`;
        }
        if (remaining <= 0 && btn.__countdownInterval) {
          window.clearInterval(btn.__countdownInterval);
          btn.__countdownInterval = null;
        }
      }, 1000);

      btn.__gameTimeout = window.setTimeout(async () => {
        btn.__gameTimeout = null;
        btn.__remainingSeconds = 0;
        let finalMessage = '';
        let finalError = false;
        try {
          if (statusEl) {
            statusEl.textContent = 'Marking game complete...';
          }
          await postCompletion(gameId, sessionId, durationSeconds);
          finalMessage = 'Game marked complete! Check the dashboard for updates.';
        } catch (err) {
          finalMessage = 'Could not update progress. Try again after reloading.';
          finalError = true;
          console.warn(err);
        } finally {
          clearButtonTimer(btn, { message: finalMessage, isError: finalError });
        }
      }, durationSeconds * 1000);
    });
  });
}

function initVideoTracking() {
  const videos = Array.from(document.querySelectorAll('video.trackable-video[data-video-id]'));
  if (!videos.length) return;

  (async function bootstrapVideoTracking() {
    const state = {
      loggedIn: false,
      visible: !document.hidden,
    };

    async function checkAuth() {
      try {
        const res = await fetch('/api/me', { credentials: 'include' });
        if (!res.ok) {
          state.loggedIn = false;
          return;
        }
        const data = await res.json();
        state.loggedIn = !!(data && data.authenticated);
      } catch (err) {
        state.loggedIn = false;
      }
    }

    await checkAuth();
    if (!state.loggedIn) return;

    const newSessionId = () => {
      if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        return window.crypto.randomUUID();
      }
      return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    };

    const visibleVideos = new Set();
    const intersection = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const video = entry.target;
        if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
          visibleVideos.add(video);
        } else {
          visibleVideos.delete(video);
        }
      });
    }, { threshold: [0.5] });

    document.addEventListener('visibilitychange', () => {
      state.visible = !document.hidden;
      if (!state.visible) {
        videos.forEach(v => v.__flushProgress && v.__flushProgress(true));
      }
    });

    async function postProgress(video, extra) {
      if (!state.loggedIn) return;
      const payload = {
        video_id: video.dataset.videoId,
        seconds_delta: 0,
        position: Math.round(video.currentTime),
        duration: Math.round(video.duration || 0),
        ...extra,
      };
      if (video.__sessionId) {
        payload.session_id = video.__sessionId;
      }
      try {
        const res = await fetch('/api/video/progress', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(payload),
        });
        if (res.status === 401) {
          state.loggedIn = false;
        }
      } catch (err) {
        console.warn('progress post failed', err);
      }
    }

    videos.forEach(video => {
      intersection.observe(video);
      video.__sessionId = null;
      video.__sessionEnded = false;

      const ensureSessionId = () => {
        if (!video.__sessionId || video.__sessionEnded || video.currentTime < 1) {
          video.__sessionId = newSessionId();
          video.__sessionEnded = false;
        }
        return video.__sessionId;
      };

      let lastTime = video.currentTime;
      let accum = 0;
      let lastWall = performance.now();
      let intervalId = null;

      const flush = (force = false, extra = {}) => {
        if (!state.loggedIn) {
          accum = 0;
          return;
        }
        const seconds = Math.round(accum);
        if (!force && seconds <= 0) return;
        accum = 0;
        postProgress(video, {
          seconds_delta: seconds,
          position: Math.round(video.currentTime),
          duration: Math.round(video.duration || 0),
          ...extra,
        });
      };

      video.__flushProgress = (force = false) => flush(force);

      const tick = () => {
        if (!state.loggedIn) return;
        const shouldCount = state.visible && visibleVideos.has(video) && !video.paused && !video.ended;
        const now = performance.now();
        if (shouldCount) {
          const wallDelta = Math.max(0, (now - lastWall) / 1000);
          const current = video.currentTime;
          if (current > lastTime) {
            const delta = Math.min(current - lastTime, wallDelta + 0.25);
            accum += delta;
            lastTime = current;
          }
        } else {
          lastTime = video.currentTime;
        }
        lastWall = now;

        if (video.ended) {
          flush(true, { completed: 1 });
        } else if (accum >= 10) {
          flush();
        }
      };

      video.addEventListener('play', () => {
        ensureSessionId();
        lastTime = video.currentTime;
        lastWall = performance.now();
        if (intervalId === null) {
          intervalId = window.setInterval(tick, 1000);
        }
        postProgress(video, { seconds_delta: 0, started: 1 });
      });

      video.addEventListener('pause', () => {
        tick();
        if (intervalId !== null) {
          window.clearInterval(intervalId);
          intervalId = null;
        }
        flush(true);
      });

      video.addEventListener('ended', () => {
        tick();
        if (intervalId !== null) {
          window.clearInterval(intervalId);
          intervalId = null;
        }
        video.__sessionEnded = true;
      });

      window.addEventListener('beforeunload', () => {
        if (!state.loggedIn) return;
        const seconds = Math.round(accum);
        if (seconds <= 0) return;
        const payload = {
          video_id: video.dataset.videoId,
          seconds_delta: seconds,
          position: Math.round(video.currentTime),
          duration: Math.round(video.duration || 0),
          completed: video.ended ? 1 : 0,
        };
        if (video.__sessionId) {
          payload.session_id = video.__sessionId;
        }
        try {
          const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
          navigator.sendBeacon('/api/video/progress', blob);
        } catch (_) {}
      });
    });
  })();
}
