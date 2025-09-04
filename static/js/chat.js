const socket = io();

function sendMessage() {
  const input = document.getElementById('message-input');
  const message = input.value;
  socket.emit('send_message', { username: 'Anonymous', message });
  input.value = '';
}

socket.on('receive_message', data => {
  const box = document.getElementById('chat-box');
  const msg = document.createElement('div');
  msg.textContent = `${data.username}: ${data.message}`;
  box.appendChild(msg);
});
