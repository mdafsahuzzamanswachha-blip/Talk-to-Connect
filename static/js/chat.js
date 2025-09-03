// Connect to Socket.IO server
const socket = io({
    transports: ['websocket', 'polling'], // fallback for older browsers
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

// Helper: update a user's badge in the sidebar
function updateSidebarStatus(userId, status) {
    const badge = document.querySelector(`.person[data-user-id="${userId}"] .badge`);
    if (badge) {
        if (status === 'online') {
            badge.textContent = 'Active';
            badge.classList.remove('idle');
            badge.classList.add('active');
        } else {
            badge.textContent = 'Offline';
            badge.classList.remove('active');
            badge.classList.add('idle');
        }
    }
}

// Helper: update the chat header if we’re viewing this user
function updateChatHeaderStatus(userId, status) {
    const chatNameEl = document.getElementById('chat-name');
    const chatStatusEl = document.getElementById('chat-status');

    if (chatNameEl && chatStatusEl) {
        // Find the sidebar entry for this user to match IDs
        const activePerson = document.querySelector(`.person[data-user-id="${userId}"]`);
        if (activePerson && chatNameEl.textContent.trim() === activePerson.querySelector('.name').textContent.trim()) {
            chatStatusEl.textContent = status === 'online' ? 'Active now' : 'Offline';
            chatStatusEl.className = `status ${status}`;
        }
    }
}

// 1️⃣ Mark initial online users from server-rendered list
if (window.INIT_ONLINE && Array.isArray(window.INIT_ONLINE)) {
    window.INIT_ONLINE.forEach(id => updateSidebarStatus(id, 'online'));
}

// 2️⃣ Listen for presence updates from backend
socket.on('presence', data => {
    const { user_id, status } = data;
    updateSidebarStatus(user_id, status);
    updateChatHeaderStatus(user_id, status);
});

// 3️⃣ Tell server you are online when connected
socket.on('connect', () => {
    if (window.CURRENT_USER_ID) {
        socket.emit('set_online', { user_id: window.CURRENT_USER_ID });
    }
});

// 4️⃣ Optional: handle disconnect UI feedback
socket.on('disconnect', () => {
    console.warn('Disconnected from server — attempting to reconnect...');
});
