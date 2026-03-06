// ============================================
// SECTION: Report Functions
// ============================================

function loadReport() {
    fetch(`${API_URL}/report`)
        .then(response => response.json())
        .then(data => {
            renderReport(data);
        })
        .catch(err => showError('Hata', `Rapor yüklenirken hata: ${err}`));
}

function toggleFileDetails(button, fileName) {
    const detailsDiv = document.querySelector(`.file-details-${fileName}`);
    if (detailsDiv) {
        const isHidden = detailsDiv.style.display === 'none';
        detailsDiv.style.display = isHidden ? 'block' : 'none';
        button.textContent = isHidden ? '📋 Gizle' : '📋 Detaylar';
    }
}

function analyzeMissingFunctions(projectId, fileName, fileId) {
    if (confirm(`"${fileName}" dosyasındaki tüm eksik özetler oluşturulacak. Devam etmek istiyor musunuz?`)) {
        showSuccess('Bilgi', `"${fileName}" dosyasının analizi başlatıldı...`);
        // Get all functions in this file that don't have summaries
        fetch(`${API_URL}/analysis/file/${fileId}?missing_only=true`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showSuccess('Başarılı', `Dosya analizi tamamlandı`);
                setTimeout(() => loadReport(), 1000);
            } else {
                showError('Hata', data.error || 'Analiz yapılamadı');
            }
        })
        .catch(err => showError('Hata', `Analiz sırasında hata: ${err}`));
    }
}

function analyzeSingleFunction(functionId) {
    // Generate AI summary for single function
    const taskId = `task-${Date.now()}`;
    fetch(`${API_URL}/analysis/function/${functionId}/ai-summary?task_id=${taskId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.summary) {
            showSuccess('Başarılı', `Fonksiyon özeti oluşturuldu`);
            setTimeout(() => loadReport(), 500);
        } else if (data.error) {
            showError('Hata', data.error);
        } else {
            showError('Hata', 'Özet oluşturulamadı');
        }
    })
    .catch(err => showError('Hata', `AI özeti alırken hata: ${err}`));
}

function renderReport(reportData) {
    const container = document.getElementById('reportContainer');
    
    const stats = reportData.statistics;
    let html = `
        <div style="background: white; padding: 20px; border-radius: 4px; margin-bottom: 20px;">
            <h3>📊 Genel İstatistikler</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div style="background: #f0f8ff; padding: 15px; border-radius: 4px;">
                    <div style="font-size: 24px; font-weight: bold; color: #3498db;">${stats.total}</div>
                    <div style="color: #7f8c8d; font-size: 14px;">Toplam Fonksiyon</div>
                </div>
                <div style="background: #f0fff4; padding: 15px; border-radius: 4px;">
                    <div style="font-size: 24px; font-weight: bold; color: #27ae60;">${stats.with_summary}</div>
                    <div style="color: #7f8c8d; font-size: 14px;">✅ Özetlenmiş</div>
                </div>
                <div style="background: #fff5f5; padding: 15px; border-radius: 4px;">
                    <div style="font-size: 24px; font-weight: bold; color: #e74c3c;">${stats.without_summary}</div>
                    <div style="color: #7f8c8d; font-size: 14px;">❌ Özetlenmeyen</div>
                </div>
                <div style="background: #fdf8f0; padding: 15px; border-radius: 4px;">
                    <div style="font-size: 24px; font-weight: bold; color: #f39c12;">${stats.coverage}</div>
                    <div style="color: #7f8c8d; font-size: 14px;">Kapsama Oranı</div>
                </div>
            </div>
        </div>
    `;
    
    // Proje detayları
    if (reportData.projects && reportData.projects.length > 0) {
        html += '<h3>📁 Proje Bazlı Detaylar</h3>';
        
        reportData.projects.forEach(project => {
            const pStats = project.statistics;
            html += `
                <div style="background: white; padding: 15px; margin-bottom: 15px; border-left: 4px solid #3498db; border-radius: 4px;">
                    <h4 style="margin-top: 0;">${project.name}</h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 10px;">
                        <div><strong>Fonksiyonlar:</strong> ${pStats.total}</div>
                        <div><strong>Özetlendi:</strong> ${pStats.with_summary} (${pStats.coverage})</div>
                        <div><strong>Beklemede:</strong> ${pStats.without_summary}</div>
                    </div>
            `;
            
            // Dosya detayları
            if (project.files) {
                html += '<div style="margin-top: 15px;"><strong>Dosyalar:</strong>';
                for (const [fileName, fileData] of Object.entries(project.files)) {
                    const coverage = fileData.total > 0 ? Math.round((fileData.with_summary / fileData.total) * 100) : 0;
                    const isComplete = coverage === 100;
                    const progressColor = coverage === 100 ? '#27ae60' : coverage >= 80 ? '#f39c12' : '#e74c3c';
                    
                    html += `
                        <div style="background: ${isComplete ? '#f0fff4' : '#fff5f5'}; margin-top: 10px; padding: 10px; border-radius: 4px; border-left: 3px solid ${progressColor};">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="flex: 1;">
                                    <strong>${fileName}</strong>
                                    <div style="font-size: 14px; color: #7f8c8d; margin-top: 5px;">
                                        İlerleme: <strong style="color: ${progressColor};">${coverage}%</strong> (${fileData.with_summary}/${fileData.total})
                                    </div>
                                    <div style="width: 200px; height: 8px; background: #e0e0e0; border-radius: 4px; margin-top: 5px; overflow: hidden;">
                                        <div style="width: ${coverage}%; height: 100%; background: ${progressColor};"></div>
                                    </div>
                                </div>
                                <div style="margin-left: 10px; display: flex; gap: 5px;">
                                    ${coverage < 100 ? `
                                        <button class="btn btn-sm" onclick="analyzeMissingFunctions(${project.id}, '${fileName}', ${fileData.file_id})" 
                                                style="padding: 6px 12px; background: #3498db; color: white; border: none; border-radius: 3px; cursor: pointer;">
                                            🤖 Analiz Et (${fileData.missing_functions ? fileData.missing_functions.length : 0})
                                        </button>
                                    ` : `
                                        <span style="color: #27ae60; font-weight: bold;">✅ Tamamlandı</span>
                                    `}
                                    <button class="btn btn-sm" onclick="toggleFileDetails(this, '${fileName}')" 
                                            style="padding: 6px 12px; background: #95a5a6; color: white; border: none; border-radius: 3px; cursor: pointer;">
                                        📋 Detaylar
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Dosya detayları (gizli) -->
                            <div class="file-details-${fileName}" style="display: none; margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd;">
                                <strong>Eksik Özetler:</strong>
                                ${fileData.missing_functions && fileData.missing_functions.length > 0 ? `
                                    <ul style="margin: 5px 0 0 20px; font-size: 13px;">
                                        ${fileData.missing_functions.map(f => `
                                            <li style="margin: 5px 0;">
                                                <span style="color: #e74c3c;">❌</span> 
                                                <strong>${f.qualified_name}</strong> (${f.type})
                                                <button onclick="analyzeSingleFunction(${f.function_id})" 
                                                        style="margin-left: 10px; padding: 2px 6px; background: #3498db; color: white; border: none; border-radius: 2px; cursor: pointer; font-size: 11px;">
                                                    🤖 Analiz
                                                </button>
                                            </li>
                                        `).join('')}
                                    </ul>
                                ` : `
                                    <p style="margin-top: 5px; color: #27ae60; font-size: 13px;">✅ Tüm fonksiyonlar özetlenmiş</p>
                                `}
                            </div>
                        </div>
                    `;
                }
                html += '</div>';
            }
            
            html += '</div>';
        });
    }
    
    container.innerHTML = html;
}

// ============================================
// SECTION: Admin Panel Functions
// ============================================

function showAdminPanel() {
    if (currentUser && currentUser.role === 'admin') {
        showSection('adminPanel');
        loadAllUsers();
    } else {
        showError('Erişim Hatası', 'Sadece admin kullanıcılar erişebilir');
    }
}

function switchAdminTab(tabName) {
    // Hide all tabs
    document.getElementById('usersTab').style.display = 'none';
    document.getElementById('rolesTab').style.display = 'none';
    
    // Show selected tab
    document.getElementById(tabName + 'Tab').style.display = 'block';
    
    // Update button styles
    document.querySelectorAll('.tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
}

function loadAllUsers() {
    fetch(`${API_URL}/users/admin/all`)
        .then(response => response.json())
        .then(data => {
            if (Array.isArray(data)) {
                renderUsersList(data);
            } else {
                showError('Hata', 'Kullanıcı listesi alınamadı');
            }
        })
        .catch(err => showError('Hata', `Kullanıcılar yüklenirken hata: ${err}`));
}

function renderUsersList(users) {
    const container = document.getElementById('usersList');
    
    if (users.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999;">Kullanıcı bulunamadı</p>';
        return;
    }
    
    let html = '<table style="width:100%; border-collapse: collapse;">';
    html += '<tr style="background: #f5f5f5; border-bottom: 2px solid #ccc;">';
    html += '<th style="padding: 10px; text-align: left;">Kullanıcı Adı</th>';
    html += '<th style="padding: 10px; text-align: left;">Ad Soyad</th>';
    html += '<th style="padding: 10px; text-align: left;">Email</th>';
    html += '<th style="padding: 10px; text-align: left;">Rol</th>';
    html += '<th style="padding: 10px; text-align: left;">Durum</th>';
    html += '<th style="padding: 10px; text-align: center;">İşlemler</th>';
    html += '</tr>';
    
    users.forEach(user => {
        const roleBadge = {
            'admin': '👑 Admin',
            'developer': '👨‍💻 Geliştirici',
            'analyzer': '🔍 Analizci'
        }[user.role] || user.role;
        
        const statusBadge = user.is_active ? '✅ Aktif' : '❌ Pasif';
        
        html += '<tr style="border-bottom: 1px solid #eee;">';
        html += `<td style="padding: 10px;">${user.username}</td>`;
        html += `<td style="padding: 10px;">${user.full_name || '-'}</td>`;
        html += `<td style="padding: 10px;">${user.email || '-'}</td>`;
        html += `<td style="padding: 10px;">${roleBadge}</td>`;
        html += `<td style="padding: 10px;">${statusBadge}</td>`;
        html += `<td style="padding: 10px; text-align: center;">`;
        html += `<button class="btn btn-sm" onclick="editUser(${user.id})" style="padding: 5px 10px; margin: 0 2px;">✏️ Düzenle</button>`;
        html += `<button class="btn btn-sm" onclick="deleteUser(${user.id})" style="padding: 5px 10px; margin: 0 2px; background: #e74c3c;">🗑️ Sil</button>`;
        html += '</td>';
        html += '</tr>';
    });
    
    html += '</table>';
    container.innerHTML = html;
}

function showCreateUserForm() {
    document.getElementById('createUserForm').style.display = 'block';
}

function hideCreateUserForm() {
    document.getElementById('createUserForm').style.display = 'none';
    document.getElementById('newUsername').value = '';
    document.getElementById('newPassword').value = '';
    document.getElementById('newUserFullName').value = '';
    document.getElementById('newUserEmail').value = '';
}

function createNewUser() {
    const username = document.getElementById('newUsername').value;
    const password = document.getElementById('newPassword').value;
    const role = document.getElementById('newUserRole').value;
    const fullName = document.getElementById('newUserFullName').value;
    const email = document.getElementById('newUserEmail').value;
    
    if (!username || !password) {
        showError('Hata', 'Kullanıcı adı ve şifre gerekli');
        return;
    }
    
    fetch(`${API_URL}/users/admin/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, role, full_name: fullName, email })
    })
    .then(response => response.json())
    .then(data => {
        if (data.user_id) {
            showSuccess('Başarılı', 'Kullanıcı oluşturuldu');
            hideCreateUserForm();
            loadAllUsers();
        } else {
            showError('Hata', data.error || 'Kullanıcı oluşturulamadı');
        }
    })
    .catch(err => showError('Hata', `Hata: ${err}`));
}

function editUser(userId) {
    // TODO: Implement user edit modal
    showWarning('Bilgi', 'Kullanıcı düzenleme özelligi yakında eklenecek');
}

function deleteUser(userId) {
    if (confirm('Bu kullanıcıyı silmek istediğinizden emin misiniz?')) {
        fetch(`${API_URL}/users/admin/${userId}/delete`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                showSuccess('Başarılı', 'Kullanıcı silindi');
                loadAllUsers();
            } else {
                showError('Hata', data.error || 'Kullanıcı silinemedi');
            }
        })
        .catch(err => showError('Hata', `Hata: ${err}`));
    }
}

// ============================================
// SECTION: Permissions Panel Functions
// ============================================

function showPermissionsPanel() {
    if (currentUser && (currentUser.role === 'admin' || currentUser.role === 'developer')) {
        showSection('permissionsPanel');
        loadProjectsForPermissions();
    } else {
        showError('Erişim Hatası', 'Sadece admin ve geliştirici erişebilir');
    }
}

function loadProjectsForPermissions() {
    fetch(`${API_URL}/projects`)
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('projectSelectForPermissions');
            select.innerHTML = '<option value="">Proje seçin...</option>';
            
            if (Array.isArray(data)) {
                data.forEach(proj => {
                    const option = document.createElement('option');
                    option.value = proj.id;
                    option.textContent = proj.name;
                    select.appendChild(option);
                });
            }
        })
        .catch(err => console.error('Projeler yüklenirken hata:', err));
}

function loadProjectPermissions() {
    const projectId = document.getElementById('projectSelectForPermissions').value;
    if (!projectId) {
        document.getElementById('permissionsContent').style.display = 'none';
        return;
    }
    
    // Load project users
    fetch(`${API_URL}/users/projects/${projectId}/permissions`)
        .then(response => response.json())
        .then(users => {
            renderProjectUsers(users);
        })
        .catch(err => showError('Hata', `Kullanıcılar yüklenirken hata: ${err}`));
    
    // Load available users
    fetch(`${API_URL}/users/admin/all`)
        .then(response => response.json())
        .then(allUsers => {
            const currentUsers = new Set();
            const userSelect = document.getElementById('userSelectForPermission');
            
            // Get currently assigned users
            fetch(`${API_URL}/users/projects/${projectId}/permissions`)
                .then(r => r.json())
                .then(assigned => {
                    assigned.forEach(u => currentUsers.add(u.id));
                    
                    userSelect.innerHTML = '<option value="">Kullanıcı seçin...</option>';
                    allUsers.forEach(user => {
                        if (!currentUsers.has(user.id)) {
                            const option = document.createElement('option');
                            option.value = user.id;
                            option.textContent = `${user.username} (${user.role})`;
                            userSelect.appendChild(option);
                        }
                    });
                });
        })
        .catch(err => console.error('Hata:', err));
    
    document.getElementById('permissionsContent').style.display = 'block';
}

function renderProjectUsers(users) {
    const container = document.getElementById('projectUsersList');
    
    if (users.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999;">Bu projeye erişim hakkı olan kimse yok</p>';
        return;
    }
    
    let html = '<table style="width:100%; border-collapse: collapse;">';
    
    users.forEach(user => {
        const ownerBadge = user.is_owner ? '👤 Sahip' : '📤 Paylaşım';
        const accessBadge = user.read_only ? '🔒 Salt Okuma' : '✏️ Tam Erişim';
        
        html += '<tr style="border-bottom: 1px solid #eee; padding: 10px;">';
        html += `<td style="padding: 10px; width: 20%;">${user.username}</td>`;
        html += `<td style="padding: 10px; width: 20%;">${user.role}</td>`;
        html += `<td style="padding: 10px; width: 30%;">${ownerBadge}</td>`;
        html += `<td style="padding: 10px; width: 30%;">${accessBadge}</td>`;
        
        if (!user.is_owner) {
            html += `<td style="padding: 10px;"><button class="btn btn-sm" onclick="revokePermission(${user.id})" style="padding: 5px 10px; background: #e74c3c;">🗑️ Kaldır</button></td>`;
        } else {
            html += '<td></td>';
        }
        html += '</tr>';
    });
    
    html += '</table>';
    container.innerHTML = html;
}

function grantPermission() {
    const projectId = document.getElementById('projectSelectForPermissions').value;
    const userId = document.getElementById('userSelectForPermission').value;
    const readOnly = document.getElementById('readOnlyToggle').checked;
    
    if (!projectId || !userId) {
        showError('Hata', 'Proje ve kullanıcı seçin');
        return;
    }
    
    fetch(`${API_URL}/users/projects/${projectId}/permissions/grant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: parseInt(userId),
            permission_level: 'read',
            read_only: readOnly
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            showSuccess('Başarılı', 'İzin verildi');
            loadProjectPermissions();
        } else {
            showError('Hata', data.error || 'İzin verilemedi');
        }
    })
    .catch(err => showError('Hata', `Hata: ${err}`));
}

function revokePermission(userId) {
    const projectId = document.getElementById('projectSelectForPermissions').value;
    
    if (confirm('Bu kullanıcının proje erişimini kaldırmak istediğinizden emin misiniz?')) {
        fetch(`${API_URL}/users/projects/${projectId}/permissions/revoke`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                showSuccess('Başarılı', 'İzin kaldırıldı');
                loadProjectPermissions();
            } else {
                showError('Hata', data.error || 'İzin kaldırılamadı');
            }
        })
        .catch(err => showError('Hata', `Hata: ${err}`));
    }
}


