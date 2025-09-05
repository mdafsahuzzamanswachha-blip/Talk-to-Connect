const socket = io();

let localStream;
let remoteStream;
let peerConnection;

const servers = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "stun:stun1.l.google.com:19302" },
  ],
};

const localVideo = document.getElementById("localVideo");
const remoteVideo = document.getElementById("remoteVideo");
const startCallBtn = document.getElementById("startCall");
const endCallBtn = document.getElementById("endCall");

// Start the call
startCallBtn.addEventListener("click", async () => {
  localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  localVideo.srcObject = localStream;

  peerConnection = new RTCPeerConnection(servers);

  // Add local tracks to peer connection
  localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

  // Handle remote tracks
  peerConnection.ontrack = (event) => {
    remoteStream = event.streams[0];
    remoteVideo.srcObject = remoteStream;
  };

  // ICE candidates
  peerConnection.onicecandidate = (event) => {
    if (event.candidate) {
      socket.emit("ice-candidate", event.candidate);
    }
  };

  const offer = await peerConnection.createOffer();
  await peerConnection.setLocalDescription(offer);

  socket.emit("call-offer", offer);
});

// End the call
endCallBtn.addEventListener("click", () => {
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }
  if (localStream) {
    localStream.getTracks().forEach(track => track.stop());
    localStream = null;
  }
  remoteVideo.srcObject = null;
});

// Socket.IO events
socket.on("call-offer", async (offer) => {
  localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  localVideo.srcObject = localStream;

  peerConnection = new RTCPeerConnection(servers);

  localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

  peerConnection.ontrack = (event) => {
    remoteStream = event.streams[0];
    remoteVideo.srcObject = remoteStream;
  };

  peerConnection.onicecandidate = (event) => {
    if (event.candidate) {
      socket.emit("ice-candidate", event.candidate);
    }
  };

  await peerConnection.setRemoteDescription(offer);
  const answer = await peerConnection.createAnswer();
  await peerConnection.setLocalDescription(answer);

  socket.emit("call-answer", answer);
});

socket.on("call-answer", async (answer) => {
  if (peerConnection) {
    await peerConnection.setRemoteDescription(answer);
  }
});

socket.on("ice-candidate", async (candidate) => {
  if (peerConnection) {
    try {
      await peerConnection.addIceCandidate(candidate);
    } catch (err) {
      console.error("Error adding received ICE candidate", err);
    }
  }
});
