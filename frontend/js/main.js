// API URL: Use current hostname/port dynamically, but override /api path on root
const API_URL = `${window.location.protocol}//${window.location.host}/api`;
let currentProjectId = null;
let currentUser = null;
let cy = null;

// ============================================
// SECTION: Message Modal Functions
// ============================================

function showMessage(title, message, type = 'info') {
    const modal = document.getElementById('messageModal');
    const iconElement = document.getElementById('messageIcon');

    // Set icon based on type
    const icons = {
        'error': '❌',
        'success': '✅',
        'info': 'ℹ️',
        'warning': '⚠️'
    };

    iconElement.textContent = icons[type] || '❌';

    // Set content
    document.getElementById('messageTitle').textContent = title;
    document.getElementById('messageText').textContent = message;

    // Remove old type classes and add new one
    modal.className = 'message-modal visible ' + type;
}

function closeMessageModal() {
    const modal = document.getElementById('messageModal');
    modal.classList.remove('visible');
}

// Alias functions for compatibility with different message types
function showError(title, message) {
    showMessage(title, message, 'error');
}

function showSuccess(title, message) {
    showMessage(title, message, 'success');
}

function showInfo(title, message) {
    showMessage(title, message, 'info');
}

function showWarning(title, message) {
    showMessage(title, message, 'warning');
}

function getTokenBadgeStyle(tokenCount) {
    const value = Number(tokenCount || 0);
    if (value >= 16000) {
        return 'background:#fdecea; color:#c0392b; border:1px solid #f5b7b1;';
    }
    if (value >= 4000) {
        return 'background:#fff4e5; color:#b9770e; border:1px solid #f8c471;';
    }
    return 'background:#eafaf1; color:#1e8449; border:1px solid #a9dfbf;';
}

function renderTokenBadge(tokenCount, codeMode) {
    const value = Number(tokenCount || 0);
    return `<span style="display:inline-block; margin-top:4px; padding:1px 6px; border-radius:999px; font-size:11px; ${getTokenBadgeStyle(value)}">AI Tahmini Girdi: ~${value} token${codeMode ? `, ${codeMode}` : ''}</span>`;
}

// ============================================
// SECTION: Utility Functions
// ============================================

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('visible'));
    document.getElementById(sectionId).classList.add('visible');
}

function goBack() {
    showSection('projectsSection');
    loadProjects();
}

function switchTab(tabName) {
    document.querySelectorAll('#projectDetailSection .tab-content').forEach(tab => tab.style.display = 'none');
    document.querySelectorAll('#projectDetailSection .tab-btn').forEach(btn => btn.classList.remove('active'));

    const tabEl = document.getElementById(tabName + 'Tab');
    if (tabEl) tabEl.style.display = 'block';

    // Mark the matching button active (works both on click and programmatic calls)
    const activeBtn = document.querySelector(`#projectDetailSection .tab-btn[onclick*="'${tabName}'"]`);
    if (activeBtn) activeBtn.classList.add('active');
    else if (typeof event !== 'undefined' && event && event.target) event.target.classList.add('active');
}

// ============================================
// SECTION: Projects Management
// ============================================

async function loadProjects() {
    showSection('projectsSection');

    try {
        const response = await fetch(`${API_URL}/projects`);
        const projects = await response.json();

        if (!response.ok) {
            if (response.status === 401) {
                localStorage.removeItem('currentUser');
                currentUser = null;
                const navbar = document.getElementById('navbar');
                const mainContent = document.getElementById('mainContent');
                const loginSection = document.getElementById('loginSection');
                if (navbar) navbar.style.display = 'none';
                if (mainContent) mainContent.style.display = 'none';
                if (loginSection) loginSection.style.display = 'block';
                return;
            }
            throw new Error(projects.error || `HTTP ${response.status}`);
        }

        if (!Array.isArray(projects)) {
            throw new Error(projects.error || 'Beklenmeyen proje listesi yanıtı');
        }

        const projectsList = document.getElementById('projectsList');
        projectsList.innerHTML = '';

        if (projects.length === 0) {
            projectsList.innerHTML = '<p>Henüz proje yok. Yeni bir proje yükleyin.</p>';
            return;
        }

        projects.forEach(project => {
            const card = document.createElement('div');
            card.className = 'project-card';
            card.onclick = () => viewProject(project.id);

            let actionButtons = `<button onclick="event.stopPropagation(); viewProject(${project.id})" class="btn btn-primary">Aç</button>`;

            // Restrict Delete & Reanalyze to admin and project owners
            const canManage = currentUser && (currentUser.role === 'admin' || project.admin_id === currentUser.id);

            if (canManage) {
                actionButtons += `
                    <button onclick="event.stopPropagation(); reanalyzeProject(${project.id})" class="btn btn-secondary">🔄 Tekrar Analiz Et</button>
                    <button onclick="event.stopPropagation(); deleteProject(${project.id})" class="btn btn-secondary">Sil</button>
                `;
            }

            const totalFuncs = project.total_functions || 0;
            const aiCount = project.ai_summary_count || 0;
            const embCount = project.rag_embedding_indexed || 0;
            const ftsCount = project.rag_fts_indexed || 0;
            const ragStatus = project.rag_status || '';

            card.innerHTML = `
                <h3>${project.name}</h3>
                <p>${project.description || 'Açıklama yok'}</p>
                <p style="font-size:12px; color:#4a4a4a; margin:6px 0 4px 0;">
                    <strong>RAG:</strong> FTS ${ftsCount}/${totalFuncs} | Emb ${embCount}/${totalFuncs} ${ragStatus ? `(${ragStatus})` : ''}<br>
                    <strong>AI:</strong> ${aiCount}/${totalFuncs} (${project.ai_summary_pct || 0}%)
                </p>
                <small>Yüklenme: ${new Date(project.upload_date).toLocaleDateString('tr-TR')}</small>
                <div class="project-card-actions">
                    ${actionButtons}
                </div>
            `;
            projectsList.appendChild(card);
        });
    } catch (error) {
        if (String(error).toLowerCase().includes('unauthorized')) {
            return;
        }
        showError('Projeler Yükleme Hatası', 'Projeler yüklenirken hata oluştu: ' + error);
    }
}

async function viewProject(projectId) {
    currentProjectId = projectId;
    console.log('viewProject called with projectId:', projectId);

    try {
        const response = await fetch(`${API_URL}/projects/${projectId}`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const project = await response.json();

        document.getElementById('projectTitle').textContent = project.name;
        document.getElementById('projectDescriptionInput').value = project.description || '';
        showSection('projectDetailSection');
        switchTab('overview');

        // Load diagram
        console.log('Loading diagram...');
        await loadDiagramData();
        console.log('Diagram loaded');

        // Load functions
        console.log('Loading functions...');
        await loadFunctions();
        console.log('Functions loaded');

        // Load marks
        console.log('Loading marks...');
        await loadMarks();
        console.log('Marks loaded');

        // Load files
        console.log('Loading files...');
        await loadFiles();
        console.log('Files loaded');
    } catch (error) {
        console.error('viewProject error:', error);
        showError('Proje Yükleme Hatası', 'Hata: ' + error.message);
    }
}

async function updateProjectDescription() {
    if (!currentProjectId) return;

    const newDescription = document.getElementById('projectDescriptionInput').value;
    const btn = document.querySelector('#overviewTab .btn-primary');
    const originalText = btn.innerHTML;

    try {
        btn.innerHTML = '⏳ Kaydediliyor...';
        btn.disabled = true;

        const response = await fetch(`${API_URL}/projects/${currentProjectId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ description: newDescription })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Kaydetme hatası');
        }

        showSuccess('Başarılı', 'Proje açıklaması güncellendi.');
        loadProjects(); // Ensure project list reflects the new description later
    } catch (error) {
        showError('Hata', error.message);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// ================================================================
// SECTION: RAG Index (GELIS4)
// ================================================================

async function loadRagStatus() {
    if (!currentProjectId) return;
    const box = document.getElementById('ragStatusBox');
    const txt = document.getElementById('ragStatusText');
    if (!box || !txt) return;
    box.style.display = 'block';
    txt.textContent = 'Durum kontrol ediliyor...';
    try {
        const res = await fetch(`${API_URL}/rag/project/${currentProjectId}/status`);
        if (!res.ok) { txt.textContent = 'Durum alınamadı.'; return; }
        const d = await res.json();
        const total = d.total_functions || 0;
        const emb = d.indexed || 0;
        const fts = d.fts_indexed || 0;
        const pct = total > 0 ? Math.round((emb / total) * 100) : 0;
        const statusLabel = d.status === 'running' ? ' 🔄 Oluşturuluyor...' : d.status === 'done' ? ' ✅ Tamamlandı' : '';
        txt.innerHTML = `
            <b>FTS5:</b> ${fts} / ${total} fonksiyon indekslendi &nbsp;|&nbsp;
            <b>Embedding:</b> ${emb} / ${total} (%${pct})${statusLabel}
            ${d.elapsed ? `<br><small>Son işlem: ${d.elapsed}s</small>` : ''}
        `;
        // Auto-refresh while running
        if (d.status === 'running') {
            setTimeout(loadRagStatus, 3000);
        }
    } catch (e) {
        txt.textContent = `Hata: ${e.message}`;
    }
}

async function buildRagIndex() {
    if (!currentProjectId) return;
    if (!confirm('FTS5 tam metin indeksi hemen, embedding indeksi arka planda oluşturulacak. Devam edilsin mi?')) return;
    const box = document.getElementById('ragStatusBox');
    const txt = document.getElementById('ragStatusText');
    box.style.display = 'block';
    txt.textContent = '⏳ İndeks oluşturma başlatılıyor...';
    try {
        const res = await fetch(`${API_URL}/rag/project/${currentProjectId}/build`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fts: true, embeddings: true })
        });
        const d = await res.json();
        txt.innerHTML = `✅ FTS5 indeks tamam (${d.fts_indexed || 0} fonksiyon). Embedding arka planda çalışıyor... <span id="ragPollNote">Otomatik güncelleniyor</span>`;
        // Start polling status
        setTimeout(loadRagStatus, 2000);
    } catch (e) {
        txt.textContent = `❌ Hata: ${e.message}`;
    }
}

async function addFileToProject() {
    if (!currentProjectId) return;
    const input = document.getElementById('addFileInput');
    const resultDiv = document.getElementById('addFileResult');
    const resultTxt = document.getElementById('addFileResultText');
    if (!input || !input.files || input.files.length === 0) return;

    resultDiv.style.display = 'block';
    resultTxt.textContent = `⏳ ${input.files.length} dosya yükleniyor...`;

    const formData = new FormData();
    for (const file of input.files) {
        formData.append('file', file);
    }

    try {
        const res = await fetch(`${API_URL}/projects/${currentProjectId}/add-file`, {
            method: 'POST',
            body: formData
        });
        const d = await res.json();

        if (!res.ok) {
            resultTxt.innerHTML = `❌ Hata: ${d.error || res.statusText}`;
            return;
        }

        const lines = [`✅ İşlem tamamlandı: <b>${d.code_files_added || 0}</b> kod dosyası eklendi, <b>${d.doc_chunks_added || 0}</b> doküman chunk'ı oluşturuldu.`];
        if (d.files && d.files.length > 0) {
            d.files.forEach(f => {
                const icon = f.status === 'ok' ? '📄' : f.status === 'skipped' ? '⏭️' : '⚠️';
                lines.push(`${icon} ${f.file} — ${f.type || f.status}${f.chunks ? ` (${f.chunks} chunk)` : ''}`);
            });
        }
        if ((d.code_files_added || 0) > 0) {
            lines.push('<small>🔄 Kod analizi arka planda çalışıyor, FTS5 indeksi güncelleniyor.</small>');
        }
        resultTxt.innerHTML = lines.join('<br>');
    } catch (e) {
        resultTxt.innerHTML = `❌ Bağlantı hatası: ${e.message}`;
    } finally {
        input.value = ''; // Reset file input for next use
    }
}

async function startBulkAiAnalysis() {
    if (!currentProjectId) return;

    if (!confirm('Tüm eksik AI analizleri için arka planda istek başlatılacaktır. Emin misiniz?')) {
        return;
    }

    const progressDiv = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('uploadProgressBar');
    const progressText = document.getElementById('uploadProgressText');
    const progressTitle = document.querySelector('#uploadProgress h3');

    if (progressTitle) progressTitle.textContent = 'Toplu AI Analizi Yapılıyor';
    progressDiv.style.display = 'block';

    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
    }
    if (progressText) {
        progressText.textContent = 'İşlem başlatılıyor...';
    }

    try {
        const taskId = 'bulk_ai_' + Date.now();
        const extraCriteria = (document.getElementById('bulkAiExtraCriteria')?.value || '').trim();
        const extraQuestion = (document.getElementById('bulkAiExtraQuestion')?.value || '').trim();
        const response = await startTrackedAnalysis(
            taskId,
            `Toplu AI Ozeti: Proje #${currentProjectId}`,
            () => fetch(`${API_URL}/analysis/project/${currentProjectId}/bulk-ai-summary?task_id=${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    extra_criteria: extraCriteria,
                    extra_question: extraQuestion
                })
            })
        );

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'İşlem başlatılamadı');
        }

        if (progressText) {
            progressText.textContent = 'AI toplu analiz işi global kuyruğa alındı.';
        }
        setTimeout(() => {
            progressDiv.style.display = 'none';
        }, 1200);
    } catch (error) {
        showError('Hata', error.message);
        progressDiv.style.display = 'none';
    }
}

// ============================================
// SECTION: AI Chat
// ============================================

let chatHistory = [];        // { role: 'user'|'assistant', content: string }
let chatStreaming = false;
let ragSearchResults = [];   // latest RAG search results
let ragSearchBestScore = 0;   // best score from last RAG search (0-1)
let ragSelectedFunctionIds = new Set();

function initChatTab() {
    // Scroll to bottom on tab switch
    const msgs = document.getElementById('chatMessages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function runRagSearch() {
    const input = document.getElementById('ragSearchInput');
    const query = input ? input.value.trim() : '';
    if (!query) return;

    const resultsContainer = document.getElementById('ragSearchResults');
    const resultsList = document.getElementById('ragSearchResultsList');
    resultsContainer.style.display = 'block';
    resultsList.innerHTML = '<div style="opacity:.7; font-size:13px;">Aranıyor...</div>';

    // Clear previous selection when a new search is run
    ragSelectedFunctionIds.clear();

    fetch(`${API_URL}/rag/project/${currentProjectId}/search?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
            if (!data.results) {
                resultsList.innerHTML = '<div style="color:#c0392b;">Arama sonucu alınamadı.</div>';
                return;
            }
            ragSearchResults = data.results;
            ragSearchBestScore = Number(data.best_score || 0);
            renderRagSearchResults();
        })
        .catch(err => {
            resultsList.innerHTML = `<div style="color:#c0392b;">Hata: ${err.message}</div>`;
        });
}

function clearRagSearchResults() {
    ragSearchResults = [];
    ragSearchBestScore = 0;
    ragSelectedFunctionIds.clear();
    const resultsContainer = document.getElementById('ragSearchResults');
    const resultsList = document.getElementById('ragSearchResultsList');
    if (resultsContainer) resultsContainer.style.display = 'none';
    if (resultsList) resultsList.innerHTML = '';
}

function clearRagSelection() {
    ragSelectedFunctionIds.clear();
    renderRagSearchResults();
}

function selectAllRagResults() {
    ragSearchResults.forEach(r => {
        if (r && r.id) {
            ragSelectedFunctionIds.add(r.id);
        }
    });
    renderRagSearchResults();
}

function toggleRagSelection(functionId) {
    if (ragSelectedFunctionIds.has(functionId)) {
        ragSelectedFunctionIds.delete(functionId);
    } else {
        ragSelectedFunctionIds.add(functionId);
    }
    renderRagSearchResults();
}

function renderRagSearchResults() {
    const resultsList = document.getElementById('ragSearchResultsList');
    if (!resultsList) return;

    if (!ragSearchResults || ragSearchResults.length === 0) {
        resultsList.innerHTML = '<div style="opacity:.7; font-size:13px;">Sonuç bulunamadı.</div>';
        return;
    }

    const bestScore = ragSearchBestScore || Math.max(...ragSearchResults.map(r => Number(r.score) || 0));
    const lowConfidence = bestScore < 0.25;

    resultsList.innerHTML = (lowConfidence ?
        '<div style="color:#c0392b; margin-bottom:8px; font-size:13px;">Bu arama için yeterli bağlam bulunamadı. Lütfen daha genel ya da farklı bir arama yapın.</div>' :
        '') +
        ragSearchResults.map(r => {
            const qualified = r.class_name ? `${r.class_name}.${r.function_name}` : r.function_name;
            const selected = ragSelectedFunctionIds.has(r.id);
            const score = r.score != null ? ` (score: ${Number(r.score).toFixed(3)})` : '';
            return `
                <div class="rag-result-item">
                    <div class="rag-result-meta">
                        <div><strong>${qualified}</strong>${score}</div>
                        <button class="btn btn-sm" onclick="toggleRagSelection(${r.id})">${selected ? '✓ Seçili' : 'Seç'}</button>
                    </div>
                    <p style="margin:4px 0 0 0;" title="${r.file_name || ''}">Dosya: ${r.file_name || 'bilinmiyor'}</p>
                    ${r.ai_summary ? `<p style="margin:4px 0 0 0; color:#555;">Özet: ${r.ai_summary}</p>` : ''}
                </div>
            `;
        }).join('');
}

function askAiWithRagSelection() {
    if (!ragSelectedFunctionIds.size) {
        showError('Seçim Yok', 'Önce bir veya daha fazla RAG sonucu seçin.');
        return;
    }

    // If there is text in the chat input, keep it; otherwise use a default prompt
    const input = document.getElementById('chatInput');

    const selectedNames = Array.from(ragSelectedFunctionIds).map(id => {
        const r = ragSearchResults.find(x => x.id === id);
        if (!r) return null;
        return r.class_name ? `${r.class_name}.${r.function_name}` : r.function_name;
    }).filter(Boolean);

    if (input && !input.value.trim()) {
        input.value = selectedNames.length > 0
            ? `Bu fonksiyonlar hakkında ne söyleyebilirsin? ${selectedNames.join(', ')}`
            : 'Bu seçilen fonksiyonlar hakkında ne söyleyebilirsin?';
    }

    // Send message with selection context
    sendChatMessage();
}

function handleChatKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}

function _appendChatBubble(role, text) {
    const msgs = document.getElementById('chatMessages');
    if (!msgs) return null;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble chat-bubble-${role}`;
    bubble.textContent = text;
    msgs.appendChild(bubble);
    msgs.scrollTop = msgs.scrollHeight;
    return bubble;
}

function clearChatHistory() {
    chatHistory = [];
    const msgs = document.getElementById('chatMessages');
    if (!msgs) return;
    msgs.innerHTML = `<div class="chat-bubble chat-bubble-assistant">Konuşma sıfırlandı. Yeni bir soru sorabilirsiniz.</div>`;
}

function viewFunctionFromChat(functionId) {
    // Switch to Functions tab
    switchTab('functions');

    // Give the tab + any lazy rendering time to complete
    const tryScroll = (attempts) => {
        const item = document.querySelector(`[data-func-id="${functionId}"]`);
        if (!item) {
            if (attempts > 0) setTimeout(() => tryScroll(attempts - 1), 150);
            return;
        }

        // Expand parent class-content and package-content (they start collapsed)
        let el = item.parentElement;
        while (el) {
            if (el.classList.contains('class-content')) {
                el.style.display = 'block';
                // Update the class header arrow indicator
                const hdr = el.previousElementSibling;
                if (hdr && hdr.classList.contains('class-header')) {
                    const arrow = hdr.querySelector('span');
                    if (arrow) arrow.textContent = '▼';
                }
            }
            if (el.classList.contains('package-content')) {
                el.style.display = 'block';
                // Update the package header arrow indicator
                const hdr = el.previousElementSibling;
                if (hdr && hdr.classList.contains('package-header')) {
                    hdr.innerHTML = hdr.innerHTML.replace('▶', '▼');
                }
            }
            el = el.parentElement;
        }

        // Scroll and highlight
        item.scrollIntoView({ behavior: 'smooth', block: 'center' });
        item.style.outline = '3px solid #3498db';
        item.style.borderRadius = '4px';
        item.style.transition = 'outline 0.5s';
        setTimeout(() => {
            item.style.outline = '';
        }, 2200);
    };

    setTimeout(() => tryScroll(10), 200);
}


async function sendChatMessage() {
    if (chatStreaming) return;
    if (!currentProjectId) return;

    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSendBtn');
    if (!input) return;

    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    chatStreaming = true;
    sendBtn.disabled = true;
    sendBtn.textContent = '⏳';

    // Show user bubble
    _appendChatBubble('user', text);

    // Show typing indicator
    const msgs = document.getElementById('chatMessages');
    const typingEl = document.createElement('div');
    typingEl.className = 'chat-bubble chat-bubble-assistant chat-typing';
    typingEl.innerHTML = '<span></span><span></span><span></span>';
    msgs.appendChild(typingEl);
    msgs.scrollTop = msgs.scrollHeight;

    // Build history for backend (last 8 messages = 4 turns)
    const historySlice = chatHistory.slice(-8);

    try {
        const payload = { message: text, history: historySlice };
        if (ragSelectedFunctionIds.size > 0) {
            payload.context_function_ids = Array.from(ragSelectedFunctionIds);
        }

        const response = await fetch(`${API_URL}/chat/project/${currentProjectId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ error: response.statusText }));
            typingEl.remove();
            _appendChatBubble('assistant', `⚠️ Hata: ${err.error || 'Sunucu hatası'}`);
            return;
        }

        // Remove typing indicator, create reply bubble
        typingEl.remove();
        const replyBubble = document.createElement('div');
        replyBubble.className = 'chat-bubble chat-bubble-assistant chat-cursor';
        replyBubble.textContent = '';
        msgs.appendChild(replyBubble);
        msgs.scrollTop = msgs.scrollHeight;

        // Read SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let replyText = '';
        let streamDone = false;
        let currentEvent = 'message';
        let refs = [];

        try {
            while (!streamDone) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop(); // Last partial line stays in buffer

                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        currentEvent = line.slice(6).trim();
                        continue;
                    }
                    if (!line.startsWith('data:')) continue;

                    // NO trim — preserve leading spaces (they are part of LLM word tokens)
                    const chunk = line.slice(5);

                    if (currentEvent === 'refs') {
                        try { refs = JSON.parse(chunk); } catch (e) { }
                        currentEvent = 'message';
                        continue;
                    }

                    if (chunk === '[DONE]') {
                        streamDone = true;
                        break;
                    }
                    // Unescape newlines (backend sends \n as literal \\n)
                    const token = chunk.replace(/\\n/g, '\n');
                    replyText += token;
                    replyBubble.textContent = replyText;
                    msgs.scrollTop = msgs.scrollHeight;
                }
            }
        } catch (streamErr) {
            if (!replyText) throw streamErr;
        } finally {
            replyBubble.classList.remove('chat-cursor');
            // Render Markdown after stream completes
            if (replyText) {
                try {
                    if (typeof marked !== 'undefined') {
                        replyBubble.innerHTML = marked.parse(replyText);
                    }
                } catch (mdErr) { /* keep textContent */ }
            }

            // Render reference function chips
            if (refs.length > 0) {
                const refsEl = document.createElement('div');
                refsEl.className = 'chat-refs';
                refsEl.innerHTML = '<span class="chat-refs-label">📎 Kaynaklar:</span> ' +
                    refs.map(r => {
                        const shortName = r.name.split('.').pop();
                        return `<span class="chat-ref-chip" onclick="viewFunctionFromChat(${r.id})" title="${r.name}\n${r.file}">${shortName}</span>`;
                    }).join('');
                msgs.appendChild(refsEl);
                msgs.scrollTop = msgs.scrollHeight;
            }
        }

        // Store in history
        chatHistory.push({ role: 'user', content: text });
        chatHistory.push({ role: 'assistant', content: replyText });

    } catch (err) {
        typingEl.remove();
        _appendChatBubble('assistant', `⚠️ Bağlantı hatası: ${err.message}`);
    } finally {
        chatStreaming = false;
        sendBtn.disabled = false;
        sendBtn.textContent = '➤ Gönder';
        input.focus();
    }
}

async function deleteProject(projectId) {
    if (!confirm('Bu projeyi silmek istediğinizden emin misiniz?')) return;

    try {
        const response = await fetch(`${API_URL}/projects/${projectId}`, { method: 'DELETE' });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Silme işlemi başarısız');
        }

        showSuccess('Başarılı', 'Proje silindi');
        loadProjects(); // Refresh project list
    } catch (error) {
        showError('Silme Hatası', 'Proje silinirken hata oluştu: ' + error.message);
    }
}

function showUpload() {
    showSection('uploadSection');
    switchUploadMode('zip');  // Default to ZIP upload
}

function switchUploadMode(mode) {
    const zipForm = document.getElementById('uploadForm');
    const gitForm = document.getElementById('gitImportForm');
    const zipTab = document.getElementById('zipUploadTab');
    const gitTab = document.getElementById('gitImportTab');

    if (mode === 'zip') {
        zipForm.style.display = 'block';
        gitForm.style.display = 'none';
        zipTab.style.background = '#3498db';
        zipTab.style.color = 'white';
        gitTab.style.background = '';
        gitTab.style.color = '';
    } else {
        zipForm.style.display = 'none';
        gitForm.style.display = 'block';
        zipTab.style.background = '';
        zipTab.style.color = '';
        gitTab.style.background = '#3498db';
        gitTab.style.color = 'white';
    }
}

function showSettings() {
    showSection('settingsSection');
    loadSettings();
}

function showReport() {
    showSection('reportSection');
    loadReport();
}

function showAiJobs() {
    showSection('aiJobsSection');
    if (typeof renderAnalysisMonitor === 'function') {
        renderAnalysisMonitor();
    }
}

// ============================================
// SECTION: Upload & Analysis
// ============================================

let uploadPolling = null;
let analysisPolling = null;
let reanalysisPolling = null;
let aiPolling = null;

async function pollUploadProgress(taskId, projectId) {
    const progressBar = document.getElementById('uploadProgressBar');
    const progressText = document.getElementById('uploadProgressText');
    const progressDetails = document.getElementById('uploadProgressDetails');

    const poll = async () => {
        try {
            const response = await fetch(`${API_URL}/projects/progress/${taskId}`);

            if (!response.ok) {
                clearInterval(uploadPolling);
                return;
            }

            const progress = await response.json();

            // Update progress bar
            if (progressBar) {
                progressBar.style.width = `${progress.progress}%`;
                progressBar.textContent = `${progress.progress}%`;
            }

            // Update status text
            if (progressText) {
                progressText.textContent = progress.current_step || 'İşleniyor...';
            }

            // Update details list
            if (progressDetails && progress.details && progress.details.length > 0) {
                const lastDetails = progress.details.slice(-5); // Show last 5 details
                progressDetails.innerHTML = lastDetails.map(detail =>
                    `<div class="progress-detail">• ${detail.message}</div>`
                ).join('');
                // Auto-scroll to bottom
                progressDetails.scrollTop = progressDetails.scrollHeight;
            }

            // Check if completed
            if (progress.status === 'completed') {
                clearInterval(uploadPolling);

                // Start analysis with its own progress task
                progressText.textContent = 'Kod analizi başlatılıyor...';
                startAnalysisWithProgress(projectId);
            } else if (progress.status === 'failed') {
                clearInterval(uploadPolling);
                showError('Yükleme Başarısız', progress.current_step || 'Bilinmeyen hata');
                document.getElementById('uploadProgress').style.display = 'none';
            }
        } catch (error) {
            console.error('Progress polling error:', error);
        }
    };

    // Poll every 1500ms to reduce backend load
    uploadPolling = setInterval(poll, 1500);
    poll(); // Initial call
}

// Reanalyze an existing project
async function reanalyzeProject(projectId) {
    const confirmed = confirm('Projeyi tekrar analiz etmek istiyor musunuz? Mevcut bağımlılık bilgileri yenilenecektir.');
    if (!confirmed) return;

    // Show progress UI
    document.getElementById('uploadProgress').style.display = 'block';
    const progressBar = document.getElementById('uploadProgressBar');
    const progressText = document.getElementById('uploadProgressText');
    const progressDetails = document.getElementById('uploadProgressDetails');
    const progressTitle = document.querySelector('#uploadProgress h3');

    if (progressTitle) {
        progressTitle.textContent = 'Tekrar Analiz İlerlemesi';
    }

    const analysisTaskId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : `reanalysis-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
    }
    if (progressText) {
        progressText.textContent = 'Tekrar analiz başlatılıyor...';
    }
    if (progressDetails) {
        progressDetails.innerHTML = '<div class="progress-detail">• Analiz görevi oluşturuluyor...</div>';
    }

    const poll = async () => {
        try {
            const response = await fetch(`${API_URL}/projects/progress/${analysisTaskId}`);
            if (!response.ok) return;

            const progress = await response.json();

            if (progressBar) {
                progressBar.style.width = `${progress.progress}%`;
                progressBar.textContent = `${progress.progress}%`;
            }

            if (progressText) {
                progressText.textContent = progress.current_step || 'Analiz sürüyor...';
            }

            if (progressDetails && progress.details && progress.details.length > 0) {
                const lastDetails = progress.details.slice(-8);
                progressDetails.innerHTML = lastDetails.map(detail =>
                    `<div class="progress-detail">• ${detail.message}</div>`
                ).join('');
                progressDetails.scrollTop = progressDetails.scrollHeight;
            }

            if (progress.status === 'completed') {
                clearInterval(reanalysisPolling);
            }

            if (progress.status === 'failed') {
                clearInterval(reanalysisPolling);
            }
        } catch (error) {
            console.error('Reanalysis progress polling error:', error);
        }
    };

    reanalysisPolling = setInterval(poll, 1500);
    poll();

    try {
        const analysisResponse = await fetch(
            `${API_URL}/analysis/project/${projectId}?task_id=${encodeURIComponent(analysisTaskId)}`,
            { method: 'POST' }
        );
        const analysisResult = await analysisResponse.json();

        clearInterval(reanalysisPolling);

        if (!analysisResponse.ok) {
            throw new Error(analysisResult.error || 'Bilinmeyen analiz hatası');
        }

        showSuccess(
            'Tekrar Analiz Tamamlandı',
            `✓ Proje başarıyla tekrar analiz edildi!\n` +
            `${analysisResult.functions_found} fonksiyon bulundu.\n` +
            `Bağımlılıklar yenilendi.`
        );

        document.getElementById('uploadProgress').style.display = 'none';

        // Reload current project if it's being viewed
        if (currentProjectId === projectId) {
            viewProject(projectId);
        }
    } catch (analysisError) {
        clearInterval(reanalysisPolling);
        showError('Tekrar Analiz Hatası', 'Analiz sırasında hata: ' + analysisError.message);
        document.getElementById('uploadProgress').style.display = 'none';
    }
}

async function startAnalysisWithProgress(projectId) {
    const progressBar = document.getElementById('uploadProgressBar');
    const progressText = document.getElementById('uploadProgressText');
    const progressDetails = document.getElementById('uploadProgressDetails');
    const progressTitle = document.querySelector('#uploadProgress h3');

    if (progressTitle) {
        progressTitle.textContent = 'Analiz İlerlemesi';
    }

    const analysisTaskId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : `analysis-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
    }
    if (progressText) {
        progressText.textContent = 'Analiz görevi oluşturuluyor...';
    }
    if (progressDetails) {
        progressDetails.innerHTML = '<div class="progress-detail">• Analiz başlatılıyor...</div>';
    }

    const poll = async () => {
        try {
            const response = await fetch(`${API_URL}/projects/progress/${analysisTaskId}`);
            if (!response.ok) return;

            const progress = await response.json();

            if (progressBar) {
                progressBar.style.width = `${progress.progress}%`;
                progressBar.textContent = `${progress.progress}%`;
            }

            if (progressText) {
                progressText.textContent = progress.current_step || 'Analiz sürüyor...';
            }

            if (progressDetails && progress.details && progress.details.length > 0) {
                const lastDetails = progress.details.slice(-8);
                progressDetails.innerHTML = lastDetails.map(detail =>
                    `<div class="progress-detail">• ${detail.message}</div>`
                ).join('');
                progressDetails.scrollTop = progressDetails.scrollHeight;
            }

            if (progress.status === 'completed') {
                clearInterval(analysisPolling);
            }

            if (progress.status === 'failed') {
                clearInterval(analysisPolling);
            }
        } catch (error) {
            console.error('Analysis progress polling error:', error);
        }
    };

    analysisPolling = setInterval(poll, 1500);
    poll();

    try {
        const analysisResponse = await fetch(
            `${API_URL}/analysis/project/${projectId}?task_id=${encodeURIComponent(analysisTaskId)}`,
            { method: 'POST' }
        );
        const analysisResult = await analysisResponse.json();

        clearInterval(analysisPolling);

        if (!analysisResponse.ok) {
            throw new Error(analysisResult.error || 'Bilinmeyen analiz hatası');
        }

        showSuccess(
            'İşlem Tamamlandı',
            `✓ Proje yüklendi ve analiz edildi!\n` +
            `${analysisResult.functions_found} fonksiyon bulundu.\n` +
            `Atlanan (desteklenmeyen): ${analysisResult.files_skipped_unsupported || 0}`
        );

        document.getElementById('uploadForm').reset();
        document.getElementById('uploadProgress').style.display = 'none';
        loadProjects();
    } catch (analysisError) {
        clearInterval(analysisPolling);
        showError('Analiz Hatası', 'Analiz sırasında hata: ' + analysisError.message);
        document.getElementById('uploadProgress').style.display = 'none';
    }
}

document.getElementById('uploadForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const name = document.getElementById('projectName').value;
    const desc = document.getElementById('projectDesc').value;
    const file = document.getElementById('projectFile').files[0];

    if (!file) {
        showError('Dosya Seçilmedi', 'Lütfen bir dosya seçin');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    formData.append('description', desc);

    try {
        // Show progress UI
        const progressSection = document.getElementById('uploadProgress');
        progressSection.style.display = 'block';

        const progressBar = document.getElementById('uploadProgressBar');
        const progressText = document.getElementById('uploadProgressText');
        const progressDetails = document.getElementById('uploadProgressDetails');
        const progressTitle = document.querySelector('#uploadProgress h3');
        if (progressTitle) progressTitle.textContent = 'Yükleme İlerlemesi';

        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
        }
        if (progressText) progressText.textContent = 'Yükleme başlatılıyor...';
        if (progressDetails) progressDetails.innerHTML = '';

        // Start upload
        const response = await fetch(`${API_URL}/projects/upload`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok && result.task_id) {
            // Start polling for progress
            pollUploadProgress(result.task_id, result.project_id);
        } else {
            showError('Yükleme Hatası', 'Hata: ' + (result.error || 'Bilinmeyen hata'));
            progressSection.style.display = 'none';
        }
    } catch (error) {
        showError('Yükleme Hatası', 'Yükleme hatası oluştu: ' + error);
        document.getElementById('uploadProgress').style.display = 'none';
    }
});

// Git Repository Import Handler
document.getElementById('gitImportForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const repoUrl = document.getElementById('gitRepoUrl').value.trim();
    const branch = document.getElementById('gitBranch').value.trim() || 'main';
    const projectName = document.getElementById('gitProjectName').value.trim();
    const projectDesc = document.getElementById('gitProjectDesc').value.trim();

    if (!repoUrl || !projectName) {
        showError('Gerekli Alan Eksik', 'Git URL ve Proje Adı gereklidir');
        return;
    }

    try {
        // Show progress UI
        const progressSection = document.getElementById('uploadProgress');
        progressSection.style.display = 'block';

        const progressBar = document.getElementById('uploadProgressBar');
        const progressText = document.getElementById('uploadProgressText');
        const progressDetails = document.getElementById('uploadProgressDetails');
        const progressTitle = document.querySelector('#uploadProgress h3');
        if (progressTitle) progressTitle.textContent = 'Git Clone ve Analiz İlerlemesi';

        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
        }
        if (progressText) progressText.textContent = 'Repository klonlanıyor...';
        if (progressDetails) progressDetails.innerHTML = '';

        // Start Git import
        const response = await fetch(`${API_URL}/projects/import-git`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: repoUrl,
                branch: branch,
                name: projectName,
                description: projectDesc
            })
        });

        const result = await response.json();

        if (response.ok && result.task_id) {
            // Start polling for progress
            pollUploadProgress(result.task_id, result.project_id);
        } else {
            showError('Git Import Hatası', 'Hata: ' + (result.error || 'Bilinmeyen hata'));
            progressSection.style.display = 'none';
        }
    } catch (error) {
        showError('Git Import Hatası', 'Hata oluştu: ' + error.message);
        document.getElementById('uploadProgress').style.display = 'none';
    }
});

// ============================================
// SECTION: Diagram
// ============================================

async function loadDiagramData() {
    try {
        const container = document.getElementById('diagramContainer');
        if (!container || !currentProjectId) return;

        // Check if Cytoscape is loaded
        if (typeof cytoscape === 'undefined') {
            console.error('Cytoscape library not loaded. Waiting...');
            // Wait for Cytoscape to load
            await new Promise(resolve => {
                const checkInterval = setInterval(() => {
                    if (typeof cytoscape !== 'undefined') {
                        clearInterval(checkInterval);
                        resolve();
                    }
                }, 100);
                setTimeout(() => clearInterval(checkInterval), 5000); // 5 second timeout
            });
        }

        const response = await fetch(`${API_URL}/diagram/project/${currentProjectId}/`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        const validNodeIds = new Set(data.nodes.map(node => node.id.toString()));

        cy = cytoscape({
            container: container,
            elements: [
                ...data.nodes.map(node => ({
                    data: {
                        id: node.id.toString(),
                        label: node.label,
                        type: node.type,
                        summary: node.summary
                    },
                    classes: (node.is_entry_point ? 'entry ' : '') + (node.type || '')
                })),
                ...data.edges
                    // Filter out edges with nonexistent nodes (defensive check)
                    .filter(edge => validNodeIds.has(edge.from.toString()) && validNodeIds.has(edge.to.toString()))
                    .map(edge => ({
                        data: {
                            source: edge.from.toString(),
                            target: edge.to.toString()
                        }
                    }))
            ],
            style: [
                {
                    selector: 'node',
                    style: {
                        'content': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'background-color': '#3498db',
                        'color': '#fff',
                        'padding': '10px',
                        'border-width': '2px',
                        'border-color': '#2c3e50',
                        'font-size': '12px',
                        'width': '150px',
                        'height': '100px'
                    }
                },
                {
                    selector: 'node.entry',
                    style: {
                        'background-color': '#27ae60'
                    }
                },
                {
                    selector: 'node.class',
                    style: {
                        'background-color': '#e74c3c'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'line-color': '#95a5a6',
                        'target-arrow-color': '#95a5a6',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'width': 2
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'background-color': '#f39c12',
                        'border-width': '3px'
                    }
                }
            ],
            layout: {
                name: 'cose',
                directed: true,
                animate: true,
                animationDuration: 500
            }
        });

        // Click handler
        cy.on('tap', 'node', function (evt) {
            const node = evt.target;
            showFunctionDetails(node.data('id'));

            // Display entry points legend
            if (data.entry_points && data.entry_points.length > 0) {
                const legendDiv = document.getElementById('diagramLegend');
                const entryPointsList = document.getElementById('entryPointsList');

                // Get entry point names from nodes
                const entryPointNames = data.nodes
                    .filter(node => data.entry_points.includes(node.id))
                    .map(node => node.label);

                if (entryPointNames.length > 0) {
                    entryPointsList.innerHTML = entryPointNames
                        .map(name => `<div style="padding: 4px 8px; background: white; margin: 2px 0; border-left: 3px solid #27ae60; border-radius: 2px;">🟢 ${name}</div>`)
                        .join('');
                    legendDiv.style.display = 'block';
                }
            } else {
                document.getElementById('diagramLegend').style.display = 'none';
            }
        });

    } catch (error) {
        console.error('Diagram yükleme hatası:', error);
    }
}

function zoomIn() {
    if (cy) cy.zoom(cy.zoom() * 1.2);
}

function zoomOut() {
    if (cy) cy.zoom(cy.zoom() / 1.2);
}

function fitDiagram() {
    if (cy) cy.fit();
}

async function exportDiagram() {
    try {
        const png = cy.png();
        const a = document.createElement('a');
        a.href = png;
        a.download = `diagram_${currentProjectId}.png`;
        a.click();
    } catch (error) {
        showError('Dışa Aktarma Hatası', 'PNG dışa aktarımı hatayla sonuçlandı');
    }
}

// ============================================
// SECTION: Functions
// ============================================

async function loadFunctions() {
    try {
        console.log('loadFunctions started. currentProjectId:', currentProjectId, 'API_URL:', API_URL);

        if (!currentProjectId) {
            console.error('loadFunctions: currentProjectId is null!');
            showError('Hata', 'Proje seçilmedi. Lütfen bir proje açınız.');
            return;
        }

        const url = `${API_URL}/analysis/project/${currentProjectId}/functions`;
        console.log('Fetching from URL:', url);

        const response = await fetch(url);
        console.log('Response status:', response.status, 'ok:', response.ok);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const functions = await response.json();
        console.log('Functions loaded, count:', functions.length);

        const list = document.getElementById('functionsList');
        list.innerHTML = '';

        // Group functions by package and class
        const groups = {};
        functions.forEach(func => {
            const pkg = func.package_name || 'Bilinmeyen Paket';
            const cls = func.class_name || 'Global Fonksiyonlar';

            if (!groups[pkg]) groups[pkg] = {};
            if (!groups[pkg][cls]) groups[pkg][cls] = [];
            groups[pkg][cls].push(func);
        });

        // Render groups
        for (const [pkgName, classes] of Object.entries(groups)) {
            const pkgDiv = document.createElement('div');
            pkgDiv.className = 'package-group';

            // Allow package collapsing
            const pkgHeader = document.createElement('h3');
            pkgHeader.className = 'package-header';
            pkgHeader.style.cssText = 'background: #2c3e50; color: white; padding: 8px 12px; margin-bottom: 5px; border-radius: 4px; cursor: pointer; user-select: none; display: flex; justify-content: space-between;';
            pkgHeader.innerHTML = `<span>📦 ${pkgName}</span> <span>▶</span>`;

            const pkgContent = document.createElement('div');
            pkgContent.className = 'package-content';
            pkgContent.style.display = 'none'; // Default: collapsed

            pkgHeader.onclick = () => {
                const isHidden = pkgContent.style.display === 'none';
                pkgContent.style.display = isHidden ? 'block' : 'none';
                pkgHeader.innerHTML = `<span>📦 ${pkgName}</span> <span>${isHidden ? '▼' : '▶'}</span>`;
            };

            pkgDiv.appendChild(pkgHeader);
            pkgDiv.appendChild(pkgContent);

            for (const [clsName, funcs] of Object.entries(classes)) {
                const clsDiv = document.createElement('div');
                clsDiv.className = 'class-group';
                clsDiv.style.marginLeft = '15px';
                clsDiv.style.borderLeft = '2px solid #3498db';
                clsDiv.style.paddingLeft = '10px';

                // Allow class collapsing
                const clsHeader = document.createElement('h4');
                clsHeader.className = 'class-header';
                clsHeader.style.cssText = 'color: #2980b9; margin: 10px 0 5px 0; cursor: pointer; user-select: none; display: flex; align-items: center;';
                clsHeader.innerHTML = `<span style="margin-right: 5px;">▶</span> 🏷️ ${clsName}`;

                const clsContent = document.createElement('div');
                clsContent.className = 'class-content';
                clsContent.style.display = 'none'; // Default: collapsed

                clsHeader.onclick = () => {
                    const isHidden = clsContent.style.display === 'none';
                    clsContent.style.display = isHidden ? 'block' : 'none';
                    clsHeader.innerHTML = `<span style="margin-right: 5px;">${isHidden ? '▼' : '▶'}</span> 🏷️ ${clsName}`;

                    // Lazy-load dependencies when class opens
                    if (isHidden) {
                        setTimeout(() => populateDependencies(clsContent), 0);
                    }
                };

                clsDiv.appendChild(clsHeader);
                clsDiv.appendChild(clsContent);

                funcs.forEach(func => {
                    const called = Array.isArray(func.called_functions) ? func.called_functions : [];
                    const calledBy = Array.isArray(func.called_by_functions) ? func.called_by_functions : [];
                    const estimatedTokens = Number(func.ai_estimated_input_tokens || 0);
                    const codeMode = func.ai_code_mode || 'full';

                    const item = document.createElement('div');
                    item.className = 'function-item searchable-item';
                    item.dataset.search = `${func.function_name} ${func.ai_summary || ''}`.toLowerCase();

                    // Store dependencies as data attributes (lazy-load on accordion open)
                    item.dataset.funcId = func.id;
                    item.dataset.called = JSON.stringify(called);
                    item.dataset.calledBy = JSON.stringify(calledBy);

                    // Minimal HTML - dependencies lazy-loaded when class opens
                    item.innerHTML = `
                        <h5>${func.function_name} <small>(${func.function_type})</small></h5>
                        <p>${func.ai_summary || 'Özet henüz oluşturulmadı'}</p>
                        <div class="function-meta">
                            Satırlar: ${func.start_line}-${func.end_line}
                            <br/><small>Dosya: ${func.file_path || 'Bilinmiyor'}</small>
                            <br/>${renderTokenBadge(estimatedTokens, codeMode)}
                            <div class="function-deps" data-deps-loaded="false">
                                <div><strong>Çağırdığı Fonksiyonlar:</strong> <span class="deps-placeholder">Yükleniyor...</span></div>
                                <div><strong>Bunu Çağıran Fonksiyonlar:</strong> <span class="deps-placeholder">Yükleniyor...</span></div>
                            </div>
                        </div>
                    `;
                    item.onclick = () => showFunctionDetails(func.id);
                    clsContent.appendChild(item);
                });
                pkgContent.appendChild(clsDiv);
            }
            list.appendChild(pkgDiv);
        }

        // Attach search listener once after load
        setupSearchListener();
    } catch (error) {
        console.error('Fonksiyonlar yükleme hatası:', error);
    }
}

// Global var for current function ID in modal
let currentModalFunctionId = null;

async function showFunctionDetails(functionId) {
    // Hide error state when loading new function
    document.getElementById('funcModalError').style.display = 'none';

    try {
        currentModalFunctionId = functionId;
        const response = await fetch(`${API_URL}/analysis/function/${functionId}`, {
            signal: AbortSignal.timeout(15000) // 15 second timeout
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        let func = await response.json();

        // Validate response data
        if (!func || typeof func !== 'object') {
            throw new Error('Geçersiz sunucu yanıtı (invalid JSON)');
        }

        const modal = document.getElementById('functionModal');
        // Use qualified name (ClassName.functionName) if available, else just function name
        const displayName = func.qualified_name || func.function_name;
        document.getElementById('funcModalTitle').textContent = displayName;

        // Build dependency chips HTML with qualified names
        const called = Array.isArray(func.called_functions) ? func.called_functions : [];
        const calledBy = Array.isArray(func.called_by_functions) ? func.called_by_functions : [];

        const calledHtml = called.length > 0
            ? called.map(c => {
                const label = c.qualified_name || c.function_name;
                return `<span class="dep-chip" data-func-id="${c.id}" style="cursor: pointer; margin: 2px 4px 2px 0;" title="${label}">${label}</span>`;
            }).join('')
            : '<span class="dep-empty">Yok</span>';

        const calledByHtml = calledBy.length > 0
            ? calledBy.map(c => {
                const label = c.qualified_name || c.function_name;
                return `<span class="dep-chip dep-chip-caller" data-func-id="${c.id}" style="cursor: pointer; margin: 2px 4px 2px 0;" title="${label}">${label}</span>`;
            }).join('')
            : '<span class="dep-empty">Yok</span>';

        // Build DB mapping section placeholders (will be filled async)
        const dbTablesPlaceholderId = 'funcModalDbTables';
        const dbProcsPlaceholderId = 'funcModalDbProcs';

        // Meta info display with dependencies
        document.getElementById('funcModalContent').innerHTML = `
            <p><strong>Tür:</strong> ${func.function_type}</p>
            <p><strong>Parametreler:</strong> ${Array.isArray(func.parameters) ? func.parameters.join(', ') : (func.parameters || 'Yok')}</p>
            <p><strong>Dönüş Tipi:</strong> ${func.return_type || 'Yok'}</p>
            <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
            <div style="margin-top: 15px;">
                <p><strong>Çağırdığı Fonksiyonlar:</strong></p>
                <div style="padding: 8px 0;">${calledHtml}</div>
            </div>
            <div style="margin-top: 15px;">
                <p><strong>Bunu Çağıran Fonksiyonlar:</strong></p>
                <div style="padding: 8px 0;">${calledByHtml}</div>
            </div>
            <div style="margin-top: 15px;">
                <p><strong>Kullanılan Veri Tabanı Tabloları:</strong></p>
                <div id="${dbTablesPlaceholderId}" style="padding: 8px 0; color: #555;">Yükleniyor...</div>
            </div>
            <div style="margin-top: 15px;">
                <p><strong>Kullanılan SP/Fonksiyonlar:</strong></p>
                <div id="${dbProcsPlaceholderId}" style="padding: 8px 0; color: #555;">Yükleniyor...</div>
            </div>
        `;

        // Start async load of DB mapping info
        (async () => {
            try {
                const resp = await fetch(`${API_URL}/projects/${currentProjectId}/dalmaps`);
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

                const data = await resp.json();
                const dalmaps = Array.isArray(data.dalmaps) ? data.dalmaps : [];
                const sqlTables = (data.sql_tables && typeof data.sql_tables === 'object') ? data.sql_tables : {};
                const sqlProcs = (data.sql_procedures && typeof data.sql_procedures === 'object') ? data.sql_procedures : {};

                const className = func.class_name || '';
                const usedTablesFromCode = Array.isArray(func.used_db_tables) ? func.used_db_tables : [];
                const usedProcsFromCode = Array.isArray(func.used_stored_procedures) ? func.used_stored_procedures : [];
                const usedDalmapClasses = Array.isArray(func.used_dalmap_classes) ? func.used_dalmap_classes : [];

                // Collect table candidates (from code usage + DALMap class mapping)
                const tableEntries = [];

                // From code usage (.from("table"))
                usedTablesFromCode.forEach(t => {
                    const normalized = (t || '').toLowerCase().split('.').pop();
                    const createStmt = sqlTables[normalized];
                    tableEntries.push({label: t, sql: createStmt, source: 'code'});
                });

                // From DALMap class -> table mapping
                if (className) {
                    const match = dalmaps
                        .flatMap(d => (d.sections && Array.isArray(d.sections.classes) ? d.sections.classes : []))
                        .find(c => (c.name || c.class || '').toLowerCase() === className.toLowerCase());
                    if (match && match.table) {
                        const tableName = match.table;
                        const normalized = tableName.toLowerCase().split('.').pop();
                        const createStmt = sqlTables[normalized];
                        tableEntries.push({label: tableName, sql: createStmt, source: 'dalmap'});
                    }
                }

                // From DALMap insert class usage (DALDB.persistenceBroker().insert(..., ClassInstance))
                usedDalmapClasses.forEach(cls => {
                    const match = dalmaps
                        .flatMap(d => (d.sections && Array.isArray(d.sections.classes) ? d.sections.classes : []))
                        .find(c => (c.name || c.class || '').toLowerCase().endsWith(cls.toLowerCase()));
                    if (match && match.table) {
                        const tableName = match.table;
                        const normalized = tableName.toLowerCase().split('.').pop();
                        const createStmt = sqlTables[normalized];
                        tableEntries.push({label: tableName, sql: createStmt, source: 'dalmap'});
                    }
                });

                const tableContainer = document.getElementById(dbTablesPlaceholderId);
                if (!tableContainer) return;

                if (tableEntries.length === 0) {
                    tableContainer.textContent = 'Tablo ilişkisi bulunamadı.';
                } else {
                    tableContainer.innerHTML = tableEntries.map((t, idx) => {
                        if (t.sql) {
                            return `<div style="margin-bottom:6px;"><a href="#" data-sql-index="${idx}" class="db-table-link">${t.label}</a></div>`;
                        } else {
                            return `<div style="margin-bottom:6px;">${t.label}</div>`;
                        }
                    }).join('');

                    // Attach click handlers to show SQL DDL
                    tableContainer.querySelectorAll('.db-table-link').forEach(link => {
                        link.onclick = (e) => {
                            e.preventDefault();
                            const idx = parseInt(link.dataset.sqlIndex);
                            if (!Number.isNaN(idx) && tableEntries[idx] && tableEntries[idx].sql) {
                                openFileViewerModal(`Tablo DDL: ${tableEntries[idx].label}`, tableEntries[idx].sql);
                            }
                        };
                    });
                }

                // Build SP list HTML (from code usage + SQL procedure definitions)
                const procContainer = document.getElementById(dbProcsPlaceholderId);
                if (!procContainer) return;

                const procFromCode = usedProcsFromCode || [];
                const procFromSql = Object.keys(sqlProcs || {});

                const procCandidates = Array.from(new Set([...(procFromCode || []), ...procFromSql]));

                if (procCandidates.length === 0) {
                    procContainer.textContent = 'İlişkili SP/fonksiyon bulunamadı.';
                } else {
                    procContainer.innerHTML = procCandidates.map((pn, idx) => {
                        const hasSql = Boolean(sqlProcs && sqlProcs[pn]);
                        return `<div style="margin-bottom:6px;"><a href="#" data-proc-name="${pn}" class="db-proc-link">${pn}</a>${hasSql ? ' <small style="color:#666;">(tanım bulundu)</small>' : ''}</div>`;
                    }).join('');

                    procContainer.querySelectorAll('.db-proc-link').forEach(link => {
                        link.onclick = (e) => {
                            e.preventDefault();
                            const procName = link.dataset.procName;
                            const sql = sqlProcs[procName];
                            openFileViewerModal(`SP: ${procName}`, sql || '<i>Tanım bulunamadı</i>');
                        };
                    });
                }
            } catch (innerErr) {
                const tableContainer = document.getElementById(dbTablesPlaceholderId);
                const procContainer = document.getElementById(dbProcsPlaceholderId);
                if (tableContainer) tableContainer.textContent = 'DB haritalama yüklenirken hata oluştu.';
                if (procContainer) procContainer.textContent = 'DB haritalama yüklenirken hata oluştu.';
                console.warn('DALMap/SQL mapping load error', innerErr);
            }
        })();

        // Update Text Areas
        const summaryTextarea = document.getElementById('funcModalSummary');
        summaryTextarea.value = func.ai_summary || '';
        document.getElementById('funcModalSource').textContent = func.source_code || 'Kaynak kod yok.';

        // Apply role constraints: analyzer cannot edit, others can.
        // If currentUser is temporarily null (e.g. transient session/UI state), keep editor writable.
        const canEdit = !currentUser || currentUser.role !== 'analyzer';
        summaryTextarea.readOnly = !canEdit;
        const saveBtn = document.getElementById('btnSaveSummary');
        const aiBtn = document.getElementById('btnGenerateAI');
        const addMarkBtn = document.getElementById('btnAddMark');

        if (saveBtn) saveBtn.style.display = canEdit ? 'inline-block' : 'none';
        if (aiBtn) aiBtn.style.display = canEdit ? 'inline-block' : 'none';
        if (addMarkBtn) addMarkBtn.style.display = canEdit ? 'inline-block' : 'none';

        modal.classList.add('visible');

        // Show copy button if there's source code
        const copyBtn = document.getElementById('copyCodeBtn');
        if (copyBtn && func.source_code && func.source_code.trim() !== 'Kaynak kod yok.') {
            copyBtn.style.display = 'inline-block';
            copyBtn.textContent = '📋 Kopyala';
        } else if (copyBtn) {
            copyBtn.style.display = 'none';
        }

        // Attach click handlers to dependency chips in modal
        setTimeout(() => {
            modal.querySelectorAll('.dep-chip[data-func-id]').forEach(chip => {
                chip.onclick = (e) => {
                    e.stopPropagation();
                    const funcId = chip.dataset.funcId;
                    if (funcId) {
                        showFunctionDetails(parseInt(funcId));
                    }
                };
                chip.style.transition = 'all 0.2s';
                chip.onmouseover = () => chip.style.opacity = '0.7';
                chip.onmouseout = () => chip.style.opacity = '1';
            });
        }, 0);
    } catch (error) {
        // User-friendly error handling
        const errorDiv = document.getElementById('funcModalError');
        const errorMsg = document.getElementById('funcModalErrorMessage');

        let userMessage = 'Bilinmeyen bir hata oluştu.';

        // Detect error type
        if (error.name === 'AbortError') {
            userMessage = 'İstek zaman aşımına uğradı. Fonksiyon çok uzun yanıt vermiş olabilir.';
        } else if (error instanceof TypeError) {
            if (error.message.includes('fetch')) {
                userMessage = 'Sunucuya bağlanılamadı. Lütfen ağ bağlantınızı kontrol edin.';
            } else {
                userMessage = 'Sunucu yanıtı işlenemedi: ' + error.message;
            }
        } else if (error.message.includes('HTTP')) {
            userMessage = 'Sunucu hatası: ' + error.message + '. Lütfen yeniden deneyin.';
        } else {
            userMessage = 'Hata: ' + error.message;
        }

        errorMsg.textContent = userMessage;
        errorDiv.style.display = 'block';

        // Show modal with error state
        const modal = document.getElementById('functionModal');
        modal.classList.add('visible');

        // Hide copy button on error
        const copyBtn = document.getElementById('copyCodeBtn');
        if (copyBtn) copyBtn.style.display = 'none';

        console.error('Fonksiyon detayları yükleme hatası:', error);
    }
}

// Retry loading function
function retryFunctionLoad() {
    if (currentModalFunctionId) {
        showFunctionDetails(currentModalFunctionId);
    }
}

// Copy function code to clipboard
function copyFunctionCode() {
    const codeElement = document.getElementById('funcModalSource');
    if (!codeElement || !codeElement.textContent) {
        showError('Hata', 'Kopyalanacak kod bulunamadı');
        return;
    }

    const code = codeElement.textContent;

    // Try modern Clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(() => {
            const btn = document.getElementById('copyCodeBtn');
            const oldText = btn.textContent;
            btn.textContent = '✅ Kopyalandı!';
            setTimeout(() => {
                btn.textContent = oldText;
            }, 2000);
        }).catch(err => {
            fallbackCopyToClipboard(code);
        });
    } else {
        // Fallback for older browsers
        fallbackCopyToClipboard(code);
    }
}

// Fallback copy method
function fallbackCopyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();

    try {
        document.execCommand('copy');
        const btn = document.getElementById('copyCodeBtn');
        const oldText = btn.textContent;
        btn.textContent = '✅ Kopyalandı!';
        setTimeout(() => {
            btn.textContent = oldText;
        }, 2000);
    } catch (err) {
        showError('Hata', 'Kopyalama başarısız oldu: ' + err.message);
    } finally {
        document.body.removeChild(textarea);
    }
}

async function saveFunctionSummary() {
    if (!currentModalFunctionId) return;

    const newSummary = document.getElementById('funcModalSummary').value;

    try {
        const response = await fetch(`${API_URL}/analysis/function/${currentModalFunctionId}/summary`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ summary: newSummary })
        });

        if (response.ok) {
            showSuccess('Başarılı', 'Özet başarıyla kaydedildi!');
            loadFunctions(); // Refresh lists behind the modal optionally
        } else {
            showError('Kaydetme Hatası', 'Kaydetme hatası oluştu.');
        }
    } catch (error) {
        showError('Hata', 'Hata: ' + error);
    }
}

async function generateAISummary() {
    if (!currentModalFunctionId) {
        showWarning('Bilgi', 'Önce bir fonksiyon detayı açmalısınız.');
        return;
    }

    const summaryArea = document.getElementById('funcModalSummary');
    if (summaryArea.readOnly) {
        showWarning('Yetki', 'Bu kullanıcı rolü ile özet düzenleme/AI üretimi kapalı.');
        return;
    }

    const oldText = summaryArea.value;
    const trimmedExisting = (oldText || '').trim();
    const hasExistingSummary =
        trimmedExisting.length > 0 &&
        trimmedExisting !== 'AI Yükleniyor... Lütfen bekleyin...';

    if (hasExistingSummary) {
        const shouldOverwrite = confirm('Bu fonksiyon için mevcut bir özet var. AI ile yeniden oluşturup mevcut özeti değiştirmek istiyor musunuz?');
        if (!shouldOverwrite) {
            return;
        }
    }

    // Show progress UI
    const progressDiv = document.getElementById('uploadProgress');
    const progressBar = document.getElementById('uploadProgressBar');
    const progressText = document.getElementById('uploadProgressText');
    const progressDetails = document.getElementById('uploadProgressDetails');
    const progressTitle = document.querySelector('#uploadProgress h3');

    if (progressTitle) {
        progressTitle.textContent = 'AI Özeti Üretiliyor';
    }

    progressDiv.style.display = 'block';
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
    }
    if (progressText) {
        progressText.textContent = 'AI işi global kuyruğa alındı, sıra bekleniyor...';
    }
    if (progressDetails) {
        progressDetails.innerHTML = '<div class="progress-detail">• İş global kuyruğa alındı. Sırası gelince başlatılacak...</div>';
    }

    // Generate task ID for progress tracking
    const aiTaskId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : `ai-summary-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

    // Progress polling starts only after the request is actually started by the global queue.
    const poll = async () => {
        try {
            const response = await fetch(`${API_URL}/projects/progress/${aiTaskId}`);
            if (!response.ok) return;

            const progress = await response.json();

            if (progressBar) {
                progressBar.style.width = `${progress.progress}%`;
                progressBar.textContent = `${progress.progress}%`;
            }

            if (progressText) {
                progressText.textContent = progress.current_step || 'AI analiz sürüyor...';
            }

            if (progressDetails && progress.details && progress.details.length > 0) {
                const lastDetails = progress.details.slice(-10);  // Show last 10 details
                progressDetails.innerHTML = lastDetails.map(detail =>
                    `<div class="progress-detail">• ${detail.message}</div>`
                ).join('');
                progressDetails.scrollTop = progressDetails.scrollHeight;
            }

            if (progress.status === 'completed' || progress.status === 'failed') {
                clearInterval(aiPolling);
            }
        } catch (error) {
            console.error('AI progress polling error:', error);
        }
    };

    let aiPolling = null;
    let requestStarted = false;

    try {
        const extraCriteria = (document.getElementById('funcAiExtraCriteria')?.value || '').trim();
        const extraQuestion = (document.getElementById('funcAiExtraQuestion')?.value || '').trim();
        const aiResponse = await startTrackedAnalysis(
            aiTaskId,
            `Fonksiyon AI Ozeti: #${currentModalFunctionId}`,
            () => fetch(`${API_URL}/analysis/function/${currentModalFunctionId}/ai-summary?task_id=${encodeURIComponent(aiTaskId)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    extra_criteria: extraCriteria,
                    extra_question: extraQuestion
                })
            })
        );
        requestStarted = true;

        summaryArea.value = 'AI Yükleniyor... Lütfen bekleyin...';
        summaryArea.disabled = true;

        if (progressText) {
            progressText.textContent = 'AI analiz başlatıldı...';
        }
        if (progressDetails) {
            progressDetails.innerHTML = '<div class="progress-detail">• LMStudio bağlantısı kontrol ediliyor...</div>';
        }

        aiPolling = setInterval(poll, 1500);
        poll();

        const aiResult = await aiResponse.json();

        if (aiPolling) clearInterval(aiPolling);

        if (aiResponse.ok) {
            summaryArea.value = aiResult.summary;

            if (progressText) {
                progressText.textContent = '✓ AI özeti başarıyla oluşturuldu!';
            }

            // Hide progress after 2 seconds
            setTimeout(() => {
                progressDiv.style.display = 'none';
            }, 2000);

            loadFunctions(); // optionally refresh list in background
        } else {
            summaryArea.value = oldText;
            progressDiv.style.display = 'none';
            showError('AI Analiz Hatası', 'AI analiz hatası: ' + aiResult.error);
        }
    } catch (error) {
        if (aiPolling) clearInterval(aiPolling);
        if (requestStarted) {
            summaryArea.value = oldText;
        }
        progressDiv.style.display = 'none';
        showError('Bağlantı Hatası', 'AI analiz bağlantı hatası: ' + error);
    } finally {
        summaryArea.disabled = false;
    }
}

function closeFunctionModal() {
    const modal = document.getElementById('functionModal');
    modal.classList.remove('visible');
    // Reset fullscreen when closing
    const content = modal.querySelector('.modal-content');
    if (content.classList.contains('fullscreen')) {
        content.classList.remove('fullscreen');
        document.getElementById('fullscreenBtn').textContent = '⛶';
    }
    // Clear source code search when closing
    clearSourceCodeSearch();
}

function openFileViewerModal(title, content) {
    const modal = document.getElementById('fileViewerModal');
    const titleEl = document.getElementById('fileViewerTitle');
    const contentEl = document.getElementById('fileViewerContent');

    if (!modal || !titleEl || !contentEl) return;
    titleEl.textContent = title;
    contentEl.textContent = content;

    modal.classList.add('visible');
}

function closeFileViewerModal() {
    const modal = document.getElementById('fileViewerModal');
    if (!modal) return;
    modal.classList.remove('visible');
}

// Close modals on Escape
document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;

    const fileModal = document.getElementById('fileViewerModal');
    if (fileModal && fileModal.classList.contains('visible')) {
        closeFileViewerModal();
        return;
    }

    const funcModal = document.getElementById('functionModal');
    if (funcModal && funcModal.classList.contains('visible')) {
        closeFunctionModal();
    }
});

// Search in source code
function searchInSourceCode() {
    const searchTerm = document.getElementById('sourceCodeSearch').value.trim();
    const sourceCodeElement = document.getElementById('funcModalSource');
    const resultsDiv = document.getElementById('searchResults');

    if (!searchTerm) {
        clearSourceCodeSearch();
        return;
    }

    // Get original source code (from stored data or current text)
    let sourceCode = sourceCodeElement.dataset.originalSource || sourceCodeElement.textContent;

    // Store original if not already stored
    if (!sourceCodeElement.dataset.originalSource) {
        sourceCodeElement.dataset.originalSource = sourceCode;
    }

    // Case-insensitive search with highlights
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    const matches = sourceCode.match(regex);
    const matchCount = matches ? matches.length : 0;

    if (matchCount > 0) {
        // Highlight matches
        const highlightedCode = sourceCode.replace(regex, '<mark style="background-color: #ffeb3b; color: #000; padding: 2px 0;">$1</mark>');
        sourceCodeElement.innerHTML = highlightedCode;

        // Show results
        resultsDiv.textContent = `${matchCount} eşleşme bulundu`;
        resultsDiv.style.display = 'block';
        resultsDiv.style.color = '#28a745';
    } else {
        // No matches
        resultsDiv.textContent = 'Eşleşme bulunamadı';
        resultsDiv.style.display = 'block';
        resultsDiv.style.color = '#dc3545';
    }
}

// Clear source code search
function clearSourceCodeSearch() {
    const searchInput = document.getElementById('sourceCodeSearch');
    const sourceCodeElement = document.getElementById('funcModalSource');
    const resultsDiv = document.getElementById('searchResults');

    // Clear input
    if (searchInput) {
        searchInput.value = '';
    }

    // Restore original source code
    if (sourceCodeElement && sourceCodeElement.dataset.originalSource) {
        sourceCodeElement.textContent = sourceCodeElement.dataset.originalSource;
    }

    // Hide results
    if (resultsDiv) {
        resultsDiv.style.display = 'none';
    }
}

function toggleFullscreenModal() {
    const modal = document.getElementById('functionModal');
    const content = modal.querySelector('.modal-content');
    const btn = document.getElementById('fullscreenBtn');

    content.classList.toggle('fullscreen');
    btn.textContent = content.classList.contains('fullscreen') ? '✕' : '⛶';
    btn.title = content.classList.contains('fullscreen') ? 'Normal Görünüm (F11)' : 'Tam Ekran (F11)';
}

// Lazy-load dependency chips when class accordion opens
function populateDependencies(classContent) {
    classContent.querySelectorAll('.function-deps[data-deps-loaded="false"]').forEach(depsDiv => {
        const item = depsDiv.closest('.function-item');
        if (!item) return;

        const called = JSON.parse(item.dataset.called || '[]');
        const calledBy = JSON.parse(item.dataset.calledBy || '[]');

        const calledHtml = called.length > 0
            ? called.map(c => `<span class="dep-chip" data-func-id="${c.id}" style="cursor: pointer;">${c.function_name}</span>`).join(' ')
            : '<span class="dep-empty">Yok</span>';

        const calledByHtml = calledBy.length > 0
            ? calledBy.map(c => `<span class="dep-chip dep-chip-caller" data-func-id="${c.id}" style="cursor: pointer;">${c.function_name}</span>`).join(' ')
            : '<span class="dep-empty">Yok</span>';

        // Update HTML with dependency chips
        const divs = depsDiv.querySelectorAll('div');
        if (divs[0]) divs[0].innerHTML = `<strong>Çağırdığı Fonksiyonlar:</strong> ${calledHtml}`;
        if (divs[1]) divs[1].innerHTML = `<strong>Bunu Çağıran Fonksiyonlar:</strong> ${calledByHtml}`;

        // Attach click handlers to newly created chips
        depsDiv.querySelectorAll('.dep-chip[data-func-id]').forEach(chip => {
            chip.onclick = (e) => {
                e.stopPropagation();
                const funcId = chip.dataset.funcId;
                if (funcId) {
                    showFunctionDetails(parseInt(funcId));
                }
            };
            chip.style.transition = 'all 0.2s';
            chip.onmouseover = () => chip.style.opacity = '0.7';
            chip.onmouseout = () => chip.style.opacity = '1';
        });

        depsDiv.setAttribute('data-deps-loaded', 'true');
    });
}

function setupSearchListener() {
    const searchInput = document.getElementById('searchFunctionsText');
    if (!searchInput) return;

    // Remove old listener if exists
    const newSearchInput = searchInput.cloneNode(true);
    searchInput.parentNode.replaceChild(newSearchInput, searchInput);

    newSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();

        // Filter elements
        document.querySelectorAll('.package-group').forEach(pkgDiv => {
            let pkgHasVisible = false;

            pkgDiv.querySelectorAll('.class-group').forEach(clsDiv => {
                let clsHasVisible = false;

                clsDiv.querySelectorAll('.searchable-item').forEach(item => {
                    if (item.dataset.search.includes(query)) {
                        item.style.display = 'block';
                        clsHasVisible = true;
                    } else {
                        item.style.display = 'none';
                    }
                });

                clsDiv.style.display = clsHasVisible ? 'block' : 'none';
                if (clsHasVisible) pkgHasVisible = true;
            });

            pkgDiv.style.display = pkgHasVisible ? 'block' : 'none';
        });
    });
}

// ============================================
// GELIS7: Code Fullscreen View
// ============================================

function toggleCodeFullscreen() {
    const container = document.getElementById('sourceCodeContainer');
    const btn = document.getElementById('expandCodeBtn');

    if (!container || !btn) return;

    // Toggle the fullscreen class
    const isFullscreen = container.classList.toggle('fullscreen-code-container');

    // Update button text and styling based on state
    if (isFullscreen) {
        btn.innerHTML = '🗗 Küçült';
        btn.classList.replace('btn-primary', 'btn-secondary');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    } else {
        btn.innerHTML = '⛶ Genişlet';
        btn.classList.replace('btn-secondary', 'btn-primary');
        document.body.style.overflow = ''; // Restore background scrolling
    }
}

// ============================================
// SECTION: Marks (Comments)
// ============================================

async function loadMarks() {
    try {
        const response = await fetch(`${API_URL}/users/marks/${currentProjectId}`);
        const marks = await response.json();

        const list = document.getElementById('marksList');
        list.innerHTML = '';

        if (marks.length === 0) {
            list.innerHTML = '<p>Henüz işaret yok</p>';
            return;
        }

        marks.forEach(mark => {
            const item = document.createElement('div');
            item.className = `mark-item ${mark.status === 'resolved' ? 'resolved' : ''}`;
            item.innerHTML = `
                <h4>${mark.username} - ${mark.function_name}</h4>
                <p><strong>Tür:</strong> ${mark.mark_type}</p>
                <p>${mark.comment}</p>
                <small>${new Date(mark.created_at).toLocaleDateString('tr-TR')}</small>
            `;
            list.appendChild(item);
        });
    } catch (error) {
        console.error('İşaretler yükleme hatası:', error);
    }
}

async function addMark() {
    const comment = prompt('İşaret açıklaması girin:');
    if (!comment) return;

    try {
        await fetch(`${API_URL}/users/marks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                project_id: currentProjectId,
                function_id: 1,  // TODO: Get actual function ID
                user_id: 1,
                mark_type: 'comment',
                comment: comment
            })
        });
        showSuccess('Başarılı', 'İşaret eklendi');
        loadMarks();
    } catch (error) {
        showError('İşaret Ekleme Hatası', 'İşaret eklenirken hata oluştu: ' + error);
    }
}

// ============================================
// SECTION: Files
// ============================================

let allSourceFiles = [];
let allDocuments = [];

async function loadFiles() {
    try {
        const response = await fetch(`${API_URL}/projects/${currentProjectId}/files`);
        const data = await response.json();

        const list = document.getElementById('filesList');
        list.innerHTML = '';

        allSourceFiles = data.source_files || [];
        allDocuments = data.documents || [];

        filterFiles();
        await loadDalmapFiles();
        return;

    } catch (error) {
        console.error('Dosyalar yükleme hatası:', error);
    }
}

async function viewFileContent(fileId, fileName) {
    if (!currentProjectId) return;

    try {
        const response = await fetch(`${API_URL}/projects/${currentProjectId}/files/${fileId}`);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            showError('Dosya Yükleme Hatası', err.error || 'Dosya içeriği alınamadı');
            return;
        }

        const data = await response.json();
        const content = data.content || '';
        openFileViewerModal(fileName || data.file_name || 'Dosya Görüntüleme', content);
    } catch (error) {
        showError('Dosya Yükleme Hatası', error.message);
    }
}

async function buildDalmapMappingView(dalmap, sqlTables, sqlProcedures) {
    const sections = dalmap.sections || {};
    const classes = Array.isArray(sections.classes) ? sections.classes : [];

    const lines = [];
    lines.push(`DALMap: ${dalmap.file_name || 'DALMap'}`);
    lines.push('');

    if (classes.length === 0) {
        lines.push('⚠️ Hiç CLASS tanımı bulunamadı.');
    } else {
        lines.push('CLASS → TABLO EŞLEMELERİ:');
        lines.push('');
        classes.forEach((cls, idx) => {
            const className = cls.name || cls['class'] || '<unknown>';
            const tableName = cls.table || '<yok>';
            lines.push(`${idx + 1}. CLASS: ${className}`);
            lines.push(`   TABLO: ${tableName}`);

            if (Array.isArray(cls.fields) && cls.fields.length > 0) {
                lines.push('   Alanlar:');
                cls.fields.forEach(f => {
                    const fieldName = f.name || f['column'] || f.field || '<unknown>';
                    const fieldType = f.type || f['datatype'] || '';
                    lines.push(`     - ${fieldName}${fieldType ? ` (${fieldType})` : ''}`);
                });
            } else {
                lines.push('   (Bu CLASS için alan bilgisi bulunamadı)');
            }

            // Show SQL schema if available
            const normalizedTable = (tableName || '').toLowerCase().split('.').pop();
            if (normalizedTable && sqlTables) {
                const sql = sqlTables[normalizedTable];
                if (sql) {
                    lines.push('   --- DB TABLO ŞEMASI (CREATE TABLE) ---');
                    const sqlLines = sql.split('\n').map(l => `     ${l}`);
                    lines.push(...sqlLines);
                }
            }

            // Find related stored procedures (by table name or class name)
            const normalizedClassName = (className || '').toLowerCase();
            const procMatches = [];
            if (sqlProcedures) {
                Object.keys(sqlProcedures).forEach(procName => {
                    const pn = procName.toLowerCase();
                    if (normalizedTable && pn.includes(normalizedTable)) {
                        procMatches.push(procName);
                    } else if (normalizedClassName && pn.includes(normalizedClassName)) {
                        procMatches.push(procName);
                    }
                });
            }

            if (procMatches.length > 0) {
                lines.push('   İlgili SP/Function (SQL):');
                procMatches.forEach(pn => lines.push(`     - ${pn}`));
            }

            lines.push('');
        });
    }

    // Global SQL procedures list
    const procedures = sqlProcedures || {};
    const procNames = Object.keys(procedures);
    if (procNames.length > 0) {
        lines.push('SQL PROSEDÜRLERİ / FONKSİYONLAR:');
        lines.push('');
        procNames.forEach(name => {
            lines.push(`- ${name}`);
        });
    }

    return lines.join('\n');
}

async function loadDalmapFiles() {
    if (!currentProjectId) return;

    const container = document.getElementById('dalmapList');
    if (!container) return;
    container.innerHTML = '<div style="color:#666;">DALMap dosyaları yükleniyor...</div>';

    try {
        const resp = await fetch(`${API_URL}/projects/${currentProjectId}/dalmaps`);
        if (!resp.ok) {
            container.innerHTML = `<div style="color:#c0392b;">Hata: ${resp.status}</div>`;
            return;
        }

        const data = await resp.json();
        const dalmaps = Array.isArray(data.dalmaps) ? data.dalmaps : [];
        const sqlTables = (data.sql_tables && typeof data.sql_tables === 'object') ? data.sql_tables : {};
        const sqlProcedures = (data.sql_procedures && typeof data.sql_procedures === 'object') ? data.sql_procedures : {};

        if (!dalmaps.length) {
            container.innerHTML = '<div style="color:#666;">Bu projede DALMap dosyası bulunamadı.</div>';
            return;
        }

        container.innerHTML = '';
        dalmaps.forEach(d => {
            const item = document.createElement('div');
            item.style.cssText = 'padding:8px; border:1px solid #e1e7ee; border-radius:6px; margin-bottom:8px; background:#fff; display:flex; justify-content:space-between; align-items:flex-start;';

            const info = document.createElement('div');
            const title = document.createElement('div');
            title.style.fontWeight = '600';
            title.textContent = d.file_name || 'DALMap';
            const meta = document.createElement('div');
            meta.style.fontSize = '12px';
            meta.style.color = '#555';
            meta.textContent = `Oluşturulma: ${new Date(d.created_at).toLocaleString('tr-TR')}`;
            info.appendChild(title);
            info.appendChild(meta);

            const btn = document.createElement('button');
            btn.className = 'btn btn-secondary';
            btn.style.fontSize = '12px';
            btn.textContent = 'Göster';
            btn.onclick = async () => {
                const mappedView = await buildDalmapMappingView(d, sqlTables, sqlProcedures);
                openFileViewerModal(d.file_name || 'DALMap', mappedView);
            };

            item.appendChild(info);
            item.appendChild(btn);
            container.appendChild(item);
        });
    } catch (error) {
        container.innerHTML = `<div style="color:#c0392b;">Hata: ${error.message}</div>`;
    }
}

function filterFiles() {
    const query = (document.getElementById('fileFilterInput')?.value || '').trim().toLowerCase();
    const type = (document.getElementById('fileFilterType')?.value || 'all');

    const list = document.getElementById('filesList');
    list.innerHTML = '';

    const filteredSources = allSourceFiles.filter(f => {
        if (type === 'doc') return false;
        if (!query) return true;
        return (`${f.file_name} ${f.file_path} ${f.language || ''}`).toLowerCase().includes(query);
    });

    const filteredDocs = allDocuments.filter(d => {
        if (type === 'source') return false;
        if (!query) return true;
        return (`${d.file_name} ${d.file_path} ${d.document_type || ''}`).toLowerCase().includes(query);
    });

    if (filteredSources.length === 0 && filteredDocs.length === 0) {
        const empty = document.createElement('p');
        empty.style.cssText = 'color:#666; padding:10px;';
        empty.textContent = 'Bu filtreye uyan dosya bulunamadı.';
        list.appendChild(empty);
        return;
    }

    if (filteredSources.length > 0) {
        const header = document.createElement('h4');
        header.style.cssText = 'margin: 0 0 10px 0; color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 6px;';
        header.textContent = `📄 Kaynak Dosyalar (${filteredSources.length})`;
        list.appendChild(header);

        filteredSources.forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.style.cssText = 'display:flex; justify-content:space-between; align-items:flex-start; gap:8px;';

            const infoDiv = document.createElement('div');
            infoDiv.style.flex = '1';
            const nameEl = document.createElement('h4');
            nameEl.style.margin = '0 0 2px 0';
            nameEl.textContent = file.file_name;
            const pathEl = document.createElement('p');
            pathEl.style.cssText = 'font-size:12px; color:#666; margin:2px 0;';
            pathEl.textContent = file.file_path;
            const langEl = document.createElement('small');
            langEl.textContent = `Dil: ${file.language || 'bilinmiyor'}`;
            infoDiv.appendChild(nameEl);
            infoDiv.appendChild(pathEl);
            infoDiv.appendChild(langEl);

            const analyzeBtn = document.createElement('button');
            analyzeBtn.className = 'btn btn-secondary';
            analyzeBtn.style.cssText = 'font-size:11px; padding:4px 8px; white-space:nowrap; flex-shrink:0;';
            analyzeBtn.textContent = '🔍 Analiz Et';
            analyzeBtn.onclick = (e) => { e.stopPropagation(); analyzeFileById(file.id, file.file_name, analyzeBtn); };

            item.appendChild(infoDiv);
            item.appendChild(analyzeBtn);
            item.style.cursor = 'pointer';
            item.onclick = () => viewFileContent(file.id, file.file_name);
            list.appendChild(item);
        });
    }

    if (filteredDocs.length > 0) {
        const header = document.createElement('h4');
        header.style.cssText = 'margin: 16px 0 10px 0; color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 6px;';
        header.textContent = `📁 Dokümanlar / RAG Dosyaları (${filteredDocs.length})`;
        list.appendChild(header);

        filteredDocs.forEach(doc => {
            const item = document.createElement('div');
            item.className = 'file-item';
            const nameEl = document.createElement('h4');
            nameEl.textContent = doc.file_name;
            const pathEl = document.createElement('p');
            pathEl.style.cssText = 'font-size:12px; color:#666; margin:2px 0;';
            pathEl.textContent = doc.file_path;
            const typeEl = document.createElement('small');
            typeEl.textContent = `Tip: ${doc.document_type || 'doküman'} • RAG`;
            item.appendChild(nameEl);
            item.appendChild(pathEl);
            item.appendChild(typeEl);
            list.appendChild(item);
        });
    }
}

function clearFileFilter() {
    const input = document.getElementById('fileFilterInput');
    const typeEl = document.getElementById('fileFilterType');
    if (input) input.value = '';
    if (typeEl) typeEl.value = 'all';
    filterFiles();
}


// Add file to existing project (GELIS8)
async function addFileToProject() {
    const fileInput = document.getElementById('addFileInput');
    const file = fileInput.files[0];
    
    if (!file) {
        showError('Dosya Seçiniz', 'Lütfen eklemek için bir dosya seçiniz');
        return;
    }
    
    // Validate file type
    const fileName = file.name.toLowerCase();
    const validExtensions = ['.zip', '.war', '.jar', '.java', '.sql', '.py', '.js', '.ts', '.php', '.xml',
                             '.pdf', '.doc', '.docx', '.txt', '.md'];
    const isValid = validExtensions.some(ext => fileName.endsWith(ext));
    
    if (!isValid) {
        showError('Geçersiz Dosya Tipi', `Desteklenmeyen dosya tipi: ${file.name}\n\nDesteklenen: ZIP, WAR, JAR, Java, Python, JavaScript, SQL, PDF, DOC, DOCX, TXT, MD`);
        return;
    }
    
    const progressDiv = document.getElementById('addFileProgress');
    const progressBar = document.getElementById('addFileProgressBar');
    const progressText = document.getElementById('addFileProgressText');
    
    progressDiv.style.display = 'block';
    progressBar.style.width = '0%';
    progressText.textContent = `Yükleniyor: ${file.name}...`;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        // Simulate progress
        let simulatedProgress = 0;
        const progressInterval = setInterval(() => {
            if (simulatedProgress < 90) {
                simulatedProgress += Math.random() * 30;
                if (simulatedProgress > 90) simulatedProgress = 90;
                progressBar.style.width = simulatedProgress + '%';
            }
        }, 300);
        
        const response = await fetch(`${API_URL}/projects/${currentProjectId}/add-file`, {
            method: 'POST',
            body: formData
        });
        
        clearInterval(progressInterval);
        
        if (response.ok) {
            const result = await response.json();
            progressBar.style.width = '100%';
            progressText.textContent = `✓ Dosya yüklendi, analiz başlatılıyor...`;

            // If a single source code file was added, auto-analyze it
            if (result.added_file_id) {
                let funcCount = 0;
                try {
                    progressText.textContent = `🔍 Fonksiyonlar çıkarılıyor: ${result.file_name}...`;
                    const analyzeResp = await fetch(
                        `${API_URL}/analysis/project/${currentProjectId}/analyze-single-file/${result.added_file_id}`,
                        { method: 'POST' }
                    );
                    if (analyzeResp.ok) {
                        const analyzeResult = await analyzeResp.json();
                        funcCount = analyzeResult.functions_found || 0;
                    }
                } catch (e) {
                    console.warn('Otomatik analiz başlatılamadı:', e);
                }
                progressText.textContent = `✓ Tamamlandı! ${funcCount} fonksiyon çıkarıldı`;
                setTimeout(() => {
                    fileInput.value = '';
                    progressDiv.style.display = 'none';
                    loadFiles();
                    loadFunctions();
                    showSuccess('Dosya Ekleme', `${result.file_name} eklendi, ${funcCount} fonksiyon çıkarıldı`);
                }, 1200);
            } else {
                // ZIP/doc uploads
                setTimeout(() => {
                    fileInput.value = '';
                    progressDiv.style.display = 'none';
                    loadFiles();
                    showSuccess('Dosya Ekleme', `${result.files_processed} kaynak dosya, ${result.documents_added} doküman başarıyla eklendi`);
                }, 1200);
            }
        } else {
            const error = await response.json();
            clearInterval(progressInterval);
            progressDiv.style.display = 'none';
            showError('Dosya Ekleme Hatası', error.error || 'Dosya eklenirken hata oluştu');
        }
    } catch (error) {
        console.error('Dosya ekleme hatası:', error);
        progressDiv.style.display = 'none';
        showError('Dosya Ekleme Hatası', error.message || 'Bilinmeyen bir hata oluştu');
    }
}

async function analyzeFileById(fileId, fileName, btn) {
    if (!fileId || !currentProjectId) return;
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Analiz ediliyor...';
    try {
        const resp = await fetch(
            `${API_URL}/analysis/project/${currentProjectId}/analyze-single-file/${fileId}`,
            { method: 'POST' }
        );
        if (resp.ok) {
            const result = await resp.json();
            const cnt = result.functions_found || 0;
            btn.textContent = `✓ ${cnt} fonksiyon`;
            loadFunctions();
            showSuccess('Analiz Tamamlandı', `${fileName}: ${cnt} fonksiyon çıkarıldı`);
        } else {
            const err = await resp.json().catch(() => ({}));
            btn.textContent = '❌ Hata';
            showError('Analiz Hatası', err.error || `HTTP ${resp.status}`);
        }
    } catch (e) {
        btn.textContent = '❌ Hata';
        showError('Analiz Hatası', e.message || 'Bilinmeyen hata');
    } finally {
        setTimeout(() => { btn.disabled = false; btn.textContent = original; }, 3000);
    }
}


// ============================================
// SECTION: Settings
// ============================================

async function loadSettings() {
    try {
        const apiUrlInput = document.getElementById('apiUrl');
        const queueLimitInput = document.getElementById('globalAiQueueLimit');
        let userApiUrl = '';
        let userPreferences = {};

        // Load per-user settings first (includes ai_api_url)
        const userSettingsResp = await fetch(`${API_URL}/users/settings`);
        if (userSettingsResp.ok) {
            const userSettings = await userSettingsResp.json();
            userApiUrl = (userSettings.ai_api_url || '').trim();
            try {
                userPreferences = userSettings.preferences ? JSON.parse(userSettings.preferences) : {};
            } catch (_err) {
                userPreferences = {};
            }
            if (apiUrlInput && userApiUrl) {
                apiUrlInput.value = userApiUrl;
            }
            if (queueLimitInput) {
                queueLimitInput.value = userPreferences.ai_queue_limit || 2;
            }
            if (typeof setGlobalAiQueueLimit === 'function') {
                setGlobalAiQueueLimit(userPreferences.ai_queue_limit || 2);
            }
        }

        // Load global AI parameters
        const response = await fetch(`${API_URL}/ai-settings/`);
        const settings = await response.json();

        // Fallback to global api_url if user-specific value is empty
        if (apiUrlInput && !userApiUrl && settings.api_url !== undefined) {
            apiUrlInput.value = settings.api_url;
        }

        // Load settings into form
        if (settings.temperature !== undefined) {
            const tempInput = document.getElementById('temperature');
            if (tempInput) {
                tempInput.value = settings.temperature;
                const tempValue = document.getElementById('temperatureValue');
                if (tempValue) tempValue.textContent = settings.temperature;
            }
        }

        if (settings.top_p !== undefined) {
            const topPInput = document.getElementById('topP');
            if (topPInput) {
                topPInput.value = settings.top_p;
                const topPValue = document.getElementById('topPValue');
                if (topPValue) topPValue.textContent = settings.top_p;
            }
        }

        if (settings.max_tokens !== undefined) {
            const maxTokensInput = document.getElementById('maxTokens');
            if (maxTokensInput) {
                maxTokensInput.value = settings.max_tokens;
            }
        }

        if (settings.timeout !== undefined) {
            const timeoutInput = document.getElementById('timeout');
            if (timeoutInput) {
                timeoutInput.value = settings.timeout;
            }
        }

        if (settings.frequency_penalty !== undefined) {
            const freqInput = document.getElementById('frequencyPenalty');
            if (freqInput) {
                freqInput.value = settings.frequency_penalty;
                const freqValue = document.getElementById('frequencyPenaltyValue');
                if (freqValue) freqValue.textContent = settings.frequency_penalty;
            }
        }

        if (settings.presence_penalty !== undefined) {
            const presInput = document.getElementById('presencePenalty');
            if (presInput) {
                presInput.value = settings.presence_penalty;
                const presValue = document.getElementById('presencePenaltyValue');
                if (presValue) presValue.textContent = settings.presence_penalty;
            }
        }

        if (settings.retry_count !== undefined) {
            const retryInput = document.getElementById('retryCount');
            if (retryInput) {
                retryInput.value = settings.retry_count;
            }
        }

        console.log('Settings loaded from database:', settings);
    } catch (error) {
        console.error('Ayarlar yükleme hatası:', error);
    }
}

async function saveLMSettings() {
    const apiUrlValue = document.getElementById('apiUrl').value.trim();
    const queueLimitValue = parseInt(document.getElementById('globalAiQueueLimit').value, 10);
    const tempValue = parseFloat(document.getElementById('temperature').value);
    const topPValue = parseFloat(document.getElementById('topP').value);
    const maxTokensValue = parseInt(document.getElementById('maxTokens').value);
    const timeoutValue = parseInt(document.getElementById('timeout').value);
    const frequencyPenaltyValue = parseFloat(document.getElementById('frequencyPenalty').value);
    const presencePenaltyValue = parseFloat(document.getElementById('presencePenalty').value);
    const retryCountValue = parseInt(document.getElementById('retryCount').value);

    const settings = {
        temperature: { value: tempValue, type: 'float' },
        top_p: { value: topPValue, type: 'float' },
        max_tokens: { value: maxTokensValue, type: 'integer' },
        timeout: { value: timeoutValue, type: 'integer' },
        frequency_penalty: { value: frequencyPenaltyValue, type: 'float' },
        presence_penalty: { value: presencePenaltyValue, type: 'float' },
        retry_count: { value: retryCountValue, type: 'integer' }
    };

    try {
        // Validate the AI server URL before saving
        if (!apiUrlValue) {
            throw new Error('Lütfen AI Sunucu URL’sini girin');
        }

        const testResult = await testLMConnection(apiUrlValue);
        if (testResult.status !== 'connected') {
            throw new Error(`Bağlantı testi başarısız: ${testResult.message || 'Bilinmeyen hata'}`);
        }

        console.log('Saving settings:', settings);

        let existingPreferences = {};
        try {
            const currentUserSettingsResponse = await fetch(`${API_URL}/users/settings`);
            if (currentUserSettingsResponse.ok) {
                const currentUserSettings = await currentUserSettingsResponse.json();
                existingPreferences = currentUserSettings.preferences ? JSON.parse(currentUserSettings.preferences) : {};
            }
        } catch (_err) {
            existingPreferences = {};
        }

        const nextPreferences = {
            ...existingPreferences,
            ai_queue_limit: Math.max(1, Math.min(8, queueLimitValue || 2))
        };

        // Save per-user AI server URL
        const userSettingsResponse = await fetch(`${API_URL}/users/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ai_api_url: apiUrlValue, preferences: JSON.stringify(nextPreferences) })
        });

        if (!userSettingsResponse.ok) {
            const errData = await userSettingsResponse.json().catch(() => ({}));
            throw new Error(errData.error || 'Failed to save user AI server URL');
        }

        for (const [key, setting] of Object.entries(settings)) {
            const response = await fetch(`${API_URL}/ai-settings/${key}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    value: setting.value,
                    type: setting.type
                })
            });

            if (!response.ok) {
                throw new Error(`Failed to save ${key}: ${response.statusText}`);
            }

            console.log(`Setting ${key} saved successfully`);
        }

        if (typeof setGlobalAiQueueLimit === 'function') {
            setGlobalAiQueueLimit(nextPreferences.ai_queue_limit);
        }

        showSuccess('Başarılı', 'Ayarlar kaydedildi ve sisteme uygulandı');
    } catch (error) {
        console.error('Ayarlar Kaydetme Hatası:', error);
        showError('Ayarlar Kaydetme Hatası', 'Ayarlar kaydedilirken hata oluştu: ' + error.message);
    }
}

async function testLMConnection(apiUrl) {
    try {
        const response = await fetch(`${API_URL}/ai-settings/lmstudio/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_url: apiUrl })
        });
        const result = await response.json();

        const resultDiv = document.getElementById('connectionResult');
        if (!resultDiv) return result;

        if (result.status === 'connected') {
            resultDiv.textContent = '✓ Bağlantı başarılı!';
            resultDiv.className = 'success';
        } else {
            resultDiv.textContent = '✗ Bağlantı başarısız: ' + result.message;
            resultDiv.className = 'error';
        }

        return result;
    } catch (error) {
        const resultDiv = document.getElementById('connectionResult');
        if (resultDiv) {
            resultDiv.textContent = 'Hata: ' + error;
            resultDiv.className = 'error';
        }
        return { status: 'error', message: error.message || String(error) };
    }
}

async function changePassword() {
    const currentPasswordInput = document.getElementById('currentPassword');
    const newPasswordInput = document.getElementById('newPassword');
    const confirmNewPasswordInput = document.getElementById('confirmNewPassword');

    if (!currentPasswordInput || !newPasswordInput || !confirmNewPasswordInput) {
        showError('Hata', 'Şifre alanları bulunamadı');
        return;
    }

    const currentPassword = currentPasswordInput.value;
    const newPassword = newPasswordInput.value;
    const confirmNewPassword = confirmNewPasswordInput.value;

    if (!currentPassword || !newPassword || !confirmNewPassword) {
        showError('Hata', 'Lütfen tüm şifre alanlarını doldurun');
        return;
    }

    if (newPassword.length < 4) {
        showError('Hata', 'Yeni şifre en az 4 karakter olmalı');
        return;
    }

    if (newPassword !== confirmNewPassword) {
        showError('Hata', 'Yeni şifreler eşleşmiyor');
        return;
    }

    if (newPassword === currentPassword) {
        showError('Hata', 'Yeni şifre mevcut şifreyle aynı olamaz');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/users/change-password`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Şifre güncellenemedi');
        }

        currentPasswordInput.value = '';
        newPasswordInput.value = '';
        confirmNewPasswordInput.value = '';

        showSuccess('Başarılı', 'Şifreniz güncellendi');
    } catch (error) {
        showError('Hata', error.message || 'Şifre güncellenirken hata oluştu');
    }
}

// ============================================
// SECTION: Event Listeners
// ============================================

document.getElementById('temperature')?.addEventListener('input', (e) => {
    document.getElementById('temperatureValue').textContent = e.target.value;
});

document.getElementById('topP')?.addEventListener('input', (e) => {
    document.getElementById('topPValue').textContent = e.target.value;
});

document.getElementById('frequencyPenalty')?.addEventListener('input', (e) => {
    document.getElementById('frequencyPenaltyValue').textContent = e.target.value;
});

document.getElementById('presencePenalty')?.addEventListener('input', (e) => {
    document.getElementById('presencePenaltyValue').textContent = e.target.value;
});

// ============================================
// SECTION: Authentication
// ============================================

function checkSession() {
    const user = localStorage.getItem('currentUser');
    const loginSection = document.getElementById('loginSection');
    const navbar = document.getElementById('navbar');
    const mainContent = document.getElementById('mainContent');

    if (user) {
        currentUser = JSON.parse(user);
        // Show main UI, hide login
        if (loginSection) loginSection.style.display = 'none';
        if (navbar) navbar.style.display = 'flex';
        if (mainContent) mainContent.style.display = 'block';
        document.getElementById('userInfo').textContent = `👤 ${currentUser.username} (${currentUser.role})`;

        // Show admin/developer links based on role
        const adminLink = document.getElementById('adminLink');
        const permissionsLink = document.getElementById('permissionsLink');
        const uploadLink = document.getElementById('uploadLink');

        if (currentUser.role === 'admin') {
            if (adminLink) adminLink.style.display = 'inline-block';
            if (permissionsLink) permissionsLink.style.display = 'inline-block';
            if (uploadLink) uploadLink.style.display = 'inline-block';
        } else if (currentUser.role === 'developer') {
            if (adminLink) adminLink.style.display = 'none';
            if (permissionsLink) permissionsLink.style.display = 'inline-block';
            if (uploadLink) uploadLink.style.display = 'inline-block';
        } else {
            if (adminLink) adminLink.style.display = 'none';
            if (permissionsLink) permissionsLink.style.display = 'none';
            if (uploadLink) uploadLink.style.display = 'none';
        }

        return true;
    } else {
        // Show login, hide main UI
        if (loginSection) loginSection.style.display = 'block';
        if (navbar) navbar.style.display = 'none';
        if (mainContent) mainContent.style.display = 'none';
        return false;
    }
}

async function handleLogin(e) {
    e.preventDefault();

    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorDiv = document.getElementById('loginError');

    try {
        const response = await fetch(`${API_URL}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok && data.user) {
            // Store user info
            localStorage.setItem('currentUser', JSON.stringify(data.user));
            currentUser = data.user;

            // Update UI
            errorDiv.style.display = 'none';
            document.getElementById('loginForm').reset();
            checkSession();

            // Load projects
            loadProjects();
        } else {
            const serverMessage = data.error || 'Giriş başarısız';
            if (response.status === 401) {
                errorDiv.textContent = `${serverMessage}. Demo: admin/admin123, developer/developer123 veya analyzer/analyzer123`;
            } else {
                errorDiv.textContent = serverMessage;
            }
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Sunucuya bağlanılamadı. Backend çalışıyor mu kontrol edin.';
        errorDiv.style.display = 'block';
    }
}

function logout() {
    // Call server logout
    fetch(`${API_URL}/users/logout`, {
        method: 'POST'
    }).then(() => {
        localStorage.removeItem('currentUser');
        currentUser = null;
        checkSession();
    }).catch(err => {
        // Even if server fails, still logout locally
        localStorage.removeItem('currentUser');
        currentUser = null;
        checkSession();
    });
}

// ============================================
// SECTION: Initialization
// ============================================

// Fetch Git repository info and populate branch list
async function fetchGitInfo() {
    const urlInput = document.getElementById('gitRepoUrl');
    const branchSelect = document.getElementById('gitBranch');
    const nameInput = document.getElementById('gitProjectName');
    const loader = document.getElementById('gitUrlLoader');

    const url = urlInput.value.trim();

    if (!url) {
        return;
    }

    // Show loader
    loader.style.display = 'block';
    branchSelect.innerHTML = '<option value="">Branch seçin...</option>';
    branchSelect.disabled = true;

    try {
        const response = await fetch(`${API_URL}/projects/git-info`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        if (!response.ok) {
            throw new Error('Repository bilgileri alınamadı');
        }

        const data = await response.json();

        // Populate branch dropdown
        branchSelect.innerHTML = '';
        data.branches.forEach(branch => {
            const option = document.createElement('option');
            option.value = branch;
            option.textContent = branch;
            if (branch === data.default_branch) {
                option.selected = true;
            }
            branchSelect.appendChild(option);
        });
        branchSelect.disabled = false;

        // Auto-fill project name if empty
        if (!nameInput.value && data.repo_name) {
            nameInput.value = data.repo_name;
        }

        // Show warning if any
        if (data.warning) {
            console.warn('Git info warning:', data.warning);
        }

    } catch (error) {
        console.error('Git info fetch error:', error);
        // Fallback to default branches
        branchSelect.innerHTML = `
            <option value="main">main</option>
            <option value="master">master</option>
            <option value="develop">develop</option>
        `;
        branchSelect.disabled = false;
    } finally {
        loader.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Setup login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    // Setup Git URL autocomplete
    const gitUrlInput = document.getElementById('gitRepoUrl');
    if (gitUrlInput) {
        // Debounce function to avoid too many requests
        let gitUrlTimeout;
        gitUrlInput.addEventListener('input', () => {
            clearTimeout(gitUrlTimeout);
            gitUrlTimeout = setTimeout(() => {
                const url = gitUrlInput.value.trim();
                // Check if it looks like a valid Git URL
                if (url && (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('git@'))) {
                    fetchGitInfo();
                }
            }, 1000); // Wait 1 second after user stops typing
        });

        // Also fetch on blur
        gitUrlInput.addEventListener('blur', () => {
            const url = gitUrlInput.value.trim();
            if (url && (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('git@'))) {
                fetchGitInfo();
            }
        });
    }

    // Global ESC key handler to close modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.keyCode === 27) {
            // Close function modal if visible
            const functionModal = document.getElementById('functionModal');
            if (functionModal && functionModal.classList.contains('visible')) {
                closeFunctionModal();
                return;
            }

            // Close message modal if visible
            const messageModal = document.getElementById('messageModal');
            if (messageModal && messageModal.classList.contains('visible')) {
                closeMessageModal();
                return;
            }
        }
    });

    // Source code search - Enter key support
    const searchInput = document.getElementById('sourceCodeSearch');
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                searchInSourceCode();
            }
        });
    }

    // Check session on page load
    if (checkSession()) {
        loadProjects();
    }
});

// ----------------------------------------------------
// GELIS3: Call Graph Modal Functions
// ----------------------------------------------------
let cyCallGraph = null;

async function showCallGraph(functionId) {
    if (!functionId) return;

    const modal = document.getElementById('callGraphModal');
    const loading = document.getElementById('cgLoadingIndicator');

    // Close the details modal to prevent overlay stacking issues
    const detailsModal = document.getElementById('functionModal');
    if (detailsModal) detailsModal.classList.remove('visible');

    modal.classList.add('visible');
    loading.style.display = 'block';

    if (cyCallGraph) {
        cyCallGraph.destroy();
        cyCallGraph = null;
    }

    try {
        const response = await fetch(`${API_URL}/diagram/function/${functionId}/callgraph`);
        if (!response.ok) throw new Error('Ağ bağlantı hatası veya fonksiyon bulunamadı');
        const data = await response.json();

        // Check if cytoscape is already loaded, similar to loadDiagramData()
        if (typeof cytoscape === 'undefined') {
            await new Promise(resolve => {
                const interval = setInterval(() => {
                    if (typeof cytoscape !== 'undefined') {
                        clearInterval(interval);
                        resolve();
                    }
                }, 100);
            });
        }

        const container = document.getElementById('callGraphContainer');

        cyCallGraph = cytoscape({
            container: container,
            elements: [
                ...data.nodes.map(node => ({
                    data: {
                        id: node.id.toString(),
                        label: node.label,
                        title: node.title,
                        is_target: node.is_target_node
                    },
                    classes: node.is_target_node ? 'target-node' : 'dependent-node'
                })),
                ...data.edges.map(edge => ({
                    data: {
                        source: edge.from.toString(),
                        target: edge.to.toString()
                    }
                }))
            ],
            style: [
                {
                    selector: 'node',
                    style: {
                        'content': 'data(label)',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'color': '#fff',
                        'padding': '10px',
                        'font-size': '12px',
                        'width': '140px',
                        'height': '60px',
                        'text-wrap': 'wrap',
                        'text-max-width': '130px',
                        'border-width': '2px',
                        'border-color': '#2c3e50'
                    }
                },
                {
                    selector: 'node.target-node',
                    style: {
                        'background-color': '#f39c12',
                        'border-width': '4px',
                        'border-color': '#d35400'
                    }
                },
                {
                    selector: 'node.dependent-node',
                    style: {
                        'background-color': '#3498db'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'line-color': '#95a5a6',
                        'target-arrow-color': '#95a5a6',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'width': 2,
                        'arrow-scale': 1.2
                    }
                }
            ],
            layout: {
                name: 'cose',
                directed: true,
                padding: 50,
                componentSpacing: 100,
                nodeRepulsion: function (node) { return 2000000; }, // Massive repulsion to prevent overlaps
                nodeOverlap: 50, // Extra padding around nodes
                idealEdgeLength: function (edge) { return 150; }, // Longer edges
                edgeElasticity: function (edge) { return 100; },
                nestingFactor: 5,
                gravity: 80, // Lower gravity so they can spread out
                numIter: 2500, // More iterations for the engine to settle
                initialTemp: 200,
                coolingFactor: 0.95,
                minTemp: 1.0,
                animate: true
            }
        });

        // Event handler for clicking a node in the call graph opens its details
        cyCallGraph.on('tap', 'node', function (evt) {
            const node = evt.target;
            closeCallGraphModal();
            showFunctionDetails(node.data('id'));
        });

    } catch (err) {
        console.error('Call Graph yükleme hatası:', err);
        showError('Hata', 'Call Graph yüklenirken bir sorun oluştu: ' + err.message);
        closeCallGraphModal();
    } finally {
        loading.style.display = 'none';
        if (cyCallGraph) {
            setTimeout(() => cyCallGraph.fit(), 300);
        }
    }
}

function closeCallGraphModal() {
    const modal = document.getElementById('callGraphModal');
    if (modal) {
        modal.classList.remove('visible');
    }
    if (cyCallGraph) {
        cyCallGraph.destroy();
        cyCallGraph = null;
    }
}

function resetCallGraphZoom() {
    if (cyCallGraph) {
        cyCallGraph.fit();
        cyCallGraph.center();
    }
}

function toggleCallGraphFullscreen() {
    const modalContent = document.querySelector('#callGraphModal .modal-content');
    const graphContainer = document.getElementById('callGraphContainer');

    if (!document.fullscreenElement) {
        modalContent.requestFullscreen().catch(err => {
            console.error(`Tam ekran hatası: ${err.message}`);
        });
        graphContainer.style.height = 'calc(100vh - 100px)';
    } else {
        document.exitFullscreen();
        graphContainer.style.height = 'auto';
    }

    setTimeout(() => {
        if (cyCallGraph) cyCallGraph.resize().fit();
    }, 200);
}
