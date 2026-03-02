const API_URL = 'http://localhost:5000/api';
let currentProjectId = null;
let cy = null;

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
        alert('Projeler yüklenirken hata: ' + error);
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
        alert('Proje açılırken hata: ' + error);
    }
}

async function deleteProject(projectId) {
    if (!confirm('Bu projeyi silmek istediğinizden emin misiniz?')) return;
    
    try {
        await fetch(`${API_URL}/projects/${projectId}`, { method: 'DELETE' });
        alert('Proje silindi');
        loadProjects();
    } catch (error) {
        alert('Proje silinirken hata: ' + error);
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

document.getElementById('uploadForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('projectName').value;
    const desc = document.getElementById('projectDesc').value;
    const file = document.getElementById('projectFile').files[0];
    
    if (!file) {
        alert('Lütfen bir dosya seçin');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    formData.append('description', desc);
    
    try {
        document.getElementById('uploadProgress').style.display = 'block';
        
        const response = await fetch(`${API_URL}/projects/upload`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert(`Proje başarıyla yüklendi!\n${result.files_processed} dosya işlendi`);
            
            // Analyze project
            const analysisResponse = await fetch(`${API_URL}/analysis/project/${result.project_id}`, {
                method: 'POST'
            });
            const analysisResult = await analysisResponse.json();
            alert(`Analiz tamamlandı: ${analysisResult.functions_found} fonksiyon bulundu`);
            
            document.getElementById('uploadForm').reset();
            loadProjects();
        } else {
            alert('Hata: ' + result.error);
        }
    } catch (error) {
        alert('Yükleme hatası: ' + error);
    } finally {
        document.getElementById('uploadProgress').style.display = 'none';
    }
});

// ============================================
// SECTION: Diagram
// ============================================

async function loadDiagramData() {
    try {
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
        cy.on('tap', 'node', function(evt) {
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
        alert('PNG dışa aktarımı hatayla sonuçlandı');
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
        
        functions.forEach(func => {
            const item = document.createElement('div');
            item.className = 'function-item';
            item.innerHTML = `
                <h4>${func.function_name} <small>(${func.function_type})</small></h4>
                <p>${func.ai_summary || 'Özet henüz oluşturulmadı'}</p>
                <div class="function-meta">
                    Satırlar: ${func.start_line}-${func.end_line}
                </div>
            `;
            item.onclick = () => showFunctionDetails(func.id);
            list.appendChild(item);
        });
    } catch (error) {
        console.error('Fonksiyonlar yükleme hatası:', error);
    }
}

async function showFunctionDetails(functionId) {
    try {
        const response = await fetch(`${API_URL}/analysis/function/${functionId}`);
        const func = await response.json();
        
        const modal = document.getElementById('functionModal');
        document.getElementById('funcModalTitle').textContent = func.function_name;
        document.getElementById('funcModalContent').innerHTML = `
            <p><strong>Tür:</strong> ${func.function_type}</p>
            <p><strong>Parametreler:</strong> ${func.parameters || 'Yok'}</p>
            <p><strong>Dönüş Tipi:</strong> ${func.return_type || 'Yok'}</p>
            <p><strong>Özet:</strong> ${func.ai_summary || 'Henüz analiz edilmedi'}</p>
        `;
        
        modal.classList.add('visible');
    } catch (error) {
        console.error('Fonksiyon detayları yükleme hatası:', error);
    }
}

function closeFunctionModal() {
    document.getElementById('functionModal').classList.remove('visible');
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
        alert('İşaret eklendi');
        loadMarks();
    } catch (error) {
        alert('İşaret eklenirken hata: ' + error);
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

function viewSource() {
    alert('Kaynak kodu görüntüleme işlemi gelecek sürümlerde eklenecek');
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
        alert('Ayarlar kaydedildi');
    } catch (error) {
        alert('Ayarlar kaydedilirken hata: ' + error);
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
// SECTION: Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    loadProjects();
});

// Logout
function logout() {
    if (confirm('Çıkış yapmak istediğinizden emin misiniz?')) {
        window.location.href = '/';
    }
}
