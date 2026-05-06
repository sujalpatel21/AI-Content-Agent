let pipelineData = {
    scraper: null,
    validator: null,
    voice_writer: null,
    hook_generator: null
};

document.addEventListener('DOMContentLoaded', () => {
    const newRunBtn = document.getElementById('new-run-btn');
    const startModal = document.getElementById('start-modal');
    const confirmRunBtn = document.getElementById('confirm-run-btn');
    const topicInput = document.getElementById('topic-input');
    const skipScrapeCb = document.getElementById('skip-scrape');

    let eventSource = null;

    // Connect SSE for live updates
    function connectSSE() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/api/events');

        eventSource.addEventListener('pipeline_start', (e) => {
            resetPipelineUI();
        });

        eventSource.addEventListener('agent_status', (e) => {
            const data = JSON.parse(e.data);
            updateAgentNodeStatus(data.agent, data.status);
        });

        eventSource.addEventListener('agent_output', (e) => {
            const data = JSON.parse(e.data);
            pipelineData[data.agent] = data.data;
            updateAgentMetrics(data.agent, data.data);
            enableViewButton(data.agent);
        });

        eventSource.addEventListener('pipeline_done', (e) => {
            const data = JSON.parse(e.data);
            updateInsights(data.validation);
            addRecentRun(data.topic);
            updateTopics(data.validation);
        });
    }
    
    connectSSE();

    // --- Modal Controls ---
    newRunBtn.addEventListener('click', () => {
        startModal.classList.add('active');
    });

    window.closeStartModal = () => {
        startModal.classList.remove('active');
    };

    window.closeResultsModal = () => {
        document.getElementById('results-modal').classList.remove('active');
    };

    // Start Run
    confirmRunBtn.addEventListener('click', async () => {
        closeStartModal();
        try {
            await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic: topicInput.value,
                    skip_scrape: skipScrapeCb.checked
                })
            });
        } catch (err) {
            alert('Failed to start pipeline: ' + err.message);
        }
    });

    // --- Pipeline UI Updaters ---
    function resetPipelineUI() {
        pipelineData = { scraper: null, validator: null, voice_writer: null, hook_generator: null };
        const agents = ['scraper', 'validator', 'voice_writer', 'hook_generator'];
        agents.forEach(agent => {
            updateAgentNodeStatus(agent, 'idle');
            const btn = document.querySelector(`#node-${agent} .view-link`);
            if (btn) btn.disabled = true;
        });
        
        // Reset metrics
        document.getElementById('metric-scraper-val').textContent = '--';
        document.getElementById('metric-validator-val').textContent = '--';
        document.getElementById('metric-writer-val').textContent = '--';
        document.getElementById('metric-hook-val').textContent = '--';
    }

    function updateAgentNodeStatus(agent, status) {
        const statusEl = document.getElementById(`status-${agent}`);
        if (!statusEl) return;
        
        if (status === 'idle') {
            statusEl.innerHTML = `<span class="badge-idle">Idle</span>`;
        } else if (status === 'running') {
            statusEl.innerHTML = `<span class="badge-running"><i class="fa-solid fa-circle-notch fa-spin"></i> Running</span>`;
        } else if (status === 'done' || status === 'skipped') {
            statusEl.innerHTML = `<span class="badge-done"><i class="fa-solid fa-check"></i> Completed</span>`;
            // Also color the connector if this agent is done (except hook_generator which has no outgoing connector)
            const node = document.getElementById(`node-${agent}`);
            const connector = node.nextElementSibling;
            if (connector && connector.classList.contains('connector')) {
                connector.classList.add('active');
            }
        } else if (status === 'error') {
            statusEl.innerHTML = `<span style="color:#ef4444"><i class="fa-solid fa-xmark"></i> Failed</span>`;
        }
    }

    function updateAgentMetrics(agent, data) {
        if (!data) return;
        if (agent === 'scraper') {
            // Because we might skip scrape and fetch cached, it might not broadcast output explicitly if skipped. 
            // We rely on /api/output endpoints or the passed data.
            // If data is array (raw json), we count length.
            const len = Array.isArray(data) ? data.length : (data.validated_posts ? data.validated_posts.length : '--');
            document.getElementById('metric-scraper-val').textContent = len;
            document.getElementById('metric-scraper-dur').textContent = 'Cached';
        } else if (agent === 'validator') {
            const filtered = data.validated_posts ? data.validated_posts.length : '--';
            document.getElementById('metric-validator-val').textContent = filtered;
            document.getElementById('metric-validator-conf').textContent = '89%'; // Mock
        } else if (agent === 'voice_writer') {
            document.getElementById('metric-writer-val').textContent = '1';
            document.getElementById('metric-writer-match').textContent = '91%'; // Mock
        } else if (agent === 'hook_generator') {
            const hookCount = data.hooks ? data.hooks.length : '--';
            document.getElementById('metric-hook-val').textContent = hookCount;
            document.getElementById('metric-hook-score').textContent = '88%'; // Mock
        }
    }

    function enableViewButton(agent) {
        const btn = document.querySelector(`#node-${agent} .view-link`);
        if (btn) btn.disabled = false;
    }

    // --- Results Modal Renderer ---
    window.showResults = async (agent) => {
        const modal = document.getElementById('results-modal');
        const title = document.getElementById('modal-title');
        const body = document.getElementById('modal-body-content');
        
        let data = pipelineData[agent];
        
        // If data isn't in memory, try fetching it
        if (!data) {
            try {
                const res = await fetch(`/api/output/${agent === 'voice_writer' ? 'script' : agent === 'hook_generator' ? 'hooks' : agent === 'validator' ? 'validate' : 'scrape'}`);
                data = await res.json();
                pipelineData[agent] = data; // Cache it
                updateAgentMetrics(agent, data); // Backfill metrics
            } catch (e) {
                body.innerHTML = `<p style="color:red">Failed to load data.</p>`;
                modal.classList.add('active');
                return;
            }
        }

        body.innerHTML = '';

        if (agent === 'scraper' || agent === 'validator') {
            title.textContent = agent === 'scraper' ? 'Scraped Content Results' : 'Validated Content Insights';
            const posts = agent === 'scraper' ? data : data.validated_posts;
            
            if (agent === 'validator') {
                body.innerHTML += `
                    <div style="background: rgba(16, 185, 129, 0.1); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; border: 1px solid rgba(16, 185, 129, 0.3);">
                        <h4 style="color: #34d399; margin-bottom:0.5rem">Recommendation</h4>
                        <p>${data.recommendation.replace(/\*\*/g, '')}</p>
                    </div>
                `;
            }

            let tableHtml = `<table class="result-table">
                <thead><tr><th>Platform</th><th>Format</th><th>Views</th><th>ER</th><th>Topic/Hook</th></tr></thead><tbody>`;
            
            (posts || []).slice(0, 15).forEach(p => {
                tableHtml += `<tr>
                    <td>${p.platform}</td>
                    <td>${p.format}</td>
                    <td>${(p.views || 0).toLocaleString()}</td>
                    <td>${p.engagement_rate}%</td>
                    <td><div style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(p.hook_text)}">${escapeHtml(p.hook_text)}</div></td>
                </tr>`;
            });
            tableHtml += `</tbody></table>`;
            body.innerHTML += tableHtml;
        } 
        else if (agent === 'voice_writer') {
            title.textContent = 'Generated Script';
            body.innerHTML = `
                <div style="margin-bottom: 1rem; color: var(--text-secondary);">Topic: <strong>${escapeHtml(data.topic || 'Auto')}</strong></div>
                <div class="script-preview">${escapeHtml(data.full_script)}</div>
            `;
        }
        else if (agent === 'hook_generator') {
            title.textContent = 'Generated Hooks';
            if (data.hooks) {
                body.innerHTML = data.hooks.map(h => `
                    <div class="hook-item">
                        <h4>Hook 0${h.number} - ${escapeHtml(h.pattern)} ${h.number === data.recommended_hook ? '⭐ RECOMMENDED' : ''}</h4>
                        <p>"${escapeHtml(h.hook_text)}"</p>
                    </div>
                `).join('');
            }
        }

        modal.classList.add('active');
    };

    // --- Bottom Row Updaters ---
    function updateInsights(valData) {
        if (!valData) return;
        document.getElementById('ui-insight-topic').textContent = valData.top_topics[0]?.topic_cluster || 'N/A';
        document.getElementById('ui-insight-topic-sub').textContent = 'High viral signal detected';
        document.getElementById('ui-insight-format').textContent = valData.top_formats[0]?.format || 'Reels';
        document.getElementById('ui-insight-format-sub').textContent = 'Best performing format';
    }

    function addRecentRun(topic) {
        const tbody = document.getElementById('runs-tbody');
        const now = new Date();
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${topic || 'Auto Viral Scan Run'}</td>
            <td><span class="agent-pill">01</span><i class="fa-solid fa-arrow-right"></i><span class="agent-pill">02</span><i class="fa-solid fa-arrow-right"></i><span class="agent-pill">03</span><i class="fa-solid fa-arrow-right"></i><span class="agent-pill">04</span></td>
            <td><span class="status-text success">Completed</span></td>
            <td>${now.toLocaleDateString('en-US', {month: 'short', day: '2-digit', year: 'numeric'})} ${now.toLocaleTimeString('en-US', {hour: '2-digit', minute:'2-digit'})}</td>
            <td>Full Pipeline Output</td>
            <td><i class="fa-solid fa-chevron-right"></i></td>
        `;
        tbody.insertBefore(row, tbody.firstChild);
        if (tbody.children.length > 4) tbody.removeChild(tbody.lastChild);
    }

    function updateTopics(valData) {
        if (!valData || !valData.top_topics) return;
        const list = document.getElementById('ui-topics-list');
        list.innerHTML = valData.top_topics.slice(0, 4).map((t, i) => {
            const max = valData.top_topics[0].avg_views;
            const pct = Math.max(10, Math.round((t.avg_views / max) * 100));
            return `
            <div class="topic-item">
                <div class="topic-item-head"><span>${escapeHtml(t.topic_cluster)}</span><span>${(t.avg_views/1000).toFixed(0)}K</span></div>
                <div class="progress-bg"><div class="progress-fill bg-purple" style="width: ${pct}%;"></div></div>
            </div>`;
        }).join('');
    }

    function escapeHtml(unsafe) {
        return (unsafe || "").toString()
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    // Auto-fetch cached data to populate buttons on load if they exist
    setTimeout(() => {
        ['scraper', 'validator', 'voice_writer', 'hook_generator'].forEach(agent => {
            fetch(`/api/output/${agent === 'voice_writer' ? 'script' : agent === 'hook_generator' ? 'hooks' : agent === 'validator' ? 'validate' : 'scrape'}`)
            .then(r => {
                if(r.ok) {
                    r.json().then(d => {
                        if (Object.keys(d).length > 0) {
                            pipelineData[agent] = d;
                            enableViewButton(agent);
                            updateAgentMetrics(agent, d);
                            if (agent === 'validator') {
                                updateInsights(d);
                                updateTopics(d);
                            }
                        }
                    });
                }
            }).catch(()=>{});
        });
    }, 1000);
});
