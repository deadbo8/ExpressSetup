/**
 * ExpressVPN Gateway — API Client
 * 
 * Thin wrapper around fetch() for communicating with the backend.
 * Handles auth tokens, automatic 401 redirects, and JSON parsing.
 */

const API = {

    /** JWT token persisted across page reloads */
    token: localStorage.getItem('gateway_token'),

    /**
     * Core request helper.
     * @param {'GET'|'POST'|'PUT'|'DELETE'} method  HTTP method
     * @param {string}  path   API path (relative, e.g. '/status')
     * @param {object|null} body   JSON body for POST/PUT
     * @returns {Promise<object>}  Parsed JSON response
     */
    async request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const opts = { method, headers };
        if (body) {
            opts.body = JSON.stringify(body);
        }

        const resp = await fetch(`/api${path}`, opts);

        // Handle auth expiration globally
        if (resp.status === 401) {
            this.token = null;
            localStorage.removeItem('gateway_token');
            window.location.reload();
            throw new Error('Unauthorized');
        }

        if (!resp.ok) {
            const text = await resp.text();
            throw new Error(text || `HTTP ${resp.status}`);
        }

        // Handle 204 No Content
        if (resp.status === 204) return {};

        return resp.json();
    },

    /* ────────── Auth ────────── */

    /**
     * Authenticate with a PIN and store the returned JWT.
     * @param {string} pin  User-supplied PIN
     * @returns {Promise<object>}  { token, ... }
     */
    async login(pin) {
        const data = await this.request('POST', '/auth', { pin });
        this.token = data.token;
        localStorage.setItem('gateway_token', data.token);
        return data;
    },

    /** Remove stored credentials */
    logout() {
        this.token = null;
        localStorage.removeItem('gateway_token');
    },

    /* ────────── Status ────────── */

    /** Fetch current VPN connection status */
    async getStatus() {
        return this.request('GET', '/status');
    },

    /* ────────── AdGuard ────────── */

    /** Fetch AdGuard DNS statistics */
    async getAdguard() {
        return this.request('GET', '/adguard');
    },

    /** Toggle AdGuard protection on/off */
    async toggleAdguard() {
        return this.request('POST', '/adguard/toggle');
    },

    /* ────────── Mode ────────── */

    /** Fetch the current gateway mode */
    async getMode() {
        return this.request('GET', '/mode');
    },
};
