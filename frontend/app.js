document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('runBtn');
    const targetInput = document.getElementById('targetInput');
    const timelineContainer = document.getElementById('timelineContainer');

    // Config
    const API_BASE = 'http://127.0.0.1:8000';
    let activeEventSource = null; // Track the active SSE connection globally

    // Auto-cancel backend scan on page unload (refresh/close)
    window.addEventListener('beforeunload', () => {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }
        // sendBeacon is the ONLY reliable way to send data during page unload
        navigator.sendBeacon(`${API_BASE}/api/v1/pentest/cancel`);
    });

    // UI Setup for Max Steps
    const maxStepsInput = document.getElementById('maxStepsInput');
    const maxStepsValue = document.getElementById('maxStepsValue');
    if (maxStepsInput && maxStepsValue) {
        maxStepsInput.addEventListener('input', (e) => {
            maxStepsValue.textContent = e.target.value;
        });
    }

    // Tab Navigation
    const tabs = ['tabStream', 'tabChain', 'tabFindings', 'tabSOC'];
    const views = ['viewStream', 'viewChain', 'viewFindings', 'viewSOC'];

    // Restore State from localStorage
    const streamContainer = document.getElementById('streamContainer');
    const chainContainer = document.getElementById('chainContainer');
    const findingsContainer = document.getElementById('findingsContainer');
    const dynamicSocTable = document.getElementById('dynamicSocTable');

    if (streamContainer && localStorage.getItem('vanguard_stream')) {
        streamContainer.innerHTML = localStorage.getItem('vanguard_stream');
        // Add a visual indicator that this is cached/interrupted data
        const banner = document.createElement('div');
        banner.style.cssText = 'text-align:center; padding:10px; background:#1a1a2e; border:1px solid #ffb86c; color:#ffb86c; font-family:"IBM Plex Mono",monospace; font-size:0.8rem; margin-bottom:10px; border-radius:4px;';
        banner.textContent = '⚠ CACHED — SCAN WAS INTERRUPTED. Click INITIALIZE RUN to start a new scan.';
        streamContainer.prepend(banner);
        timelineContainer.scrollTop = timelineContainer.scrollHeight;
    }
    if (chainContainer && localStorage.getItem('vanguard_chain')) {
        chainContainer.innerHTML = localStorage.getItem('vanguard_chain');
    }
    if (findingsContainer && localStorage.getItem('vanguard_findings')) {
        findingsContainer.innerHTML = localStorage.getItem('vanguard_findings');
    }
    if (dynamicSocTable && localStorage.getItem('vanguard_soc')) {
        dynamicSocTable.innerHTML = localStorage.getItem('vanguard_soc');
    }

    // Zoom Logic
    let currentZoom = 1;
    function applyZoom() {
        const svg = document.querySelector('#chainContainer svg');
        if (svg) {
            svg.style.transform = `scale(${currentZoom})`;
            svg.style.transformOrigin = 'top center';
            svg.style.transition = 'transform 0.2s ease';
        }
    }

    document.getElementById('zoomInBtn')?.addEventListener('click', () => {
        currentZoom += 0.2;
        applyZoom();
    });

    document.getElementById('zoomOutBtn')?.addEventListener('click', () => {
        if (currentZoom > 0.4) {
            currentZoom -= 0.2;
            applyZoom();
        }
    });

    // Clear Cache & Cancel Backend Scan
    document.getElementById('clearBtn')?.addEventListener('click', async () => {
        // 1. Close any active SSE connection
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        // 2. Tell backend to kill the running scan
        try {
            await fetch(`${API_BASE}/api/v1/pentest/cancel`, { method: 'POST' });
        } catch (e) {
            console.warn('Cancel request failed:', e);
        }

        // 3. Clear localStorage
        localStorage.removeItem('vanguard_stream');
        localStorage.removeItem('vanguard_chain');
        localStorage.removeItem('vanguard_findings');
        localStorage.removeItem('vanguard_soc');

        // 4. Reset UI
        if (streamContainer) streamContainer.innerHTML = '<div class="empty-state mono-label">AWAITING TELEMETRY STREAM...</div>';
        if (chainContainer) chainContainer.innerHTML = '<div class="empty-state mono-label">NO ATTACK DATA AVAILABLE YET...</div>';
        if (findingsContainer) findingsContainer.innerHTML = '<div class="empty-state mono-label">NO VULNERABILITIES DETECTED YET...</div>';
        if (dynamicSocTable) dynamicSocTable.innerHTML = '<tr style="border-bottom:1px solid #222;"><td colspan="4" style="padding:10px; text-align:center; color:var(--text-muted); font-style:italic;">AWAITING SIMULATION COMPLETION TO GENERATE RULES...</td></tr>';
        currentZoom = 1;

        // 5. Reset button state
        runBtn.textContent = 'INITIALIZE RUN';
        runBtn.disabled = false;
    });

    tabs.forEach((tabId, index) => {
        document.getElementById(tabId).addEventListener('click', (e) => {
            e.preventDefault();
            // Reset all tabs
            tabs.forEach(id => {
                const el = document.getElementById(id);
                el.style.borderBottom = '2px solid transparent';
                el.style.color = 'var(--text-primary)';
            });
            // Hide all views
            views.forEach(id => document.getElementById(id).style.display = 'none');

            // Set active
            e.target.style.borderBottom = '2px solid var(--accent)';
            e.target.style.color = 'var(--accent)';
            document.getElementById(views[index]).style.display = 'block';
        });
    });

    runBtn.addEventListener('click', () => {
        const targetUrl = targetInput.value.trim();
        const scope = document.getElementById('scopeSelect').value;
        const maxSteps = document.getElementById('maxStepsInput') ? document.getElementById('maxStepsInput').value : 20;

        if (!targetUrl) return;

        runBtn.textContent = 'EXECUTING...';
        runBtn.disabled = true;

        // Reset container and clear storage on new run
        timelineContainer.innerHTML = '<div class="timeline" id="streamContainer"></div>';
        const streamContainer = document.getElementById('streamContainer');

        const chainEl = document.getElementById('chainContainer');
        const findingsEl = document.getElementById('findingsContainer');
        const socEl = document.getElementById('dynamicSocTable');

        if (chainEl) chainEl.innerHTML = '<div class="empty-state mono-label">NO ATTACK DATA AVAILABLE YET...</div>';
        if (findingsEl) findingsEl.innerHTML = '<div class="empty-state mono-label">NO VULNERABILITIES DETECTED YET...</div>';
        if (socEl) socEl.innerHTML = '<tr style="border-bottom:1px solid #222;"><td colspan="4" style="padding:10px; text-align:center; color:var(--text-muted); font-style:italic;">AWAITING SIMULATION COMPLETION TO GENERATE RULES...</td></tr>';

        localStorage.removeItem('vanguard_stream');
        localStorage.removeItem('vanguard_chain');
        localStorage.removeItem('vanguard_findings');
        localStorage.removeItem('vanguard_soc');

        // Close any previous SSE connection
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        // Connect to SSE stream (backend auto-cancels any previous scan)
        const eventSource = new EventSource(`${API_BASE}/api/v1/pentest/stream?target_url=${encodeURIComponent(targetUrl)}&scope=${encodeURIComponent(scope)}&max_steps=${maxSteps}`);
        activeEventSource = eventSource;

        eventSource.onmessage = function (event) {
            const data = JSON.parse(event.data);
            const node = document.createElement('details');

            if (data.type === 'thought') {
                node.className = 'node blue-detect';
                node.open = true;
                node.innerHTML = `
                    <summary class="node-title" style="cursor: pointer; list-style: none;">🧠 Cognitive Reason</summary>
                    <div class="code-block" style="color:#e0e0e0; font-family: 'Inter', sans-serif; margin-top: 1rem;">${data.data}</div>
                `;
            } else if (data.type === 'action') {
                node.className = 'node red-action';
                node.open = true;
                node.innerHTML = `
                    <summary class="node-title" style="cursor: pointer; list-style: none;">⚡ Tool Executed</summary>
                    <div class="code-block" style="color:#ffb86c; margin-top: 1rem;">${data.data}</div>
                `;
            } else if (data.type === 'observation') {
                node.className = 'node';
                node.style.borderLeft = '2px solid #53a8b6';
                node.open = true;
                node.innerHTML = `
                    <summary class="node-title" style="cursor: pointer; list-style: none;">📤 Environment Observation</summary>
                    <div class="node-meta mono-label" style="margin-top: 1rem;">STDOUT / STDERR</div>
                    <div class="code-block" style="color:#8be9fd">${data.data.replace(/\n/g, '<br>')}</div>
                `;
            } else if (data.type === 'chain') {
                const chainContainer = document.getElementById('chainContainer');

                // Using mermaid.render() for raw string injection avoids the init() race condition
                if (window.mermaid) {
                    mermaid.render('mermaid-graph-gen', data.data).then((result) => {
                        chainContainer.innerHTML = result.svg;
                        localStorage.setItem('vanguard_chain', chainContainer.innerHTML);
                        applyZoom();
                    }).catch((err) => {
                        console.error('Mermaid render error:', err);
                        chainContainer.innerHTML = `<div style="color:red; font-family:monospace;">Mermaid Syntax Error. Could not render graph.</div>`;
                        localStorage.setItem('vanguard_chain', chainContainer.innerHTML);
                    });
                } else {
                    chainContainer.innerHTML = `<pre>${data.data}</pre>`;
                    localStorage.setItem('vanguard_chain', chainContainer.innerHTML);
                }

                // Don't append to stream
                return;
            } else if (data.type === 'findings') {
                const findingsContainer = document.getElementById('findingsContainer');
                if (data.data && data.data.length > 0) {
                    let html = `<ul style="color:#ffb86c; font-family:'IBM Plex Mono', monospace; font-size: 0.9rem; line-height: 1.6; list-style-type: none; padding-left: 0;">`;

                    // Sometimes the LLM returns an array of strings, sometimes a string representation of an array.
                    let findingList = data.data;
                    if (!Array.isArray(findingList)) {
                        try {
                            // Try to parse if it's a stringified array
                            findingList = JSON.parse(findingList);
                        } catch (e) {
                            findingList = [findingList];
                        }
                    }

                    if (Array.isArray(findingList)) {
                        findingList.forEach((f, index) => {
                            const cleanText = String(f).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                            html += `<li style="margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #333;">
                                <span style="color:#50fa7b; font-weight:bold;">[Finding ${index + 1}]</span> ${cleanText}
                            </li>`;
                        });
                    } else {
                        html += `<li style="margin-bottom: 15px;">${String(findingList).replace(/</g, "&lt;")}</li>`;
                    }
                    html += '</ul>';
                    findingsContainer.innerHTML = html;
                } else {
                    findingsContainer.innerHTML = '<div class="empty-state mono-label" style="color:#50fa7b;">✅ ZERO EXPLOITABLE VULNERABILITIES IDENTIFIED</div>';
                }
                localStorage.setItem('vanguard_findings', findingsContainer.innerHTML);
                return;
            } else if (data.type === 'soc_rules') {
                const socTable = document.getElementById('dynamicSocTable');
                if (data.data) {
                    let html = '';

                    // Parse data.data if it arrives as a string
                    let parsedData = data.data;
                    if (typeof parsedData === 'string') {
                        try {
                            parsedData = JSON.parse(parsedData);
                        } catch (e) {
                            console.error("Failed to parse SOC rules payload: ", e);
                        }
                    }

                    const existingRules = parsedData.existing_rules || [];
                    const newRules = parsedData.newly_generated_rules || [];

                    // Render Existing Rules
                    existingRules.forEach((rule, idx) => {
                        const ruleId = rule.id || `SIG-EXIST-${idx + 1}`;
                        const name = rule.rule_name || rule.name || "Unknown Rule";
                        const sev = rule.severity || "Medium";
                        const logic = rule.logic || "N/A";

                        let sevColor = '#ffb86c'; // Medium
                        if (sev.toLowerCase() === 'high') sevColor = '#ff5555';
                        else if (sev.toLowerCase() === 'critical') sevColor = '#ff5555; font-weight:bold';
                        else if (sev.toLowerCase() === 'low') sevColor = '#f1fa8c';

                        html += `<tr style="border-bottom:1px solid #222;">
                            <td style="padding:10px;">${ruleId.replace(/</g, "&lt;")}</td>
                            <td style="padding:10px;">
                                <div style="font-weight:bold; margin-bottom:4px;">${name.replace(/</g, "&lt;")}</div>
                                <div style="color:var(--text-muted); font-size:0.8rem; background:rgba(0,0,0,0.3); padding:4px; border-radius:2px;">${logic.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
                            </td>
                            <td style="padding:10px; color:${sevColor};">${sev.replace(/</g, "&lt;")}</td>
                            <td style="padding:10px; color:var(--text-muted);">Active SIEM Rule</td>
                        </tr>`;
                    });

                    // Render News Rules
                    newRules.forEach((rule, idx) => {
                        const ruleId = rule.id || `SIG-NEW-${idx + 1}`;
                        const name = rule.rule_name || rule.name || "Unknown Rule";
                        const sev = rule.severity || "Medium";
                        const logic = rule.logic || "N/A";

                        let sevColor = '#ffb86c'; // Medium
                        if (sev.toLowerCase() === 'high') sevColor = '#ff5555';
                        else if (sev.toLowerCase() === 'critical') sevColor = '#ff5555; font-weight:bold';
                        else if (sev.toLowerCase() === 'low') sevColor = '#f1fa8c';

                        html += `<tr style="border-bottom:1px solid #222; background: rgba(80, 250, 123, 0.05);">
                            <td style="padding:10px;">${ruleId.replace(/</g, "&lt;")}</td>
                            <td style="padding:10px;">
                                <div style="font-weight:bold; margin-bottom:4px;">${name.replace(/</g, "&lt;")}</div>
                                <div style="color:var(--text-muted); font-size:0.8rem; background:rgba(0,0,0,0.3); padding:4px; border-radius:2px;">${logic.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
                            </td>
                            <td style="padding:10px; color:${sevColor};">${sev.replace(/</g, "&lt;")}</td>
                            <td style="padding:10px; color:#50fa7b; font-weight:bold;">✨ AI Generated</td>
                        </tr>`;
                    });

                    if (existingRules.length === 0 && newRules.length === 0) {
                        html += `<tr style="border-bottom:1px solid #222;"><td colspan="4" style="padding:15px; text-align:center; color:#ffb86c; font-weight:bold; font-style:italic;">SYSTEM NOTICE: Elasticsearch/Kibana is currently offline, so Vanguard could not query existing definitions. Furthermore, the AI Engine failed to synthesize new defenses for this session.</td></tr>`;
                    }

                    if (socTable) {
                        socTable.innerHTML = html;
                        localStorage.setItem('vanguard_soc', html);
                    }
                }
                return;
            } else if (data.type === 'finish') {
                node.className = 'node blue-detect';
                node.style.borderLeft = '2px solid #50fa7b';
                node.open = true;
                node.innerHTML = `
                    <summary class="node-title" style="cursor: pointer; list-style: none;">✅ Mission Complete</summary>
                    <div class="code-block" style="color:#50fa7b; margin-top: 1rem;">${data.data}</div>
                `;
                eventSource.close();
                runBtn.textContent = 'INITIALIZE RUN';
                runBtn.disabled = false;
            } else if (data.type === 'error') {
                node.className = 'node red-action';
                node.open = true;
                node.innerHTML = `
                    <summary class="node-title" style="cursor: pointer; list-style: none;">❌ Error</summary>
                    <div class="code-block" style="color:#ff5555; margin-top: 1rem;">${data.data}</div>
                `;
                eventSource.close();
                runBtn.textContent = 'INITIALIZE RUN';
                runBtn.disabled = false;
            } else if (data.type === 'close') {
                eventSource.close();
                if (runBtn.disabled) {
                    runBtn.textContent = 'INITIALIZE RUN';
                    runBtn.disabled = false;
                }
            }

            streamContainer.appendChild(node);
            localStorage.setItem('vanguard_stream', streamContainer.innerHTML);

            // Auto-scroll to bottom
            timelineContainer.scrollTop = timelineContainer.scrollHeight;
        };

        eventSource.onerror = function (err) {
            console.error("SSE Error:", err);
            eventSource.close();
            runBtn.textContent = 'INITIALIZE RUN';
            runBtn.disabled = false;

            const errNode = document.createElement('div');
            errNode.className = 'empty-state mono-label';
            errNode.style.color = '#e24a4a';
            errNode.textContent = 'CONNECTION ERROR / STREAM TERMINATED';
            streamContainer.appendChild(errNode);
        };
    });
});
