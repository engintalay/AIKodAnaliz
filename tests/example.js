// JavaScript örneği
function getUserData(userId) {
    /**
     * API'den kullanıcı verilerini alır
     */
    return fetch(`/api/users/${userId}`)
        .then(response => response.json())
        .catch(error => console.error('Hata:', error));
}

function processUserData(data) {
    /**
     * Kullanıcı verilerini işler
     */
    const user = {
        id: data.id,
        name: data.name.toUpperCase(),
        email: data.email,
        isActive: data.status === 'active'
    };
    
    return user;
}

async function initialize() {
    /**
     * Uygulamayı başlatır (entry point)
     */
    try {
        const user = await getUserData(1);
        const processed = processUserData(user);
        console.log('Kullanıcı işlenmiş:', processed);
    } catch (error) {
        console.error('Başlatma hatası:', error);
    }
}

// Çalıştır
document.addEventListener('DOMContentLoaded', initialize);
