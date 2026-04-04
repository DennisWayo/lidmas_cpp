use axum::{
    Json,
    extract::{Path, State},
};
use chrono::Utc;
use uuid::Uuid;

use crate::{
    app_error::{AppError, AppResult},
    models::{CreateProviderRequest, Provider, ValidateProviderOutputRequest, ValidationReport},
    state::AppState,
};

pub async fn list_providers(State(state): State<AppState>) -> AppResult<Json<Vec<Provider>>> {
    let providers = state.providers.read().await;
    let mut out: Vec<Provider> = providers.values().cloned().collect();
    out.sort_by_key(|p| p.created_at);
    Ok(Json(out))
}

pub async fn get_provider(
    State(state): State<AppState>,
    Path(provider_id): Path<Uuid>,
) -> AppResult<Json<Provider>> {
    let providers = state.providers.read().await;
    let provider = providers
        .get(&provider_id)
        .cloned()
        .ok_or_else(|| AppError::NotFound(format!("provider {provider_id}")))?;
    Ok(Json(provider))
}

pub async fn create_provider(
    State(state): State<AppState>,
    Json(req): Json<CreateProviderRequest>,
) -> AppResult<Json<Provider>> {
    if req.name.trim().is_empty() {
        return Err(AppError::BadRequest(
            "provider name cannot be empty".to_string(),
        ));
    }
    if req.supported_formats.is_empty() {
        return Err(AppError::BadRequest(
            "supported_formats cannot be empty".to_string(),
        ));
    }
    let now = Utc::now();
    let provider = Provider {
        id: Uuid::new_v4(),
        name: req.name.trim().to_string(),
        kind: req.kind,
        contact_email: req.contact_email,
        supported_formats: req
            .supported_formats
            .into_iter()
            .map(|v| v.trim().to_string())
            .filter(|v| !v.is_empty())
            .collect(),
        notes: req.notes,
        created_at: now,
        updated_at: now,
    };
    if provider.supported_formats.is_empty() {
        return Err(AppError::BadRequest(
            "supported_formats resolved to empty values".to_string(),
        ));
    }
    let mut providers = state.providers.write().await;
    providers.insert(provider.id, provider.clone());
    Ok(Json(provider))
}

pub async fn validate_provider_output(
    State(state): State<AppState>,
    Path(provider_id): Path<Uuid>,
    Json(req): Json<ValidateProviderOutputRequest>,
) -> AppResult<Json<ValidationReport>> {
    let providers = state.providers.read().await;
    if !providers.contains_key(&provider_id) {
        return Err(AppError::NotFound(format!("provider {provider_id}")));
    }
    drop(providers);

    if req.dataset_label.trim().is_empty() {
        return Err(AppError::BadRequest(
            "dataset_label cannot be empty".to_string(),
        ));
    }

    let line_coverage_ok = req.response_lines == req.request_lines;
    let parse_integrity_ok = req.request_parse_errors == 0 && req.response_parse_errors == 0;
    let decoder_name_integrity_ok = req.decoder_name_mismatch_count == 0;
    let warning_rate = if req.response_lines > 0 {
        Some(req.warning_no_syndrome_count.unwrap_or(0) as f64 / req.response_lines as f64)
    } else {
        None
    };
    let overall_ok = line_coverage_ok && parse_integrity_ok && decoder_name_integrity_ok;

    let mut checks = Vec::new();
    if line_coverage_ok {
        checks.push("line coverage check passed".to_string());
    } else {
        checks.push("line coverage mismatch: response_lines != request_lines".to_string());
    }
    if parse_integrity_ok {
        checks.push("parse integrity check passed".to_string());
    } else {
        checks.push("parse integrity failed: nonzero parse errors".to_string());
    }
    if decoder_name_integrity_ok {
        checks.push("decoder-name integrity check passed".to_string());
    } else {
        checks.push("decoder-name integrity failed: mismatched decoder labels".to_string());
    }

    Ok(Json(ValidationReport {
        provider_id,
        dataset_label: req.dataset_label,
        line_coverage_ok,
        parse_integrity_ok,
        decoder_name_integrity_ok,
        warning_rate,
        overall_ok,
        checks,
        checked_at: Utc::now(),
    }))
}
