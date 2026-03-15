// JSON 评分结果解析页面前端逻辑

const $ = (id) => document.getElementById(id);

const jsonUploadZone = $('jsonUploadZone');
const jsonFileInput = $('jsonFileInput');
const jsonUploadResult = $('jsonUploadResult');
const jsonResultCard = $('jsonResultCard');
const jsonResultTable = $('jsonResultTable');
const btnClearJsonExcel = $('btnClearJsonExcel');
const btnExportCsv = $('btnExportCsv');

let parsedRows = [];
let lastJsonFileName = '';

function showToast(msg, type = '') {
    const t = $('toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast ' + type;
    t.classList.remove('hidden');
    const duration = type === 'error' ? 6000 : 2500;
    setTimeout(() => t.classList.add('hidden'), duration);
}

jsonUploadZone.addEventListener('click', () => jsonFileInput.click());
jsonUploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    jsonUploadZone.classList.add('dragover');
});
jsonUploadZone.addEventListener('dragleave', () => jsonUploadZone.classList.remove('dragover'));
jsonUploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    jsonUploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) uploadJsonExcel(file);
});

jsonFileInput.addEventListener('change', () => {
    const file = jsonFileInput.files[0];
    if (file) uploadJsonExcel(file);
});

btnClearJsonExcel.addEventListener('click', () => {
    parsedRows = [];
    lastJsonFileName = '';
    jsonFileInput.value = '';
    jsonUploadResult.textContent = '';
    jsonUploadResult.className = 'upload-result hidden';
    jsonResultCard.style.display = 'none';
    if (jsonResultTable.tHead) jsonResultTable.tHead.innerHTML = '';
    if (jsonResultTable.tBodies[0]) jsonResultTable.tBodies[0].innerHTML = '';
    showToast('已清除解析结果', 'success');
});

async function uploadJsonExcel(file) {
    const fd = new FormData();
    fd.append('file', file);
    jsonUploadResult.className = 'upload-result';
    jsonUploadResult.textContent = '正在解析，请稍候...';
    jsonUploadResult.classList.remove('hidden');

    try {
        const r = await fetch('/api/json-eval/parse', {
            method: 'POST',
            body: fd,
        });
        let data;
        try {
            data = await r.json();
        } catch {
            throw new Error(r.ok ? '服务器响应解析失败' : `服务器错误 ${r.status}`);
        }
        if (!r.ok || !data.success) {
            throw new Error(data.error || '解析失败');
        }

        parsedRows = data.rows || [];
        lastJsonFileName = file.name;

        if (!parsedRows.length) {
            jsonUploadResult.className = 'upload-result error';
            jsonUploadResult.textContent = '未解析到有效 JSON 数据';
            jsonResultCard.style.display = 'none';
            return;
        }

        jsonUploadResult.className = 'upload-result success';
        jsonUploadResult.textContent = `解析成功：${parsedRows.length} 条记录（${file.name}）`;
        renderResultTable(parsedRows);
        jsonResultCard.style.display = 'block';
    } catch (e) {
        parsedRows = [];
        jsonResultCard.style.display = 'none';
        jsonUploadResult.className = 'upload-result error';
        jsonUploadResult.textContent = '解析失败: ' + (e.message || String(e));
        showToast('解析失败', 'error');
    }
}

function renderResultTable(rows) {
    if (!rows.length) return;
    const headers = Object.keys(rows[0]);

    let thead = jsonResultTable.tHead;
    if (!thead) {
        thead = jsonResultTable.createTHead();
    }
    thead.innerHTML = '';
    const headerRow = thead.insertRow();
    headers.forEach((h) => {
        const th = document.createElement('th');
        th.textContent = h;
        headerRow.appendChild(th);
    });

    let tbody = jsonResultTable.tBodies[0];
    if (!tbody) {
        tbody = jsonResultTable.createTBody();
    }
    tbody.innerHTML = '';
    rows.forEach((row) => {
        const tr = tbody.insertRow();
        headers.forEach((h) => {
            const td = tr.insertCell();
            const v = row[h];
            td.textContent = v == null ? '' : String(v);
        });
    });
}

btnExportCsv.addEventListener('click', () => {
    if (!parsedRows.length) {
        showToast('暂无可导出的数据', 'error');
        return;
    }
    const headers = Object.keys(parsedRows[0]);
    const lines = [];
    lines.push(headers.join(','));
    parsedRows.forEach((row) => {
        const line = headers
            .map((h) => {
                let v = row[h];
                if (v == null) v = '';
                v = String(v).replace(/"/g, '""');
                if (v.includes(',') || v.includes('"') || v.includes('\n')) {
                    return `"${v}"`;
                }
                return v;
            })
            .join(',');
        lines.push(line);
    });
    const csvContent = lines.join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const baseName = lastJsonFileName.replace(/\.[^.]+$/, '');
    a.download = (baseName || 'json_parsed_result') + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('已开始下载 CSV', 'success');
});

