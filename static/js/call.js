let localStream;
let peerConnection;
const servers = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };
const socket = io({ withCredentials: true });

const currentUserId = window.CURRENT_USER_ID;
let currentChatUserId = window.CALL_PEER_ID || null; // set from call.html when used
const callType = window.CALL_TYPE || 'video';

// Start call
async function startCall(type = callType) {
  if (!currentChatUserId) return;
  try {
    localStream = await navigator.mediaDevices.getUserMedia({
      video: type === 'video',
      audio: true
    });
    document.getElementById('localVideo').srcObject = localStream;

    peerConnection = new RTCPeerConnection(servers);
    localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

    peerConnection.ontrack = event => {
      document.getElementById('remoteVideo').srcObject = event.streams[0];
    };

    peerConnection.onicecandidate = event => {
      if (event.candidate) {
        socket.emit('webrtc_ice_candidate', { candidate: event.candidate, to: currentChatUserId });
      }
    };

    socket.emit('webrtc_join', { other_id: currentChatUserId });

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    socket.emit('webrtc_offer', { offer, to: currentChatUserId, type });
  } catch (err) {
    console.error('Error starting call:', err);
    alert('Could not start call. Check camera/mic permissions.');
  }
}

// Receive offer
socket.on('webrtc_offer', async ({ offer, from, type }) => {
  currentChatUserId = from;
  localStream = await navigator.mediaDevices.getUserMedia({
    video: type === 'video',
    audio: true
  });
  document.getElementById('localVideo').srcObject = localStream;

  peerConnection = new RTCPeerConnection(servers);
  localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

  peerConnection.ontrack = event => {
    document.getElementById('remoteVideo').srcObject = event.streams[0];
  };

  peerConnection.onicecandidate = event => {
    if (event.candidate) {
      socket.emit('webrtc_ice_candidate', { candidate: event.candidate, to: from });
    }
  };

  await peerConnection.setRemoteDescription(new RTCSessionDescription(offer));
  const answer = await peerConnection.createAnswer();
  await peerConnection.setLocalDescription(answer);
  socket.emit('webrtc_answer', { answer, to: from });
});

// Receive answer
socket.on('webrtc_answer', async ({ answer }) => {
  if (!peerConnection) return;
  await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
});

// ICE candidates
socket.on('webrtc_ice_candidate', async ({ candidate }) => {
  try {
    if (peerConnection) await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
  } catch (err) {
    console.error('Error adding ICE candidate:', err);
  }
});

// End call
function endCall() {
  if (peerConnection) {
    peerConnection.getSenders().forEach(s => { try { s.track?.stop(); } catch(e){} });
    peerConnection.close(); // <= bug fixed (must call ())
    peerConnection = null;
  }
  if (localStream) {
    localStream.getTracks().forEach(t => t.stop());
    localStream = null;
  }
  socket.emit('end_call', { to: currentChatUserId });
}

window.startCall = startCall;
window.endCall = endCall;
