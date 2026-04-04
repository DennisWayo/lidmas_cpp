use axum::{
    Json,
    extract::{Path, State},
};
use chrono::Utc;
use uuid::Uuid;

use crate::{
    app_error::{AppError, AppResult},
    models::{CreateJobRequest, Job, JobStatus, UpdateJobStatusRequest},
    state::AppState,
};

pub async fn list_jobs(State(state): State<AppState>) -> AppResult<Json<Vec<Job>>> {
    let jobs = state.jobs.read().await;
    let mut out: Vec<Job> = jobs.values().cloned().collect();
    out.sort_by_key(|j| j.created_at);
    Ok(Json(out))
}

pub async fn get_job(
    State(state): State<AppState>,
    Path(job_id): Path<Uuid>,
) -> AppResult<Json<Job>> {
    let jobs = state.jobs.read().await;
    let job = jobs
        .get(&job_id)
        .cloned()
        .ok_or_else(|| AppError::NotFound(format!("job {job_id}")))?;
    Ok(Json(job))
}

pub async fn create_job(
    State(state): State<AppState>,
    Json(req): Json<CreateJobRequest>,
) -> AppResult<Json<Job>> {
    if req.dataset_label.trim().is_empty() {
        return Err(AppError::BadRequest(
            "dataset_label cannot be empty".to_string(),
        ));
    }
    if req.decoders.is_empty() {
        return Err(AppError::BadRequest("decoders cannot be empty".to_string()));
    }

    let providers = state.providers.read().await;
    if !providers.contains_key(&req.provider_id) {
        return Err(AppError::NotFound(format!("provider {}", req.provider_id)));
    }
    drop(providers);

    let now = Utc::now();
    let job = Job {
        id: Uuid::new_v4(),
        provider_id: req.provider_id,
        dataset_label: req.dataset_label.trim().to_string(),
        decoders: req
            .decoders
            .into_iter()
            .map(|d| d.trim().to_string())
            .filter(|d| !d.is_empty())
            .collect(),
        priority: req.priority.unwrap_or(5).min(10),
        status: JobStatus::Queued,
        message: None,
        created_at: now,
        updated_at: now,
        started_at: None,
        completed_at: None,
    };
    if job.decoders.is_empty() {
        return Err(AppError::BadRequest(
            "decoders resolved to empty values".to_string(),
        ));
    }

    let mut jobs = state.jobs.write().await;
    jobs.insert(job.id, job.clone());
    Ok(Json(job))
}

pub async fn update_job_status(
    State(state): State<AppState>,
    Path(job_id): Path<Uuid>,
    Json(req): Json<UpdateJobStatusRequest>,
) -> AppResult<Json<Job>> {
    let mut jobs = state.jobs.write().await;
    let job = jobs
        .get_mut(&job_id)
        .ok_or_else(|| AppError::NotFound(format!("job {job_id}")))?;

    if !is_valid_transition(&job.status, &req.status) {
        return Err(AppError::BadRequest(format!(
            "invalid status transition: {:?} -> {:?}",
            job.status, req.status
        )));
    }

    let now = Utc::now();
    if matches!(req.status, JobStatus::Running) && job.started_at.is_none() {
        job.started_at = Some(now);
    }
    if matches!(
        req.status,
        JobStatus::Completed | JobStatus::Failed | JobStatus::Cancelled
    ) {
        job.completed_at = Some(now);
    }
    job.status = req.status;
    job.message = req.message;
    job.updated_at = now;

    Ok(Json(job.clone()))
}

fn is_valid_transition(current: &JobStatus, next: &JobStatus) -> bool {
    if std::mem::discriminant(current) == std::mem::discriminant(next) {
        return true;
    }
    matches!(
        (current, next),
        (JobStatus::Queued, JobStatus::Running)
            | (JobStatus::Queued, JobStatus::Cancelled)
            | (JobStatus::Running, JobStatus::Completed)
            | (JobStatus::Running, JobStatus::Failed)
            | (JobStatus::Running, JobStatus::Cancelled)
    )
}
