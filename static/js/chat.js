// =======================
// CHAT.JS (Professional)
// =======================
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const chatBox = document.getElementById('chat-box');

  /**
   * Utility: Format time as HH:MM
   */
  function formatTime(date = new Date()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  /**
   * Utility: Create a message bubble
   */
  function createMessageBubble(text, sender = 'user') {
    const bubble = document.createElement('div');
    bubble.classList.add('message', sender);

    const content = document.createElement('div');
    content.textContent = text;

    const timestamp = document.createElement('span');
    timestamp.classList.add('timestamp');
    timestamp.textContent = formatTime();

    bubble.appendChild(content);
    bubble.appendChild(timestamp);

    return bubble;
  }

  /**
   * Add a message to the chat box
   */
  function addMessage(text, sender = 'user') {
    const bubble = createMessageBubble(text, sender);
    chatBox.appendChild(bubble);

    // Smooth scroll to bottom
    chatBox.scrollTo({
      top: chatBox.scrollHeight,
      behavior: 'smooth'
    });
  }

  /**
   * Show typing indicator
   */
  function showTyping(sender = 'bot') {
    const typing = document.createElement('div');
    typing.classList.add('message', sender, 'typing');
    typing.textContent = '...';
    typing.setAttribute('id', 'typing-indicator');
    chatBox.appendChild(typing);

    chatBox.scrollTo({
      top: chatBox.scrollHeight,
      behavior: 'smooth'
    });
  }

  /**
   * Remove typing indicator
   */
  function removeTyping() {
    const typing = document.getElementById('typing-indicator');
    if (typing) typing.remove();
  }

  // Handle form submit
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    // User message
    addMessage(message, 'user');
    input.value = '';

    // Simulated bot reply (for demo)
    showTyping('bot');
    setTimeout(() => {
      removeTyping();
      addMessage("Got it! You said: " + message, 'bot');
    }, 1000);
  });
});
