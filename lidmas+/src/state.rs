use std::{collections::HashMap, sync::Arc};

use chrono::{DateTime, Utc};
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::models::{Job, Provider, Run};

#[derive(Clone)]
pub struct AppState {
    pub started_at: DateTime<Utc>,
    pub providers: Arc<RwLock<HashMap<Uuid, Provider>>>,
    pub jobs: Arc<RwLock<HashMap<Uuid, Job>>>,
    pub runs: Arc<RwLock<HashMap<Uuid, Run>>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            started_at: Utc::now(),
            providers: Arc::new(RwLock::new(HashMap::new())),
            jobs: Arc::new(RwLock::new(HashMap::new())),
            runs: Arc::new(RwLock::new(HashMap::new())),
        }
    }
}
