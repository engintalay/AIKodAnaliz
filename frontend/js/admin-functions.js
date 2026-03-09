// ============================================
// SECTION: Report Functions
// ============================================

const analysisJobs = new Map();
let latestReportData = null;
const bulkAnalysisState = {
    active: 0,
    maxConcurrent: 2,
    pending: [],
    running: false,
    total: 0,
    succeeded: 0,
    failed: 0,
};

function formatEta(seconds) {
    if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '-';
    const s = Math.max(0, parseInt(seconds, 10));
    if (s < 60) return `${s} sn`;
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m} dk ${r} sn`;
}

function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '-';
    const value = Number(seconds);
    if (value < 60) return `${value.toFixed(1)} sn`;
    const minutes = Math.floor(value / 60);
    const remaining = Math.round(value % 60);
    return `${minutes} dk ${remaining} sn`;
}

function renderAnalysisMonitor() {
    const monitor = document.getElementById('analysisMonitor');
    const list = document.getElementById('analysisTaskList');
    const stats = document.getElementById('analysisGlobalStats');
    if (!monitor || !list || !stats) return;

    const jobs = Array.from(analysisJobs.values());
    if (jobs.length === 0) {
        monitor.style.display = 'none';
        list.innerHTML = '';
        stats.textContent = '';
        return;
    }

    monitor.style.display = 'block';

    let totalFunctions = 0;
    let completedFunctions = 0;
    let remainingFunctions = 0;
    let etaTotal = 0;
    let etaCount = 0;
    let aiTotalTokens = 0;
    let aiTotalDuration = 0;
    let aiTotalCalls = 0;

    jobs.forEach(job => {
        const m = job.metrics || {};
        totalFunctions += m.total_functions || 0;
        completedFunctions += m.completed_functions || 0;
        remainingFunctions += m.remaining_functions || 0;
        aiTotalTokens += m.ai_total_tokens || 0;
        aiTotalDuration += m.ai_total_duration_seconds || 0;
        aiTotalCalls += m.ai_calls || 0;
        if (typeof m.estimated_remaining_seconds === 'number' && job.status === 'started') {
            etaTotal += m.estimated_remaining_seconds;
            etaCount += 1;
        }
    });

    const combinedEta = etaCount > 0 ? Math.round(etaTotal / etaCount) : null;
    stats.innerHTML = `
        <strong>Aktif İş:</strong> ${jobs.filter(j => j.status === 'started').length} |
        <strong>Toplam Fonksiyon:</strong> ${totalFunctions} |
        <strong>Biten:</strong> ${completedFunctions} |
        <strong>Kalan:</strong> ${remainingFunctions} |
        <strong>Tahmini Süre:</strong> ${formatEta(combinedEta)} |
        <strong>AI Cagri:</strong> ${aiTotalCalls} |
        <strong>Toplam Token:</strong> ${aiTotalTokens} |
        <strong>Toplam AI Suresi:</strong> ${formatDuration(aiTotalDuration)}
    `;

    list.innerHTML = jobs.map(job => {
        const m = job.metrics || {};
        const progress = job.progress || 0;
        const color = job.status === 'completed' ? '#27ae60' : job.status === 'failed' ? '#e74c3c' : '#3498db';
        const threadName = m.active_thread || '-';
        return `
            <div style="background:white; border:1px solid #e4ecf5; border-left:4px solid ${color}; border-radius:4px; padding:8px; margin-bottom:8px;">
                <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap;">
                    <div><strong>${job.label}</strong> <span style="color:#7f8c8d; font-size:12px;">(${job.taskId})</span></div>
                    <div style="font-size:12px; color:${color}; font-weight:bold;">${job.status.toUpperCase()} - ${progress}%</div>
                </div>
                <div style="height:8px; background:#ecf0f1; border-radius:4px; overflow:hidden; margin:6px 0;">
                    <div style="width:${progress}%; height:100%; background:${color};"></div>
                </div>
                <div style="font-size:12px; color:#2c3e50;">
                    Thread: <strong>${threadName}</strong> |
                    Başlayan: <strong>${m.total_functions || 0}</strong> |
                    Biten: <strong>${m.completed_functions || 0}</strong> |
                    Kalan: <strong>${m.remaining_functions || 0}</strong> |
                    ETA: <strong>${formatEta(m.estimated_remaining_seconds)}</strong> |
                    Token: <strong>${m.ai_total_tokens || 0}</strong> |
                    AI Süre: <strong>${formatDuration(m.ai_total_duration_seconds || 0)}</strong>
                </div>
                <div style="font-size:12px; color:#2c3e50; margin-top:3px;">
                    Prompt: <strong>${m.ai_prompt_tokens || 0}</strong> |
                    Completion: <strong>${m.ai_completion_tokens || 0}</strong> |
                    Çağrı: <strong>${m.ai_calls || 0}</strong> |
                    Ort. Çağrı Süresi: <strong>${formatDuration(m.ai_avg_duration_seconds || 0)}</strong>
                </div>
                <div style="font-size:12px; color:#555; margin-top:4px;">${job.current_step || '-'}</div>
            </div>
        `;
    }).join('');
}

function removeAnalysisJob(taskId) {
    const job = analysisJobs.get(taskId);
    if (job && job.pollTimer) {
        clearInterval(job.pollTimer);
    }
    analysisJobs.delete(taskId);
    renderAnalysisMonitor();
}

function pollAnalysisTask(taskId) {
    const job = analysisJobs.get(taskId);
    if (!job) return;

    const tick = async () => {
        try {
            const response = await fetch(`${API_URL}/projects/progress/${taskId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    job.notFoundCount = (job.notFoundCount || 0) + 1;
                    const ageMs = Date.now() - (job.createdAt || Date.now());

                    // A short initial 404 window is tolerated while backend task is being created.
                    if (ageMs < 10000 && job.notFoundCount < 8) {
                        return;
                    }

                    job.status = 'failed';
                    job.current_step = 'İlerleme görevi bulunamadı (task timeout/yeniden başlatma).';
                    renderAnalysisMonitor();
                    clearInterval(job.pollTimer);
                    job.pollTimer = null;
                    setTimeout(() => removeAnalysisJob(taskId), 15000);
                    return;
                }
                throw new Error(`Progress endpoint error: ${response.status}`);
            }

            const progress = await response.json();
            job.notFoundCount = 0;
            job.progress = progress.progress || 0;
            job.status = progress.status || 'started';
            job.current_step = progress.current_step || '';
            job.metrics = progress.metrics || {};
            renderAnalysisMonitor();

            if (job.status === 'completed' || job.status === 'failed') {
                clearInterval(job.pollTimer);
                job.pollTimer = null;
                if (job.status === 'completed') {
                    setTimeout(() => loadReport(), 500);
                }
                setTimeout(() => removeAnalysisJob(taskId), 12000);
            }
        } catch (err) {
            job.errorCount = (job.errorCount || 0) + 1;
            job.current_step = `Polling hatası: ${err}`;

            if (job.errorCount >= 5) {
                job.status = 'failed';
                clearInterval(job.pollTimer);
                job.pollTimer = null;
                setTimeout(() => removeAnalysisJob(taskId), 15000);
            }

            renderAnalysisMonitor();
        }
    };

    tick();
    job.pollTimer = setInterval(tick, 1500);
}

function startTrackedAnalysis(taskId, label, requestPromise) {
    analysisJobs.set(taskId, {
        taskId,
        label,
        status: 'started',
        progress: 0,
        current_step: 'Analiz işi kuyruğa alındı...',
        metrics: {
            total_functions: 0,
            completed_functions: 0,
            remaining_functions: 0,
            active_thread: null,
            estimated_remaining_seconds: null,
            ai_calls: 0,
            ai_prompt_tokens: 0,
            ai_completion_tokens: 0,
            ai_total_tokens: 0,
            ai_total_duration_seconds: 0,
            ai_avg_duration_seconds: 0,
        },
        createdAt: Date.now(),
        notFoundCount: 0,
        errorCount: 0,
        pollTimer: null,
    });
    renderAnalysisMonitor();
    pollAnalysisTask(taskId);

    requestPromise
        .then(async (response) => {
            const data = await response.json().catch(() => ({}));
            const job = analysisJobs.get(taskId);
            if (!job) return;

            if (!response.ok) {
                job.status = 'failed';
                job.current_step = data.error || `Analiz başarısız (${response.status})`;
                renderAnalysisMonitor();
                return;
            }

            if (data.error) {
                job.status = 'failed';
                job.current_step = data.error;
                renderAnalysisMonitor();
                return;
            }

            if (job.status !== 'completed') {
                job.current_step = data.message || 'Analiz tamamlandı';
                renderAnalysisMonitor();
            }
        })
        .catch((err) => {
            const job = analysisJobs.get(taskId);
            if (!job) return;
            job.status = 'failed';
            job.current_step = `İstek hatası: ${err}`;
            renderAnalysisMonitor();
        });
}

function loadReport() {
    Promise.all([
        fetch(`${API_URL}/report`).then(r => r.json()),
        fetch(`${API_URL}/analysis/errors`).then(r => r.json())
    ])
        .then(([reportData, errorData]) => {
            latestReportData = reportData;
            renderReport(reportData, errorData);
        })
        .catch(err => showError('Hata', `Rapor yüklenirken hata: ${err}`));
}

function collectMissingFileTargets(reportData) {
    if (!reportData || !Array.isArray(reportData.projects)) {
        return [];
    }

    const targets = [];
    reportData.projects.forEach(project => {
        const files = project.files || {};
        Object.entries(files).forEach(([fileName, fileData]) => {
            const missingCount = Array.isArray(fileData.missing_functions)
                ? fileData.missing_functions.length
                : 0;

            if (missingCount > 0 && fileData.file_id) {
                targets.push({
                    projectId: project.id,
                    projectName: project.name,
                    fileId: fileData.file_id,
                    fileName,
                    missingCount,
                });
            }
        });
    });

    return targets;
}

function analyzeAllMissingFiles() {
    const reportData = latestReportData;

    if (!reportData) {
        showWarning('Rapor Gerekli', 'Lütfen önce raporu oluşturun.');
        return;
    }

    const targets = collectMissingFileTargets(reportData);
    if (targets.length === 0) {
        showInfo('Bilgi', 'Analiz bekleyen dosya bulunmuyor.');
        return;
    }

    const missingFunctionsTotal = targets.reduce((sum, t) => sum + t.missingCount, 0);
    const message = `${targets.length} dosyada toplam ${missingFunctionsTotal} eksik özet analiz edilecek. Devam edilsin mi?`;
    if (!confirm(message)) {
        return;
    }

    bulkAnalysisState.pending = targets.slice();
    bulkAnalysisState.active = 0;
    bulkAnalysisState.total = targets.length;
    bulkAnalysisState.succeeded = 0;
    bulkAnalysisState.failed = 0;
    bulkAnalysisState.running = true;

    processBulkAnalysisQueue();

    showSuccess(
        'Toplu Analiz Başlatıldı',
        `${targets.length} dosya kuyruğa alındı. Aynı anda en fazla ${bulkAnalysisState.maxConcurrent} analiz çalıştırılacak.`
    );
}

function processBulkAnalysisQueue() {
    if (!bulkAnalysisState.running) {
        return;
    }

    while (
        bulkAnalysisState.active < bulkAnalysisState.maxConcurrent &&
        bulkAnalysisState.pending.length > 0
    ) {
        const target = bulkAnalysisState.pending.shift();
        const taskId = `ai-file-${target.fileId}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
        const requestPromise = fetch(
            `${API_URL}/analysis/file/${target.fileId}?missing_only=true&task_id=${encodeURIComponent(taskId)}`,
            { method: 'POST' }
        );

        bulkAnalysisState.active += 1;

        startTrackedAnalysis(
            taskId,
            `Toplu Dosya Analizi: ${target.projectName} / ${target.fileName}`,
            requestPromise
        );

        requestPromise
            .then((response) => {
                if (response.ok) {
                    bulkAnalysisState.succeeded += 1;
                } else {
                    bulkAnalysisState.failed += 1;
                }
            })
            .catch(() => {
                bulkAnalysisState.failed += 1;
            })
            .finally(() => {
                bulkAnalysisState.active = Math.max(0, bulkAnalysisState.active - 1);

                if (bulkAnalysisState.pending.length === 0 && bulkAnalysisState.active === 0) {
                    bulkAnalysisState.running = false;
                    showInfo(
                        'Toplu Analiz Kuyruğu Tamamlandı',
                        `Toplam: ${bulkAnalysisState.total}, Başarılı: ${bulkAnalysisState.succeeded}, Hatalı: ${bulkAnalysisState.failed}`
                    );
                    return;
                }

                processBulkAnalysisQueue();
            });
    }
}

function clearErrorSummary(functionId) {
    fetch(`${API_URL}/analysis/errors/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ function_ids: [functionId] })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showSuccess('Başarılı', 'Error özeti temizlendi');
                loadReport();
            } else {
                showError('Hata', data.error || 'Temizleme başarısız');
            }
        })
        .catch(err => showError('Hata', `Temizleme sırasında hata: ${err}`));
}

function clearAllErrorSummaries() {
    if (!confirm('Tüm Error: özetleri temizlemek istiyor musunuz?')) return;

    fetch(`${API_URL}/analysis/errors/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showSuccess('Başarılı', `${data.cleared} adet Error özeti temizlendi`);
                loadReport();
            } else {
                showError('Hata', data.error || 'Toplu temizleme başarısız');
            }
        })
        .catch(err => showError('Hata', `Toplu temizleme sırasında hata: ${err}`));
}

function reanalyzeErrorSummary(functionId) {
    const taskId = `ai-error-func-${functionId}-${Date.now()}`;
    startTrackedAnalysis(
        taskId,
        `Error Re-Analyze: #${functionId}`,
        fetch(`${API_URL}/analysis/errors/reanalyze?task_id=${encodeURIComponent(taskId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ function_ids: [functionId] })
        })
    );
}

function reanalyzeAllErrorSummaries() {
    if (!confirm('Tüm Error: özetler tekrar AI analizine sokulacak. Devam edilsin mi?')) return;
    const taskId = `ai-error-all-${Date.now()}`;
    startTrackedAnalysis(
        taskId,
        'Error Re-Analyze: Tümü',
        fetch(`${API_URL}/analysis/errors/reanalyze?task_id=${encodeURIComponent(taskId)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        })
    );
}

function toggleFileDetails(button, fileId) {
    const detailsDiv = document.querySelector(`[data-file-id="${fileId}"]`);
    if (detailsDiv) {
        const isHidden = detailsDiv.style.display === 'none';
        detailsDiv.style.display = isHidden ? 'block' : 'none';
        button.textContent = isHidden ? '📋 Gizle' : '📋 Detaylar';
    } else {
        console.error(`Detaylar div bulunamadı. File ID: ${fileId}`);
    }
}

function analyzeMissingFunctions(projectId, fileName, fileId) {
    if (confirm(`"${fileName}" dosyasındaki tüm eksik özetler oluşturulacak. Devam etmek istiyor musunuz?`)) {
        const taskId = `ai-file-${fileId}-${Date.now()}`;
        showSuccess('Bilgi', `"${fileName}" için analiz işi başlatıldı`);
        startTrackedAnalysis(
            taskId,
            `Dosya Analizi: ${fileName}`,
            fetch(`${API_URL}/analysis/file/${fileId}?missing_only=true&task_id=${encodeURIComponent(taskId)}`, {
                method: 'POST'
            })
        );
    }
}

function analyzeSingleFunction(functionId) {
    // Generate AI summary for single function
    const taskId = `ai-func-${functionId}-${Date.now()}`;
    startTrackedAnalysis(
        taskId,
        `Fonksiyon Analizi: #${functionId}`,
        fetch(`${API_URL}/analysis/function/${functionId}/ai-summary?task_id=${encodeURIComponent(taskId)}`, {
            method: 'POST'
        })
    );
}

function renderReport(reportData, errorData) {
    const container = document.getElementById('reportContainer');
    const missingTargets = collectMissingFileTargets(reportData);
    const missingFilesCount = missingTargets.length;
    const missingFunctionsTotal = missingTargets.reduce((sum, t) => sum + t.missingCount, 0);

    const stats = reportData.statistics;
    let html = `
        <div style="background: white; padding: 20px; border-radius: 4px; margin-bottom: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px;">
                <h3 style="margin:0;">📊 Genel İstatistikler</h3>
                <button
                    class="btn btn-sm"
                    onclick="analyzeAllMissingFiles()"
                    ${missingFilesCount === 0 ? 'disabled' : ''}
                    style="background:${missingFilesCount === 0 ? '#bdc3c7' : '#16a085'}; color:white; border:none; border-radius:4px; padding:8px 12px; cursor:${missingFilesCount === 0 ? 'not-allowed' : 'pointer'};">
                    🤖 Analiz Edilmeyen Tum Dosyalari Analiz Et (${missingFilesCount})
                </button>
            </div>
            <div style="font-size:13px; color:#7f8c8d; margin-bottom:10px;">
                Bekleyen dosya: <strong>${missingFilesCount}</strong> | Bekleyen fonksiyon: <strong>${missingFunctionsTotal}</strong>
            </div>
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

    const errorItems = (errorData && Array.isArray(errorData.items)) ? errorData.items : [];
    html += `
        <div style="background: #fff8f8; padding: 16px; border-radius: 6px; margin-bottom: 18px; border: 1px solid #ffd9d9;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px;">
                <h3 style="margin:0; color:#c0392b;">🚨 Error: Özetleri</h3>
                <div style="display:flex; gap:8px;">
                    <button class="btn btn-sm" onclick="reanalyzeAllErrorSummaries()" style="background:#3498db; color:white; border:none; border-radius:4px; padding:6px 10px; cursor:pointer;">🤖 Tümünü Tekrar Analiz Et</button>
                    <button class="btn btn-sm" onclick="clearAllErrorSummaries()" style="background:#e67e22; color:white; border:none; border-radius:4px; padding:6px 10px; cursor:pointer;">🧹 Tüm Error Özetlerini Temizle</button>
                </div>
            </div>
            <div style="font-size:13px; color:#7f8c8d; margin-bottom:8px;">Toplam Error özeti: <strong>${errorItems.length}</strong></div>
            ${errorItems.length === 0 ? `
                <div style="color:#27ae60; font-size:13px;">✅ Error: ile başlayan özet bulunamadı</div>
            ` : `
                <div style="max-height:320px; overflow:auto; border-top:1px solid #f0cfcf; padding-top:8px;">
                    ${errorItems.map(item => `
                        <div style="background:white; border:1px solid #f2dede; border-left:4px solid #e74c3c; border-radius:4px; padding:8px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap;">
                                <div>
                                    <strong>${item.qualified_name}</strong>
                                    <div style="font-size:12px; color:#7f8c8d;">${item.project_name || '-'} • ${item.file_path || '-'}</div>
                                </div>
                                <div style="display:flex; gap:6px;">
                                    <button onclick="reanalyzeErrorSummary(${item.function_id})" style="background:#3498db; color:white; border:none; border-radius:3px; padding:4px 8px; cursor:pointer;">🤖 Tekrar AI Analiz</button>
                                    <button onclick="clearErrorSummary(${item.function_id})" style="background:#e67e22; color:white; border:none; border-radius:3px; padding:4px 8px; cursor:pointer;">🧹 Temizle</button>
                                </div>
                            </div>
                            <div style="font-size:12px; color:#c0392b; margin-top:6px; white-space:pre-wrap;">${(item.ai_summary || '').slice(0, 260)}</div>
                        </div>
                    `).join('')}
                </div>
            `}
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
                                    <button class="btn btn-sm" onclick="toggleFileDetails(this, ${fileData.file_id})" 
                                            style="padding: 6px 12px; background: #95a5a6; color: white; border: none; border-radius: 3px; cursor: pointer;">
                                        📋 Detaylar
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Dosya detayları (gizli) -->
                            <div data-file-id="${fileData.file_id}" style="display: none; margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd;">
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
    document.getElementById('createUserModal').classList.add('visible');
    hideEditUserForm(); // Ensure edit is closed
}

function hideCreateUserForm() {
    document.getElementById('createUserModal').classList.remove('visible');
    document.getElementById('adminNewUsername').value = '';
    document.getElementById('adminNewPassword').value = '';
    document.getElementById('adminNewUserFullName').value = '';
    document.getElementById('adminNewUserEmail').value = '';
}

function createNewUser() {
    const username = document.getElementById('adminNewUsername').value.trim();
    const password = document.getElementById('adminNewPassword').value.trim();
    const role = document.getElementById('adminNewUserRole').value;
    const fullName = document.getElementById('adminNewUserFullName').value.trim();
    const email = document.getElementById('adminNewUserEmail').value.trim();

    if (!username || !password) {
        showError('Hata', 'Kullanıcı adı ve şifre gerekli');
        return;
    }

    if (password.length < 4) {
        showError('Hata', 'Şifre en az 4 karakter olmalıdır');
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
    fetch(`${API_URL}/users/admin/${userId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('Hata', data.error);
                return;
            }

            document.getElementById('editUserId').value = data.id;
            document.getElementById('editUsername').value = data.username || '';
            document.getElementById('editUserFullName').value = data.full_name || '';
            document.getElementById('editUserEmail').value = data.email || '';
            document.getElementById('editUserRole').value = data.role || 'analyzer';
            document.getElementById('editUserStatus').value = data.is_active ? '1' : '0';
            document.getElementById('editUserPassword').value = '';

            document.getElementById('editUserModal').classList.add('visible');
            hideCreateUserForm(); // Ensure create is closed
        })
        .catch(err => showError('Hata', `Kullanıcı bilgileri alınırken hata: ${err}`));
}

function hideEditUserForm() {
    document.getElementById('editUserModal').classList.remove('visible');
}

function updateUser() {
    const userId = document.getElementById('editUserId').value;
    const fullName = document.getElementById('editUserFullName').value.trim();
    const email = document.getElementById('editUserEmail').value.trim();
    const role = document.getElementById('editUserRole').value;
    const isActive = parseInt(document.getElementById('editUserStatus').value);
    const password = document.getElementById('editUserPassword').value.trim();

    if (!userId) return;

    const payload = {
        full_name: fullName,
        email: email,
        role: role,
        is_active: isActive
    };

    if (password) {
        if (password.length < 4) {
            showError('Hata', 'Şifre en az 4 karakter olmalıdır');
            return;
        }
        payload.password = password;
    }

    fetch(`${API_URL}/users/admin/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                showSuccess('Başarılı', 'Kullanıcı güncellendi');
                hideEditUserForm();
                loadAllUsers();
            } else {
                showError('Hata', data.error || 'Kullanıcı güncellenemedi');
            }
        })
        .catch(err => showError('Hata', `Güncelleme sırasında hata: ${err}`));
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


