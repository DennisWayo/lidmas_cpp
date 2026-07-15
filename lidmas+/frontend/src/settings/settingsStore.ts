import type { ThemeId } from "../theme/themes";

export const SETTINGS_STORAGE_KEY = "lidmas.settings.v1";

export type EnvironmentName = "production" | "staging" | "development";
export type UiDensity = "comfortable" | "compact";
export type EscalationPolicy = "pagerduty" | "slack" | "email";
export type DigestCadence = "5m" | "15m" | "1h";
export type ExportFormat = "json" | "csv" | "parquet";
export type BackupSchedule = "hourly" | "daily" | "weekly";
export type AuditTrailMode = "strict" | "standard" | "relaxed";

export interface AppSettings {
  systemName: string;
  environment: EnvironmentName;
  uiThemeId: ThemeId;
  uiDensity: UiDensity;
  timezone: string;
  locale: string;
  enableDebugLogs: boolean;
  autoSaveConfigurations: boolean;

  maxCacheSizeGb: number;
  jobTimeoutSeconds: number;
  providerAutoFailover: boolean;
  maxParallelRuns: number;
  retryBudget: number;
  circuitBreakerEnabled: boolean;

  emailNotifications: boolean;
  slackNotifications: boolean;
  pagerdutyEscalation: boolean;
  escalationPolicy: EscalationPolicy;
  digestCadence: DigestCadence;

  twoFactorAuthentication: boolean;
  sessionTimeoutMinutes: number;
  ipAllowlist: string;
  auditTrailMode: AuditTrailMode;
  dataMasking: boolean;

  webhookEndpoint: string;
  defaultExportFormat: ExportFormat;
  artifactRetentionDays: number;
  enableSso: boolean;

  backupSchedule: BackupSchedule;
  offsiteReplication: boolean;
  backupRetentionDays: number;
  encryptionAtRest: boolean;
}

export const DEFAULT_SETTINGS: AppSettings = {
  systemName: "LiDMaS+ Decoder",
  environment: "production",
  uiThemeId: "dark-core",
  uiDensity: "comfortable",
  timezone: "UTC",
  locale: "en-US",
  enableDebugLogs: false,
  autoSaveConfigurations: true,

  maxCacheSizeGb: 5,
  jobTimeoutSeconds: 3600,
  providerAutoFailover: true,
  maxParallelRuns: 8,
  retryBudget: 3,
  circuitBreakerEnabled: true,

  emailNotifications: true,
  slackNotifications: true,
  pagerdutyEscalation: true,
  escalationPolicy: "pagerduty",
  digestCadence: "15m",

  twoFactorAuthentication: true,
  sessionTimeoutMinutes: 30,
  ipAllowlist: "",
  auditTrailMode: "strict",
  dataMasking: true,

  webhookEndpoint: "https://api.example.com/lidmas/webhook",
  defaultExportFormat: "json",
  artifactRetentionDays: 30,
  enableSso: false,

  backupSchedule: "daily",
  offsiteReplication: true,
  backupRetentionDays: 90,
  encryptionAtRest: true,
};

function toFiniteNumber(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.max(min, Math.min(max, Math.round(parsed)));
}

function toStringValue(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function toBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function normalizeSettings(input: Partial<AppSettings>): AppSettings {
  const base = { ...DEFAULT_SETTINGS, ...input };
  return {
    ...base,
    systemName: toStringValue(base.systemName, DEFAULT_SETTINGS.systemName).trim() || DEFAULT_SETTINGS.systemName,
    timezone: toStringValue(base.timezone, DEFAULT_SETTINGS.timezone).trim() || DEFAULT_SETTINGS.timezone,
    locale: toStringValue(base.locale, DEFAULT_SETTINGS.locale).trim() || DEFAULT_SETTINGS.locale,
    ipAllowlist: toStringValue(base.ipAllowlist, DEFAULT_SETTINGS.ipAllowlist),
    webhookEndpoint: toStringValue(base.webhookEndpoint, DEFAULT_SETTINGS.webhookEndpoint).trim() || DEFAULT_SETTINGS.webhookEndpoint,
    maxCacheSizeGb: toFiniteNumber(base.maxCacheSizeGb, DEFAULT_SETTINGS.maxCacheSizeGb, 1, 256),
    jobTimeoutSeconds: toFiniteNumber(base.jobTimeoutSeconds, DEFAULT_SETTINGS.jobTimeoutSeconds, 60, 86_400),
    maxParallelRuns: toFiniteNumber(base.maxParallelRuns, DEFAULT_SETTINGS.maxParallelRuns, 1, 512),
    retryBudget: toFiniteNumber(base.retryBudget, DEFAULT_SETTINGS.retryBudget, 0, 20),
    sessionTimeoutMinutes: toFiniteNumber(base.sessionTimeoutMinutes, DEFAULT_SETTINGS.sessionTimeoutMinutes, 5, 480),
    artifactRetentionDays: toFiniteNumber(base.artifactRetentionDays, DEFAULT_SETTINGS.artifactRetentionDays, 1, 3650),
    backupRetentionDays: toFiniteNumber(base.backupRetentionDays, DEFAULT_SETTINGS.backupRetentionDays, 1, 3650),
    autoSaveConfigurations: toBoolean(base.autoSaveConfigurations, DEFAULT_SETTINGS.autoSaveConfigurations),
    enableDebugLogs: toBoolean(base.enableDebugLogs, DEFAULT_SETTINGS.enableDebugLogs),
    providerAutoFailover: toBoolean(base.providerAutoFailover, DEFAULT_SETTINGS.providerAutoFailover),
    circuitBreakerEnabled: toBoolean(base.circuitBreakerEnabled, DEFAULT_SETTINGS.circuitBreakerEnabled),
    emailNotifications: toBoolean(base.emailNotifications, DEFAULT_SETTINGS.emailNotifications),
    slackNotifications: toBoolean(base.slackNotifications, DEFAULT_SETTINGS.slackNotifications),
    pagerdutyEscalation: toBoolean(base.pagerdutyEscalation, DEFAULT_SETTINGS.pagerdutyEscalation),
    twoFactorAuthentication: toBoolean(base.twoFactorAuthentication, DEFAULT_SETTINGS.twoFactorAuthentication),
    dataMasking: toBoolean(base.dataMasking, DEFAULT_SETTINGS.dataMasking),
    enableSso: toBoolean(base.enableSso, DEFAULT_SETTINGS.enableSso),
    offsiteReplication: toBoolean(base.offsiteReplication, DEFAULT_SETTINGS.offsiteReplication),
    encryptionAtRest: toBoolean(base.encryptionAtRest, DEFAULT_SETTINGS.encryptionAtRest),
  };
}

export function coerceSettings(input: Partial<AppSettings>): AppSettings {
  return normalizeSettings(input);
}

export function loadSettings(): AppSettings {
  if (typeof window === "undefined") {
    return DEFAULT_SETTINGS;
  }
  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_SETTINGS;
    }
    const parsed = JSON.parse(raw) as Partial<AppSettings>;
    return coerceSettings(parsed);
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: AppSettings): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(coerceSettings(settings)));
}

export function resetSettings(): AppSettings {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(SETTINGS_STORAGE_KEY);
  }
  return DEFAULT_SETTINGS;
}
