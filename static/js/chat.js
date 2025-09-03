// =======================
// Socket.IO connection
// =======================
const socket = io({
    transports: ['websocket', 'polling'],
    reconnection: true
});

// =======================
// Presence Handling
// =======================
function updateSidebarStatus(userId, status) {
    const badge = document.querySelector(`.person[data-user-id="${userId}"] .badge`);
    if (badge) {
        badge.textContent = status === 'online' ? 'Active' : 'Offline';
        badge.classList.toggle('active', status === 'online');
        badge.classList.toggle('idle', status !== 'online');
    }
}

function updateChatHeaderStatus(userId, status) {
    const chatNameEl = document.getElementById('chat-name');
    const chatStatusEl = document.getElementById('chat-status');
    const activePerson = document.querySelector(`.person[data-user-id="${userId}"]`);
    if (chatNameEl && chatStatusEl && activePerson) {
        if (chatNameEl.textContent.trim() === activePerson.querySelector('.name').textContent.trim()) {
            chatStatusEl.textContent = status === 'online' ? 'Active now' : 'Offline';
            chatStatusEl.className = `status ${status}`;
        }
    }
}

// Initial online users
if (window.INIT_ONLINE && Array.isArray(window.INIT_ONLINE)) {
    window.INIT_ONLINE.forEach(id => updateSidebarStatus(id, 'online'));
}

// Listen for presence events
socket.on('presence', data => {
    const { user_id, status } = data;
    updateSidebarStatus(user_id, status);
    updateChatHeaderStatus(user_id, status);
});

// =======================
// Messaging
// =======================
let currentChatUserId = null;

document.querySelectorAll('.person').forEach(person => {
    person.addEventListener('click', () => {
        currentChatUserId = parseInt(person.dataset.userId);
        document.getElementById('chat-name').textContent = person.querySelector('.name').textContent;
        document.getElementById('chat-avatar').querySelector('img').src = person.querySelector('img').src;
        document.getElementById('messages').innerHTML = '<div class="placeholder">Loading...</div>';

        // Join DM room
        socket.emit('join_dm', { other_id: currentChatUserId });

        // Fetch messages
        fetch(`/api/messages/${currentChatUserId}`)
            .then(res => res.json())
            .then(msgs => {
                const messagesEl = document.getElementById('messages');
                messagesEl.innerHTML = '';
                msgs.forEach(m => appendMessage(m, m.sender_id === window.CURRENT_USER_ID));
            });

        // Enable call buttons
        document.getElementById('audio-call').disabled = false;
        document.getElementById('video-call').disabled = false;
    });
});

function appendMessage(msg, isOwn) {
    const messagesEl = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = `message ${isOwn ? 'own' : ''}`;
    if (msg.file_url) {
        div.innerHTML = `<a href="${msg.file_url}" target="_blank">📎 File</a>`;
    } else {
        div.textContent = msg.content;
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Send message
document.getElementById('send').addEventListener('click', () => {
    const textArea = document.getElementById('msg');
    const content = textArea.value.trim();
    if (!content || !currentChatUserId) return;

    socket.emit('send_message', { other_id: currentChatUserId, content });
    textArea.value = '';
});

// Receive message
socket.on('new_message', msg => {
    if (msg.sender_id === currentChatUserId || msg.receiver_id === currentChatUserId) {
        appendMessage(msg, msg.sender_id === window.CURRENT_USER_ID);
    }
});

// =======================
// Typing Indicator
// =======================
const typingEl = document.getElementById('typing');
let typingTimeout;

document.getElementById('msg').addEventListener('input', () => {
    if (!currentChatUserId) return;
    socket.emit('typing', { other_id: currentChatUserId, typing: true });
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        socket.emit('typing', { other_id: currentChatUserId, typing: false });
    }, 1000);
});

socket.on('typing', data => {
    if (data.from === currentChatUserId) {
        typingEl.textContent = data.typing ? 'Typing...' : '';
    }
});

// =======================
// File Upload Progress
// =======================
document.getElementById('file-input').addEventListener('change', e => {
    if (!currentChatUserId) return;
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('receiver_id', currentChatUserId);
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);

    xhr.upload.onprogress = evt => {
        if (evt.lengthComputable) {
            const percent = Math.round((evt.loaded / evt.total) * 100);
            typingEl.textContent = `Uploading: ${percent}%`;
        }
    };

    xhr.onload = () => {
        typingEl.textContent = '';
        if (xhr.status === 200) {
            const res = JSON.parse(xhr.responseText);
            if (res.message) {
                appendMessage(res.message, true);
            }
        }
    };

    xhr.send(formData);
});

// =======================
// Last Seen
// =======================
function updateLastSeen(userId) {
    fetch(`/api/last_seen/${userId}`)
        .then(res => res.json())
        .then(data => {
            const chatStatusEl = document.getElementById('chat-status');
            if (data.status === 'online') {
                chatStatusEl.textContent = 'Active now';
            } else {
                chatStatusEl.textContent = `Last seen: ${data.last_seen}`;
            }
        });
}

// Optional: call this when opening a chat
// updateLastSeen(currentChatUserId);

// =======================
// Reconnect Handling
// =======================
socket.on('connect', () => {
    if (window.CURRENT_USER_ID) {
        socket.emit('set_online', { user_id: window.CURRENT_USER_ID });
    }
});
