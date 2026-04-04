use axum::{
    Json,
    extract::{Path, State},
};
use chrono::Utc;
use uuid::Uuid;

use crate::{
    app_error::{AppError, AppResult},
    models::{
        AddRunArtifactRequest, CreateRunRequest, Run, RunArtifact, RunStatus,
        UpdateRunStatusRequest,
    },
    state::AppState,
};

pub async fn list_runs(State(state): State<AppState>) -> AppResult<Json<Vec<Run>>> {
    let runs = state.runs.read().await;
    let mut out: Vec<Run> = runs.values().cloned().collect();
    out.sort_by_key(|r| r.created_at);
    Ok(Json(out))
}

pub async fn get_run(
    State(state): State<AppState>,
    Path(run_id): Path<Uuid>,
) -> AppResult<Json<Run>> {
    let runs = state.runs.read().await;
    let run = runs
        .get(&run_id)
        .cloned()
        .ok_or_else(|| AppError::NotFound(format!("run {run_id}")))?;
    Ok(Json(run))
}

pub async fn create_run(
    State(state): State<AppState>,
    Json(req): Json<CreateRunRequest>,
) -> AppResult<Json<Run>> {
    let mut dataset_label = req.dataset_label.unwrap_or_default().trim().to_string();
    let mut decoders = req.decoders.unwrap_or_default();
    let mut provider_id = req.provider_id;

    if let Some(job_id) = req.job_id {
        let jobs = state.jobs.read().await;
        let job = jobs
            .get(&job_id)
            .ok_or_else(|| AppError::NotFound(format!("job {job_id}")))?;
        if provider_id.is_none() {
            provider_id = Some(job.provider_id);
        } else if provider_id != Some(job.provider_id) {
            return Err(AppError::BadRequest(
                "provider_id does not match linked job provider".to_string(),
            ));
        }
        if dataset_label.is_empty() {
            dataset_label = job.dataset_label.clone();
        }
        if decoders.is_empty() {
            decoders = job.decoders.clone();
        }
    }

    let provider_id =
        provider_id.ok_or_else(|| AppError::BadRequest("provider_id is required".to_string()))?;
    if dataset_label.trim().is_empty() {
        return Err(AppError::BadRequest(
            "dataset_label is required".to_string(),
        ));
    }
    if decoders.is_empty() {
        return Err(AppError::BadRequest("decoders cannot be empty".to_string()));
    }

    let providers = state.providers.read().await;
    if !providers.contains_key(&provider_id) {
        return Err(AppError::NotFound(format!("provider {provider_id}")));
    }
    drop(providers);

    decoders = decoders
        .into_iter()
        .map(|d| d.trim().to_string())
        .filter(|d| !d.is_empty())
        .collect();
    if decoders.is_empty() {
        return Err(AppError::BadRequest(
            "decoders resolved to empty values".to_string(),
        ));
    }

    let now = Utc::now();
    let run = Run {
        id: Uuid::new_v4(),
        job_id: req.job_id,
        provider_id,
        dataset_label,
        decoders,
        status: RunStatus::Created,
        message: None,
        artifacts: Vec::new(),
        metrics: None,
        created_at: now,
        updated_at: now,
    };

    let mut runs = state.runs.write().await;
    runs.insert(run.id, run.clone());
    Ok(Json(run))
}

pub async fn update_run_status(
    State(state): State<AppState>,
    Path(run_id): Path<Uuid>,
    Json(req): Json<UpdateRunStatusRequest>,
) -> AppResult<Json<Run>> {
    let mut runs = state.runs.write().await;
    let run = runs
        .get_mut(&run_id)
        .ok_or_else(|| AppError::NotFound(format!("run {run_id}")))?;

    if !is_valid_transition(&run.status, &req.status) {
        return Err(AppError::BadRequest(format!(
            "invalid status transition: {:?} -> {:?}",
            run.status, req.status
        )));
    }

    run.status = req.status;
    run.message = req.message;
    run.updated_at = Utc::now();
    Ok(Json(run.clone()))
}

pub async fn add_run_artifact(
    State(state): State<AppState>,
    Path(run_id): Path<Uuid>,
    Json(req): Json<AddRunArtifactRequest>,
) -> AppResult<Json<Run>> {
    if req.name.trim().is_empty() {
        return Err(AppError::BadRequest(
            "artifact name cannot be empty".to_string(),
        ));
    }
    if req.kind.trim().is_empty() {
        return Err(AppError::BadRequest(
            "artifact kind cannot be empty".to_string(),
        ));
    }
    if req.path.trim().is_empty() {
        return Err(AppError::BadRequest(
            "artifact path cannot be empty".to_string(),
        ));
    }

    let mut runs = state.runs.write().await;
    let run = runs
        .get_mut(&run_id)
        .ok_or_else(|| AppError::NotFound(format!("run {run_id}")))?;

    run.artifacts.push(RunArtifact {
        name: req.name,
        kind: req.kind,
        path: req.path,
        sha256: req.sha256,
        created_at: Utc::now(),
    });
    run.updated_at = Utc::now();

    Ok(Json(run.clone()))
}

fn is_valid_transition(current: &RunStatus, next: &RunStatus) -> bool {
    if std::mem::discriminant(current) == std::mem::discriminant(next) {
        return true;
    }
    matches!(
        (current, next),
        (RunStatus::Created, RunStatus::Running)
            | (RunStatus::Created, RunStatus::Cancelled)
            | (RunStatus::Running, RunStatus::Finished)
            | (RunStatus::Running, RunStatus::Failed)
            | (RunStatus::Running, RunStatus::Cancelled)
    )
}
