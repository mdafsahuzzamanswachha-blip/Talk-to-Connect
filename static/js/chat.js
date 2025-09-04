document.addEventListener('DOMContentLoaded', () => {
  const socket = io({ withCredentials: true });

  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const chatBox = document.getElementById('chat-box');
  const usersList = document.getElementById('users-list');

  // Current chat target (set by clicking a user)
  let otherId = window.INIT_OTHER_ID || null;

  function scrollBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function renderMsg(m) {
    const isMine = Number(m.sender_id) === Number(window.CURRENT_USER_ID);
    const wrap = document.createElement('div');
    wrap.className = `msg-row ${isMine ? 'mine' : 'theirs'}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (m.content) bubble.textContent = m.content;
    if (m.file_url) {
      const a = document.createElement('a');
      a.href = m.file_url;
      a.target = '_blank';
      a.rel = 'noreferrer';
      a.textContent = '📎 Attachment';
      bubble.appendChild(document.createElement('br'));
      bubble.appendChild(a);
    }
    wrap.appendChild(bubble);
    chatBox.appendChild(wrap);
  }

  // Load history when selecting a user
  async function loadHistory(id) {
    const res = await fetch(`/api/messages/${id}`, { credentials: 'include' });
    const data = await res.json();
    chatBox.innerHTML = '';
    data.forEach(renderMsg);
    scrollBottom();
  }

  // Click user in sidebar
  usersList?.addEventListener('click', async (e) => {
    const li = e.target.closest('[data-uid]');
    if (!li) return;
    otherId = Number(li.dataset.uid);
    socket.emit('join_dm', { other_id: otherId });
    await loadHistory(otherId);
    document.querySelectorAll('#users-list [data-uid]').forEach(n => n.classList.remove('active'));
    li.classList.add('active');
  });

  // Send message
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message || !otherId) return;
    socket.emit('send_message', { other_id: otherId, content: message });
    input.value = '';
  });

  // Typing indicator
  let typingTimer;
  input?.addEventListener('input', () => {
    if (!otherId) return;
    socket.emit('typing', { other_id: otherId, typing: true });
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => {
      socket.emit('typing', { other_id, typing: false });
    }, 1200);
  });

  // Incoming events
  socket.on('new_message', (m) => {
    if (!otherId) return; // ignore if no chat opened
    const relevant = (Number(m.sender_id) === Number(otherId)) || (Number(m.sender_id) === Number(window.CURRENT_USER_ID));
    if (relevant) {
      renderMsg(m);
      scrollBottom();
    }
  });

  socket.on('presence', ({ user_id, status }) => {
    const badge = document.querySelector(`[data-uid="${user_id}"] .status`);
    if (badge) {
      badge.className = `status ${status}`;
      badge.title = status;
    }
  });

  socket.on('typing', ({ from, typing }) => {
    if (Number(from) !== Number(otherId)) return;
    const bar = document.getElementById('typing-bar');
    if (!bar) return;
    bar.style.visibility = typing ? 'visible' : 'hidden';
  });

  // Default select first user if exists
  const first = document.querySelector('#users-list [data-uid]');
  if (first) first.click();
});
