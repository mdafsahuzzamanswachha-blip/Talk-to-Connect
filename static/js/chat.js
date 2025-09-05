document.addEventListener("DOMContentLoaded", () => {
  const socket = io();
  const chatBox = document.getElementById("chat-box");
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message-input");

  socket.on("connect", () => {
    console.log("Connected to server");
  });

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = messageInput.value;
    if (message.trim() !== "") {
      socket.emit("send_message", { 
        message: message,
        receiver_id: 0 // 0 = broadcast to all, adjust if 1:1 chat
      });
      messageInput.value = "";
    }
  });

  socket.on("receive_message", (data) => {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("chat-message");
    msgDiv.textContent = `${data.sender}: ${data.message}`;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
  });
});
