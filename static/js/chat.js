document.addEventListener('DOMContentLoaded', () => {
  const socket = io();
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const chatBox = document.getElementById('chat-box');

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    socket.emit('send_message', {
      sender_id: window.CURRENT_USER_ID,
      content: message
    });

    input.value = '';
  });

  socket.on('receive_message', (data) => {
    const bubble = document.createElement('div');
    bubble.classList.add('message');
    if (data.sender_id === window.CURRENT_USER_ID) {
      bubble.classList.add('user');
    }
    bubble.textContent = data.content;
    chatBox.appendChild(bubble);
    chatBox.scrollTop = chatBox.scrollHeight;
  });

  socket.emit('set_online', { user_id: window.CURRENT_USER_ID });
});
