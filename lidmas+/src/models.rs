use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProviderKind {
    Photonic,
    Superconducting,
    TrappedIon,
    Simulated,
    Other,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Provider {
    pub id: Uuid,
    pub name: String,
    pub kind: ProviderKind,
    pub contact_email: Option<String>,
    pub supported_formats: Vec<String>,
    pub notes: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CreateProviderRequest {
    pub name: String,
    pub kind: ProviderKind,
    pub contact_email: Option<String>,
    pub supported_formats: Vec<String>,
    pub notes: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    pub id: Uuid,
    pub provider_id: Uuid,
    pub dataset_label: String,
    pub decoders: Vec<String>,
    pub priority: u8,
    pub status: JobStatus,
    pub message: Option<String>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub started_at: Option<DateTime<Utc>>,
    pub completed_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CreateJobRequest {
    pub provider_id: Uuid,
    pub dataset_label: String,
    pub decoders: Vec<String>,
    pub priority: Option<u8>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct UpdateJobStatusRequest {
    pub status: JobStatus,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RunStatus {
    Created,
    Running,
    Finished,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunArtifact {
    pub name: String,
    pub kind: String,
    pub path: String,
    pub sha256: Option<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunMetrics {
    pub avg_flip_count: Option<f64>,
    pub nonempty_flip_rate: Option<f64>,
    pub syndrome_satisfaction_rate: Option<f64>,
    pub residual_nonzero_rate: Option<f64>,
    pub warning_rate: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Run {
    pub id: Uuid,
    pub job_id: Option<Uuid>,
    pub provider_id: Uuid,
    pub dataset_label: String,
    pub decoders: Vec<String>,
    pub status: RunStatus,
    pub message: Option<String>,
    pub artifacts: Vec<RunArtifact>,
    pub metrics: Option<RunMetrics>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CreateRunRequest {
    pub job_id: Option<Uuid>,
    pub provider_id: Option<Uuid>,
    pub dataset_label: Option<String>,
    pub decoders: Option<Vec<String>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct UpdateRunStatusRequest {
    pub status: RunStatus,
    pub message: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AddRunArtifactRequest {
    pub name: String,
    pub kind: String,
    pub path: String,
    pub sha256: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ValidateProviderOutputRequest {
    pub dataset_label: String,
    pub request_lines: u64,
    pub response_lines: u64,
    pub request_parse_errors: u64,
    pub response_parse_errors: u64,
    pub decoder_name_mismatch_count: u64,
    pub warning_no_syndrome_count: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ValidationReport {
    pub provider_id: Uuid,
    pub dataset_label: String,
    pub line_coverage_ok: bool,
    pub parse_integrity_ok: bool,
    pub decoder_name_integrity_ok: bool,
    pub warning_rate: Option<f64>,
    pub overall_ok: bool,
    pub checks: Vec<String>,
    pub checked_at: DateTime<Utc>,
}
