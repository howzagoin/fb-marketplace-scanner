// State
let currentTab = 'listings';
let rulesCache = [];
let scanStatusPollTimer = null;

// DOM Elements
const sessionPill = document.getElementById('sessionPill');
const sessionStatusText = document.getElementById('sessionStatusText');
const scannerPill = document.getElementById('scannerPill');
const scannerStatusText = document.getElementById('scannerStatusText');
const btnConnectFb = document.getElementById('btnConnectFb');
const btnScanNow = document.getElementById('btnScanNow');
const btnEmptyScan = document.getElementById('btnEmptyScan');
const listingsGrid = document.getElementById('listingsGrid');
const listingsEmpty = document.getElementById('listingsEmpty');
const listingsCountBadge = document.getElementById('listingsCountBadge');
const rulesCountBadge = document.getElementById('rulesCountBadge');
const filterSelectRule = document.getElementById('filterSelectRule');
const listingSearchInput = document.getElementById('listingSearchInput');
const checkOnlyFavorites = document.getElementById('checkOnlyFavorites');
const checkShowDismissed = document.getElementById('checkShowDismissed');
const btnRefreshListings = document.getElementById('btnRefreshListings');
const rulesList = document.getElementById('rulesList');
const btnNewRule = document.getElementById('btnNewRule');
const ruleModal = document.getElementById('ruleModal');
const modalClose = document.getElementById('modalClose');
const btnCancelRule = document.getElementById('btnCancelRule');
const ruleForm = document.getElementById('ruleForm');
const modalTitle = document.getElementById('modalTitle');
const logsTableBody = document.getElementById('logsTableBody');
const btnRefreshLogs = document.getElementById('btnRefreshLogs');
const settingsForm = document.getElementById('settingsForm');
const toastContainer = document.getElementById('toastContainer');

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initEventListeners();
    refreshAll();
    startStatusPolling();
});

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 4000);
}

// Tab Switching
function initTabs() {
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            currentTab = tab.dataset.tab;
            document.getElementById(`tab-${currentTab}`).classList.add('active');

            if (currentTab === 'listings') loadListings();
            if (currentTab === 'filters') loadRules();
            if (currentTab === 'logs') loadLogs();
            if (currentTab === 'settings') loadSettings();
        });
    });
}

// Event Listeners
function initEventListeners() {
    btnConnectFb.addEventListener('click', handleConnectFb);
    btnScanNow.addEventListener('click', handleTriggerScan);
    if (btnEmptyScan) btnEmptyScan.addEventListener('click', handleTriggerScan);
    btnRefreshListings.addEventListener('click', loadListings);
    listingSearchInput.addEventListener('input', debounce(loadListings, 300));
    filterSelectRule.addEventListener('change', loadListings);
    checkOnlyFavorites.addEventListener('change', loadListings);
    checkShowDismissed.addEventListener('change', loadListings);

    btnNewRule.addEventListener('click', () => openRuleModal());
    modalClose.addEventListener('click', closeRuleModal);
    btnCancelRule.addEventListener('click', closeRuleModal);
    ruleForm.addEventListener('submit', handleSaveRule);

    btnRefreshLogs.addEventListener('click', loadLogs);
    settingsForm.addEventListener('submit', handleSaveSettings);
}

function refreshAll() {
    checkScannerStatus();
    loadRules();
    loadListings();
}

// Status Polling
function startStatusPolling() {
    checkScannerStatus();
    scanStatusPollTimer = setInterval(checkScannerStatus, 5000);
}

async function checkScannerStatus() {
    try {
        const res = await fetch('/api/scanner/status');
        const data = await res.json();
        if (data.success && data.status) {
            const s = data.status;
            // Update Scanner Pill
            if (s.is_scanning) {
                scannerPill.className = 'pill pill-running';
                scannerStatusText.textContent = s.status_message || 'Scanning in progress...';
                btnScanNow.disabled = true;
            } else {
                scannerPill.className = 'pill pill-idle';
                scannerStatusText.textContent = `Scanner: ${s.status_message || 'Idle'}`;
                btnScanNow.disabled = false;
            }

            // Update Session Pill
            if (s.session && s.session.valid) {
                sessionPill.className = 'pill pill-success';
                sessionStatusText.textContent = 'Facebook: Connected';
            } else {
                sessionPill.className = 'pill pill-warning';
                sessionStatusText.textContent = 'Facebook: Needs Login';
            }
        }
    } catch (e) {
        console.error('Failed to poll scanner status:', e);
    }
}

// Connect Facebook (Interactive Session Launch)
async function handleConnectFb() {
    if (!confirm('This will open a browser window for you to log into Facebook and complete 2FA. Once signed in, the session will be saved locally. Continue?')) {
        return;
    }
    showToast('Launching interactive login browser...', 'info');
    try {
        const res = await fetch('/api/session/login', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'info');
        } else {
            showToast(data.error || 'Failed to start browser login', 'danger');
        }
    } catch (e) {
        showToast('Error connecting to backend: ' + e.message, 'danger');
    }
}

// Trigger Manual Scan
async function handleTriggerScan(ruleId = null) {
    showToast('Starting scan in background...', 'info');
    try {
        const body = ruleId ? { filter_id: ruleId } : {};
        const res = await fetch('/api/scanner/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'info');
            checkScannerStatus();
            setTimeout(loadListings, 4000);
        } else {
            showToast(data.error || 'Failed to start scan', 'danger');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'danger');
    }
}

// Load Listings
async function loadListings() {
    const ruleId = filterSelectRule.value;
    const keyword = listingSearchInput.value.trim();
    const onlyFav = checkOnlyFavorites.checked ? '1' : '0';
    const showDis = checkShowDismissed.checked ? '1' : '0';

    const params = new URLSearchParams({
        filter_id: ruleId,
        keyword: keyword,
        only_favorites: onlyFav,
        show_dismissed: showDis
    });

    try {
        const res = await fetch(`/api/listings?${params.toString()}`);
        const data = await res.json();
        if (data.success) {
            renderListings(data.listings || []);
            listingsCountBadge.textContent = data.count || 0;
        }
    } catch (e) {
        console.error('Error loading listings:', e);
    }
}

function renderListings(items) {
    listingsGrid.innerHTML = '';
    if (!items || items.length === 0) {
        listingsGrid.classList.add('hidden');
        listingsEmpty.classList.remove('hidden');
        return;
    }

    listingsEmpty.classList.add('hidden');
    listingsGrid.classList.remove('hidden');

    items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'listing-card';

        const isFree = item.price.toLowerCase().includes('free') || item.price_num === 0;
        const priceClass = isFree ? 'price-tag price-free' : 'price-tag';

        const imgHtml = item.image_url
            ? `<img src="${item.image_url}" alt="${escapeHtml(item.title)}" class="listing-img" loading="lazy" />`
            : `<div class="listing-img-placeholder">📦</div>`;

        const dateStr = item.first_seen ? new Date(item.first_seen * 1000).toLocaleDateString() : '';

        card.innerHTML = `
            <div class="listing-img-container">
                ${imgHtml}
                <div class="${priceClass}">${escapeHtml(item.price)}</div>
            </div>
            <div class="listing-content">
                <h4 class="listing-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</h4>
                <div class="listing-location">📍 ${escapeHtml(item.location || 'Local area')}</div>
                <div class="listing-meta">Found: ${dateStr} &bull; Rule: ${escapeHtml(item.filter_name || 'General')}</div>
                <div class="listing-actions">
                    <div class="action-buttons">
                        <button class="btn-star ${item.is_favorite ? 'active' : ''}" title="Star Item" data-id="${item.listing_id}">⭐</button>
                        <button class="btn-dismiss" title="Dismiss Item" data-id="${item.listing_id}">${item.is_dismissed ? '↩️' : '🗑️'}</button>
                    </div>
                    <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn-view-fb">View on FB ↗</a>
                </div>
            </div>
        `;

        // Card action listeners
        const starBtn = card.querySelector('.btn-star');
        starBtn.addEventListener('click', async () => {
            const nextFav = !item.is_favorite;
            await toggleFavorite(item.listing_id, nextFav);
            item.is_favorite = nextFav;
            starBtn.classList.toggle('active', nextFav);
        });

        const disBtn = card.querySelector('.btn-dismiss');
        disBtn.addEventListener('click', async () => {
            const nextDis = !item.is_dismissed;
            await toggleDismiss(item.listing_id, nextDis);
            loadListings();
        });

        listingsGrid.appendChild(card);
    });
}

async function toggleFavorite(id, isFav) {
    await fetch(`/api/listings/${id}/favorite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_favorite: isFav })
    });
}

async function toggleDismiss(id, isDis) {
    await fetch(`/api/listings/${id}/dismiss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_dismissed: isDis })
    });
}

// Load Search Rules
async function loadRules() {
    try {
        const res = await fetch('/api/filters');
        const data = await res.json();
        if (data.success) {
            rulesCache = data.filters || [];
            renderRules(rulesCache);
            updateFilterDropdown(rulesCache);
            rulesCountBadge.textContent = rulesCache.length;
        }
    } catch (e) {
        console.error('Error loading rules:', e);
    }
}

function updateFilterDropdown(rules) {
    const currentVal = filterSelectRule.value;
    filterSelectRule.innerHTML = '<option value="">All Search Rules</option>';
    rules.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.id;
        opt.textContent = r.name;
        filterSelectRule.appendChild(opt);
    });
    filterSelectRule.value = currentVal;
}

function renderRules(rules) {
    rulesList.innerHTML = '';
    rules.forEach(r => {
        const card = document.createElement('div');
        card.className = 'rule-card';

        const priceLabel = (r.max_price === 0) ? 'Free Only ($0)' : (r.max_price ? `Up to $${r.max_price}` : 'Any Price');
        const keywordLabel = r.query ? `Term: "${escapeHtml(r.query)}"` : 'All Items Feed';

        card.innerHTML = `
            <div class="rule-info">
                <h3>
                    <span>${escapeHtml(r.name)}</span>
                    <span class="tag ${r.enabled ? 'tag-highlight' : ''}">${r.enabled ? 'Active' : 'Disabled'}</span>
                </h3>
                <div class="rule-tags">
                    <span class="tag">🔍 ${keywordLabel}</span>
                    <span class="tag">📍 Postcode: ${escapeHtml(r.postcode)} (${r.radius_km}km)</span>
                    <span class="tag">💰 ${priceLabel}</span>
                    <span class="tag">${r.notify_email ? '📧 Email Alert: ON' : '🔕 Alert: OFF'}</span>
                </div>
            </div>
            <div class="rule-controls">
                <button class="btn btn-secondary btn-sm btn-rule-scan" data-id="${r.id}">⚡ Scan This</button>
                <button class="btn btn-secondary btn-sm btn-rule-edit" data-id="${r.id}">✏️ Edit</button>
                <button class="btn btn-danger btn-sm btn-rule-del" data-id="${r.id}">🗑️</button>
            </div>
        `;

        card.querySelector('.btn-rule-scan').addEventListener('click', () => handleTriggerScan(r.id));
        card.querySelector('.btn-rule-edit').addEventListener('click', () => openRuleModal(r));
        card.querySelector('.btn-rule-del').addEventListener('click', () => handleDeleteRule(r.id));

        rulesList.appendChild(card);
    });
}

function openRuleModal(rule = null) {
    modalTitle.textContent = rule ? 'Edit Search Rule' : 'Add New Search Rule';
    document.getElementById('ruleId').value = rule ? rule.id : '';
    document.getElementById('ruleName').value = rule ? rule.name : '';
    document.getElementById('ruleQuery').value = rule ? (rule.query || '') : '';
    document.getElementById('rulePostcode').value = rule ? rule.postcode : '3011';
    document.getElementById('ruleRadius').value = rule ? rule.radius_km : 50;
    document.getElementById('ruleMinPrice').value = rule && rule.min_price !== null ? rule.min_price : '';
    document.getElementById('ruleMaxPrice').value = rule && rule.max_price !== null ? rule.max_price : 0;
    document.getElementById('ruleEnabled').checked = rule ? rule.enabled : true;
    document.getElementById('ruleNotify').checked = rule ? rule.notify_email : true;
    ruleModal.classList.remove('hidden');
}

function closeRuleModal() {
    ruleModal.classList.add('hidden');
}

async function handleSaveRule(e) {
    e.preventDefault();
    const idVal = document.getElementById('ruleId').value;
    const payload = {
        name: document.getElementById('ruleName').value.trim(),
        query: document.getElementById('ruleQuery').value.trim(),
        postcode: document.getElementById('rulePostcode').value.trim(),
        radius_km: parseInt(document.getElementById('ruleRadius').value) || 50,
        min_price: document.getElementById('ruleMinPrice').value ? parseInt(document.getElementById('ruleMinPrice').value) : null,
        max_price: document.getElementById('ruleMaxPrice').value !== '' ? parseInt(document.getElementById('ruleMaxPrice').value) : 0,
        enabled: document.getElementById('ruleEnabled').checked,
        notify_email: document.getElementById('ruleNotify').checked
    };
    if (idVal) payload.id = parseInt(idVal);

    try {
        const res = await fetch('/api/filters', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast('Search rule saved!', 'info');
            closeRuleModal();
            loadRules();
        } else {
            showToast(data.error || 'Failed to save rule', 'danger');
        }
    } catch (e) {
        showToast('Error saving rule: ' + e.message, 'danger');
    }
}

async function handleDeleteRule(id) {
    if (!confirm('Are you sure you want to delete this search rule?')) return;
    try {
        const res = await fetch(`/api/filters/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast('Search rule removed.', 'info');
            loadRules();
        }
    } catch (e) {
        showToast('Error deleting rule: ' + e.message, 'danger');
    }
}

// Load Activity Logs
async function loadLogs() {
    try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        if (data.success) {
            renderLogs(data.logs || []);
        }
    } catch (e) {
        console.error('Error loading logs:', e);
    }
}

function renderLogs(logs) {
    logsTableBody.innerHTML = '';
    if (!logs || logs.length === 0) {
        logsTableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No scan logs yet.</td></tr>';
        return;
    }

    logs.forEach(l => {
        const tr = document.createElement('tr');
        const timeStr = l.timestamp ? new Date(l.timestamp * 1000).toLocaleString() : '';
        const statusClass = l.status === 'Success' ? 'pill-success' : 'pill-danger';

        tr.innerHTML = `
            <td>${timeStr}</td>
            <td>${escapeHtml(l.filter_name || 'All Rules')}</td>
            <td><span class="pill ${statusClass}">${escapeHtml(l.status)}</span></td>
            <td><strong>${l.count_found}</strong> items</td>
            <td><strong style="color:var(--success);">${l.count_new}</strong> new</td>
            <td>${escapeHtml(l.error_message || 'Completed normally')}</td>
        `;
        logsTableBody.appendChild(tr);
    });
}

// Load Settings
async function loadSettings() {
    try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        if (data.success && data.settings) {
            const s = data.settings;
            document.getElementById('inputAlertEmail').value = s.alert_email || 'maclatchy@gmail.com';
            document.getElementById('checkAutoScan').checked = Boolean(s.auto_scan_enabled);
            document.getElementById('inputScanInterval').value = s.scan_interval_minutes || 60;
        }
    } catch (e) {
        console.error('Error loading settings:', e);
    }
}

async function handleSaveSettings(e) {
    e.preventDefault();
    const payload = {
        alert_email: document.getElementById('inputAlertEmail').value.trim(),
        auto_scan_enabled: document.getElementById('checkAutoScan').checked,
        scan_interval_minutes: parseInt(document.getElementById('inputScanInterval').value) || 60
    };

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast('Settings saved successfully!', 'info');
        } else {
            showToast(data.error || 'Failed to save settings', 'danger');
        }
    } catch (e) {
        showToast('Error saving settings: ' + e.message, 'danger');
    }
}

// Helpers
function debounce(fn, wait) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), wait);
    };
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
