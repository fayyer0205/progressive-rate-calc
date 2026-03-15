/**
 * 4S店对话数据分析系统 - 前端逻辑
 * 刷新页面会从 localStorage 恢复 API Key、上传数据、提示词等；上传区支持一键清除历史文件。
 */

const STORAGE_KEY = 'conversation_analysis_persist';

let conversationsText = null;
const $ = id => document.getElementById(id);

function getTemperatureInput(id) {
    const el = $(id);
    if (!el) return 0.5;
    const v = parseFloat(el.value);
    if (Number.isNaN(v)) return 0.5;
    return Math.min(1, Math.max(0, v));
}

function loadState() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const s = JSON.parse(raw);
        if (s.api_key != null) $('apiKey').value = s.api_key;
        if (s.system_instructions_1 != null) $('systemInstructions1').value = s.system_instructions_1;
        if (s.model_1 != null) $('model1').value = s.model_1;
        if (s.original_prompt != null && $('originalPrompt')) $('originalPrompt').value = s.original_prompt;
        if (s.analysis_result != null) {
            $('analysisResult').textContent = s.analysis_result;
            $('analysisResultBox').style.display = 'block';
        }
        if (s.conversations_text != null && s.upload_file_name != null) {
            conversationsText = s.conversations_text;
            lastUploadFileName = s.upload_file_name;
            lastUploadCount = s.upload_count ?? 0;
            lastUploadPreview = s.upload_preview || [];
            uploadResult.className = 'upload-result success';
            uploadResult.textContent = `已恢复：${lastUploadCount} 条对话（${lastUploadFileName}）`;
            uploadResult.classList.remove('hidden');
        }
        if (s.temp_1 != null && $('temp1')) {
            $('temp1').value = s.temp_1;
        }
        if (s.temp_2 != null && $('temp2')) {
            $('temp2').value = s.temp_2;
        }
    } catch (e) { /* ignore */ }
}

function saveState() {
    try {
        const s = {
            api_key: $('apiKey').value,
            system_instructions_1: $('systemInstructions1').value,
            model_1: $('model1').value,
            original_prompt: $('originalPrompt') ? $('originalPrompt').value : undefined,
            temp_1: $('temp1') ? $('temp1').value : undefined,
            analysis_result: $('analysisResult').textContent || null,
        };
        if (conversationsText != null) {
            s.conversations_text = conversationsText;
            s.upload_file_name = lastUploadFileName;
            s.upload_count = lastUploadCount;
            s.upload_preview = lastUploadPreview;
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    } catch (e) { /* ignore */ }
}

let lastUploadFileName = '';
let lastUploadCount = 0;
let lastUploadPreview = [];

let saveStateTimer = null;
function debouncedSaveState() {
    if (saveStateTimer) clearTimeout(saveStateTimer);
    saveStateTimer = setTimeout(saveState, 300);
}

// 上传
const uploadZone = $('uploadZone');
const fileInput = $('fileInput');
const uploadResult = $('uploadResult');

uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', e => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) doUpload(file);
});

fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) doUpload(file);
});

function clearExcelUpload() {
    conversationsText = null;
    lastUploadFileName = '';
    lastUploadCount = 0;
    lastUploadPreview = [];
    fileInput.value = '';
    uploadResult.textContent = '';
    uploadResult.className = 'upload-result hidden';
    uploadResult.classList.add('hidden');
    saveState();
    showToast('已清除对话数据', 'success');
}

$('btnClearExcel').addEventListener('click', clearExcelUpload);

async function doUpload(file) {
    const fd = new FormData();
    fd.append('file', file);
    try {
        showLoading(true);
        const r = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await r.json();
        if (data.success) {
            conversationsText = data.conversations_text;
            lastUploadFileName = file.name;
            lastUploadCount = data.count;
            lastUploadPreview = data.preview || [];
            uploadResult.className = 'upload-result success';
            uploadResult.textContent = `已上传：${file.name}（${data.count} 条对话）`;
            uploadResult.classList.remove('hidden');
            saveState();
        } else {
            uploadResult.className = 'upload-result error';
            uploadResult.textContent = data.error || '上传失败';
            uploadResult.classList.remove('hidden');
            conversationsText = null;
        }
    } catch (e) {
        uploadResult.className = 'upload-result error';
        uploadResult.textContent = '上传失败: ' + e.message;
        uploadResult.classList.remove('hidden');
        conversationsText = null;
    } finally {
        showLoading(false);
    }
}

function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

const API_TIMEOUT_MS = 180000;  // 3 分钟

async function fetchWithTimeout(url, options, timeout = API_TIMEOUT_MS) {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), timeout);
    try {
        const r = await fetch(url, { ...options, signal: ctrl.signal });
        clearTimeout(id);
        return r;
    } catch (e) {
        clearTimeout(id);
        if (e.name === 'AbortError') throw new Error('请求超时，请尝试减少对话数据量或更换模型（如 gemini-1.5-flash）');
        throw e;
    }
}

// 执行分析
$('btnAnalyze').addEventListener('click', async () => {
    if (!conversationsText) {
        showToast('请先上传对话数据', 'error');
        return;
    }
    try {
        showLoading(true);
        const r = await fetchWithTimeout('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversations_text: conversationsText,
                system_instructions: $('systemInstructions1').value,
                api_key: $('apiKey').value,
                model: $('model1').value,
                temperature: getTemperatureInput('temp1')
            })
        });
        let data;
        try {
            data = await r.json();
        } catch {
            throw new Error(r.ok ? '响应解析失败' : `服务器错误 ${r.status}`);
        }
        if (data.success) {
            $('analysisResult').textContent = data.analysis;
            $('analysisResult').classList.remove('collapsed');
            $('analysisResultBox').style.display = 'block';
            saveState();
            showToast('分析完成', 'success');
        } else {
            showToast(data.error || '分析失败', 'error');
        }
    } catch (e) {
        showToast('分析失败: ' + (e.message || String(e)), 'error');
    } finally {
        showLoading(false);
    }
});

// （已合并为单一“执行”流程，改写和一键执行逻辑移除）

// 复制 / 展开（改写模块已合并，只保留分析结果）
$('copyAnalysis').addEventListener('click', () => copyToClipboard($('analysisResult').textContent));
$('expandAnalysis').addEventListener('click', () => $('analysisResult').classList.toggle('collapsed'));

function copyToClipboard(text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => showToast('已复制到剪贴板', 'success')).catch(() => showToast('复制失败', 'error'));
}

function showToast(msg, type = '') {
    if (type === 'error') {
        showErrorModal(msg);
        return;
    }
    const t = $('toast');
    t.textContent = msg;
    t.className = 'toast ' + type;
    t.classList.remove('hidden');
    const duration = type === 'error' ? 6000 : 2500;
    setTimeout(() => t.classList.add('hidden'), duration);
}

function showErrorModal(message) {
    const overlay = $('errorModal');
    const body = $('errorModalMessage');
    body.textContent = message || '发生未知错误';
    overlay.classList.remove('hidden');
}

function closeErrorModal() {
    $('errorModal').classList.add('hidden');
}

function copyErrorModal() {
    const text = $('errorModalMessage').textContent || '';
    if (!text) return;
    navigator.clipboard.writeText(text)
        .then(() => showToast('已复制错误信息', 'success'))
        .catch(() => showToast('复制失败', 'error'));
}

// 错误弹窗：复制 / 关闭
$('btnCopyErrorModal').addEventListener('click', copyErrorModal);
$('btnDismissErrorModal').addEventListener('click', closeErrorModal);
$('btnCloseErrorModal').addEventListener('click', closeErrorModal);
// 点击遮罩关闭（点弹窗内容不关闭）
$('errorModal').addEventListener('click', (e) => {
    if (e.target === $('errorModal')) closeErrorModal();
});
// ESC 关闭
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('errorModal').classList.contains('hidden')) closeErrorModal();
});

// API Key 显示/隐藏切换
const apiKeyInput = $('apiKey');
const btnToggleApiKey = $('btnToggleApiKey');
if (apiKeyInput && btnToggleApiKey) {
    btnToggleApiKey.addEventListener('click', () => {
        if (apiKeyInput.type === 'password') {
            apiKeyInput.type = 'text';
            btnToggleApiKey.textContent = '隐藏';
        } else {
            apiKeyInput.type = 'password';
            btnToggleApiKey.textContent = '显示';
        }
    });
}

function showLoading(show) {
    $('loading').classList.toggle('hidden', !show);
}

// 持久化：输入变更时写入 localStorage
$('apiKey').addEventListener('blur', saveState);
$('apiKey').addEventListener('input', debouncedSaveState);
$('systemInstructions1').addEventListener('input', debouncedSaveState);
$('model1').addEventListener('change', saveState);
if ($('temp1')) $('temp1').addEventListener('input', debouncedSaveState);

// 页面加载时从 localStorage 恢复
loadState();

// 加载默认指令
fetch('/api/defaults')
    .then(r => r.json())
    .then(data => {
        if (!$('systemInstructions1').value) $('systemInstructions1').placeholder = '留空则使用默认分析指令（点击执行时生效）';
        const si2 = $('systemInstructions2');
        if (si2 && !si2.value) si2.placeholder = '留空则使用默认改写指令（点击执行时生效）';
    })
    .catch(() => {});
