import TomSelect from 'tom-select';

// Inspired by https://github.com/mehdibo/hibp-js/blob/master/hibp.js
function sha1(string) {
    const buffer = new TextEncoder('utf-8').encode(string);
    return crypto.subtle.digest('SHA-1', buffer).then(function(digest) {
        const hexCodes = [];
        const view = new DataView(digest);
        for (let i = 0; i < view.byteLength; i += 4) {
            const value = view.getUint32(i);
            hexCodes.push(('00000000' + value.toString(16)).slice(-8));
        }
        return hexCodes.join('');
    });
}

function hibpCheck(password) {
    if (!password) return;

    sha1(password).then(function(hash) {
        const request = new XMLHttpRequest();
        request.open('GET', 'https://api.pwnedpasswords.com/range/' + hash.slice(0, 5));
        request.setRequestHeader('Add-Padding', 'true');
        request.addEventListener('load', function() {
            const hashSuffix = hash.slice(5).toUpperCase();
            for (const line of this.responseText.split('\n')) {
                if (line.substring(0, 35) === hashSuffix) {
                    document.querySelector('#pwned').value = parseInt(line.trimEnd().split(':')[1]);
                    return;
                }
            }
            document.querySelector('#pwned').value = 0;
        });
        request.send();
    });
}

function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).catch(function() {
            copyTextFallback(text);
        });
    } else {
        copyTextFallback(text);
    }
}

function copyTextFallback(text) {
    const input = document.createElement('textarea');
    input.value = text;
    input.style.position = 'fixed';
    input.style.opacity = '0';
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    input.remove();
}

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

class MailuTable {
    constructor(table, index) {
        this.table = table;
        this.rows = Array.from(table.tBodies[0]?.rows || []);
        this.headers = Array.from(table.tHead?.rows[0]?.cells || []);
        this.locale = document.documentElement.lang.replaceAll('_', '-');
        this.collator = new Intl.Collator(this.locale, {
            numeric: true,
            sensitivity: 'base',
        });
        this.storageKey = `mailu-table:${window.location.pathname}:${index}`;
        this.page = 0;
        this.pageSize = 10;
        this.query = '';
        this.order = JSON.parse(table.dataset.order || '[]')[0] || null;

        try {
            Object.assign(this, JSON.parse(localStorage.getItem(this.storageKey)) || {});
        } catch (_) {}

        this.buildControls();
        this.bindSorting();
        this.render();
    }

    buildControls() {
        const toolbar = element('div', 'd-flex flex-wrap justify-content-between align-items-center gap-2 mb-3');
        const lengthLabel = element('label', 'd-flex align-items-center gap-2');
        this.lengthSelect = element('select', 'form-select form-select-sm w-auto');
        for (const [value, label] of [[10, '10'], [25, '25'], [50, '50'], [75, '75'], [100, '100'], [-1, '∞']]) {
            const option = element('option', '', label);
            option.value = value;
            option.selected = Number(value) === Number(this.pageSize);
            this.lengthSelect.appendChild(option);
        }
        const [lengthPrefix, lengthSuffix = ''] = this.table.dataset.lengthMenu.split('_MENU_');
        lengthLabel.append(
            document.createTextNode(lengthPrefix),
            this.lengthSelect,
            document.createTextNode(lengthSuffix),
        );

        this.searchInput = element('input', 'form-control form-control-sm w-auto');
        this.searchInput.type = 'search';
        this.searchInput.placeholder = this.table.dataset.search;
        this.searchInput.setAttribute('aria-label', this.table.dataset.search);
        this.searchInput.value = this.query;
        toolbar.append(lengthLabel, this.searchInput);

        const responsive = element('div', 'table-responsive');
        this.table.before(toolbar, responsive);
        responsive.appendChild(this.table);

        this.empty = element('p', 'text-secondary text-center my-3 d-none', this.table.dataset.empty);
        this.pagination = element('nav', 'd-flex justify-content-center align-items-center gap-2 mt-3');
        this.pagination.setAttribute('aria-label', `${this.table.dataset.previous} / ${this.table.dataset.next}`);
        responsive.after(this.empty, this.pagination);

        this.lengthSelect.addEventListener('change', () => {
            this.pageSize = Number(this.lengthSelect.value);
            this.page = 0;
            this.render();
        });
        this.searchInput.addEventListener('input', () => {
            this.query = this.searchInput.value;
            this.page = 0;
            this.render();
        });
    }

    bindSorting() {
        this.headers.forEach((header, index) => {
            if (header.dataset.orderable === 'false') return;
            const button = element('button', 'mailu-table-sort');
            button.type = 'button';
            button.append(...header.childNodes);
            header.appendChild(button);
            const sort = () => {
                this.order = [index, this.order?.[0] === index && this.order[1] === 'asc' ? 'desc' : 'asc'];
                this.page = 0;
                this.render();
            };
            button.addEventListener('click', sort);
        });
    }

    render() {
        const query = this.query.toLocaleLowerCase(this.locale);
        const rows = this.rows.filter(row => row.textContent.toLocaleLowerCase(this.locale).includes(query));
        if (this.order) {
            const [column, direction] = this.order;
            rows.sort((left, right) => {
                const leftCell = left.cells[column];
                const rightCell = right.cells[column];
                const leftValue = leftCell?.dataset.order ?? leftCell?.dataset.sort ?? leftCell?.textContent.trim() ?? '';
                const rightValue = rightCell?.dataset.order ?? rightCell?.dataset.sort ?? rightCell?.textContent.trim() ?? '';
                const result = this.collator.compare(leftValue, rightValue);
                return direction === 'desc' ? -result : result;
            });
        }

        const pageCount = this.pageSize === -1 ? 1 : Math.max(1, Math.ceil(rows.length / this.pageSize));
        this.page = Math.min(this.page, pageCount - 1);
        const start = this.pageSize === -1 ? 0 : this.page * this.pageSize;
        const end = this.pageSize === -1 ? rows.length : start + this.pageSize;
        const visible = new Set(rows.slice(start, end));

        for (const row of this.rows) row.hidden = true;
        for (const row of rows) {
            row.hidden = !visible.has(row);
            this.table.tBodies[0].appendChild(row);
        }
        this.empty.classList.toggle('d-none', rows.length !== 0);
        this.updateHeaders();
        this.updatePagination(pageCount);
        try {
            localStorage.setItem(this.storageKey, JSON.stringify({
                page: this.page,
                pageSize: this.pageSize,
                query: this.query,
                order: this.order,
            }));
        } catch (_) {}
    }

    updateHeaders() {
        this.headers.forEach((header, index) => {
            if (header.dataset.orderable === 'false') return;
            header.setAttribute('aria-sort', this.order?.[0] === index
                ? (this.order[1] === 'asc' ? 'ascending' : 'descending')
                : 'none');
        });
    }

    updatePagination(pageCount) {
        this.pagination.replaceChildren();
        const previous = element('button', 'btn btn-sm btn-outline-secondary', this.table.dataset.previous);
        previous.type = 'button';
        previous.disabled = this.page === 0;
        previous.addEventListener('click', () => {
            this.page--;
            this.render();
        });

        const status = element('span', 'small', `${this.page + 1} / ${pageCount}`);
        status.setAttribute('aria-live', 'polite');
        const next = element('button', 'btn btn-sm btn-outline-secondary', this.table.dataset.next);
        next.type = 'button';
        next.disabled = this.page >= pageCount - 1;
        next.addEventListener('click', () => {
            this.page++;
            this.render();
        });
        this.pagination.append(previous, status, next);
        this.pagination.classList.toggle('d-none', pageCount === 1);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.activeElement.matches('input, textarea')) document.activeElement.select();

    document.querySelectorAll('[data-clicked]').forEach(link => {
        link.addEventListener('click', event => {
            event.preventDefault();
            window.location.href = link.dataset.clicked;
        });
    });

    document.querySelectorAll('#mailu-languages > a').forEach(link => {
        link.addEventListener('click', event => {
            event.preventDefault();
            fetch(link.href, { method: 'POST' }).then(response => {
                if (response.ok) window.location.reload();
            });
        });
    });

    document.querySelectorAll('fieldset legend input[type=checkbox]').forEach(toggle => {
        toggle.addEventListener('change', function() {
            const fieldset = this.closest('fieldset');
            const controls = Array.from(fieldset.querySelectorAll('input, textarea, select')).filter(control => control !== this);
            fieldset.disabled = !this.checked;
            controls.forEach(control => { control.disabled = !this.checked; });
            if (this.checked) controls[0]?.focus();
        });
    });

    document.querySelectorAll('input[type=range]').forEach(input => {
        const output = document.querySelector(`#${CSS.escape(input.id)}_value`);
        if (!output) return;
        const update = () => {
            const unit = input.dataset.unit === undefined || input.dataset.unit === 'false' ? 1 : Number(input.dataset.unit);
            let value = input.dataset.infinity && input.value === '0' ? '∞' : (input.value / unit).toFixed(2);
            if (value.endsWith('.00')) value = value.slice(0, -3);
            output.textContent = value;
        };
        input.addEventListener('input', update);
        update();
    });

    document.querySelectorAll('.mailselect').forEach(select => {
        new TomSelect(select, {
            create: select.multiple,
            createOnBlur: select.multiple,
            persist: false,
            plugins: select.multiple ? ['remove_button'] : [],
            splitOn: /[,\s]+/,
        });
    });

    document.querySelectorAll('.mailu-table').forEach((table, index) => new MailuTable(table, index));

    document.querySelectorAll('.btn-clip, [data-clipboard-text]').forEach(button => {
        button.addEventListener('click', event => {
            event.preventDefault();
            const target = button.dataset.clipboardTarget;
            copyText(button.dataset.clipboardText || document.querySelector(target).textContent);
        });
    });

    const insecureLogin = document.querySelector('#login_needs_https');
    if (insecureLogin && window.location.protocol !== 'https:') {
        insecureLogin.classList.remove('d-none');
        document.querySelectorAll('form :is(input, button, select, textarea)').forEach(control => { control.disabled = true; });
    }

    if (window.isSecureContext) {
        const password = document.querySelector('#pw');
        password?.addEventListener('change', () => hibpCheck(password.value));
        password?.addEventListener('paste', () => setTimeout(() => hibpCheck(password.value)));
        password?.closest('form')?.addEventListener('submit', () => {
            if (Number(document.querySelector('#pwned').value) < 0) hibpCheck(password.value);
        });
    }
});
