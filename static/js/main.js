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
const filterInterestStatus = document.getElementById('filterInterestStatus');
const listingSearchInput = document.getElementById('listingSearchInput');
const checkOnlyFavorites = document.getElementById('checkOnlyFavorites');
const checkShowDismissed = document.getElementById('checkShowDismissed');
const btnRefreshListings = document.getElementById('btnRefreshListings');
const interestsCountBadge = document.getElementById('interestsCountBadge');
const formAddInterest = document.getElementById('formAddInterest');
const inputNewInterest = document.getElementById('inputNewInterest');
const checkNewInterestAlert = document.getElementById('checkNewInterestAlert');
const interestsList = document.getElementById('interestsList');
const formAddExcluded = document.getElementById('formAddExcluded');
const inputNewExcluded = document.getElementById('inputNewExcluded');
const excludedList = document.getElementById('excludedList');
const condensedProductsGrid = document.getElementById('condensedProductsGrid');
const condensedEmpty = document.getElementById('condensedEmpty');
const condensedSearchInput = document.getElementById('condensedSearchInput');
const filterCondensedStatus = document.getElementById('filterCondensedStatus');
const btnRefreshCondensed = document.getElementById('btnRefreshCondensed');
const rulesList = document.getElementById('rulesList');
const btnNewRule = document.getElementById('btnNewRule');
const ruleModal = document.getElementById('ruleModal');
const modalClose = document.getElementById('modalClose');
const btnCancelRule = document.getElementById('btnCancelRule');
const ruleForm = document.getElementById('ruleForm');
const modalTitle = document.getElementById('modalTitle');
const sessionModal = document.getElementById('sessionModal');
const sessionModalClose = document.getElementById('sessionModalClose');
const btnOpenFbTab = document.getElementById('btnOpenFbTab');
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
            const targetPane = document.getElementById(`tab-${currentTab}`);
            if (targetPane) targetPane.classList.add('active');

            if (currentTab === 'listings') loadListings();
            if (currentTab === 'interests') {
                loadInterests();
                loadCondensedProducts();
            }
            if (currentTab === 'filters') loadRules();
            if (currentTab === 'logs') loadLogs();
            if (currentTab === 'settings') loadSettings();
        });
    });
}

// Event Listeners
function initEventListeners() {
    btnConnectFb.addEventListener('click', openSessionModal);
    sessionModalClose.addEventListener('click', closeSessionModal);
    if (btnOpenFbTab) {
        btnOpenFbTab.addEventListener('click', handleOpenFbTab);
    }

    btnScanNow.addEventListener('click', () => handleTriggerScan());
    if (btnEmptyScan) btnEmptyScan.addEventListener('click', () => handleTriggerScan());
    const btnEmptyReset = document.getElementById('btnEmptyReset');
    if (btnEmptyReset) {
        btnEmptyReset.addEventListener('click', () => {
            if (filterInterestStatus) filterInterestStatus.value = 'all';
            if (listingSearchInput) listingSearchInput.value = '';
            loadListings();
        });
    }
    btnRefreshListings.addEventListener('click', async () => {
        await loadListings();
        showToast('Feed refreshed from local database', 'info');
    });
    listingSearchInput.addEventListener('input', debounce(loadListings, 300));
    filterSelectRule.addEventListener('change', loadListings);
    if (filterInterestStatus) filterInterestStatus.addEventListener('change', loadListings);
    const filterRetentionDays = document.getElementById('filterRetentionDays');
    if (filterRetentionDays) {
        filterRetentionDays.addEventListener('change', () => {
            loadListings();
            saveQuickRetention(filterRetentionDays.value);
        });
    }
    checkOnlyFavorites.addEventListener('change', loadListings);
    checkShowDismissed.addEventListener('change', loadListings);

    const sliderRetention = document.getElementById('sliderRetentionDays');
    const inputRetention = document.getElementById('inputRetentionDays');
    const labelRetention = document.getElementById('retentionDaysLabel');
    if (sliderRetention && inputRetention) {
        sliderRetention.addEventListener('input', () => {
            inputRetention.value = sliderRetention.value;
            if (labelRetention) labelRetention.textContent = `${sliderRetention.value} Days`;
        });
        inputRetention.addEventListener('input', () => {
            sliderRetention.value = inputRetention.value;
            if (labelRetention) labelRetention.textContent = `${inputRetention.value} Days`;
        });
    }

    if (formAddInterest) formAddInterest.addEventListener('submit', handleAddInterest);
    if (formAddExcluded) formAddExcluded.addEventListener('submit', handleAddExcluded);

    if (condensedSearchInput) condensedSearchInput.addEventListener('input', debounce(renderCondensedProducts, 200));
    if (filterCondensedStatus) filterCondensedStatus.addEventListener('change', renderCondensedProducts);
    if (btnRefreshCondensed) btnRefreshCondensed.addEventListener('click', handleReanalyzeAllProducts);

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
    loadInterests();
    loadCondensedProducts();
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
                sessionStatusText.textContent = `Facebook: ${s.session.status_text || 'Active'}`;
            } else {
                sessionPill.className = 'pill pill-warning';
                sessionStatusText.textContent = 'Facebook: Needs Login';
            }

            // Update Main Session Banner
            const banner = document.getElementById('mainSessionBanner');
            const bIcon = document.getElementById('mainSessionIcon');
            const bTitle = document.getElementById('mainSessionTitle');
            const bDesc = document.getElementById('mainSessionDesc');
            const bBtn = document.getElementById('btnBannerConnect');

            if (banner) {
                if (s.session && s.session.valid) {
                    banner.className = 'session-status-banner banner-active';
                    if (bIcon) bIcon.textContent = '✅';
                    if (bTitle) {
                        bTitle.style.color = '#22c55e';
                        bTitle.textContent = 'Facebook Account: Connected & Active';
                    }
                    if (bDesc) bDesc.textContent = '24/7 background scanner is authenticated and searching for matching marketplace items.';
                    if (bBtn) {
                        bBtn.textContent = '⚙️ Manage Session';
                        bBtn.className = 'btn btn-secondary btn-sm';
                    }
                } else {
                    banner.className = 'session-status-banner banner-warning';
                    if (bIcon) bIcon.textContent = '⚠️';
                    if (bTitle) {
                        bTitle.style.color = '#f59e0b';
                        bTitle.textContent = 'Facebook Account: Not Connected (Login Required)';
                    }
                    if (bDesc) bDesc.textContent = 'Scanner cannot retrieve live listings without Facebook authentication. Connect your account to enable scanning.';
                    if (bBtn) {
                        bBtn.textContent = '🔑 Connect Facebook (2FA)';
                        bBtn.className = 'btn btn-primary btn-sm';
                    }
                }
            }
        }
    } catch (e) {
        console.error('Failed to poll scanner status:', e);
    }
}

// Connect Facebook Session Modal & Handlers
function openSessionModal() {
    sessionModal.classList.remove('hidden');
}

function closeSessionModal() {
    sessionModal.classList.add('hidden');
}

async function handleLaunchDesktopBrowser() {
    showToast('Launching desktop browser for sign-in...', 'info');
    // Invoke Windows registered protocol handler to pop up Connect-Facebook.bat
    window.location.href = 'fb-scanner://login';
    try {
        const res = await fetch('/api/session/login', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'info');
        } else {
            showToast(data.error || 'Opening browser on your desktop...', 'info');
        }
    } catch (e) {
        showToast('Local launcher triggered. Please complete sign-in in the opened browser.', 'info');
    }
}

async function handleSaveCookies(e) {
    e.preventDefault();
    const cUser = inputCUser.value.trim();
    const xs = inputXs.value.trim();
    const raw = inputRawCookies.value.trim();

    let payload = {};
    if (raw) {
        payload = { cookies: raw };
    } else if (cUser && xs) {
        payload = {
            cookies: [
                { name: 'c_user', value: cUser },
                { name: 'xs', value: xs }
            ]
        };
    } else {
        showToast('Please enter both c_user and xs, or paste raw cookies.', 'danger');
        return;
    }

    try {
        showToast('Saving and verifying Facebook session...', 'info');
        const res = await fetch('/api/session/cookies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || 'Facebook session activated!', 'info');
            closeSessionModal();
            checkScannerStatus();
        } else {
            showToast(data.error || 'Invalid session cookies', 'danger');
        }
    } catch (e) {
        showToast('Error saving cookies: ' + e.message, 'danger');
    }
}

let isScanRunning = false;
let scanMonitorTimer = null;

function setScanButtonState(running) {
    isScanRunning = running;
    if (btnScanNow) {
        btnScanNow.disabled = running;
        if (running) {
            btnScanNow.innerHTML = `<span class="spinner-sm"></span> Scanning...`;
        } else {
            btnScanNow.innerHTML = `⚡ Scan Now`;
        }
    }
    if (btnEmptyScan) {
        btnEmptyScan.disabled = running;
        btnEmptyScan.textContent = running ? 'Scanning in progress...' : '⚡ Scan Marketplace Now';
    }
}

// Trigger Manual Scan
async function handleTriggerScan(ruleId = null) {
    if (isScanRunning) {
        showToast('Scan already in progress. Please wait...', 'info');
        return;
    }

    setScanButtonState(true);
    showToast('Starting Facebook Marketplace scan...', 'info');

    try {
        const isValidId = (typeof ruleId === 'number' && !isNaN(ruleId)) || (typeof ruleId === 'string' && /^\d+$/.test(ruleId));
        const body = isValidId ? { filter_id: parseInt(ruleId) } : {};
        const res = await fetch('/api/scanner/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();

        if (!data.success) {
            setScanButtonState(false);
            showToast(data.error || 'Failed to start scan', 'danger');
            return;
        }

        showToast('⚡ Live scan running on Facebook... Monitoring for items', 'info');
        checkScannerStatus();

        if (scanMonitorTimer) clearInterval(scanMonitorTimer);
        let elapsed = 0;

        scanMonitorTimer = setInterval(async () => {
            elapsed += 2;
            try {
                const sRes = await fetch('/api/scanner/status');
                const sData = await sRes.json();
                if (sData.success && sData.status) {
                    const st = sData.status;
                    if (!st.is_scanning) {
                        clearInterval(scanMonitorTimer);
                        scanMonitorTimer = null;
                        setScanButtonState(false);

                        showToast(`✅ ${st.status_message || 'Scan completed successfully!'}`, 'success');
                        await loadListings();
                        await loadCondensedProducts();
                        await loadRules();
                        return;
                    }
                }
            } catch (pollErr) {}

            if (elapsed >= 90) {
                clearInterval(scanMonitorTimer);
                scanMonitorTimer = null;
                setScanButtonState(false);
                loadListings();
            }
        }, 2000);

    } catch (e) {
        setScanButtonState(false);
        showToast('Error: ' + e.message, 'danger');
    }
}

// Load Listings
async function loadListings() {
    const ruleId = filterSelectRule.value;
    const keyword = listingSearchInput.value.trim();
    const onlyFav = checkOnlyFavorites.checked ? '1' : '0';
    const showDis = checkShowDismissed.checked ? '1' : '0';
    const interestStatus = filterInterestStatus ? filterInterestStatus.value : 'all';
    const filterRetentionDays = document.getElementById('filterRetentionDays');
    const retentionDays = filterRetentionDays ? filterRetentionDays.value : '7';

    const params = new URLSearchParams({
        filter_id: ruleId,
        keyword: keyword,
        interest_status: interestStatus,
        only_favorites: onlyFav,
        show_dismissed: showDis,
        max_age_days: retentionDays
    });

    try {
        const res = await fetch(`/api/listings?${params.toString()}`);
        const data = await res.json();
        if (data.success) {
            renderListings(data.listings || [], data.total_active || 0);
            listingsCountBadge.textContent = data.count || 0;
        }
    } catch (e) {
        console.error('Error loading listings:', e);
    }
}

function renderListings(items, totalActive = 0) {
    listingsGrid.innerHTML = '';
    const emptyMsg = document.getElementById('emptyStateMsg');
    const emptyResetBtn = document.getElementById('btnEmptyReset');

    if (!items || items.length === 0) {
        listingsGrid.classList.add('hidden');
        listingsEmpty.classList.remove('hidden');

        const isFiltered = (filterInterestStatus && filterInterestStatus.value !== 'all') || (listingSearchInput && listingSearchInput.value.trim().length > 0);

        if (isFiltered) {
            const filterName = filterInterestStatus ? filterInterestStatus.options[filterInterestStatus.selectedIndex]?.text : '';
            if (emptyMsg) {
                emptyMsg.textContent = `No listings found matching ${filterName || 'selected filter'}. (${totalActive} active listings are available in total).`;
            }
            if (emptyResetBtn) {
                emptyResetBtn.textContent = `✨ Show All Active Listings (${totalActive} available)`;
                emptyResetBtn.classList.remove('hidden');
            }
        } else {
            if (emptyMsg) {
                emptyMsg.textContent = 'Run a scan or adjust your search rules to discover Marketplace items.';
            }
            if (emptyResetBtn) {
                emptyResetBtn.classList.add('hidden');
            }
        }
        return;
    }

    listingsEmpty.classList.add('hidden');
    listingsGrid.classList.remove('hidden');
    if (emptyResetBtn) emptyResetBtn.classList.add('hidden');

    items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'listing-card';

        const isFree = item.price.toLowerCase().includes('free') || item.price_num === 0;
        const priceClass = isFree ? 'price-tag price-free' : 'price-tag';

        const proxyUrl = `/api/image-proxy?id=${encodeURIComponent(item.listing_id || '')}&url=${encodeURIComponent(item.image_url || '')}`;
        const isExpiredUrl = Boolean(item.image_url && item.image_url.match(/[?&]oe=([0-9a-fA-F]+)/) && parseInt(item.image_url.match(/[?&]oe=([0-9a-fA-F]+)/)[1], 16) < (Date.now() / 1000));
        const initialImgSrc = isExpiredUrl ? proxyUrl : (item.image_url || proxyUrl);

        const imgHtml = (item.image_url || item.listing_id)
            ? `<img src="${initialImgSrc}" referrerpolicy="no-referrer" alt="${escapeHtml(item.title)}" class="listing-img" loading="lazy" onerror="if(!this.src.includes('/api/image-proxy')){this.src='${proxyUrl}';}else{this.onerror=null;this.parentElement.innerHTML='<div class=\\'listing-img-placeholder\\'>&#x1F4E6;</div>';}" />`
            : `<div class="listing-img-placeholder">&#x1F4E6;</div>`;

        const dateStr = formatDateDMY(item.first_seen);
        const priorityBadge = item.instant_match
            ? `<div class="badge-priority">⭐ Priority Match</div>`
            : '';

        const isInterested = item.interest_status === 'interested';
        const isNotInterested = item.interest_status === 'not_interested';

        card.innerHTML = `
            <div class="listing-img-container">
                <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="listing-img-link" title="Open listing on Facebook Marketplace">
                    ${imgHtml}
                </a>
                <div class="${priceClass}">${escapeHtml(item.price)}</div>
                ${priorityBadge}
            </div>
            <div class="listing-content">
                <h4 class="listing-title" title="${escapeHtml(item.title)}">
                    <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="listing-title-link">
                        ${escapeHtml(item.title)}
                    </a>
                </h4>
                <div class="listing-location">📍 ${escapeHtml(item.location || 'Local area')}</div>
                <div class="listing-meta" title="Discovered: ${formatDateTimeDMY(item.first_seen)}">Found: ${dateStr} &bull; Rule: ${escapeHtml(item.filter_name || 'General')}</div>
                
                <div class="interest-feedback-row">
                    <button class="btn-interest btn-interested ${isInterested ? 'active' : ''}" 
                            title="Interested in items like this (see more in future)" data-id="${item.listing_id}">
                        👍 Interested
                    </button>
                    <button class="btn-interest btn-not-interested ${isNotInterested ? 'active' : ''}" 
                            title="Not interested (auto-exclude similar items)" data-id="${item.listing_id}">
                        👎 Not Interested
                    </button>
                </div>

                <div class="listing-actions">
                    <div class="action-buttons">
                        <button class="btn-star ${item.is_favorite ? 'active' : ''}" title="Star Item" data-id="${item.listing_id}">⭐</button>
                        <button class="btn-dismiss" title="Dismiss Item" data-id="${item.listing_id}">${item.is_dismissed ? '↩️' : '🗑️'}</button>
                    </div>
                    <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="btn-view-fb">View on FB ↗</a>
                </div>
            </div>
        `;

        // Interest feedback handlers
        const btnInterested = card.querySelector('.btn-interested');
        const btnNotInterested = card.querySelector('.btn-not-interested');

        btnInterested.addEventListener('click', async () => {
            const nextStatus = item.interest_status === 'interested' ? 'none' : 'interested';
            await handleSetListingInterest(item.listing_id, nextStatus);
            item.interest_status = nextStatus;
            btnInterested.classList.toggle('active', nextStatus === 'interested');
            btnNotInterested.classList.remove('active');
            loadInterests();
            loadCondensedProducts();
        });

        btnNotInterested.addEventListener('click', async () => {
            const nextStatus = item.interest_status === 'not_interested' ? 'none' : 'not_interested';
            if (nextStatus === 'not_interested' && (!filterInterestStatus || filterInterestStatus.value !== 'not_interested')) {
                // Instantly remove card with smooth animation
                card.style.transition = 'all 0.25s ease';
                card.style.transform = 'scale(0.85)';
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    const badge = document.getElementById('listingsCountBadge');
                    if (badge) {
                        const cur = parseInt(badge.textContent) || 0;
                        if (cur > 0) badge.textContent = cur - 1;
                    }
                }, 250);
            }
            await handleSetListingInterest(item.listing_id, nextStatus);
            item.interest_status = nextStatus;
            loadInterests();
            loadCondensedProducts();
        });

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
            if (nextDis && !checkShowDismissed.checked) {
                // Instantly remove dismissed item from feed
                card.style.transition = 'all 0.25s ease';
                card.style.transform = 'scale(0.85)';
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    const badge = document.getElementById('listingsCountBadge');
                    if (badge) {
                        const cur = parseInt(badge.textContent) || 0;
                        if (cur > 0) badge.textContent = cur - 1;
                    }
                }, 250);
            }
            await toggleDismiss(item.listing_id, nextDis);
            item.is_dismissed = nextDis ? 1 : 0;
        });

        listingsGrid.appendChild(card);
    });
}

async function handleSetListingInterest(listingId, status) {
    try {
        const res = await fetch(`/api/listings/${listingId}/interest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        const data = await res.json();
        if (data.success && data.message) {
            showToast(data.message, 'info');
        }
    } catch (e) {
        showToast('Error saving feedback: ' + e.message, 'danger');
    }
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
        const timeStr = formatDateTimeDMY(l.timestamp);
        let statusClass = 'pill-danger';
        if (l.status === 'Success') statusClass = 'pill-success';
        else if (l.status === 'Needs Login') statusClass = 'pill-warning';

        tr.innerHTML = `
            <td>${timeStr}</td>
            <td>${escapeHtml(l.filter_name || 'All Rules')}</td>
            <td><span class="pill ${statusClass}">${escapeHtml(l.status)}</span></td>
            <td><strong>${l.count_found}</strong> items</td>
            <td><strong style="color:var(--success);">${l.count_new}</strong> new</td>
            <td>${escapeHtml(l.error_message || (l.status === 'Success' ? 'Completed normally' : 'Error during scan'))}</td>
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
            const isAuto = Boolean(s.auto_scan_enabled);
            const checkAuto = document.getElementById('checkAutoScan');
            checkAuto.checked = isAuto;
            document.getElementById('inputScanInterval').value = s.scan_interval_minutes || 60;

            const retentionDays = s.listing_retention_days || 14;
            const sliderRetention = document.getElementById('sliderRetentionDays');
            const inputRetention = document.getElementById('inputRetentionDays');
            const labelRetention = document.getElementById('retentionDaysLabel');
            const filterRetention = document.getElementById('filterRetentionDays');
            if (sliderRetention) sliderRetention.value = retentionDays;
            if (inputRetention) inputRetention.value = retentionDays;
            if (labelRetention) labelRetention.textContent = `${retentionDays} Days`;
            if (filterRetention) {
                const opt = Array.from(filterRetention.options).find(o => o.value === String(retentionDays));
                if (opt) filterRetention.value = String(retentionDays);
            }

            const schedPill = document.getElementById('scheduleStatusPill');
            if (schedPill) {
                schedPill.className = isAuto ? 'pill pill-success' : 'pill pill-warning';
                schedPill.innerHTML = `<span class="dot"></span> ${isAuto ? 'Active' : 'Paused'}`;
            }

            checkAuto.onchange = () => {
                if (schedPill) {
                    schedPill.className = checkAuto.checked ? 'pill pill-success' : 'pill pill-warning';
                    schedPill.innerHTML = `<span class="dot"></span> ${checkAuto.checked ? 'Active' : 'Paused'}`;
                }
            };
        }
    } catch (e) {
        console.error('Error loading settings:', e);
    }
}

async function handleSaveSettings(e) {
    e.preventDefault();
    const inputRetention = document.getElementById('inputRetentionDays');
    const retentionDays = inputRetention ? (parseInt(inputRetention.value) || 14) : 14;

    const payload = {
        alert_email: document.getElementById('inputAlertEmail').value.trim(),
        auto_scan_enabled: document.getElementById('checkAutoScan').checked,
        scan_interval_minutes: parseInt(document.getElementById('inputScanInterval').value) || 60,
        listing_retention_days: retentionDays
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
            const filterRetention = document.getElementById('filterRetentionDays');
            if (filterRetention) {
                const opt = Array.from(filterRetention.options).find(o => o.value === String(retentionDays));
                if (opt) filterRetention.value = String(retentionDays);
            }
            loadListings();
        } else {
            showToast(data.error || 'Failed to save settings', 'danger');
        }
    } catch (e) {
        showToast('Error saving settings: ' + e.message, 'danger');
    }
}

async function saveQuickRetention(days) {
    try {
        const d = parseInt(days) || 14;
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ listing_retention_days: d })
        });
        const slider = document.getElementById('sliderRetentionDays');
        const input = document.getElementById('inputRetentionDays');
        const label = document.getElementById('retentionDaysLabel');
        if (slider) slider.value = d;
        if (input) input.value = d;
        if (label) label.textContent = `${d} Days`;
        showToast(`Listing retention set to ${d === 0 ? 'All (No Expiry)' : d + ' Days'}`, 'info');
    } catch (e) {
        console.error('Failed to save quick retention preference:', e);
    }
}

// ---------------- Product Interests Profile ----------------
async function loadInterests() {
    try {
        const res = await fetch('/api/interests');
        const data = await res.json();
        if (data.success) {
            const items = data.interests || [];
            const interested = items.filter(x => x.type === 'interested');
            const excluded = items.filter(x => x.type === 'excluded');

            if (interestsCountBadge) {
                interestsCountBadge.textContent = interested.length;
            }

            renderInterestsList(interested);
            renderExcludedList(excluded);
        }
    } catch (e) {
        console.error('Error loading interests:', e);
    }
}

function renderInterestsList(items) {
    if (!interestsList) return;
    interestsList.innerHTML = '';
    if (items.length === 0) {
        interestsList.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; padding:16px; text-align:center;">No interested items saved yet. Add items above or click 👍 Interested on listings!</div>';
        return;
    }

    items.forEach(item => {
        const row = document.createElement('div');
        const isStarred = Boolean(item.instant_alert);
        row.className = `interest-item-row ${isStarred ? 'is-starred' : ''}`;

        const starBtnText = isStarred ? '⭐ Instant Alert: ON' : '☆ Alert: Off';

        row.innerHTML = `
            <div class="interest-keyword">${escapeHtml(item.keyword)}</div>
            <div class="interest-item-meta">
                <button class="star-alert-btn ${isStarred ? 'starred' : 'unstarred'}" title="Toggle instant priority alert when this item appears">
                    ${starBtnText}
                </button>
                <button class="btn-delete-interest" title="Remove item">&times;</button>
            </div>
        `;

        row.querySelector('.star-alert-btn').addEventListener('click', async () => {
            await handleToggleInstantAlert(item.id);
        });

        row.querySelector('.btn-delete-interest').addEventListener('click', async () => {
            await handleDeleteInterest(item.id);
        });

        interestsList.appendChild(row);
    });
}

function renderExcludedList(items) {
    if (!excludedList) return;
    excludedList.innerHTML = '';
    if (items.length === 0) {
        excludedList.innerHTML = '<div style="color:var(--text-muted); font-size:0.85rem; padding:16px; text-align:center;">No excluded keywords yet. Add keywords above or click 👎 Not Interested on listings.</div>';
        return;
    }

    items.forEach(item => {
        const row = document.createElement('div');
        row.className = 'interest-item-row';

        row.innerHTML = `
            <div class="interest-keyword" style="color:var(--text-secondary); text-decoration: line-through;">${escapeHtml(item.keyword)}</div>
            <div class="interest-item-meta">
                <button class="btn-delete-interest" title="Remove exclusion">&times;</button>
            </div>
        `;

        row.querySelector('.btn-delete-interest').addEventListener('click', async () => {
            await handleDeleteInterest(item.id);
        });

        excludedList.appendChild(row);
    });
}

async function handleAddInterest(e) {
    e.preventDefault();
    const kw = inputNewInterest.value.trim();
    if (!kw) return;
    const instant = checkNewInterestAlert.checked;

    try {
        const res = await fetch('/api/interests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword: kw, instant_alert: instant, type: 'interested' })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || `Added '${kw}'!`, 'info');
            inputNewInterest.value = '';
            loadInterests();
        } else {
            showToast(data.error || 'Failed to add item', 'danger');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'danger');
    }
}

async function handleAddExcluded(e) {
    e.preventDefault();
    const kw = inputNewExcluded.value.trim();
    if (!kw) return;

    try {
        const res = await fetch('/api/interests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword: kw, instant_alert: false, type: 'excluded' })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || `Excluded '${kw}'!`, 'info');
            inputNewExcluded.value = '';
            loadInterests();
        } else {
            showToast(data.error || 'Failed to exclude item', 'danger');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'danger');
    }
}

async function handleToggleInstantAlert(id) {
    try {
        const res = await fetch(`/api/interests/${id}/toggle-alert`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            loadInterests();
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'danger');
    }
}

async function handleDeleteInterest(id) {
    try {
        const res = await fetch(`/api/interests/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast('Item removed.', 'info');
            loadInterests();
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'danger');
    }
}

// ---------------- Unique Condensed Products (Last 12 Months) ----------------
let condensedProductsCache = [];

async function handleReanalyzeAllProducts() {
    if (!condensedProductsGrid) return;
    showToast('Re-analyzing all listings and reconciling exclusions...', 'info');
    if (btnRefreshCondensed) btnRefreshCondensed.disabled = true;
    try {
        const reconcileRes = await fetch('/api/interests/reconcile', { method: 'POST' });
        const reconcileData = await reconcileRes.json();
        
        await loadCondensedProducts();
        await loadInterests();
        await loadListings();
        
        const count = reconcileData.affected_listings || 0;
        showToast(`Re-analysis complete! Updated ${count} excluded listings.`, 'info');
    } catch (e) {
        showToast('Error during re-analysis: ' + e.message, 'danger');
    } finally {
        if (btnRefreshCondensed) btnRefreshCondensed.disabled = false;
    }
}

async function loadCondensedProducts() {
    if (!condensedProductsGrid) return;
    try {
        const res = await fetch('/api/products/condensed?days=365');
        const data = await res.json();
        if (data.success) {
            condensedProductsCache = data.products || [];
            renderCondensedProducts();
        }
    } catch (e) {
        console.error('Error loading condensed products:', e);
    }
}

function renderCondensedProducts() {
    if (!condensedProductsGrid) return;
    condensedProductsGrid.innerHTML = '';

    const query = condensedSearchInput ? condensedSearchInput.value.toLowerCase().trim() : '';
    const statusFilter = filterCondensedStatus ? filterCondensedStatus.value : 'all';

    let filtered = condensedProductsCache.filter(p => {
        if (query && !p.name.toLowerCase().includes(query) && !p.category.toLowerCase().includes(query)) {
            return false;
        }
        if (statusFilter !== 'all') {
            if (p.interest_status !== statusFilter) return false;
        }
        return true;
    });

    if (filtered.length === 0) {
        condensedProductsGrid.classList.add('hidden');
        if (condensedEmpty) condensedEmpty.classList.remove('hidden');
        return;
    }

    condensedProductsGrid.classList.remove('hidden');
    if (condensedEmpty) condensedEmpty.classList.add('hidden');

    filtered.forEach(p => {
        const card = document.createElement('div');
        card.className = `condensed-card status-${p.interest_status}`;

        const isInterested = p.interest_status === 'interested';
        const isDisliked = p.interest_status === 'not_interested';
        const isStarred = Boolean(p.instant_alert);

        const imgHtml = p.sample_image
            ? `<img src="${p.sample_image}" alt="${escapeHtml(p.name)}" class="condensed-img" loading="lazy" />`
            : `<div class="condensed-img" style="display:flex;align-items:center;justify-content:center;font-size:1.5rem;">📦</div>`;

        card.innerHTML = `
            <div class="condensed-header">
                ${imgHtml}
                <div class="condensed-info">
                    <div class="condensed-title" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</div>
                    <div class="condensed-meta-row">
                        <span class="badge-count">${p.count} listed this year</span>
                        <span class="badge-cat">${escapeHtml(p.category)}</span>
                    </div>
                </div>
            </div>

            <div class="condensed-actions">
                <div class="condensed-feedback-btns">
                    <button class="btn-interest btn-interested ${isInterested ? 'active' : ''}" 
                            title="Interested in this product type" data-slug="${p.slug}">
                        👍 Interested
                    </button>
                    <button class="star-alert-btn ${isStarred ? 'starred' : 'unstarred'}" 
                            title="Immediate Priority Alert ⭐" data-slug="${p.slug}">
                        ${isStarred ? '⭐ Alert' : '☆ Alert'}
                    </button>
                    <button class="btn-interest btn-not-interested ${isDisliked ? 'active' : ''}" 
                            title="Dislike / Exclude this product type" data-slug="${p.slug}">
                        👎 Exclude
                    </button>
                </div>
                <button class="btn-toggle-listings" data-slug="${p.slug}">
                    👁️ Items (${p.listings.length})
                </button>
            </div>

            <div class="condensed-drawer hidden" id="drawer-${p.slug}">
                ${p.listings.map(item => `
                    <div class="condensed-item-row">
                        <span class="item-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</span>
                        <span style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(item.location || 'Local')}</span>
                        <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="item-link">View FB ↗</a>
                    </div>
                `).join('')}
            </div>
        `;

        // Drawer toggle
        const toggleBtn = card.querySelector('.btn-toggle-listings');
        const drawer = card.querySelector(`#drawer-${p.slug}`);
        toggleBtn.addEventListener('click', () => {
            drawer.classList.toggle('hidden');
            toggleBtn.textContent = drawer.classList.contains('hidden') ? `👁️ Items (${p.listings.length})` : `▲ Hide (${p.listings.length})`;
        });

        // Interested click
        const btnInt = card.querySelector('.btn-interested');
        btnInt.addEventListener('click', async () => {
            const nextStatus = isInterested ? 'none' : 'interested';
            await handleSetProductInterest(p.slug, nextStatus, isStarred);
        });

        // Star toggle
        const btnStar = card.querySelector('.star-alert-btn');
        btnStar.addEventListener('click', async () => {
            const nextStar = !isStarred;
            await handleSetProductInterest(p.slug, 'interested', nextStar);
        });

        // Exclude click
        const btnEx = card.querySelector('.btn-not-interested');
        btnEx.addEventListener('click', async () => {
            const nextStatus = isDisliked ? 'none' : 'not_interested';
            await handleSetProductInterest(p.slug, nextStatus, false);
        });

        condensedProductsGrid.appendChild(card);
    });
}

async function handleSetProductInterest(slug, status, instantAlert) {
    try {
        const res = await fetch(`/api/products/${slug}/interest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: status, instant_alert: instantAlert })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Updated preference for '${data.name}'!`, 'info');
            loadInterests();
            loadCondensedProducts();
            loadListings();
        }
    } catch (e) {
        showToast('Error updating product preference: ' + e.message, 'danger');
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

function formatDateDMY(timestamp) {
    if (!timestamp) return '';
    const d = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
    if (isNaN(d.getTime())) return '';
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    return `${day}/${month}/${year}`;
}

function formatDateTimeDMY(timestamp) {
    if (!timestamp) return '';
    const d = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
    if (isNaN(d.getTime())) return '';
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
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
