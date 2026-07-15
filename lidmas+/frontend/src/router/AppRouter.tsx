import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../ui/AppShell";
import { AlertsPage } from "../ui/pages/AlertsPage";
import { DecoderDashboard } from "../ui/pages/DecoderDashboard";
import { EnhancedProvidersPage } from "../ui/pages/EnhancedProvidersPage";
import { HelpPage } from "../ui/pages/HelpPage";
import { HardwareApiPage } from "../ui/pages/HardwareApiPage";
import { JobsPage } from "../ui/pages/JobsPage";
import { LogsPage } from "../ui/pages/LogsPage";
import { SettingsPage } from "../ui/pages/SettingsPage";
import { AccessGate } from "../ui/security/AccessGate";
import { TelemetryPage } from "../ui/pages/TelemetryPage";
import { ValidationPage } from "../ui/pages/ValidationPage";

export function AppRouter() {
  return (
    <AccessGate>
      <AppShell>
        <Routes>
          <Route path="/" element={<Navigate to="/decoder/scientific" replace />} />
          <Route path="/decoder" element={<Navigate to="/decoder/scientific" replace />} />
          <Route path="/decoder/scientific" element={<DecoderDashboard />} />
          <Route path="/decoder/telemetry" element={<TelemetryPage />} />
          <Route path="/decoder/validation" element={<ValidationPage />} />
          <Route path="/decoder/logs" element={<LogsPage />} />
          <Route path="/runs" element={<JobsPage />} />
          <Route path="/providers" element={<EnhancedProvidersPage />} />
          <Route path="/observability" element={<AlertsPage />} />
          <Route path="/jobs" element={<Navigate to="/runs" replace />} />
          <Route path="/hardware-api" element={<HardwareApiPage />} />
          <Route path="/dashboard" element={<Navigate to="/decoder/scientific" replace />} />
          <Route path="/validation" element={<Navigate to="/decoder/validation" replace />} />
          <Route path="/telemetry" element={<Navigate to="/decoder/telemetry" replace />} />
          <Route path="/logs" element={<Navigate to="/decoder/logs" replace />} />
          <Route path="/alerts" element={<Navigate to="/observability" replace />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/help" element={<HelpPage />} />
          <Route path="*" element={<Navigate to="/decoder/scientific" replace />} />
        </Routes>
      </AppShell>
    </AccessGate>
  );
}
