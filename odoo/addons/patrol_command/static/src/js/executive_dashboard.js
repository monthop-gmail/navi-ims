/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

class ExecutiveDashboard extends Component {
    static template = "patrol_command.ExecutiveDashboard";

    setup() {
        this.action = useService("action");

        this.state = useState({
            kpi: null,
            trends: [],
            byType: [],
            bySeverity: [],
            loading: true,
        });

        this.refreshInterval = null;

        onMounted(async () => {
            await this.loadData();
            this.refreshInterval = setInterval(() => this.loadData(), 30000);
        });

        onWillUnmount(() => {
            if (this.refreshInterval) clearInterval(this.refreshInterval);
        });
    }

    async loadData() {
        const [kpi, trends, byType, bySeverity] = await Promise.all([
            rpc("/patrol/api/dashboard/kpi"),
            rpc("/patrol/api/dashboard/trends", { days: 14 }),
            rpc("/patrol/api/dashboard/incident_by_type", { days: 30 }),
            rpc("/patrol/api/dashboard/incident_by_severity", { days: 30 }),
        ]);

        this.state.kpi = kpi;
        this.state.trends = trends;
        this.state.byType = byType;
        this.state.bySeverity = bySeverity;
        this.state.loading = false;

        this.renderCharts();
    }

    renderCharts() {
        // Trend bar chart (CSS-only, no library needed)
        // Rendered via template
    }

    get trendMax() {
        if (!this.state.trends.length) return 1;
        return Math.max(...this.state.trends.map((t) => t.incidents), 1);
    }

    openMissions() {
        this.action.doAction("patrol_command.patrol_mission_action");
    }

    openIncidents() {
        this.action.doAction("patrol_command.patrol_incident_action");
    }

    openCommandCenter() {
        this.action.doAction("patrol_command.action_command_center");
    }
}

registry.category("actions").add("patrol_executive_dashboard", ExecutiveDashboard);
