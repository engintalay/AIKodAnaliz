// API URL: Use current hostname/port dynamically, but override /api path on root
const API_URL = `${window.location.protocol}//${window.location.host}/api`;
let currentProjectId = null;
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
    document.querySelectorAll('.tab-content').forEach(tab => tab.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

    document.getElementById(tabName + 'Tab').style.display = 'block';
    event.target.classList.add('active');
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
            card.innerHTML = `
                <h3>${project.name}</h3>
                <p>${project.description || 'Açıklama yok'}</p>
                <small>Yüklenme: ${new Date(project.upload_date).toLocaleDateString('tr-TR')}</small>
                <div class="project-card-actions">
                    <button onclick="viewProject(${project.id})" class="btn btn-primary">Aç</button>
                    <button onclick="deleteProject(${project.id})" class="btn btn-secondary">Sil</button>
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

    try {
        const response = await fetch(`${API_URL}/projects/${projectId}`);
        const project = await response.json();

        document.getElementById('projectTitle').textContent = project.name;
        showSection('projectDetailSection');

        // Load diagram
        await loadDiagramData();

        // Load functions
        await loadFunctions();

        // Load marks
        await loadMarks();

        // Load files
        await loadFiles();
    } catch (error) {
        showError('Proje Açma Hatası', 'Proje açılırken hata oluştu: ' + error);
    }
}

async function deleteProject(projectId) {
    if (!confirm('Bu projeyi silmek istediğinizden emin misiniz?')) return;

    try {
        await fetch(`${API_URL}/projects/${projectId}`, { method: 'DELETE' });
        showSuccess('Başarılı', 'Proje silindi');
        loadProjects();
    } catch (error) {
        showError('Silme Hatası', 'Proje silinirken hata oluştu: ' + error);
    }
}

function showUpload() {
    showSection('uploadSection');
}

function showSettings() {
    showSection('settingsSection');
    loadSettings();
}

// ============================================
// SECTION: Upload & Analysis
// ============================================

let uploadPolling = null;
let analysisPolling = null;

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
    
    // Poll every 500ms
    uploadPolling = setInterval(poll, 500);
    poll(); // Initial call
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

    analysisPolling = setInterval(poll, 500);
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
                    classes: node.type
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
        const response = await fetch(`${API_URL}/analysis/project/${currentProjectId}/functions`);
        const functions = await response.json();

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
            pkgHeader.innerHTML = `<span>📦 ${pkgName}</span> <span>▼</span>`;

            const pkgContent = document.createElement('div');
            pkgContent.className = 'package-content';

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
                clsHeader.innerHTML = `<span style="margin-right: 5px;">▼</span> 🏷️ ${clsName}`;

                const clsContent = document.createElement('div');
                clsContent.className = 'class-content';

                clsHeader.onclick = () => {
                    const isHidden = clsContent.style.display === 'none';
                    clsContent.style.display = isHidden ? 'block' : 'none';
                    clsHeader.innerHTML = `<span style="margin-right: 5px;">${isHidden ? '▼' : '▶'}</span> 🏷️ ${clsName}`;
                };

                clsDiv.appendChild(clsHeader);
                clsDiv.appendChild(clsContent);

                funcs.forEach(func => {
                    const called = Array.isArray(func.called_functions) ? func.called_functions : [];
                    const calledBy = Array.isArray(func.called_by_functions) ? func.called_by_functions : [];

                    const calledHtml = called.length > 0
                        ? called.map(c => `<span class="dep-chip">${c.function_name}</span>`).join(' ')
                        : '<span class="dep-empty">Yok</span>';

                    const calledByHtml = calledBy.length > 0
                        ? calledBy.map(c => `<span class="dep-chip dep-chip-caller">${c.function_name}</span>`).join(' ')
                        : '<span class="dep-empty">Yok</span>';

                    const item = document.createElement('div');
                    item.className = 'function-item searchable-item';
                    item.dataset.search = `${func.function_name} ${func.ai_summary || ''}`.toLowerCase();
                    item.innerHTML = `
                        <h5>${func.function_name} <small>(${func.function_type})</small></h5>
                        <p>${func.ai_summary || 'Özet henüz oluşturulmadı'}</p>
                        <div class="function-meta">
                            Satırlar: ${func.start_line}-${func.end_line}
                            <br/><small>Dosya: ${func.file_path || 'Bilinmiyor'}</small>
                            <div class="function-deps">
                                <div><strong>Çağırdığı Fonksiyonlar:</strong> ${calledHtml}</div>
                                <div><strong>Bunu Çağıran Fonksiyonlar:</strong> ${calledByHtml}</div>
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
    try {
        currentModalFunctionId = functionId;
        const response = await fetch(`${API_URL}/analysis/function/${functionId}`);
        let func = await response.json();

        const modal = document.getElementById('functionModal');
        document.getElementById('funcModalTitle').textContent = func.function_name;

        // Meta info display
        document.getElementById('funcModalContent').innerHTML = `
            <p><strong>Tür:</strong> ${func.function_type}</p>
            <p><strong>Parametreler:</strong> ${Array.isArray(func.parameters) ? func.parameters.join(', ') : (func.parameters || 'Yok')}</p>
            <p><strong>Dönüş Tipi:</strong> ${func.return_type || 'Yok'}</p>
        `;

        // Update Text Areas
        document.getElementById('funcModalSummary').value = func.ai_summary || '';
        document.getElementById('funcModalSource').textContent = func.source_code || 'Kaynak kod yok.';

        modal.classList.add('visible');
    } catch (error) {
        console.error('Fonksiyon detayları yükleme hatası:', error);
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
    summaryArea.value = "AI Yükleniyor... Lütfen bekleyin...";
    summaryArea.disabled = true;

    try {
        const aiResponse = await fetch(`${API_URL}/analysis/function/${currentModalFunctionId}/ai-summary`, {
            method: 'POST'
        });
        const aiResult = await aiResponse.json();

        if (aiResponse.ok) {
            summaryArea.value = aiResult.summary;
            loadFunctions(); // optionally refresh list in background
        } else {
            summaryArea.value = oldText;
            showError('AI Analiz Hatası', 'AI analiz hatası: ' + aiResult.error);
        }
    } catch (error) {
        summaryArea.value = oldText;
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
}

function toggleFullscreenModal() {
    const modal = document.getElementById('functionModal');
    const content = modal.querySelector('.modal-content');
    const btn = document.getElementById('fullscreenBtn');
    
    content.classList.toggle('fullscreen');
    btn.textContent = content.classList.contains('fullscreen') ? '✕' : '⛶';
    btn.title = content.classList.contains('fullscreen') ? 'Normal Görünüm (F11)' : 'Tam Ekran (F11)';
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
        const response = await fetch(`${API_URL}/ai-settings`);
        const settings = await response.json();

        // TODO: Load settings into form
    } catch (error) {
        console.error('Ayarlar yükleme hatası:', error);
    }
}

async function saveLMSettings() {
    const settings = {
        temperature: document.getElementById('temperature').value,
        top_p: document.getElementById('topP').value,
        max_tokens: document.getElementById('maxTokens').value
    };

    try {
        for (const [key, value] of Object.entries(settings)) {
            await fetch(`${API_URL}/ai-settings/${key}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    value: value,
                    type: typeof value
                })
            });
        }
        showSuccess('Başarılı', 'Ayarlar kaydedildi');
    } catch (error) {
        showError('Ayarlar Kaydetme Hatası', 'Ayarlar kaydedilirken hata oluştu: ' + error);
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

// ============================================
// SECTION: Event Listeners
// ============================================

document.getElementById('temperature')?.addEventListener('input', (e) => {
    document.getElementById('tempValue').textContent = e.target.value;
});

document.getElementById('topP')?.addEventListener('input', (e) => {
    document.getElementById('topPValue').textContent = e.target.value;
});

// ============================================
// SECTION: Authentication
// ============================================

let currentUser = null;

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
        document.getElementById('userInfo').textContent = `👤 ${currentUser.username}`;
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

    const username = document.getElementById('loginUsername').value;
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
            errorDiv.textContent = data.error || 'Giriş başarısız';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Hata: ' + error;
        errorDiv.style.display = 'block';
    }
}

function logout() {
    localStorage.removeItem('currentUser');
    currentUser = null;
    checkSession();
}

// ============================================
// SECTION: Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Setup login form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    // Check session on page load
    if (checkSession()) {
        loadProjects();
    }
});
