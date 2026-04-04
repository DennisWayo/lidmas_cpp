mod health;
mod jobs;
mod providers;
mod runs;

use axum::{
    Router,
    routing::{get, post},
};

use crate::state::AppState;

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/api/v1/health", get(health::health))
        .route(
            "/api/v1/providers",
            get(providers::list_providers).post(providers::create_provider),
        )
        .route(
            "/api/v1/providers/{provider_id}",
            get(providers::get_provider),
        )
        .route(
            "/api/v1/providers/{provider_id}/validate",
            post(providers::validate_provider_output),
        )
        .route("/api/v1/jobs", get(jobs::list_jobs).post(jobs::create_job))
        .route("/api/v1/jobs/{job_id}", get(jobs::get_job))
        .route(
            "/api/v1/jobs/{job_id}/status",
            post(jobs::update_job_status),
        )
        .route("/api/v1/runs", get(runs::list_runs).post(runs::create_run))
        .route("/api/v1/runs/{run_id}", get(runs::get_run))
        .route(
            "/api/v1/runs/{run_id}/status",
            post(runs::update_run_status),
        )
        .route(
            "/api/v1/runs/{run_id}/artifacts",
            post(runs::add_run_artifact),
        )
        .with_state(state)
}
