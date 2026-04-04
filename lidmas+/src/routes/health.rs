use axum::{Json, extract::State};
use chrono::Utc;
use serde::Serialize;

use crate::state::AppState;

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
    pub version: &'static str,
    pub started_at: chrono::DateTime<chrono::Utc>,
    pub uptime_seconds: i64,
}

pub async fn health(State(state): State<AppState>) -> Json<HealthResponse> {
    let now = Utc::now();
    let uptime = (now - state.started_at).num_seconds().max(0);
    Json(HealthResponse {
        status: "ok",
        version: env!("CARGO_PKG_VERSION"),
        started_at: state.started_at,
        uptime_seconds: uptime,
    })
}
