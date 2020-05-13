let userId = null;
let timerId;
let updated = false;

let editor = CodeMirror.fromTextArea(document.getElementById('code'), {
    lineNumbers: true,
    lineWrapping: true,
    lineSeparator: '\n',
});

editor.on('changes', (instance, changes) => {
    if (updated) { // Для случая, когда обновление произошло через setValue
        updated = false;
        return
    }
    clearTimeout(timerId);
    timerId = setTimeout(() => {
        sendAction({'event': 'update', 'value': instance.doc.getValue()})
    }, 500)
});


// Код для обмена дынными по веб сокету
let ws = null;

function ws_connect() {
    const protocol = window.location.protocol === 'https:' && 'wss:' || 'ws:';
    const wsUri = `${protocol}//${window.location.host}/${KEY}/ws`;
    ws = new WebSocket(wsUri);
    ws.onopen = function () {
        sendAction({'event': 'join', 'value': usernameInput.value});
    };
    ws.onmessage = function (e) {
        let data = JSON.parse(e.data);
        console.log(data);
        switch (data.event) {
            case 'update':
                updated = true;
                editor.doc.setValue(data.value);
                break;
            case 'changeLanguage':
                changeEditorLanguage(data.value);
                break;
            case 'changeUsername':
                users[data['userId']] = data['value'];
                renderUserList();
                break;
            case 'leave':
                delete users[data['userId']];
                renderUserList();
                break;
            case 'join':
                users[data['userId']] = data['value'];
                renderUserList();
                break;
            case 'setUserId':
                // Событие происходит сразу после соединения с сервером
                userId = data['value'];
                renderUserList();
                break;
        }
    };
    ws.onclose = function () {
        disconnect();
    };
    ws.onerror = function (event) {
        console.error(event);
    }
}

function disconnect() {
    if (ws != null) {
        ws.close();
        ws = null;
    }
}

function connect() {
    if (ws == null) {
        ws_connect();
    }
}

function sendAction(obj) {
    let data = JSON.stringify(obj);
    ws.send(data);
}


function getUserList() {
    const url = `/${KEY}/users/`;
    let xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.send();
    xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4) return;
        if (xhr.status === 200) {
            JSON.parse(xhr.responseText).forEach((user) => {
                users[user[0]] = user[1];
            });
            renderUserList();
        }
    }
}


function renderUserList() {
    if (userId !== null) {
        users[userId] = usernameInput.value;
    }
    let usersList = document.getElementById('users');
    usersList.innerHTML = "";
    for (let id in users) {
        let user = users[id];
        if (parseInt(id) === userId) {
            user = `<b>${user}</b>`
        }
        user = `<li>${user}</li>`
        usersList.innerHTML += user
    }
}


function changeEditorLanguage(language) {
    let mode = CodeMirror.findModeByName(language);
    if (mode) {
        editor.setOption('mode', mode.mime);
        CodeMirror.modeURL = "/static/mode/%N/%N.js"
        CodeMirror.autoLoadMode(editor, mode.mode);

        document.querySelectorAll('#lang option').forEach((option) => {
            if (option.value.toLowerCase() === language) {
                option.selected = true;
            }
        })
    }
}

let languageSelect = document.getElementById('lang');
languageSelect.onchange = (e) => {
    let language = e.target.value;
    changeEditorLanguage(language)
    sendAction({'event': 'changeLanguage', 'value': language.toLowerCase()})
}


let themeSelect = document.getElementById('theme');
themeSelect.onchange = (e) => {
    let theme = e.target.value;
    localStorage.setItem('theme', theme);
    editor.setOption('theme', theme);
}


let usernameInput = document.getElementById('username');
usernameInput.onchange = function (e) {
    let username = e.target.value;
    localStorage.setItem('username', username);
    sendAction({'event': 'changeUsername', 'value': username})
    renderUserList();
}


document.body.onload = function () {
    // Установка темы редактора
    document.querySelectorAll('#theme option').forEach((e) => {
        let theme = localStorage.getItem('theme') || 'default'
        if (e.value === theme) {
            e.selected = true;
            editor.setOption('theme', e.value);
        }
    })
    // Формирование списка ЯП
    CodeMirror.modeInfo.forEach((modeItem) => {
        let option = document.createElement('option');
        option.innerText = modeItem.name;
        languageSelect.appendChild(option);
    })
    // Установка имени пользователя
    document.getElementById('username').value = localStorage.getItem('username');
    // Установка языка
    changeEditorLanguage(LANGUAGE);
    // Получение и вывод списка пользователей
    getUserList();
    // Подключение к веб сокету
    connect();
}

