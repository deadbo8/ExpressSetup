/**
 * ExpressVPN Gateway — Dashboard Application
 * 
 * Pure vanilla JS single-page app controller.
 * Handles login/logout, status polling, AdGuard toggling,
 * and toast notifications with smooth animations.
 */

(function () {
    'use strict';

    /* ═══════════════════════════════════════════════════════════
       DOM References
       ═══════════════════════════════════════════════════════════ */

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // Screens
    const loginScreen     = $('#login-screen');
    const dashboardScreen = $('#dashboard-screen');

    // Login elements
    const pinInput   = $('#pin-input');
    const loginBtn   = $('#login-btn');
    const loginError = $('#login-error');

    // Header
    const modeBadge = $('#mode-badge');
    const logoutBtn = $('#logout-btn');

    // Status hero
    const statusDot   = $('#status-dot');
    const statusText  = $('#status-text');
    const serverName  = $('#server-name');
    const publicIp    = $('#public-ip');
    const currentMode = $('#current-mode');

    // AdGuard
    const adguardToggle  = $('#adguard-toggle');
    const queriesBlocked = $('#queries-blocked');
    const blockPercentage = $('#block-percentage');
    const totalQueries    = $('#total-queries');

    // Connection Info
    const protocolInfo  = $('#protocol-info');
    const uptimeInfo    = $('#uptime-info');
    const dnsInfo       = $('#dns-info');
    const gatewayIpInfo = $('#gateway-ip-info');

    // Toast container
    const toastContainer = $('#toast-container');

    /* ═══════════════════════════════════════════════════════════
       State
       ═══════════════════════════════════════════════════════════ */

    let pollInterval = null;          // status polling timer
    const POLL_DELAY = 10_000;        // 10 seconds
    let isTogglingAdguard = false;    // debounce flag

    /* ═══════════════════════════════════════════════════════════
       Toast Notification System
       ═══════════════════════════════════════════════════════════ */

    const TOAST_ICONS = {
        success: '✅',
        error:   '❌',
        info:    'ℹ️',
        warning: '⚠️',
    };

    /**
     * Show a toast notification that auto-dismisses.
     * @param {string} message   Text to display
     * @param {'success'|'error'|'info'|'warning'} type
     * @param {number} duration  Milliseconds before auto-dismiss (default 4000)
     */
    function showToast(message, type = 'info', duration = 4000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${TOAST_ICONS[type] || ''}</span>
            <span>${escapeHtml(message)}</span>
        `;

        toastContainer.appendChild(toast);

        // Auto-dismiss
        const timer = setTimeout(() => dismissToast(toast), duration);

        // Click to dismiss early
        toast.addEventListener('click', () => {
            clearTimeout(timer);
            dismissToast(toast);
        });
    }

    /** Animate toast out then remove */
    function dismissToast(el) {
        if (!el || el.classList.contains('dismissing')) return;
        el.classList.add('dismissing');
        el.addEventListener('animationend', () => el.remove(), { once: true });
    }

    /** Basic HTML escaping */
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /* ═══════════════════════════════════════════════════════════
       Screen Management
       ═══════════════════════════════════════════════════════════ */

    function showScreen(screen) {
        $$('.screen').forEach((s) => s.classList.remove('active'));
        screen.classList.add('active');
    }

    /* ═══════════════════════════════════════════════════════════
       Login Flow
       ═══════════════════════════════════════════════════════════ */

    function showLoginError(msg) {
        loginError.textContent = msg;
        loginError.classList.add('visible');
    }

    function clearLoginError() {
        loginError.textContent = '';
        loginError.classList.remove('visible');
    }

    function setLoginLoading(loading) {
        const btnText   = loginBtn.querySelector('.btn-text');
        const btnLoader = loginBtn.querySelector('.btn-loader');

        if (loading) {
            loginBtn.disabled = true;
            pinInput.disabled = true;
            btnText.textContent = 'Authenticating…';
            btnLoader.hidden = false;
        } else {
            loginBtn.disabled = false;
            pinInput.disabled = false;
            btnText.textContent = 'Access Dashboard';
            btnLoader.hidden = true;
        }
    }

    async function handleLogin() {
        const pin = pinInput.value.trim();
        if (!pin) {
            showLoginError('Please enter your PIN');
            pinInput.focus();
            return;
        }

        clearLoginError();
        setLoginLoading(true);

        try {
            await API.login(pin);
            // Successful — transition to dashboard
            showScreen(dashboardScreen);
            startDashboard();
        } catch (err) {
            const msg = err.message.toLowerCase().includes('unauthorized') || err.message.includes('401')
                ? 'Invalid PIN. Please try again.'
                : 'Connection error. Please try later.';
            showLoginError(msg);
            pinInput.value = '';
            pinInput.focus();
        } finally {
            setLoginLoading(false);
        }
    }

    /* ═══════════════════════════════════════════════════════════
       Dashboard Initialisation
       ═══════════════════════════════════════════════════════════ */

    function startDashboard() {
        // Immediate first fetch
        fetchAllData();

        // Begin polling
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(fetchAllData, POLL_DELAY);
    }

    function stopDashboard() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    /** Fetch all dashboard data in parallel */
    async function fetchAllData() {
        // Fire all requests concurrently
        const [statusResult, adguardResult, modeResult] = await Promise.allSettled([
            fetchStatus(),
            fetchAdguard(),
            fetchMode(),
        ]);

        // If all fail with network errors, show one toast
        const allFailed = [statusResult, adguardResult, modeResult].every(
            (r) => r.status === 'rejected'
        );
        if (allFailed) {
            showToast('Unable to reach the gateway API', 'error');
        }
    }

    /* ═══════════════════════════════════════════════════════════
       Status Updates
       ═══════════════════════════════════════════════════════════ */

    async function fetchStatus() {
        try {
            const data = await API.getStatus();
            updateStatusUI(data);
        } catch (err) {
            console.warn('[Status]', err.message);
        }
    }

    /**
     * Update the status hero card from the API response.
     * Expected shape: { connected, server, ip, protocol, uptime, dns, gateway_ip }
     */
    function updateStatusUI(data) {
        const isConnected = !!data.connected;

        // Status dot
        statusDot.className = `status-dot ${isConnected ? 'connected' : 'disconnected'}`;

        // Status text
        statusText.textContent = isConnected ? 'Connected' : 'Disconnected';
        statusText.className = `status-text ${isConnected ? 'connected-text' : 'disconnected-text'}`;

        // Detail values
        serverName.textContent = data.server  || '—';
        publicIp.textContent   = data.ip      || '—';
        currentMode.textContent = data.mode   || '—';

        // Connection info card
        protocolInfo.textContent  = data.protocol   || '—';
        uptimeInfo.textContent    = data.uptime      || '—';
        dnsInfo.textContent       = data.dns         || '—';
        gatewayIpInfo.textContent = data.gateway_ip  || '—';
    }

    /* ═══════════════════════════════════════════════════════════
       AdGuard
       ═══════════════════════════════════════════════════════════ */

    async function fetchAdguard() {
        try {
            const data = await API.getAdguard();
            updateAdguardUI(data);
        } catch (err) {
            console.warn('[AdGuard]', err.message);
        }
    }

    /**
     * Update AdGuard stats.
     * Expected shape: { enabled, blocked, total, percentage }
     */
    function updateAdguardUI(data) {
        // Sync toggle without triggering the change event
        adguardToggle.checked = !!data.enabled;

        queriesBlocked.textContent  = formatNumber(data.blocked);
        totalQueries.textContent    = formatNumber(data.total);
        blockPercentage.textContent = data.percentage != null
            ? `${parseFloat(data.percentage).toFixed(1)}%`
            : '—%';
    }

    /** Handle user toggling AdGuard */
    async function handleAdguardToggle() {
        if (isTogglingAdguard) return;
        isTogglingAdguard = true;

        const desiredState = adguardToggle.checked ? 'enabled' : 'disabled';

        try {
            const result = await API.toggleAdguard();
            showToast(
                `AdGuard DNS ${result.enabled ? 'enabled' : 'disabled'}`,
                result.enabled ? 'success' : 'warning'
            );
            updateAdguardUI(result);
        } catch (err) {
            // Revert the toggle
            adguardToggle.checked = !adguardToggle.checked;
            showToast('Failed to toggle AdGuard: ' + err.message, 'error');
        } finally {
            isTogglingAdguard = false;
        }
    }

    /* ═══════════════════════════════════════════════════════════
       Mode
       ═══════════════════════════════════════════════════════════ */

    async function fetchMode() {
        try {
            const data = await API.getMode();
            updateModeUI(data);
        } catch (err) {
            console.warn('[Mode]', err.message);
        }
    }

    /**
     * Update mode badge.
     * Expected shape: { mode: 'vpn' | 'direct' | ... }
     */
    function updateModeUI(data) {
        const mode = (data.mode || 'unknown').toLowerCase();
        let label = 'Unknown';
        let badgeClass = 'badge-purple';

        switch (mode) {
            case 'vpn':
                label = 'VPN Mode';
                badgeClass = 'badge-cyan';
                break;
            case 'direct':
                label = 'Direct Mode';
                badgeClass = 'badge-amber';
                break;
            default:
                label = mode.charAt(0).toUpperCase() + mode.slice(1) + ' Mode';
                badgeClass = 'badge-purple';
        }

        modeBadge.textContent = label;
        modeBadge.className = `badge ${badgeClass}`;
    }

    /* ═══════════════════════════════════════════════════════════
       Logout
       ═══════════════════════════════════════════════════════════ */

    function handleLogout() {
        stopDashboard();
        API.logout();

        // Reset UI
        pinInput.value = '';
        clearLoginError();
        resetDashboardUI();

        showScreen(loginScreen);
        pinInput.focus();
        showToast('Logged out successfully', 'info');
    }

    function resetDashboardUI() {
        statusDot.className = 'status-dot disconnected';
        statusText.textContent = '—';
        statusText.className = 'status-text';
        serverName.textContent  = '—';
        publicIp.textContent    = '—';
        currentMode.textContent = '—';
        protocolInfo.textContent  = '—';
        uptimeInfo.textContent    = '—';
        dnsInfo.textContent       = '—';
        gatewayIpInfo.textContent = '—';
        queriesBlocked.textContent  = '—';
        blockPercentage.textContent = '—%';
        totalQueries.textContent    = '—';
    }

    /* ═══════════════════════════════════════════════════════════
       Helpers
       ═══════════════════════════════════════════════════════════ */

    /** Format large numbers with locale separators */
    function formatNumber(n) {
        if (n == null || isNaN(n)) return '—';
        return Number(n).toLocaleString();
    }

    /* ═══════════════════════════════════════════════════════════
       Event Binding
       ═══════════════════════════════════════════════════════════ */

    loginBtn.addEventListener('click', handleLogin);

    // Allow Enter key to submit PIN
    pinInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleLogin();
    });

    logoutBtn.addEventListener('click', handleLogout);

    adguardToggle.addEventListener('change', handleAdguardToggle);

    /* ═══════════════════════════════════════════════════════════
       Initialisation
       ═══════════════════════════════════════════════════════════ */

    function init() {
        if (API.token) {
            // Saved token exists — try to go straight to dashboard
            showScreen(dashboardScreen);
            startDashboard();
        } else {
            // No token — show login
            showScreen(loginScreen);
            pinInput.focus();
        }
    }

    // Boot the app
    init();

})();
