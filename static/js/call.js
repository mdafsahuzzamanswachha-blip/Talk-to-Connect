// =======================
// CALL.JS (Professional)
// =======================

let localStream = null;
let peerConnection = null;
const servers = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

// Start call
async function startCall(type = 'video') {
    if (!currentChatUserId) return;

    try {
        // Get local media stream
        localStream = await navigator.mediaDevices.getUserMedia({
            video: type === 'video',
            audio: true
        });

        const localVideo = document.getElementById('localVideo');
        if (localVideo) localVideo.srcObject = localStream;

        // Create peer connection
        peerConnection = new RTCPeerConnection(servers);

        // Add local tracks
        localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

        // Remote stream handler
        peerConnection.ontrack = event => {
            const remoteVideo = document.getElementById('remoteVideo');
            if (remoteVideo) remoteVideo.srcObject = event.streams[0];
        };

        // ICE candidates
        peerConnection.onicecandidate = event => {
            if (event.candidate) {
                socket.emit('webrtc_ice_candidate', {
                    candidate: event.candidate,
                    to: currentChatUserId
                });
            }
        };

        // Create offer
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);

        socket.emit('webrtc_offer', { offer, to: currentChatUserId, type });

        updateCallUI(true, type);

    } catch (err) {
        console.error('Error starting call:', err);
        alert('Unable to start call. Please check your camera/mic permissions.');
    }
}

// Handle incoming offer
socket.on('webrtc_offer', async ({ offer, from, type }) => {
    try {
        currentChatUserId = from;

        localStream = await navigator.mediaDevices.getUserMedia({
            video: type === 'video',
            audio: true
        });

        const localVideo = document.getElementById('localVideo');
        if (localVideo) localVideo.srcObject = localStream;

        peerConnection = new RTCPeerConnection(servers);

        localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));

        peerConnection.ontrack = event => {
            const remoteVideo = document.getElementById('remoteVideo');
            if (remoteVideo) remoteVideo.srcObject = event.streams[0];
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
        updateCallUI(true, type);

    } catch (err) {
        console.error('Error handling incoming offer:', err);
        alert('Failed to join call.');
    }
});

// Handle answer
socket.on('webrtc_answer', async ({ answer }) => {
    try {
        await peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (err) {
        console.error('Error setting remote description (answer):', err);
    }
});

// Handle ICE candidates
socket.on('webrtc_ice_candidate', async ({ candidate }) => {
    try {
        await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
    } catch (err) {
        console.error('Error adding ICE candidate:', err);
    }
});

// End call
function endCall() {
    try {
        if (peerConnection) {
            peerConnection.ontrack = null;
            peerConnection.onicecandidate = null;
            peerConnection.close();
            peerConnection = null;
        }

        if (localStream) {
            localStream.getTracks().forEach(track => track.stop());
            localStream = null;
        }

        const localVideo = document.getElementById('localVideo');
        if (localVideo) localVideo.srcObject = null;

        const remoteVideo = document.getElementById('remoteVideo');
        if (remoteVideo) remoteVideo.srcObject = null;

        socket.emit('webrtc_end_call', { to: currentChatUserId });
        updateCallUI(false);

        console.log('Call ended.');
    } catch (err) {
        console.error('Error ending call:', err);
    }
}

// Listen for remote end call
socket.on('webrtc_end_call', () => {
    endCall();
});

/**
 * Update Call UI (simple placeholder)
 * You can replace this with a proper modal or call controls
 */
function updateCallUI(inCall, type = 'video') {
    const callStatus = document.getElementById('callStatus');
    if (!callStatus) return;

    if (inCall) {
        callStatus.textContent = type === 'video' ? '📹 In Video Call...' : '🎙️ In Voice Call...';
        callStatus.style.color = '#4caf50';
    } else {
        callStatus.textContent = 'Not in call';
        callStatus.style.color = '#aaa';
    }
}
