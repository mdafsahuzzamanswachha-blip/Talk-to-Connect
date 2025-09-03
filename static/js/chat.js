// Wait for the DOM to load
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const chatBox = document.getElementById('chat-box');

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (message === '') return;

    // Create message bubble
    const bubble = document.createElement('div');
    bubble.classList.add('message', 'user');
    bubble.textContent = message;
    chatBox.appendChild(bubble);

    // Scroll to bottom
    chatBox.scrollTop = chatBox.scrollHeight;

    // Clear input
    input.value = '';
  });
});
