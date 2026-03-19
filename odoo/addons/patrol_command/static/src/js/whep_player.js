/** @odoo-module **/

/**
 * WHEP Video Player — subscribe live video จาก MediaMTX
 *
 * Usage:
 *   const player = new WhepPlayer(videoElement, "http://mediamtx:8889");
 *   await player.connect("patrol/Alpha-1");
 *   player.disconnect();
 */

export class WhepPlayer {
    constructor(videoEl, mediamtxBaseUrl) {
        this.videoEl = videoEl;
        this.baseUrl = mediamtxBaseUrl;
        this.pc = null;
        this.whepUrl = null;
        this.resourceUrl = null;
        this.state = "idle"; // idle, connecting, connected, failed
        this.onStateChange = null;
    }

    async connect(streamPath) {
        this.disconnect();
        this.setState("connecting");

        try {
            this.pc = new RTCPeerConnection({
                iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
            });

            this.pc.addTransceiver("video", { direction: "recvonly" });
            this.pc.addTransceiver("audio", { direction: "recvonly" });

            this.pc.ontrack = (ev) => {
                if (ev.streams && ev.streams[0]) {
                    this.videoEl.srcObject = ev.streams[0];
                }
            };

            this.pc.oniceconnectionstatechange = () => {
                const s = this.pc?.iceConnectionState;
                if (s === "connected" || s === "completed") {
                    this.setState("connected");
                } else if (s === "failed" || s === "disconnected") {
                    this.setState("failed");
                }
            };

            const offer = await this.pc.createOffer();
            await this.pc.setLocalDescription(offer);

            // Wait for ICE gathering
            await this.waitForIceGathering();

            // POST to WHEP endpoint
            this.whepUrl = `${this.baseUrl}/${streamPath}/whep`;
            const resp = await fetch(this.whepUrl, {
                method: "POST",
                headers: { "Content-Type": "application/sdp" },
                body: this.pc.localDescription.sdp,
            });

            if (!resp.ok) {
                throw new Error(`WHEP failed: ${resp.status}`);
            }

            // Store resource URL for cleanup
            const location = resp.headers.get("Location");
            if (location) {
                this.resourceUrl = location.startsWith("http")
                    ? location
                    : `${this.baseUrl}${location}`;
            }

            const answerSdp = await resp.text();
            await this.pc.setRemoteDescription(
                new RTCSessionDescription({ type: "answer", sdp: answerSdp })
            );
        } catch (err) {
            console.error("[WHEP] connect error:", err);
            this.setState("failed");
        }
    }

    disconnect() {
        if (this.pc) {
            this.pc.close();
            this.pc = null;
        }

        if (this.resourceUrl) {
            fetch(this.resourceUrl, { method: "DELETE" }).catch(() => {});
            this.resourceUrl = null;
        }

        if (this.videoEl) {
            this.videoEl.srcObject = null;
        }

        this.setState("idle");
    }

    waitForIceGathering() {
        return new Promise((resolve) => {
            if (this.pc.iceGatheringState === "complete") {
                resolve();
                return;
            }
            const check = () => {
                if (this.pc?.iceGatheringState === "complete") {
                    this.pc.removeEventListener("icegatheringstatechange", check);
                    resolve();
                }
            };
            this.pc.addEventListener("icegatheringstatechange", check);
            // Timeout fallback
            setTimeout(resolve, 3000);
        });
    }

    setState(state) {
        this.state = state;
        if (this.onStateChange) this.onStateChange(state);
    }
}
