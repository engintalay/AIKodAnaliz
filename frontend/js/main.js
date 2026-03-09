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

        const projectsList = document.getElementById('projectsList');
        projectsList.innerHTML = '';

        if (projects.length === 0) {
            projectsList.innerHTML = '<p>Henüz proje yok. Yeni bir proje yükleyin.</p>';
            return;
        }

        projects.forEach(project => {
            const card = document.createElement('div');
            card.className = 'project-card';

            let actionButtons = `<button onclick="viewProject(${project.id})" class="btn btn-primary">Aç</button>`;

            // Restrict Delete & Reanalyze to admin and project owners
            const canManage = currentUser && (currentUser.role === 'admin' || project.admin_id === currentUser.id);

            if (canManage) {
                actionButtons += `
                    <button onclick="reanalyzeProject(${project.id})" class="btn btn-secondary">🔄 Tekrar Analiz Et</button>
                    <button onclick="deleteProject(${project.id})" class="btn btn-secondary">Sil</button>
                `;
            }

            card.innerHTML = `
                <h3>${project.name}</h3>
                <p>${project.description || 'Açıklama yok'}</p>
                <small>Yüklenme: ${new Date(project.upload_date).toLocaleDateString('tr-TR')}</small>
                <div class="project-card-actions">
                    ${actionButtons}
                </div>
            `;
            projectsList.appendChild(card);
        });
    } catch (error) {
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
        const response = await fetch(`${API_URL}/analysis/project/${currentProjectId}/bulk-ai-summary?task_id=${taskId}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'İşlem başlatılamadı');
        }

        // Start polling progress
        currentTaskId = taskId;
        pollProgress(taskId);
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

function initChatTab() {
    // Scroll to bottom on tab switch
    const msgs = document.getElementById('chatMessages');
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
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
    // Switch to Functions tab and scroll to the function row
    switchTab('functions');
    setTimeout(() => {
        const row = document.querySelector(`[data-function-id="${functionId}"]`);
        if (row) {
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            row.style.outline = '2px solid #3498db';
            setTimeout(() => row.style.outline = '', 2000);
        }
    }, 200);
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
        const response = await fetch(`${API_URL}/chat/project/${currentProjectId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, history: historySlice })
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

        const response = await fetch(`${API_URL}/diagram/project/${currentProjectId}`);
        const data = await response.json();

        // Initialize Cytoscape
        const container = document.getElementById('diagramContainer');

        // Create set of valid node IDs for defensive filtering
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
        `;

        // Update Text Areas
        const summaryTextarea = document.getElementById('funcModalSummary');
        summaryTextarea.value = func.ai_summary || '';
        document.getElementById('funcModalSource').textContent = func.source_code || 'Kaynak kod yok.';

        // Apply role constraints: Analyzer cannot edit or generate AI summaries
        const canEdit = currentUser && currentUser.role !== 'analyzer';
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
    if (!currentModalFunctionId) return;

    const summaryArea = document.getElementById('funcModalSummary');
    const oldText = summaryArea.value;

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
        progressText.textContent = 'AI analiz başlatılıyor...';
    }
    if (progressDetails) {
        progressDetails.innerHTML = '<div class="progress-detail">• LMStudio bağlantısı kontrol ediliyor...</div>';
    }

    summaryArea.value = "AI Yükleniyor... Lütfen bekleyin...";
    summaryArea.disabled = true;

    // Generate task ID for progress tracking
    const aiTaskId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : `ai-summary-${Date.now()}-${Math.floor(Math.random() * 10000)}`;

    // Start polling progress
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

    let aiPolling = setInterval(poll, 1500);  // Poll every 1500ms
    poll();  // Initial poll

    try {
        const aiResponse = await fetch(`${API_URL}/analysis/function/${currentModalFunctionId}/ai-summary?task_id=${encodeURIComponent(aiTaskId)}`, {
            method: 'POST'
        });
        const aiResult = await aiResponse.json();

        clearInterval(aiPolling);

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
        clearInterval(aiPolling);
        summaryArea.value = oldText;
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

async function loadFiles() {
    try {
        const response = await fetch(`${API_URL}/projects/${currentProjectId}/files`);
        const files = await response.json();

        const list = document.getElementById('filesList');
        list.innerHTML = '';

        files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <h4>${file.file_name}</h4>
                <p>${file.file_path}</p>
                <small>Dil: ${file.language}</small>
            `;
            list.appendChild(item);
        });
    } catch (error) {
        console.error('Dosyalar yükleme hatası:', error);
    }
}



// ============================================
// SECTION: Settings
// ============================================

async function loadSettings() {
    try {
        const apiUrlInput = document.getElementById('apiUrl');
        let userApiUrl = '';

        // Load per-user settings first (includes ai_api_url)
        const userSettingsResp = await fetch(`${API_URL}/users/settings`);
        if (userSettingsResp.ok) {
            const userSettings = await userSettingsResp.json();
            userApiUrl = (userSettings.ai_api_url || '').trim();
            if (apiUrlInput && userApiUrl) {
                apiUrlInput.value = userApiUrl;
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
        console.log('Saving settings:', settings);

        // Save per-user AI server URL
        const userSettingsResponse = await fetch(`${API_URL}/users/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ai_api_url: apiUrlValue })
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

        showSuccess('Başarılı', 'Ayarlar kaydedildi ve sisteme uygulandı');
    } catch (error) {
        console.error('Ayarlar Kaydetme Hatası:', error);
        showError('Ayarlar Kaydetme Hatası', 'Ayarlar kaydedilirken hata oluştu: ' + error.message);
    }
}

async function testLMConnection() {
    try {
        const response = await fetch(`${API_URL}/ai-settings/lmstudio/test`, {
            method: 'POST'
        });
        const result = await response.json();

        const resultDiv = document.getElementById('connectionResult');
        if (result.status === 'connected') {
            resultDiv.textContent = '✓ Bağlantı başarılı!';
            resultDiv.className = 'success';
        } else {
            resultDiv.textContent = '✗ Bağlantı başarısız: ' + result.message;
            resultDiv.className = 'error';
        }
    } catch (error) {
        document.getElementById('connectionResult').textContent = 'Hata: ' + error;
        document.getElementById('connectionResult').className = 'error';
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
