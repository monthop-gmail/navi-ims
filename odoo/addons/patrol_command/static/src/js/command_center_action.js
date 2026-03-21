/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS, loadCSS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { WhepPlayer } from "./whep_player";

class CommandCenterDashboard extends Component {
    static template = "patrol_command.CommandCenterDashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            soldiers: [],
            equipment: [],
            missions: [],
            incidents: [],
            sightings: [],
            gates: [],
            stats: {},
            selectedMissionId: null,
            selectedSoldierId: null,
            showTrack: false,
            showSightings: true,
            view: "map", // "map" or "grid"
            // Video
            videoPopup: null, // { callsign, streamPath, state }
            videoGrid: [],    // [{ callsign, streamPath, state }]
            showGrid: false,
        });

        this.map = null;
        this.markers = {};
        this.trackLine = null;
        this.missionLayers = {};
        this.refreshInterval = null;

        // Video players
        this.popupPlayer = null;
        this.gridPlayers = {}; // callsign → WhepPlayer
        this.mediamtxUrl = window.location.protocol + "//" + window.location.hostname + ":8889";

        onMounted(async () => {
            await this.initMap();
            await this.loadData();
            this.refreshInterval = setInterval(() => this.loadData(), 5000);
        });

        onWillUnmount(() => {
            if (this.refreshInterval) clearInterval(this.refreshInterval);
            if (this.map) this.map.remove();
            this.closeVideoPopup();
            this.closeAllGridVideos();
        });
    }

    async initMap() {
        await loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
        await loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");

        const mapEl = document.getElementById("patrol-map");
        if (!mapEl) return;

        this.map = L.map(mapEl).setView([13.7563, 100.5018], 13);

        L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
            maxZoom: 19,
        }).addTo(this.map);
    }

    async loadData() {
        const missionId = this.state.selectedMissionId;
        const [soldiers, equipment, missions, incidents, stats, sightings, gates] = await Promise.all([
            rpc("/patrol/api/soldiers", { mission_id: missionId }),
            rpc("/patrol/api/equipment", { mission_id: missionId }),
            rpc("/patrol/api/missions", { state: "active" }),
            rpc("/patrol/api/incidents", { mission_id: missionId }),
            rpc("/patrol/api/stats", { mission_id: missionId }),
            rpc("/patrol/api/sightings", { minutes: 10 }).catch(() => []),
            rpc("/patrol/api/gates", {}).catch(() => []),
        ]);

        this.state.soldiers = soldiers;
        this.state.equipment = equipment;
        this.state.missions = missions;
        this.state.incidents = incidents;
        this.state.stats = stats;
        this.state.sightings = sightings;
        this.state.gates = gates;

        this.updateMarkers();
    }

    updateMarkers() {
        if (!this.map) return;

        // Clear old markers
        Object.values(this.markers).forEach((m) => m.remove());
        this.markers = {};

        // Soldier markers
        for (const s of this.state.soldiers) {
            if (!s.last_lat || !s.last_lng) continue;

            const color = s.is_online ? "#00ff88" : "#666";
            const icon = L.divIcon({
                className: "patrol-marker",
                html: `<div style="
                    background:${color};
                    width:12px;height:12px;border-radius:50%;
                    border:2px solid #fff;
                    box-shadow:0 0 6px ${color};
                "></div>`,
                iconSize: [16, 16],
                iconAnchor: [8, 8],
            });

            const marker = L.marker([s.last_lat, s.last_lng], { icon })
                .addTo(this.map)
                .bindPopup(`
                    <strong>${s.callsign}</strong><br/>
                    ${s.name}<br/>
                    ${s.is_online ? "🟢 Online" : "⚫ Offline"}
                `);

            marker.on("click", () => {
                this.selectSoldier(s);
                if (s.is_online && s.stream_path) {
                    this.openVideoPopup(s);
                }
            });
            this.markers[`soldier_${s.id}`] = marker;
        }

        // Equipment markers (fixed cameras)
        for (const e of this.state.equipment) {
            if (!e.gps_lat || !e.gps_lng) continue;

            const colors = {
                fixed_camera: "#00aaff",
                drone: "#ff6600",
                body_camera: "#00ff88",
            };
            const icons = {
                fixed_camera: "📷",
                drone: "🚁",
                body_camera: "🎥",
            };

            const icon = L.divIcon({
                className: "patrol-marker",
                html: `<div style="font-size:18px;text-shadow:0 0 4px ${colors[e.equipment_type] || '#fff'};">
                    ${icons[e.equipment_type] || "📍"}
                </div>`,
                iconSize: [24, 24],
                iconAnchor: [12, 12],
            });

            const marker = L.marker([e.gps_lat, e.gps_lng], { icon })
                .addTo(this.map)
                .bindPopup(`
                    <strong>${e.name}</strong><br/>
                    ${e.equipment_type}<br/>
                    ${e.is_streaming ? "🔴 Streaming" : "⚫ Idle"}
                `);

            this.markers[`equip_${e.id}`] = marker;
        }

        // Incident markers (SOS)
        for (const inc of this.state.incidents) {
            if (!inc.lat || !inc.lng) continue;
            if (inc.incident_type !== "sos" || inc.state === "closed") continue;

            const icon = L.divIcon({
                className: "patrol-marker sos-pulse",
                html: `<div style="
                    background:#ff0000;
                    width:16px;height:16px;border-radius:50%;
                    border:3px solid #fff;
                    box-shadow:0 0 12px #ff0000;
                    animation: sos-blink 0.5s infinite alternate;
                "></div>`,
                iconSize: [22, 22],
                iconAnchor: [11, 11],
            });

            const marker = L.marker([inc.lat, inc.lng], { icon })
                .addTo(this.map)
                .bindPopup(`<strong>⚠️ SOS</strong><br/>${inc.name}`);

            this.markers[`incident_${inc.id}`] = marker;
        }

        // Gate markers
        for (const g of this.state.gates) {
            if (!g.gps_lat || !g.gps_lng) continue;

            const gateColor = g.is_open ? "#00ff88" : "#ff6600";
            const gateIcon = L.divIcon({
                className: "patrol-marker",
                html: `<div style="
                    font-size:16px;
                    text-shadow: 0 0 6px ${gateColor};
                    filter: drop-shadow(0 0 3px ${gateColor});
                ">${g.is_open ? "🔓" : "🔒"}</div>`,
                iconSize: [20, 20],
                iconAnchor: [10, 10],
            });

            const marker = L.marker([g.gps_lat, g.gps_lng], { icon: gateIcon })
                .addTo(this.map)
                .bindPopup(`
                    <strong>${g.name}</strong><br/>
                    ${g.gate_type}<br/>
                    ${g.is_open ? "🟢 เปิด" : "🔴 ปิด"}
                `);

            this.markers[`gate_${g.id}`] = marker;
        }

        // Sighting markers (recent detections)
        if (this.state.showSightings) {
            for (const s of this.state.sightings) {
                if (!s.lat || !s.lng) continue;

                // สี / icon ตาม match_status + sighting_type
                const sightingStyles = {
                    // คน
                    "person_known_soldier": { color: "#2196F3", icon: "👤", label: "เจ้าหน้าที่" },
                    "person_known_staff": { color: "#2196F3", icon: "👤", label: "เจ้าหน้าที่" },
                    "person_known_vip": { color: "#9C27B0", icon: "⭐", label: "VIP" },
                    "person_known_visitor": { color: "#FFC107", icon: "🧑", label: "ผู้มาติดต่อ" },
                    "person_known_contractor": { color: "#FFC107", icon: "🧑", label: "ผู้รับเหมา" },
                    "person_unknown": { color: "#9E9E9E", icon: "❓", label: "ไม่รู้จัก" },
                    "person_watchlist": { color: "#F44336", icon: "🚨", label: "Watchlist" },
                    // รถ
                    "vehicle_known": { color: "#333333", icon: "🚗", label: "รถรู้จัก" },
                    "vehicle_unknown": { color: "#795548", icon: "🚗", label: "รถไม่รู้จัก" },
                    "vehicle_watchlist": { color: "#F44336", icon: "🚨", label: "รถ Watchlist" },
                    // เรือ
                    "vessel_known": { color: "#0077BE", icon: "🚢", label: "เรือรู้จัก" },
                    "vessel_unknown": { color: "#4FC3F7", icon: "⛵", label: "เรือไม่รู้จัก" },
                    "vessel_watchlist": { color: "#F44336", icon: "🚨", label: "เรือ Watchlist" },
                };

                // Determine style key
                let styleKey;
                if (s.sighting_type === "vessel") {
                    styleKey = `vessel_${s.match_status}`;
                } else if (s.sighting_type === "vehicle") {
                    styleKey = `vehicle_${s.match_status}`;
                } else {
                    // For known persons, try to get person_type
                    if (s.match_status === "known" && s.person_id) {
                        // Default to staff if we can't determine type
                        styleKey = "person_known_staff";
                    } else {
                        styleKey = `person_${s.match_status}`;
                    }
                }

                const style = sightingStyles[styleKey] || { color: "#9E9E9E", icon: "❓", label: "?" };

                const sIcon = L.divIcon({
                    className: "patrol-marker sighting-marker",
                    html: `<div style="
                        font-size:14px;
                        background:${style.color};
                        width:24px;height:24px;
                        border-radius:50%;
                        border:2px solid rgba(255,255,255,0.8);
                        display:flex;align-items:center;justify-content:center;
                        box-shadow:0 0 6px ${style.color};
                        opacity:0.85;
                    ">${style.icon}</div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12],
                });

                const popupContent = `
                    <strong>${style.label}</strong><br/>
                    ${s.person_name || s.detected_plate || "ไม่ทราบ"}<br/>
                    กล้อง: ${s.equipment_id ? s.equipment_id[1] : "?"}<br/>
                    ความมั่นใจ: ${s.confidence || 0}%<br/>
                    ${s.direction || ""} ${s.timestamp || ""}
                `;

                const marker = L.marker([s.lat, s.lng], { icon: sIcon })
                    .addTo(this.map)
                    .bindPopup(popupContent);

                this.markers[`sighting_${s.id}`] = marker;
            }
        }
    }

    async selectSoldier(soldier) {
        this.state.selectedSoldierId = soldier.id;
        if (this.map && soldier.last_lat && soldier.last_lng) {
            this.map.setView([soldier.last_lat, soldier.last_lng], 16);
        }
    }

    async showTrack(soldierId) {
        if (this.trackLine) {
            this.trackLine.remove();
            this.trackLine = null;
        }

        const logs = await rpc("/patrol/api/gps_track", {
            soldier_id: soldierId,
            limit: 1000,
        });

        if (logs.length === 0) return;

        const points = logs.map((l) => [l.lat, l.lng]);
        this.trackLine = L.polyline(points, {
            color: "#00ff88",
            weight: 3,
            opacity: 0.8,
        }).addTo(this.map);

        this.map.fitBounds(this.trackLine.getBounds(), { padding: [30, 30] });
    }

    clearTrack() {
        if (this.trackLine) {
            this.trackLine.remove();
            this.trackLine = null;
        }
    }

    toggleSightings() {
        this.state.showSightings = !this.state.showSightings;
        this.updateMarkers();
    }

    selectMission(missionId) {
        this.state.selectedMissionId = missionId || null;
        this.loadData();
    }

    openSoldierForm(soldierId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "patrol.soldier",
            res_id: soldierId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openIncidentForm(incidentId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "patrol.incident",
            res_id: incidentId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ── Video Popup ──

    openVideoPopup(soldier) {
        const streamPath = soldier.stream_path || soldier.callsign;
        this.state.videoPopup = {
            id: soldier.id,
            callsign: soldier.callsign,
            name: soldier.name,
            streamPath,
            state: "connecting",
        };

        // Connect after DOM renders
        setTimeout(() => {
            const videoEl = document.getElementById("popup-video");
            if (!videoEl) return;

            this.popupPlayer = new WhepPlayer(videoEl, this.mediamtxUrl);
            this.popupPlayer.onStateChange = (s) => {
                if (this.state.videoPopup) {
                    this.state.videoPopup.state = s;
                }
            };
            this.popupPlayer.connect(streamPath);
        }, 100);
    }

    closeVideoPopup() {
        if (this.popupPlayer) {
            this.popupPlayer.disconnect();
            this.popupPlayer = null;
        }
        this.state.videoPopup = null;
    }

    // ── Video Grid ──

    toggleGrid() {
        this.state.showGrid = !this.state.showGrid;
        if (this.state.showGrid) {
            this.openGridForOnlineSoldiers();
        } else {
            this.closeAllGridVideos();
        }
    }

    openGridForOnlineSoldiers() {
        const online = this.state.soldiers.filter(
            (s) => s.is_online && s.stream_path
        );
        this.state.videoGrid = online.map((s) => ({
            id: s.id,
            callsign: s.callsign,
            name: s.name,
            streamPath: s.stream_path || s.callsign,
            state: "connecting",
        }));

        // Connect all after DOM
        setTimeout(() => {
            for (const cell of this.state.videoGrid) {
                const videoEl = document.getElementById(`grid-video-${cell.callsign}`);
                if (!videoEl) continue;

                const player = new WhepPlayer(videoEl, this.mediamtxUrl);
                player.onStateChange = (s) => {
                    cell.state = s;
                };
                player.connect(cell.streamPath);
                this.gridPlayers[cell.callsign] = player;
            }
        }, 200);
    }

    closeAllGridVideos() {
        for (const [key, player] of Object.entries(this.gridPlayers)) {
            player.disconnect();
        }
        this.gridPlayers = {};
        this.state.videoGrid = [];
    }

    closeGridVideo(callsign) {
        const player = this.gridPlayers[callsign];
        if (player) {
            player.disconnect();
            delete this.gridPlayers[callsign];
        }
        this.state.videoGrid = this.state.videoGrid.filter(
            (v) => v.callsign !== callsign
        );
    }

    get gridLayoutClass() {
        const count = this.state.videoGrid.length;
        if (count <= 1) return "grid-1";
        if (count <= 2) return "grid-2";
        if (count <= 4) return "grid-4";
        return "grid-9";
    }

    get onlineSoldiers() {
        return this.state.soldiers.filter((s) => s.is_online);
    }

    get offlineSoldiers() {
        return this.state.soldiers.filter((s) => !s.is_online);
    }

    get activeIncidents() {
        return this.state.incidents.filter((i) => i.state !== "closed");
    }
}

registry.category("actions").add("patrol_command_center", CommandCenterDashboard);
