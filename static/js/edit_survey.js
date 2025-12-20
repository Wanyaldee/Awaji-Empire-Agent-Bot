/**
 * edit_survey.js
 * アンケート編集画面の動的UI制御
 */

let questions = [];

// ページ読み込み完了時に実行
document.addEventListener('DOMContentLoaded', () => {
    // HTML内の隠し要素から生データを取得
    const rawDataElement = document.getElementById('raw-data');
    if (rawDataElement) {
        const raw = rawDataElement.textContent;
        try {
            const parsed = JSON.parse(raw);
            // 古いデータ形式(ただの文字列配列)への互換性対応
            if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'string') {
                questions = parsed.map(q => ({ type: 'text', question: q, options: [] }));
            } else {
                questions = parsed || [];
            }
        } catch(e) {
            console.error("JSON Parse Error:", e);
            questions = [];
        }
    }

    // データが空ならデフォルトで1つ追加
    if (questions.length === 0) {
        addQuestion();
    } else {
        renderAll();
    }

    // 送信ボタンのイベントリスナー
    const form = document.getElementById('surveyForm');
    if (form) {
        form.addEventListener('submit', () => {
            document.getElementById('hidden-json').value = JSON.stringify(questions);
        });
    }
});

// --- 以下、HTML内のonclick等から呼ばれる関数群 ---
// windowオブジェクトに紐付けることで、動的生成されたHTMLからも呼び出せるようにする

window.addQuestion = function() {
    questions.push({ type: 'text', question: '', options: [] });
    renderAll();
};

window.removeQuestion = function(index) {
    if(!confirm('この質問を削除しますか？')) return;
    questions.splice(index, 1);
    renderAll();
};

window.updateData = function(index, key, value) {
    questions[index][key] = value;
    renderAll(); // タイプ変更時のUI切り替えのため再描画
};

window.updateOptions = function(index, value) {
    // 全角カンマを半角に変換し、配列化して保存
    const opts = value.replace(/、/g, ',').split(',').map(s => s.trim()).filter(s => s);
    questions[index].options = opts;
};

// 描画関数 (Reactライクな再描画ロジック)
function renderAll() {
    const container = document.getElementById('questions-container');
    container.innerHTML = '';

    questions.forEach((q, index) => {
        const card = document.createElement('div');
        card.className = 'card question-card bg-light';
        
        // テンプレートリテラルでHTMLを構築
        card.innerHTML = `
            <div class="card-body">
                <div class="d-flex justify-content-between mb-2">
                    <span class="badge bg-secondary">Q${index + 1}</span>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeQuestion(${index})">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
                
                <div class="row g-2">
                    <div class="col-md-8">
                        <input type="text" class="form-control fw-bold" placeholder="質問文を入力 (例: 参加しますか？)" 
                            value="${escapeHtml(q.question)}" onchange="updateData(${index}, 'question', this.value)">
                    </div>
                    <div class="col-md-4">
                        <select class="form-select" onchange="updateData(${index}, 'type', this.value)">
                            <option value="text" ${q.type === 'text' ? 'selected' : ''}>📝 記述式 (自由入力)</option>
                            <option value="radio" ${q.type === 'radio' ? 'selected' : ''}>🔘 ラジオボタン (単一)</option>
                            <option value="checkbox" ${q.type === 'checkbox' ? 'selected' : ''}>☑️ チェックボックス (複数)</option>
                        </select>
                    </div>
                </div>

                <div class="mt-3 ${q.type === 'text' ? 'd-none' : ''}">
                    <label class="form-label small text-muted">選択肢 (カンマ区切りで入力)</label>
                    <input type="text" class="form-control form-control-sm" placeholder="例: はい, いいえ, 多分"
                        value="${q.options ? escapeHtml(q.options.join(', ')) : ''}" 
                        onchange="updateOptions(${index}, this.value)">
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

// XSS対策用の簡易エスケープ関数
function escapeHtml(text) {
    if (!text) return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
