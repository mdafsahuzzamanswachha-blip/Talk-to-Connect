let localStream;
let peerConnection;
const servers = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

// Start call
async function startCall(type = 'video') {
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

        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);
        socket.emit('webrtc_offer', { offer, to: currentChatUserId, type });
    } catch (err) {
        console.error('Error starting call:', err);
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
    await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
});

// ICE candidates
socket.on('webrtc_ice_candidate', async ({ candidate }) => {
    try {
        await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (err) {
        console.error('Error adding ICE candidate:', err);
    }
});

// End call
function endCall() {
    if (peerConnection) {
        peerConnection.close
