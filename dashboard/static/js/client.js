// IIIS Client Javascript SPA Controller

document.addEventListener("DOMContentLoaded", () => {
    // Determine active tab based on active link
    const path = window.location.pathname;
    
    // Page-specific initializations
    if (path.includes("/day-replay")) {
        initDayReplay();
    } else if (path.includes("/dashboard")) {
        initMissionControl();
    } else if (path.includes("/operations")) {
        initOperations();
    } else if (path.includes("/analyst")) {
        initAnalyst();
    }
    
    // Setup logouts
    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", handleLogout);
    }

    // Refresh KPI strip on page load
    updateKpiStrip();
});

// --- GLOBAL KPI STRIP CONTROL ---

async function updateKpiStrip() {
    try {
        const response = await fetch("/api/kpi-strip");
        if (response.ok) {
            const data = await response.json();
            
            const sigVal = document.getElementById("kpi_signals");
            const riskVal = document.getElementById("kpi_risk");
            const arcVal = document.getElementById("kpi_arc");
            const watchVal = document.getElementById("kpi_watchlist");
            const slackVal = document.getElementById("kpi_slack");
            const ghostVal = document.getElementById("kpi_ghost");
            const sigTimeVal = document.getElementById("kpi_last_signal");
            const scanTimeVal = document.getElementById("kpi_last_scan");
            
            if (sigVal) sigVal.innerText = data.approved_signals;
            if (riskVal) riskVal.innerText = data.risk_used;
            if (arcVal) arcVal.innerText = data.arc_approved;
            if (watchVal) watchVal.innerText = data.watchlist_count;
            
            if (slackVal) {
                slackVal.innerHTML = `<span class="dot ${data.slack_status.toLowerCase()}"></span> ${data.slack_status}`;
            }
            if (ghostVal) {
                const isGhost = data.ghost_mode === "ACTIVE";
                ghostVal.innerHTML = `<span class="dot ${isGhost ? 'red' : 'green'}"></span> ${data.ghost_mode}`;
            }
            if (sigTimeVal) sigTimeVal.innerText = data.last_signal_time;
            if (scanTimeVal) scanTimeVal.innerText = data.last_scan_time;
        }
    } catch (error) {
        console.error("Failed to update KPI strip:", error);
    }
}

// --- LOGOUT ACTION ---

async function handleLogout() {
    const response = await fetch("/api/auth/logout", { method: "POST" });
    if (response.ok) {
        const data = await response.json();
        window.location.href = data.redirect;
    }
}

// --- PAGE 1: MISSION CONTROL ---

function initMissionControl() {
    fetchMissionControlData();
    // Auto-refresh every 10 seconds for real-time live scan status
    setInterval(fetchMissionControlData, 10000);
}

async function fetchMissionControlData() {
    try {
        const response = await fetch("/api/mission-control");
        if (!response.ok) return;
        const data = await response.json();

        // 1. Regime Details
        document.getElementById("regime_name").innerText = data.market_regime;
        document.getElementById("regime_score").innerText = data.regime_score.toFixed(1);
        document.getElementById("nifty_price").innerText = "Rs " + data.nifty_price.toLocaleString("en-IN", {minimumFractionDigits: 2});

        // 2. Narrative (Modification 3)
        document.getElementById("narrative_text").innerText = data.narrative;

        // 3. Top News (GEIE Events)
        const newsContainer = document.getElementById("top_news_list");
        newsContainer.innerHTML = "";
        if (data.top_news.length === 0) {
            newsContainer.innerHTML = "<div class='story-item'>No news impacting approved signals today.</div>";
        } else {
            data.top_news.forEach(item => {
                const cls = item.direction.toLowerCase();
                const div = document.createElement("div");
                div.className = "story-item";
                div.style.marginBottom = "10px";
                div.innerHTML = `<span class="badge ${cls}" style="margin-right: 8px;">${item.direction}</span> <strong>${item.symbol}:</strong> ${item.headline} <span style="font-size:0.75rem; color:var(--text-secondary);">(${item.confidence} Conf)</span>`;
                newsContainer.appendChild(div);
            });
        }

        // 4. What To Watch (Watchlist table)
        const watchTable = document.getElementById("watchlist_table_body");
        watchTable.innerHTML = "";
        if (data.what_to_watch.length === 0) {
            watchTable.innerHTML = "<tr><td colspan='4' style='text-align:center; padding:15px; color:var(--text-secondary);'>No signals approved today.</td></tr>";
        } else {
            data.what_to_watch.forEach(sig => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td style="padding:10px 0;"><strong>${sig.symbol}</strong></td>
                    <td><span class="badge ${sig.direction.toLowerCase()}">${sig.direction}</span></td>
                    <td>${sig.score}</td>
                    <td style="font-weight:700; color:var(--accent-purple);">${sig.grade}</td>
                `;
                watchTable.appendChild(tr);
            });
        }

        // 5. Live Scan Status
        document.getElementById("last_scan_time").innerText = data.last_scan_time;
        const statusEl = document.getElementById("session_status_val");
        statusEl.innerText = data.session_status;
        statusEl.className = data.session_status === "ACTIVE" ? "status-indicator" : "status-indicator";

        // 6. System Health Uptime Indicators
        const healthGrid = document.getElementById("system_health_grid");
        healthGrid.innerHTML = "";
        for (const [service, statusVal] of Object.entries(data.system_health)) {
            const card = document.createElement("div");
            card.className = "kpi-card";
            card.style.flexDirection = "row";
            card.style.justifyContent = "space-between";
            card.style.alignItems = "center";
            card.innerHTML = `
                <div>
                    <div class="kpi-label">${service}</div>
                </div>
                <div class="status-indicator">
                    <span class="dot ${statusVal === 'GREEN' ? 'green' : statusVal === 'YELLOW' ? 'yellow' : 'red'}"></span> ${statusVal}
                </div>
            `;
            healthGrid.appendChild(card);
        }
        
        // Sync global KPI strip
        updateKpiStrip();
    } catch (e) {
        console.error("Error loading mission control details:", e);
    }
}

// --- PAGE 2: DAY REPLAY ---

let currentDateVal = "2026-06-17";

function initDayReplay() {
    const picker = document.getElementById("replayDatePicker");
    if (picker) {
        picker.addEventListener("change", (e) => {
            currentDateVal = e.target.value;
            fetchDayReplayData(currentDateVal);
        });
    }

    // JSON and MD downloads
    document.getElementById("btnDownloadJson").addEventListener("click", () => triggerDownload("json"));
    document.getElementById("btnDownloadMd").addEventListener("click", () => triggerDownload("markdown"));
    document.getElementById("btnPrintPdf").addEventListener("click", () => window.print());

    // Compare Mode actions
    document.getElementById("btnCompareMode").addEventListener("click", toggleCompareMode);
    document.getElementById("btnExecuteCompare").addEventListener("click", executeDateComparison);

    // Initial load
    fetchDayReplayData(currentDateVal);
}

async function fetchDayReplayData(dateStr) {
    try {
        const response = await fetch(`/api/day-replay?date=${dateStr}`);
        if (!response.ok) return;
        const data = await response.json();

        // 1. Morning Story
        document.getElementById("story_geie").innerText = data.morning_story.geie;
        document.getElementById("story_arc").innerText = data.morning_story.arc;
        
        const watchlistEl = document.getElementById("story_watchlist_list");
        watchlistEl.innerHTML = "";
        if (data.morning_story.watchlist.length === 0) {
            watchlistEl.innerText = "No symbols approved for premarket watchlist.";
        } else {
            watchlistEl.innerText = data.morning_story.watchlist.join(", ");
        }

        // 2. Market Timeline
        const timelineList = document.getElementById("timeline_events_list");
        timelineList.innerHTML = "";
        if (data.timeline.length === 0) {
            timelineList.innerHTML = "<div style='color:var(--text-secondary); margin-left:10px;'>No timeline events available for this date.</div>";
        } else {
            data.timeline.forEach(event => {
                const item = document.createElement("div");
                item.className = "timeline-item";
                item.innerHTML = `
                    <div class="timeline-time">${event.time}</div>
                    <div class="timeline-title">${event.event}</div>
                    <div class="timeline-desc">${event.details}</div>
                `;
                timelineList.appendChild(item);
            });
        }

        // 3. Approved Signals List
        const signalsList = document.getElementById("approved_signals_list");
        signalsList.innerHTML = "";
        if (data.approved_signals.length === 0) {
            signalsList.innerHTML = "<div style='color:var(--text-secondary); padding: 10px 0;'>No approved signals matched today's session rules.</div>";
        } else {
            data.approved_signals.forEach(sig => {
                const card = document.createElement("div");
                card.className = "signal-detail-card";
                card.innerHTML = `
                    <div class="signal-header">
                        <div class="signal-title">${sig.symbol} <span class="badge ${sig.direction.toLowerCase()}">${sig.direction}</span></div>
                        <div style="font-weight:800; font-size:1.15rem; color:var(--accent-purple);">Grade ${sig.grade}</div>
                    </div>
                    <div class="signal-grid">
                        <div class="signal-info-item">Score <span>${sig.score}</span></div>
                        <div class="signal-info-item">GEIE Direction <span>${sig.geie}</span></div>
                        <div class="signal-info-item">ARC Decision <span>${sig.arc}</span></div>
                        <div class="signal-info-item">Big Money <span>Confluence Active</span></div>
                        <div class="signal-info-item">Risk Decision <span>Passed</span></div>
                    </div>
                    <div class="signal-explanation">
                        <strong>Decision Reasoning:</strong> ${sig.explanation}
                    </div>
                `;
                signalsList.appendChild(card);
            });
        }

        // 4. End Of Day Summary
        document.getElementById("eod_total_signals").innerText = data.eod_summary.total_signals;
        document.getElementById("eod_approved").innerText = data.eod_summary.approved_signals;
        document.getElementById("eod_risk_used").innerText = data.eod_summary.risk_used;
        document.getElementById("eod_sector").innerText = data.eod_summary.strongest_sector;
        document.getElementById("eod_symbol").innerText = data.eod_summary.strongest_symbol;

    } catch (e) {
        console.error("Error loading day replay:", e);
    }
}

function triggerDownload(format) {
    window.location.href = `/api/day-replay/download?date=${currentDateVal}&format=${format}`;
}

// --- DATE COMPARE MODE ENGINE ---

let compareModeActive = false;

function toggleCompareMode() {
    compareModeActive = !compareModeActive;
    const compareBox = document.getElementById("compareContainer");
    const compareBtn = document.getElementById("btnCompareMode");
    
    if (compareModeActive) {
        compareBox.style.display = "block";
        compareBtn.innerText = "Close Compare Mode";
        compareBtn.className = "btn btn-secondary";
        
        // Default target date for compare picker is date picker - 7 days
        const picker = document.getElementById("replayDatePicker");
        const baseDate = new Date(picker.value);
        baseDate.setDate(baseDate.getDate() - 7);
        document.getElementById("compareDatePicker").value = baseDate.toISOString().split("T")[0];
    } else {
        compareBox.style.display = "none";
        compareBtn.innerText = "Replay Compare Mode";
        compareBtn.className = "btn";
    }
}

async function executeDateComparison() {
    const date1 = document.getElementById("replayDatePicker").value;
    const date2 = document.getElementById("compareDatePicker").value;
    
    try {
        const response = await fetch(`/api/day-replay/compare?date1=${date1}&date2=${date2}`);
        if (!response.ok) return;
        const data = await response.json();
        
        // Render comparison view
        const resultsBox = document.getElementById("compareResults");
        resultsBox.innerHTML = `
            <div class="compare-columns">
                <div class="compare-column">
                    <div class="compare-date-title">${data.date1.date}</div>
                    <div class="compare-row"><span>Approved Signals:</span> <span>${data.date1.approved_signals}</span></div>
                    <div class="compare-row"><span>ARC Watchlist:</span> <span>${data.date1.arc_approvals}</span></div>
                    <div class="compare-row"><span>GEIE Sentiment:</span> <span>${data.date1.geie_direction}</span></div>
                    <div class="compare-row"><span>Risk Budget:</span> <span>${data.date1.risk_utilization}</span></div>
                </div>
                <div class="compare-column">
                    <div class="compare-date-title">${data.date2.date}</div>
                    <div class="compare-row"><span>Approved Signals:</span> <span>${data.date2.approved_signals}</span></div>
                    <div class="compare-row"><span>ARC Watchlist:</span> <span>${data.date2.arc_approvals}</span></div>
                    <div class="compare-row"><span>GEIE Sentiment:</span> <span>${data.date2.geie_direction}</span></div>
                    <div class="compare-row"><span>Risk Budget:</span> <span>${data.date2.risk_utilization}</span></div>
                </div>
            </div>
        `;
    } catch (e) {
        console.error("Comparison load error:", e);
    }
}

// --- PAGE 3: OPERATIONS & DIAGNOSTICS ---

function initOperations() {
    fetchOperationsDetails();
    setInterval(fetchOperationsDetails, 15000);
}

async function fetchOperationsDetails() {
    try {
        const response = await fetch("/api/operations");
        if (!response.ok) return;
        const data = await response.json();

        // 1. Runtime Status
        const statusVal = document.getElementById("ops_runtime_status");
        statusVal.innerText = data.runtime_status;
        statusVal.className = data.runtime_status === "RUNNING" ? "badge long" : "badge short";

        // 2. Ghost Mode
        const ghostVal = document.getElementById("ops_ghost_mode");
        ghostVal.innerText = data.ghost_mode;
        ghostVal.className = data.ghost_mode === "ACTIVE" ? "badge short" : "badge long";

        // 3. Service Indicators Grid
        const grid = document.getElementById("ops_services_grid");
        grid.innerHTML = "";
        data.services.forEach(serv => {
            const card = document.createElement("div");
            card.className = "service-card";
            card.innerHTML = `
                <div>
                    <div class="service-name">${serv.name}</div>
                    <div class="service-desc">${serv.type} (Latency: ${serv.latency})</div>
                </div>
                <div class="status-indicator">
                    <span class="dot ${serv.status.toLowerCase() === 'green' ? 'green' : serv.status.toLowerCase() === 'yellow' ? 'yellow' : 'red'}"></span> ${serv.status}
                </div>
            `;
            grid.appendChild(card);
        });

        // 4. Recent Errors Table
        const errTable = document.getElementById("ops_errors_table");
        errTable.innerHTML = "";
        if (data.recent_errors.length === 0) {
            errTable.innerHTML = "<tr><td colspan='3' style='text-align:center; padding:15px; color:var(--text-secondary);'>No operational errors recorded in system diagnostics.</td></tr>";
        } else {
            data.recent_errors.forEach(err => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td style="color:var(--text-secondary); width:80px;">${err.time}</td>
                    <td style="color:var(--accent-red); font-weight:700; width:150px;">${err.component}</td>
                    <td><code>${err.error}</code></td>
                `;
                errTable.appendChild(tr);
            });
        }
        
    } catch (e) {
        console.error("Operations diagnostic load failure:", e);
    }
}

// --- PAGE 4: AI ANALYST CHAT ---

function initAnalyst() {
    const chatInput = document.getElementById("chatInput");
    const sendBtn = document.getElementById("btnSendChat");
    
    if (sendBtn && chatInput) {
        sendBtn.addEventListener("click", submitChatMessage);
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") submitChatMessage();
        });
    }

    // Chat shortcuts
    const tags = document.querySelectorAll(".chat-shortcut-tag");
    tags.forEach(tag => {
        tag.addEventListener("click", () => {
            chatInput.value = tag.getAttribute("data-query");
            submitChatMessage();
        });
    });
}

async function submitChatMessage() {
    const chatInput = document.getElementById("chatInput");
    const query = chatInput.value.trim();
    if (!query) return;

    // Display user bubble
    appendChatBubble(query, "user");
    chatInput.value = "";

    // Add thinking/typing bubble
    const thinkingId = appendChatBubble("Searching database files...", "bot");

    try {
        const response = await fetch("/api/analyst/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: json = JSON.stringify({ message: query })
        });
        
        const botBubble = document.getElementById(thinkingId);
        if (response.ok) {
            const data = await response.json();
            botBubble.innerHTML = formatMarkdown(data.reply);
        } else {
            botBubble.innerText = "Error: Failed to obtain response from grounded database layers.";
        }
    } catch (e) {
        console.error("Chat error:", e);
        const botBubble = document.getElementById(thinkingId);
        botBubble.innerText = "Network Error: Could not connect to AI analyst service.";
    }
}

function appendChatBubble(text, sender) {
    const chatBox = document.getElementById("chatMessagesBox");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;
    bubble.innerText = text;
    
    const bubbleId = "bubble_" + Math.random().toString(36).substr(2, 9);
    bubble.id = bubbleId;
    
    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    return bubbleId;
}

function formatMarkdown(text) {
    // Simple parser for formatting bold text, inline code, and lists in chat
    let formatted = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/- (.*?)\n/g, '• $1<br>');
    return formatted;
}
