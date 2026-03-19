/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS, loadCSS } from "@web/core/assets";

class CommandCenterDashboard extends Component {
    static template = "patrol_command.CommandCenterDashboard";

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");

        this.state = useState({
            soldiers: [],
            equipment: [],
            missions: [],
            incidents: [],
            stats: {},
            selectedMissionId: null,
            selectedSoldierId: null,
            showTrack: false,
            view: "map", // "map" or "grid"
        });

        this.map = null;
        this.markers = {};
        this.trackLine = null;
        this.missionLayers = {};
        this.refreshInterval = null;

        onMounted(async () => {
            await this.initMap();
            await this.loadData();
            this.refreshInterval = setInterval(() => this.loadData(), 5000);
        });

        onWillUnmount(() => {
            if (this.refreshInterval) clearInterval(this.refreshInterval);
            if (this.map) this.map.remove();
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
        const [soldiers, equipment, missions, incidents, stats] = await Promise.all([
            this.rpc("/patrol/api/soldiers", { mission_id: missionId }),
            this.rpc("/patrol/api/equipment", { mission_id: missionId }),
            this.rpc("/patrol/api/missions", { state: "active" }),
            this.rpc("/patrol/api/incidents", { mission_id: missionId }),
            this.rpc("/patrol/api/stats", { mission_id: missionId }),
        ]);

        this.state.soldiers = soldiers;
        this.state.equipment = equipment;
        this.state.missions = missions;
        this.state.incidents = incidents;
        this.state.stats = stats;

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

            marker.on("click", () => this.selectSoldier(s));
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

        const logs = await this.rpc("/patrol/api/gps_track", {
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
