// ============================================
// SECTION: Admin Panel Functions
// ============================================

function showAdminPanel() {
    if (currentUser && currentUser.role === 'admin') {
        goToSection('adminPanel');
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
        goToSection('permissionsPanel');
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

// ============================================
// SECTION: User Settings Functions
// ============================================

function showSettings() {
    goToSection('settingsSection');
    loadUserSettings();
}

function loadUserSettings() {
    fetch(`${API_URL}/users/settings`)
        .then(response => response.json())
        .then(settings => {
            document.getElementById('apiUrl').value = settings.api_url || '';
            document.getElementById('temperature').value = settings.temperature || 0.7;
            document.getElementById('temperatureValue').textContent = settings.temperature || 0.7;
            document.getElementById('topP').value = settings.top_p || 0.9;
            document.getElementById('topPValue').textContent = settings.top_p || 0.9;
            document.getElementById('maxTokens').value = settings.max_tokens || 1000;
        })
        .catch(err => console.error('Ayarlar yüklenirken hata:', err));
}

function updateUserSettings() {
    const settings = {
        theme: 'light',
        notifications_enabled: true,
        items_per_page: 20
    };
    
    fetch(`${API_URL}/users/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        showSuccess('Başarılı', 'Ayarlar kaydedildi');
    })
    .catch(err => showError('Hata', `Hata: ${err}`));
}
