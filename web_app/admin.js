const API_BASE = (location.origin.includes('http') ? location.origin : '') + '/api';
const tg = window.Telegram?.WebApp;
const params = new URLSearchParams(location.search);
let user = tg?.initDataUnsafe?.user || (params.get('uid') ? { id: params.get('uid') } : null);
let adminConfig = { admin_id: null };
let adminAllowed = false;

const authHeaders = () => (user?.id ? { 'X-Telegram-Id': user.id } : {});

async function ensureAdminAccess() {
    try {
        if (tg) {
            tg.ready();
            tg.expand();
        }
        const res = await fetch(`${API_BASE}/admin/config`);
        if (res.ok) {
            adminConfig = await res.json();
        }
    } catch (e) {
        console.warn('Failed to load admin config', e);
    }
    adminAllowed = Boolean(adminConfig?.admin_id && user?.id && String(user.id) === String(adminConfig.admin_id));
    if (!adminAllowed) {
        document.body.innerHTML = '<div class="p-6 text-center text-red-600 text-lg font-semibold">Доступ только для администратора</div>';
    }
    return adminAllowed;
}

document.addEventListener('DOMContentLoaded', async () => {
    const allowed = await ensureAdminAccess();
    if (!allowed) return;

    const form = document.getElementById('add-dish-form');
    const result = document.getElementById('add-result');
    const refresh = document.getElementById('refresh-list');

    const addAdminForm = document.getElementById('add-admin-form');
    const addAdminResult = document.getElementById('add-admin-result');

    const addPromoForm = document.getElementById('add-promo-form');
    const addPromoResult = document.getElementById('add-promo-result');
    const refreshPromos = document.getElementById('refresh-promos');

    // Добавление блюда
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        result.textContent = 'Загрузка...';
        const fd = new FormData(form);

        try {
            const res = await fetch(`${API_BASE}/dishes`, { method: 'POST', body: fd, headers: authHeaders() });
            const data = await res.json();
            if (data.status === 'success') {
                result.textContent = 'Блюдо добавлено';
                form.reset();
                loadDishesAdmin();
            } else {
                result.textContent = 'Ошибка: ' + (data.error || 'неизвестная');
            }
        } catch (err) {
            console.error(err);
            result.textContent = 'Ошибка при запросе';
        }
        setTimeout(() => result.textContent = '', 2500);
    });

    // Обновление списка блюд
    refresh.addEventListener('click', loadDishesAdmin);

    // Добавление нового админа
    addAdminForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        addAdminResult.textContent = 'Загрузка...';
        const username = addAdminForm.username.value.trim();
        if (!username) return;

        try {
            const res = await fetch(`${API_BASE}/add_admin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                body: JSON.stringify({ username })
            });
            const data = await res.json();
            if (data.status === 'success') {
                addAdminResult.textContent = `Админ ${username} добавлен`;
                addAdminForm.reset();
            } else {
                addAdminResult.textContent = 'Ошибка: ' + (data.error || 'неизвестная');
            }
        } catch (err) {
            console.error(err);
            addAdminResult.textContent = 'Ошибка при запросе';
        }
        setTimeout(() => addAdminResult.textContent = '', 2500);
    });

    // Добавление промокода
    addPromoForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        addPromoResult.textContent = 'Загрузка...';
        const code = addPromoForm.code.value.trim();
        const discount = parseFloat(addPromoForm.discount.value);
        const maxUses = parseInt(addPromoForm.max_uses.value);
        const expiresAt = addPromoForm.expires_at.value;

        if (!code || isNaN(discount) || isNaN(maxUses) || discount < 0 || discount > 100 || maxUses <= 0) {
            addPromoResult.textContent = 'Ошибка: Проверьте данные (скидка 0-100%, макс. использований > 0)';
            setTimeout(() => addPromoResult.textContent = '', 2500);
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/promocodes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeaders() },
                body: JSON.stringify({ code, discount, max_uses: maxUses, expires_at: expiresAt || null })
            });
            const data = await res.json();
            if (data.status === 'success') {
                addPromoResult.textContent = `Промокод ${code} добавлен`;
                addPromoForm.reset();
                loadPromosAdmin();
            } else {
                addPromoResult.textContent = 'Ошибка: ' + (data.error || 'неизвестная');
            }
        } catch (err) {
            console.error(err);
            addPromoResult.textContent = 'Ошибка при запросе';
        }
        setTimeout(() => addPromoResult.textContent = '', 2500);
    });

    // Обновление списка промокодов
    refreshPromos.addEventListener('click', loadPromosAdmin);

    loadDishesAdmin();
    loadPromosAdmin();
});

// Загрузка списка блюд
async function loadDishesAdmin() {
    const list = document.getElementById('dish-list');
    list.innerHTML = 'Загрузка...';
    try {
        const res = await fetch(`${API_BASE}/dishes`, { headers: authHeaders() });
        const data = await res.json();
        if (!data || !data.length) {
            list.innerHTML = '<div class="text-gray-500">Блюд нет</div>';
            return;
        }
        list.innerHTML = '';
        data.forEach(d => {
            const card = document.createElement('div');
            card.className = 'p-3 border rounded flex gap-3 items-start bg-white';
            card.innerHTML = `
                <img src="${d.image_url || '/web_app/assets/placeholder.png'}" style="width:100px;height:70px;object-fit:cover;border-radius:8px" />
                <div class="flex-1">
                    <div class="font-semibold">${escapeHtml(d.name)}</div>
                    <div class="text-sm text-gray-500">${escapeHtml(d.description || '')}</div>
                    <div class="text-xs text-gray-700 mt-2">${d.price ? d.price + ' ₽' : ''} • ${escapeHtml(d.category || '')}</div>
                </div>
                <div class="flex flex-col gap-2">
                    <button class="delete-btn bg-red-500 text-white px-3 py-1 rounded" data-id="${d.id}">Удалить</button>
                </div>
            `;
            list.appendChild(card);
        });

        // Удаление блюд
        list.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm('Удалить блюдо?')) return;
                try {
                    const r = await fetch(`${API_BASE}/dishes/${btn.dataset.id}`, { method: 'DELETE', headers: authHeaders() });
                    const j = await r.json();
                    if (j.status === 'success') loadDishesAdmin();
                    else alert('Ошибка удаления');
                } catch (err) { console.error(err); alert('Ошибка при запросе'); }
            });
        });

    } catch (err) {
        console.error(err);
        list.innerHTML = '<div class="text-red-500">Ошибка загрузки</div>';
    }
}

// Загрузка списка промокодов
async function loadPromosAdmin() {
    const list = document.getElementById('promo-list');
    list.innerHTML = 'Загрузка...';
    try {
        const res = await fetch(`${API_BASE}/promocodes`, { headers: authHeaders() });
        const data = await res.json();
        if (!data || !data.length) {
            list.innerHTML = '<div class="text-gray-500">Промокодов нет</div>';
            return;
        }
        list.innerHTML = '<table class="promo-table"><thead><tr><th>Код</th><th>Скидка</th><th>Использований</th><th>Макс. использований</th><th>Истекает</th><th>Действует</th><th>Действия</th></tr></thead><tbody></tbody></table>';
        const tbody = list.querySelector('tbody');
        data.forEach(p => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${escapeHtml(p.code)}</td>
                <td>${p.discount}%</td>
                <td>${p.uses}</td>
                <td>${p.max_uses}</td>
                <td>${p.expires_at || '—'}</td>
                <td>${p.is_active ? 'Да' : 'Нет'}</td>
                <td><button class="delete-btn bg-red-500 text-white px-2 py-1 rounded" data-id="${p.id}">Удалить</button></td>
            `;
            tbody.appendChild(row);
        });

        // Удаление промокодов
        list.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm('Удалить промокод?')) return;
                try {
                    const r = await fetch(`${API_BASE}/promocodes`, {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json', ...authHeaders() },
                        body: JSON.stringify({ id: btn.dataset.id })
                    });
                    const j = await r.json();
                    if (j.status === 'success') loadPromosAdmin();
                    else alert('Ошибка удаления');
                } catch (err) { console.error(err); alert('Ошибка при запросе'); }
            });
        });

    } catch (err) {
        console.error(err);
        list.innerHTML = '<div class="text-red-500">Ошибка загрузки</div>';
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
}