import { useMemo, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { useRefreshVendorCalibrations, useVendorCalibrations } from "../../api/hooks";

import {
  coerceSettings,
  loadSettings,
  resetSettings,
  saveSettings,
  type AppSettings,
  type BackupSchedule,
  type DigestCadence,
  type EnvironmentName,
  type EscalationPolicy,
  type ExportFormat,
  type UiDensity,
} from "../../settings/settingsStore";
import {
  THEME_OPTIONS,
  applyTheme,
  getThemeSwatch,
  type ThemeId,
  type ThemeOption,
} from "../../theme/themes";

type SectionKey =
  | "general"
  | "operations"
  | "notifications"
  | "security"
  | "integrations"
  | "backup";

interface SectionDefinition {
  key: SectionKey;
  label: string;
  subtitle: string;
}

const SECTIONS: SectionDefinition[] = [
  {
    key: "general",
    label: "General",
    subtitle: "Environment identity, UI behavior, and presentation settings.",
  },
  {
    key: "operations",
    label: "Operations",
    subtitle: "Execution throughput, failover, and reliability guardrails.",
  },
  {
    key: "notifications",
    label: "Notifications",
    subtitle: "Incident channel delivery and escalation policy.",
  },
  {
    key: "security",
    label: "Security",
    subtitle: "Session controls, masking, and audit-trail posture.",
  },
  {
    key: "integrations",
    label: "Integrations",
    subtitle: "Outbound webhooks, artifact defaults, and platform connectors.",
  },
  {
    key: "backup",
    label: "Backup",
    subtitle: "Snapshot cadence and long-term resilience controls.",
  },
];

function downloadJson(filename: string, payload: unknown): void {
  const text = `${JSON.stringify(payload, null, 2)}\n`;
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function timestampForFile(): string {
  return new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
}

function formatTimestamp(value: string | undefined): string {
  if (!value) {
    return "Not available";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function SettingRow({
  name,
  description,
  children,
}: {
  name: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="setting-row">
      <div className="setting-label">
        <div className="setting-name">{name}</div>
        <div className="setting-description">{description}</div>
      </div>
      <div className="setting-control">{children}</div>
    </div>
  );
}

function ToggleControl({
  value,
  label,
  onChange,
}: {
  value: boolean;
  label: string;
  onChange: () => void;
}) {
  return (
    <button
      className={`toggle ${value ? "active" : ""}`}
      aria-label={label}
      onClick={onChange}
    >
      <span />
    </button>
  );
}

function ThemeCard({
  theme,
  selected,
  onSelect,
}: {
  theme: ThemeOption;
  selected: boolean;
  onSelect: (themeId: ThemeId) => void;
}) {
  const swatch = getThemeSwatch(theme.id);
  return (
    <button
      className={`theme-card ${selected ? "active" : ""}`}
      onClick={() => onSelect(theme.id)}
      type="button"
    >
      <div className="theme-card-header">
        <strong>{theme.label}</strong>
        <span className="theme-family">{theme.family}</span>
      </div>
      <p>{theme.description}</p>
      <div
        className="theme-card-preview"
        style={{
          background: swatch.bg,
          borderColor: swatch.accent,
          color: swatch.text,
        }}
      >
        <span style={{ color: swatch.accent }}>●</span>
        <span>Telemetry view</span>
      </div>
    </button>
  );
}

export function SettingsPage() {
  const [activeSection, setActiveSection] = useState<SectionKey>("general");
  const [savedSettings, setSavedSettings] = useState<AppSettings>(() => loadSettings());
  const [draftSettings, setDraftSettings] = useState<AppSettings>(() => loadSettings());
  const [statusMessage, setStatusMessage] = useState<string>("Settings loaded from local profile.");
  const [statusTone, setStatusTone] = useState<"neutral" | "good" | "warn">("neutral");
  const [lastCalibrationRefreshAt, setLastCalibrationRefreshAt] = useState<string | null>(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const vendorCalibrationsQuery = useVendorCalibrations({ refetchInterval: 30_000 });
  const refreshVendorCalibrations = useRefreshVendorCalibrations();

  const hasUnsavedChanges = useMemo(
    () => JSON.stringify(savedSettings) !== JSON.stringify(draftSettings),
    [savedSettings, draftSettings],
  );
  const calibrationSnapshots = vendorCalibrationsQuery.data?.snapshots ?? [];
  const latestCalibrationCapturedAt = useMemo(() => {
    if (calibrationSnapshots.length === 0) {
      return null;
    }
    let latest = calibrationSnapshots[0].captured_at;
    calibrationSnapshots.forEach((snapshot) => {
      if (snapshot.captured_at > latest) {
        latest = snapshot.captured_at;
      }
    });
    return latest;
  }, [calibrationSnapshots]);
  const calibrationPipelineStatus = refreshVendorCalibrations.isPending
    ? "Refreshing"
    : vendorCalibrationsQuery.isLoading
      ? "Loading"
      : vendorCalibrationsQuery.isError
        ? "Unavailable"
        : "Active";
  const calibrationStatusTone: "neutral" | "good" | "warn" = refreshVendorCalibrations.isPending
    ? "neutral"
    : vendorCalibrationsQuery.isError
      ? "warn"
      : vendorCalibrationsQuery.isLoading
        ? "neutral"
        : "good";

  const coreThemes = THEME_OPTIONS.filter((theme) => theme.family === "auto" || theme.family === "core");
  const gerryThemes = THEME_OPTIONS.filter((theme) => theme.family === "gerry");

  const setField = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setDraftSettings((previous) => ({ ...previous, [key]: value }));
  };

  const onThemeSelect = (themeId: ThemeId) => {
    setDraftSettings((previous) => ({ ...previous, uiThemeId: themeId }));
    applyTheme(themeId, { persist: false });
    setStatusMessage(`Previewing theme: ${THEME_OPTIONS.find((theme) => theme.id === themeId)?.label ?? themeId}`);
    setStatusTone("neutral");
  };

  const saveChanges = () => {
    saveSettings(draftSettings);
    applyTheme(draftSettings.uiThemeId);
    setSavedSettings(draftSettings);
    setStatusMessage("Settings saved successfully.");
    setStatusTone("good");
  };

  const discardChanges = () => {
    setDraftSettings(savedSettings);
    applyTheme(savedSettings.uiThemeId, { persist: false });
    setStatusMessage("Unsaved changes were discarded.");
    setStatusTone("warn");
  };

  const resetToDefaults = () => {
    const defaults = resetSettings();
    applyTheme(defaults.uiThemeId);
    setSavedSettings(defaults);
    setDraftSettings(defaults);
    setStatusMessage("Defaults restored and applied.");
    setStatusTone("warn");
  };

  const exportSettings = () => {
    downloadJson(`lidmas_settings_${timestampForFile()}.json`, draftSettings);
    setStatusMessage("Settings exported to JSON.");
    setStatusTone("good");
  };

  const importSettingsFromFile = async (file: File) => {
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as Partial<AppSettings>;
      const normalized = coerceSettings(parsed);
      setDraftSettings(normalized);
      applyTheme(normalized.uiThemeId, { persist: false });
      setStatusMessage("Settings imported. Review and click Save to persist.");
      setStatusTone("good");
    } catch {
      setStatusMessage("Failed to import settings JSON.");
      setStatusTone("warn");
    }
  };

  const triggerCalibrationRefresh = async () => {
    setStatusMessage("Refreshing vendor calibration snapshots...");
    setStatusTone("neutral");
    try {
      const response = await refreshVendorCalibrations.mutateAsync();
      const snapshotCount = response.catalog?.snapshots?.length ?? calibrationSnapshots.length;
      setLastCalibrationRefreshAt(response.refreshed_at);
      setStatusMessage(
        response.ok
          ? `Vendor calibration refresh completed (${snapshotCount} snapshots).`
          : `Vendor calibration refresh finished with status ${response.exit_code ?? "unknown"}.`,
      );
      setStatusTone(response.ok ? "good" : "warn");
    } catch (error) {
      let message = error instanceof Error ? error.message : "Vendor calibration refresh failed.";
      if (error instanceof ApiError && error.status === 404) {
        message =
          "Calibration API not found on this backend build. Restart LiDMaS+ with the latest backend and retry.";
      }
      setStatusMessage(message);
      setStatusTone("warn");
    }
  };

  const sectionMeta = SECTIONS.find((section) => section.key === activeSection);

  return (
    <>
      <div className="header">
        <h1>Settings</h1>
        <p>Internal control plane configuration for runtime, policy, and UI behavior</p>
      </div>

      <div className="settings-status-row">
        <span className={`settings-status-chip settings-status-${statusTone}`}>{statusMessage}</span>
        <span className={`settings-status-chip ${hasUnsavedChanges ? "settings-status-warn" : "settings-status-good"}`}>
          {hasUnsavedChanges ? "Unsaved changes" : "All changes saved"}
        </span>
      </div>

      <div className="settings-top-actions">
        <button className="btn btn-primary" onClick={saveChanges} disabled={!hasUnsavedChanges}>
          Save Changes
        </button>
        <button className="btn btn-secondary" onClick={discardChanges} disabled={!hasUnsavedChanges}>
          Discard Changes
        </button>
        <button className="btn btn-secondary" onClick={exportSettings}>
          Export JSON
        </button>
        <button className="btn btn-secondary" onClick={() => importInputRef.current?.click()}>
          Import JSON
        </button>
        <button className="btn btn-secondary" onClick={resetToDefaults}>
          Reset Defaults
        </button>
        <input
          ref={importInputRef}
          type="file"
          accept="application/json"
          className="settings-hidden-input"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              void importSettingsFromFile(file);
            }
            event.currentTarget.value = "";
          }}
        />
      </div>

      <div className="settings-grid settings-grid-wide">
        <aside className="settings-sidebar">
          <ul className="settings-menu">
            {SECTIONS.map((section) => (
              <li
                key={section.key}
                className={`settings-item ${activeSection === section.key ? "active" : ""}`}
                onClick={() => setActiveSection(section.key)}
              >
                {section.label}
              </li>
            ))}
          </ul>
        </aside>

        <section className="settings-content">
          <div className="section-title">{sectionMeta?.label} Settings</div>
          <p className="settings-section-subtitle">{sectionMeta?.subtitle}</p>

          {activeSection === "general" ? (
            <>
              <div className="settings-block">
                <div className="settings-block-title">Runtime Identity</div>
                <SettingRow
                  name="System Name"
                  description="Display label for this internal LiDMaS+ control plane instance."
                >
                  <input
                    type="text"
                    className="input-field"
                    value={draftSettings.systemName}
                    onChange={(event) => setField("systemName", event.target.value)}
                  />
                </SettingRow>
                <SettingRow
                  name="Environment"
                  description="Deployment classification used in alert and audit context."
                >
                  <select
                    className="select-field"
                    value={draftSettings.environment}
                    onChange={(event) => setField("environment", event.target.value as EnvironmentName)}
                  >
                    <option value="production">Production</option>
                    <option value="staging">Staging</option>
                    <option value="development">Development</option>
                  </select>
                </SettingRow>
                <SettingRow
                  name="Timezone"
                  description="Default timezone used for rendering relative and absolute timestamps."
                >
                  <select
                    className="select-field"
                    value={draftSettings.timezone}
                    onChange={(event) => setField("timezone", event.target.value)}
                  >
                    <option value="UTC">UTC</option>
                    <option value="America/New_York">America/New_York</option>
                    <option value="Europe/Berlin">Europe/Berlin</option>
                    <option value="Asia/Almaty">Asia/Almaty</option>
                  </select>
                </SettingRow>
                <SettingRow
                  name="Locale"
                  description="Locale used for number/date formatting in dashboards."
                >
                  <select
                    className="select-field"
                    value={draftSettings.locale}
                    onChange={(event) => setField("locale", event.target.value)}
                  >
                    <option value="en-US">en-US</option>
                    <option value="en-GB">en-GB</option>
                    <option value="de-DE">de-DE</option>
                    <option value="fr-FR">fr-FR</option>
                  </select>
                </SettingRow>
                <SettingRow
                  name="UI Density"
                  description="Controls spacing density across cards, tables, and control rows."
                >
                  <select
                    className="select-field"
                    value={draftSettings.uiDensity}
                    onChange={(event) => setField("uiDensity", event.target.value as UiDensity)}
                  >
                    <option value="comfortable">Comfortable</option>
                    <option value="compact">Compact</option>
                  </select>
                </SettingRow>
              </div>

              <div className="settings-block">
                <div className="settings-block-title">Theme Selection</div>
                <p className="settings-note">Core themes and Gerry internal presets. Selection previews instantly.</p>
                <div className="theme-gallery">
                  <div className="theme-gallery-group">
                    <h4>Core</h4>
                    <div className="theme-gallery-grid">
                      {coreThemes.map((theme) => (
                        <ThemeCard
                          key={theme.id}
                          theme={theme}
                          selected={draftSettings.uiThemeId === theme.id}
                          onSelect={onThemeSelect}
                        />
                      ))}
                    </div>
                  </div>
                  <div className="theme-gallery-group">
                    <h4>Gerry Themes</h4>
                    <div className="theme-gallery-grid">
                      {gerryThemes.map((theme) => (
                        <ThemeCard
                          key={theme.id}
                          theme={theme}
                          selected={draftSettings.uiThemeId === theme.id}
                          onSelect={onThemeSelect}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="settings-block">
                <div className="settings-block-title">Developer Ergonomics</div>
                <SettingRow
                  name="Enable Debug Logs"
                  description="Include verbose diagnostic messages from backend integration calls."
                >
                  <ToggleControl
                    value={draftSettings.enableDebugLogs}
                    label="toggle debug logs"
                    onChange={() => setField("enableDebugLogs", !draftSettings.enableDebugLogs)}
                  />
                </SettingRow>
                <SettingRow
                  name="Auto-save Configurations"
                  description="Persist configuration snapshots periodically without explicit save action."
                >
                  <ToggleControl
                    value={draftSettings.autoSaveConfigurations}
                    label="toggle auto-save"
                    onChange={() =>
                      setField("autoSaveConfigurations", !draftSettings.autoSaveConfigurations)
                    }
                  />
                </SettingRow>
              </div>
            </>
          ) : null}

          {activeSection === "operations" ? (
            <div className="settings-block">
              <div className="settings-block-title">Execution & Reliability</div>
              <SettingRow
                name="Max Cache Size (GB)"
                description="Upper bound for memory cache used by run metadata and short-lived telemetry."
              >
                <select
                  className="select-field"
                  value={String(draftSettings.maxCacheSizeGb)}
                  onChange={(event) => setField("maxCacheSizeGb", Number(event.target.value))}
                >
                  <option value="2">2 GB</option>
                  <option value="5">5 GB</option>
                  <option value="10">10 GB</option>
                  <option value="20">20 GB</option>
                </select>
              </SettingRow>
              <SettingRow
                name="Job Timeout (seconds)"
                description="Maximum execution duration before forced timeout of a single job."
              >
                <input
                  type="number"
                  className="input-field settings-input-small"
                  min={60}
                  max={86400}
                  value={draftSettings.jobTimeoutSeconds}
                  onChange={(event) => setField("jobTimeoutSeconds", Number(event.target.value))}
                />
              </SettingRow>
              <SettingRow
                name="Max Parallel Runs"
                description="Concurrency cap for simultaneous run processing."
              >
                <input
                  type="number"
                  className="input-field settings-input-small"
                  min={1}
                  max={512}
                  value={draftSettings.maxParallelRuns}
                  onChange={(event) => setField("maxParallelRuns", Number(event.target.value))}
                />
              </SettingRow>
              <SettingRow
                name="Retry Budget"
                description="Maximum number of retry attempts before marking execution as hard-failed."
              >
                <input
                  type="number"
                  className="input-field settings-input-small"
                  min={0}
                  max={20}
                  value={draftSettings.retryBudget}
                  onChange={(event) => setField("retryBudget", Number(event.target.value))}
                />
              </SettingRow>
              <SettingRow
                name="Provider Auto-failover"
                description="Reschedule impacted workloads automatically when provider health deteriorates."
              >
                <ToggleControl
                  value={draftSettings.providerAutoFailover}
                  label="toggle provider auto-failover"
                  onChange={() =>
                    setField("providerAutoFailover", !draftSettings.providerAutoFailover)
                  }
                />
              </SettingRow>
              <SettingRow
                name="Circuit Breaker"
                description="Pause new scheduling attempts when repeated failures exceed threshold."
              >
                <ToggleControl
                  value={draftSettings.circuitBreakerEnabled}
                  label="toggle circuit breaker"
                  onChange={() =>
                    setField("circuitBreakerEnabled", !draftSettings.circuitBreakerEnabled)
                  }
                />
              </SettingRow>
            </div>
          ) : null}

          {activeSection === "notifications" ? (
            <div className="settings-block">
              <div className="settings-block-title">Alert Delivery Policy</div>
              <SettingRow
                name="Escalation Policy"
                description="Default channel for unresolved critical alerts."
              >
                <select
                  className="select-field"
                  value={draftSettings.escalationPolicy}
                  onChange={(event) =>
                    setField("escalationPolicy", event.target.value as EscalationPolicy)
                  }
                >
                  <option value="pagerduty">PagerDuty</option>
                  <option value="slack">Slack</option>
                  <option value="email">Email</option>
                </select>
              </SettingRow>
              <SettingRow
                name="Digest Cadence"
                description="Grouping interval for low-priority notification digests."
              >
                <select
                  className="select-field"
                  value={draftSettings.digestCadence}
                  onChange={(event) => setField("digestCadence", event.target.value as DigestCadence)}
                >
                  <option value="5m">Every 5 minutes</option>
                  <option value="15m">Every 15 minutes</option>
                  <option value="1h">Hourly</option>
                </select>
              </SettingRow>
              <SettingRow
                name="Email Notifications"
                description="Send high-priority incidents to email recipients."
              >
                <ToggleControl
                  value={draftSettings.emailNotifications}
                  label="toggle email notifications"
                  onChange={() =>
                    setField("emailNotifications", !draftSettings.emailNotifications)
                  }
                />
              </SettingRow>
              <SettingRow
                name="Slack Notifications"
                description="Publish incidents to configured Slack channels."
              >
                <ToggleControl
                  value={draftSettings.slackNotifications}
                  label="toggle slack notifications"
                  onChange={() =>
                    setField("slackNotifications", !draftSettings.slackNotifications)
                  }
                />
              </SettingRow>
              <SettingRow
                name="PagerDuty Escalation"
                description="Escalate critical unresolved incidents into PagerDuty."
              >
                <ToggleControl
                  value={draftSettings.pagerdutyEscalation}
                  label="toggle pagerduty escalation"
                  onChange={() =>
                    setField("pagerdutyEscalation", !draftSettings.pagerdutyEscalation)
                  }
                />
              </SettingRow>
            </div>
          ) : null}

          {activeSection === "security" ? (
            <div className="settings-block">
              <div className="settings-block-title">Access & Audit Controls</div>
              <SettingRow
                name="Two-Factor Authentication"
                description="Require 2FA verification for privileged settings and operational actions."
              >
                <ToggleControl
                  value={draftSettings.twoFactorAuthentication}
                  label="toggle 2fa"
                  onChange={() =>
                    setField("twoFactorAuthentication", !draftSettings.twoFactorAuthentication)
                  }
                />
              </SettingRow>
              <SettingRow
                name="Session Timeout (minutes)"
                description="Maximum idle duration before privileged session invalidation."
              >
                <select
                  className="select-field"
                  value={String(draftSettings.sessionTimeoutMinutes)}
                  onChange={(event) =>
                    setField("sessionTimeoutMinutes", Number(event.target.value))
                  }
                >
                  <option value="15">15 minutes</option>
                  <option value="30">30 minutes</option>
                  <option value="60">60 minutes</option>
                  <option value="120">120 minutes</option>
                </select>
              </SettingRow>
              <SettingRow
                name="Audit Trail Mode"
                description="Level of strictness for retaining and validating operator actions."
              >
                <select
                  className="select-field"
                  value={draftSettings.auditTrailMode}
                  onChange={(event) =>
                    setField("auditTrailMode", event.target.value as AppSettings["auditTrailMode"])
                  }
                >
                  <option value="strict">Strict</option>
                  <option value="standard">Standard</option>
                  <option value="relaxed">Relaxed</option>
                </select>
              </SettingRow>
              <SettingRow
                name="IP Allowlist"
                description="Optional comma-separated CIDR blocks allowed for administrative access."
              >
                <input
                  type="text"
                  className="input-field settings-input-wide"
                  value={draftSettings.ipAllowlist}
                  onChange={(event) => setField("ipAllowlist", event.target.value)}
                  placeholder="10.0.0.0/8,192.168.0.0/16"
                />
              </SettingRow>
              <SettingRow
                name="Data Masking"
                description="Mask sensitive fields in logs, alerts, and exported artifacts."
              >
                <ToggleControl
                  value={draftSettings.dataMasking}
                  label="toggle data masking"
                  onChange={() => setField("dataMasking", !draftSettings.dataMasking)}
                />
              </SettingRow>
            </div>
          ) : null}

          {activeSection === "integrations" ? (
            <>
              <div className="settings-block">
                <div className="settings-block-title">Vendor Calibration Pipeline</div>
                <p className="settings-note">
                  Live vendor calibration snapshots are used to bind compile and injected noise profiles.
                </p>
                <SettingRow
                  name="Pipeline Status"
                  description="Current health of background refresh and catalog availability."
                >
                  <span className={`settings-status-chip settings-status-${calibrationStatusTone}`}>
                    {calibrationPipelineStatus}
                  </span>
                </SettingRow>
                <SettingRow
                  name="Catalog Generated"
                  description="Timestamp of latest generated calibration catalog."
                >
                  <span className="settings-status-chip settings-status-neutral">
                    {formatTimestamp(vendorCalibrationsQuery.data?.generated_at)}
                  </span>
                </SettingRow>
                <SettingRow
                  name="Latest Snapshot Capture"
                  description="Most recent vendor snapshot capture timestamp in catalog."
                >
                  <span className="settings-status-chip settings-status-neutral">
                    {formatTimestamp(latestCalibrationCapturedAt ?? undefined)}
                  </span>
                </SettingRow>
                <SettingRow
                  name="Snapshot Count"
                  description="Number of calibration snapshots currently available."
                >
                  <span className="settings-status-chip settings-status-neutral">
                    {calibrationSnapshots.length}
                  </span>
                </SettingRow>
                <SettingRow
                  name="Refresh Mode"
                  description="Refresh strategy reported by the backend catalog generator."
                >
                  <span className="settings-status-chip settings-status-neutral">
                    {vendorCalibrationsQuery.data?.refresh_mode ?? "unknown"}
                  </span>
                </SettingRow>
                <SettingRow
                  name="Last Manual Refresh"
                  description="Most recent operator-triggered refresh call timestamp."
                >
                  <span className="settings-status-chip settings-status-neutral">
                    {formatTimestamp(lastCalibrationRefreshAt ?? undefined)}
                  </span>
                </SettingRow>
                <SettingRow
                  name="Manual Refresh"
                  description="Trigger immediate calibration ingestion from configured vendor sources."
                >
                  <button
                    className="btn btn-secondary"
                    onClick={() => void triggerCalibrationRefresh()}
                    disabled={refreshVendorCalibrations.isPending}
                  >
                    {refreshVendorCalibrations.isPending ? "Refreshing..." : "Refresh Now"}
                  </button>
                </SettingRow>
              </div>

              <div className="settings-block">
                <div className="settings-block-title">External Integrations</div>
                <SettingRow
                  name="Webhook Endpoint"
                  description="Target endpoint for outbound run and incident events."
                >
                  <input
                    type="text"
                    className="input-field settings-input-wide"
                    value={draftSettings.webhookEndpoint}
                    onChange={(event) => setField("webhookEndpoint", event.target.value)}
                  />
                </SettingRow>
                <SettingRow
                  name="Default Export Format"
                  description="Preferred file format for generated internal artifacts."
                >
                  <select
                    className="select-field"
                    value={draftSettings.defaultExportFormat}
                    onChange={(event) =>
                      setField("defaultExportFormat", event.target.value as ExportFormat)
                    }
                  >
                    <option value="json">JSON</option>
                    <option value="csv">CSV</option>
                    <option value="parquet">Parquet</option>
                  </select>
                </SettingRow>
                <SettingRow
                  name="Artifact Retention (days)"
                  description="Retention period for non-backup artifacts and run outputs."
                >
                  <input
                    type="number"
                    className="input-field settings-input-small"
                    min={1}
                    max={3650}
                    value={draftSettings.artifactRetentionDays}
                    onChange={(event) =>
                      setField("artifactRetentionDays", Number(event.target.value))
                    }
                  />
                </SettingRow>
                <SettingRow
                  name="Enable SSO"
                  description="Enable institutional identity provider integration for user login."
                >
                  <ToggleControl
                    value={draftSettings.enableSso}
                    label="toggle sso"
                    onChange={() => setField("enableSso", !draftSettings.enableSso)}
                  />
                </SettingRow>
              </div>
            </>
          ) : null}

          {activeSection === "backup" ? (
            <div className="settings-block">
              <div className="settings-block-title">Backup & Recovery</div>
              <SettingRow
                name="Backup Schedule"
                description="How often full configuration and metadata snapshots are produced."
              >
                <select
                  className="select-field"
                  value={draftSettings.backupSchedule}
                  onChange={(event) =>
                    setField("backupSchedule", event.target.value as BackupSchedule)
                  }
                >
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
              </SettingRow>
              <SettingRow
                name="Backup Retention (days)"
                description="Maximum retention window for backup snapshots."
              >
                <input
                  type="number"
                  className="input-field settings-input-small"
                  min={1}
                  max={3650}
                  value={draftSettings.backupRetentionDays}
                  onChange={(event) =>
                    setField("backupRetentionDays", Number(event.target.value))
                  }
                />
              </SettingRow>
              <SettingRow
                name="Offsite Replication"
                description="Replicate backups to a secondary region for disaster recovery."
              >
                <ToggleControl
                  value={draftSettings.offsiteReplication}
                  label="toggle offsite replication"
                  onChange={() =>
                    setField("offsiteReplication", !draftSettings.offsiteReplication)
                  }
                />
              </SettingRow>
              <SettingRow
                name="Encryption at Rest"
                description="Encrypt stored backups with managed encryption keys."
              >
                <ToggleControl
                  value={draftSettings.encryptionAtRest}
                  label="toggle encryption at rest"
                  onChange={() =>
                    setField("encryptionAtRest", !draftSettings.encryptionAtRest)
                  }
                />
              </SettingRow>
            </div>
          ) : null}

          <div className="button-group">
            <button className="btn btn-primary" onClick={saveChanges} disabled={!hasUnsavedChanges}>
              Save Changes
            </button>
            <button className="btn btn-secondary" onClick={discardChanges} disabled={!hasUnsavedChanges}>
              Discard
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
