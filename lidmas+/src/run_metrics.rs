use std::collections::{HashMap, HashSet};

use crate::models::{
    DecoderExactTelemetry, DecoderIntervention, Run, RunDecoderRanking, RunMetrics, RunTelemetry,
};

const EPSILON: f64 = 1e-12;

pub fn derive_run_metrics(run: &Run, telemetry: &RunTelemetry) -> RunMetrics {
    let physical_error_rate = average(
        telemetry
            .noise_samples
            .iter()
            .map(|sample| sample.physical_error_rate),
    );
    let warning_rate = telemetry.warning_rate.or_else(|| {
        physical_error_rate.map(|per| {
            if per <= 0.0 {
                0.0
            } else {
                (per * 30.0).clamp(0.0, 1.0)
            }
        })
    });

    let avg_flip_count = average(
        telemetry
            .decoder_interventions
            .iter()
            .map(|intervention| intervention.flips as f64),
    );
    let nonempty_flip_rate = ratio(
        telemetry.decoder_interventions.len(),
        telemetry
            .decoder_interventions
            .iter()
            .filter(|intervention| intervention.flips > 0)
            .count(),
    );
    let residual_nonzero_rate = ratio(
        telemetry.decoder_interventions.len(),
        telemetry
            .decoder_interventions
            .iter()
            .filter(|intervention| intervention.residual_weight > 0)
            .count(),
    );

    let triggered_count = telemetry
        .syndrome_samples
        .iter()
        .filter(|sample| sample.is_triggered || sample.value != 0)
        .count();
    let triggered_rate = ratio(telemetry.syndrome_samples.len(), triggered_count).unwrap_or(0.0);
    let syndrome_satisfaction_rate = ratio(
        telemetry.syndrome_samples.len(),
        telemetry
            .syndrome_samples
            .iter()
            .filter(|sample| !sample.is_triggered && sample.value == 0)
            .count(),
    );

    let baseline_logical_error_rate = physical_error_rate.map(|per| {
        let warning = warning_rate.unwrap_or(0.0).clamp(0.0, 1.0);
        let baseline_multiplier = 1.0 + 0.45 * warning + 0.85 * triggered_rate;
        (per * baseline_multiplier).clamp(EPSILON, 1.0)
    });

    let exact_rankings = build_exact_decoder_rankings(telemetry, triggered_count as f64, run);
    let has_exact = !exact_rankings.is_empty();

    let estimated_rankings = if has_exact {
        Vec::new()
    } else {
        build_estimated_decoder_rankings(
            run,
            telemetry,
            baseline_logical_error_rate,
            triggered_count as f64,
        )
    };

    let decoder_rankings = if has_exact {
        exact_rankings
    } else {
        estimated_rankings
    };

    let (best_decoder, logical_error_rate) = decoder_rankings
        .first()
        .map(|entry| (Some(entry.decoder.clone()), Some(entry.logical_error_rate)))
        .unwrap_or((run.decoders.first().cloned(), baseline_logical_error_rate));

    let (logical_error_rate_source, scientific_validation_ready, ler_per_gate_triggered) =
        if has_exact {
            let gate = match (logical_error_rate, physical_error_rate) {
                (Some(ler), Some(per)) => Some(ler >= per),
                _ => None,
            };
            (Some("exact".to_string()), Some(true), gate)
        } else {
            (Some("estimated".to_string()), Some(false), None)
        };
    let ler_per_gate_passed = ler_per_gate_triggered.map(|triggered| !triggered);

    let best_encoder_state = if has_exact {
        find_best_exact_encoder_state(best_decoder.as_deref(), telemetry)
    } else {
        suggest_best_encoder_state(run, physical_error_rate, logical_error_rate)
    };

    RunMetrics {
        avg_flip_count,
        nonempty_flip_rate,
        syndrome_satisfaction_rate,
        residual_nonzero_rate,
        warning_rate,
        physical_error_rate,
        baseline_logical_error_rate,
        logical_error_rate,
        ler_per_gate_triggered,
        ler_per_gate_passed,
        logical_error_rate_source,
        scientific_validation_ready,
        best_decoder,
        best_encoder_state,
        decoder_rankings: (!decoder_rankings.is_empty()).then_some(decoder_rankings),
    }
}

fn build_estimated_decoder_rankings(
    run: &Run,
    telemetry: &RunTelemetry,
    baseline_logical_error_rate: Option<f64>,
    triggered_count: f64,
) -> Vec<RunDecoderRanking> {
    let baseline_ler = baseline_logical_error_rate.unwrap_or(EPSILON).max(EPSILON);
    let stabilizer_scale = (telemetry.stabilizer_count.max(1) as f64).max(1.0);

    let mut names = Vec::new();
    let mut seen_names = HashSet::new();
    for decoder in run.decoders.iter().chain(
        telemetry
            .decoder_interventions
            .iter()
            .map(|entry| &entry.decoder),
    ) {
        let trimmed = decoder.trim();
        if trimmed.is_empty() {
            continue;
        }
        let key = trimmed.to_ascii_lowercase();
        if seen_names.insert(key) {
            names.push(trimmed.to_string());
        }
    }

    let mut grouped: HashMap<String, Vec<&DecoderIntervention>> = HashMap::new();
    for intervention in &telemetry.decoder_interventions {
        let key = intervention.decoder.trim().to_ascii_lowercase();
        if key.is_empty() {
            continue;
        }
        grouped.entry(key).or_default().push(intervention);
    }

    let mut rankings = Vec::new();
    for decoder in names {
        let key = decoder.to_ascii_lowercase();
        let Some(observations) = grouped.get(&key) else {
            continue;
        };

        let obs_count = observations.len() as f64;
        if obs_count <= 0.0 {
            continue;
        }

        let flips_total = observations
            .iter()
            .map(|entry| entry.flips as f64)
            .sum::<f64>();
        let avg_flips = flips_total / obs_count;
        let residual_total = observations
            .iter()
            .map(|entry| entry.residual_weight as f64)
            .sum::<f64>();
        let avg_residual = residual_total / obs_count;
        let residual_nonzero_rate = observations
            .iter()
            .filter(|entry| entry.residual_weight > 0)
            .count() as f64
            / obs_count;

        let base_efficiency = if triggered_count > 0.0 {
            ((triggered_count - residual_total).max(0.0) / triggered_count).clamp(0.0, 1.0)
        } else {
            (1.0 - residual_nonzero_rate).clamp(0.0, 1.0)
        };
        let activity_bonus =
            (flips_total / (flips_total + triggered_count.max(1.0) + 1.0)).clamp(0.0, 0.18);
        let correction_efficiency = (base_efficiency + activity_bonus).clamp(0.0, 1.0);

        let normalized_flips = (avg_flips / (stabilizer_scale + 1.0)).clamp(0.0, 2.0);
        let normalized_residual = (avg_residual / (stabilizer_scale + 1.0)).clamp(0.0, 2.0);
        let multiplier = (0.12
            + 0.18 * residual_nonzero_rate
            + 0.40 * normalized_residual
            + 0.10 * normalized_flips
            + 0.30 * (1.0 - correction_efficiency))
            .clamp(0.05, 1.75);

        rankings.push(RunDecoderRanking {
            decoder,
            logical_error_rate: (baseline_ler * multiplier).clamp(EPSILON, 1.0),
            avg_flips,
            residual_nonzero_rate,
            correction_efficiency,
        });
    }

    rankings.sort_by(|left, right| left.logical_error_rate.total_cmp(&right.logical_error_rate));
    rankings
}

fn build_exact_decoder_rankings(
    telemetry: &RunTelemetry,
    triggered_count: f64,
    run: &Run,
) -> Vec<RunDecoderRanking> {
    let Some(entries) = telemetry.decoder_exact_metrics.as_ref() else {
        return Vec::new();
    };

    // Build allowed decoder set from the run declaration (defensive: only consider decoders
    // that were requested for this run).
    let allowed: HashSet<String> = run
        .decoders
        .iter()
        .map(|d| d.trim().to_ascii_lowercase())
        .filter(|s| !s.is_empty())
        .collect();

    let mut grouped: HashMap<String, Vec<&DecoderIntervention>> = HashMap::new();
    for intervention in &telemetry.decoder_interventions {
        let key = intervention.decoder.trim().to_ascii_lowercase();
        if key.is_empty() {
            continue;
        }
        grouped.entry(key).or_default().push(intervention);
    }

    let stabilizer_scale = (telemetry.stabilizer_count.max(1) as f64).max(1.0);
    let mut rankings = Vec::new();
    let mut seen = HashSet::new();

    for entry in entries {
        let decoder = entry.decoder.trim();
        if decoder.is_empty() || entry.trials == 0 || entry.logical_failures > entry.trials {
            continue;
        }
        let key = decoder.to_ascii_lowercase();
        // Skip exact entries for decoders that were not part of the run (defense-in-depth).
        if !allowed.contains(&key) {
            continue;
        }
        if !seen.insert(key.clone()) {
            continue;
        }

        let (avg_flips, residual_nonzero_rate, correction_efficiency) =
            if let Some(obs) = grouped.get(&key) {
                summarize_interventions(obs, triggered_count, stabilizer_scale)
            } else {
                (0.0, 0.0, 0.0)
            };

        rankings.push(RunDecoderRanking {
            decoder: decoder.to_string(),
            logical_error_rate: (entry.logical_failures as f64 / entry.trials as f64)
                .clamp(0.0, 1.0),
            avg_flips,
            residual_nonzero_rate,
            correction_efficiency,
        });
    }

    rankings.sort_by(|left, right| left.logical_error_rate.total_cmp(&right.logical_error_rate));
    rankings
}

fn summarize_interventions(
    observations: &[&DecoderIntervention],
    triggered_count: f64,
    stabilizer_scale: f64,
) -> (f64, f64, f64) {
    let obs_count = observations.len() as f64;
    if obs_count <= 0.0 {
        return (0.0, 0.0, 0.0);
    }

    let flips_total = observations
        .iter()
        .map(|entry| entry.flips as f64)
        .sum::<f64>();
    let avg_flips = flips_total / obs_count;
    let residual_total = observations
        .iter()
        .map(|entry| entry.residual_weight as f64)
        .sum::<f64>();
    let avg_residual = residual_total / obs_count;
    let residual_nonzero_rate = observations
        .iter()
        .filter(|entry| entry.residual_weight > 0)
        .count() as f64
        / obs_count;

    let base_efficiency = if triggered_count > 0.0 {
        ((triggered_count - residual_total).max(0.0) / triggered_count).clamp(0.0, 1.0)
    } else {
        (1.0 - residual_nonzero_rate).clamp(0.0, 1.0)
    };
    let activity_bonus =
        (flips_total / (flips_total + triggered_count.max(1.0) + 1.0)).clamp(0.0, 0.18);
    let normalized_residual = (avg_residual / (stabilizer_scale + 1.0)).clamp(0.0, 2.0);
    let correction_efficiency =
        (base_efficiency + activity_bonus - 0.12 * normalized_residual).clamp(0.0, 1.0);

    (avg_flips, residual_nonzero_rate, correction_efficiency)
}

fn find_best_exact_encoder_state(
    best_decoder: Option<&str>,
    telemetry: &RunTelemetry,
) -> Option<String> {
    let decoder = best_decoder?.trim();
    if decoder.is_empty() {
        return None;
    }
    let key = decoder.to_ascii_lowercase();
    let entries = telemetry.decoder_exact_metrics.as_ref()?;

    let mut best: Option<&DecoderExactTelemetry> = None;
    for entry in entries {
        if entry.decoder.trim().to_ascii_lowercase() != key {
            continue;
        }
        if entry.trials == 0 || entry.logical_failures > entry.trials {
            continue;
        }
        match best {
            None => best = Some(entry),
            Some(current) => {
                let lhs = entry.logical_failures as f64 / entry.trials as f64;
                let rhs = current.logical_failures as f64 / current.trials as f64;
                if lhs < rhs {
                    best = Some(entry);
                }
            }
        }
    }

    best.and_then(|entry| entry.encoder_state.clone())
}

fn suggest_best_encoder_state(
    run: &Run,
    physical_error_rate: Option<f64>,
    logical_error_rate: Option<f64>,
) -> Option<String> {
    let per = physical_error_rate?;
    let ler = logical_error_rate.unwrap_or(per).max(EPSILON);
    let ratio = (ler / per.max(EPSILON)).clamp(0.0, 8.0);

    let dataset = run.dataset_label.to_ascii_lowercase();
    let is_gkp_family = dataset.contains("gkp")
        || dataset.contains("xanadu")
        || run
            .decoders
            .iter()
            .any(|decoder| decoder.to_ascii_lowercase().contains("gkp"));

    let distance = if per <= 0.012 && ratio <= 0.95 {
        7
    } else if per <= 0.03 && ratio <= 1.15 {
        5
    } else {
        3
    };
    let family = if is_gkp_family {
        "gkp_surface"
    } else {
        "surface_code"
    };

    Some(format!("{family}_d{distance}"))
}

fn average(values: impl Iterator<Item = f64>) -> Option<f64> {
    let mut total = 0.0f64;
    let mut count = 0usize;
    for value in values {
        if !value.is_finite() {
            continue;
        }
        total += value;
        count += 1;
    }
    if count == 0 {
        None
    } else {
        Some(total / count as f64)
    }
}

fn ratio(total: usize, numerator: usize) -> Option<f64> {
    if total == 0 {
        None
    } else {
        Some((numerator as f64 / total as f64).clamp(0.0, 1.0))
    }
}

#[cfg(test)]
mod tests {
    use chrono::Utc;
    use uuid::Uuid;

    use super::derive_run_metrics;
    use crate::models::{
        DecoderExactTelemetry, DecoderIntervention, NoiseSample, Run, RunStatus, RunTelemetry,
        SyndromeSample,
    };

    #[test]
    fn computes_gate_and_best_decoder_for_stable_run() {
        let run = test_run("xanadu_gkp_fixture", &["mwpm", "uf", "bp"]);
        let telemetry = test_telemetry(
            vec![0.009, 0.011, 0.010],
            vec![
                ("mwpm", 3, 1),
                ("mwpm", 4, 1),
                ("uf", 4, 2),
                ("uf", 5, 2),
                ("bp", 6, 4),
                ("bp", 7, 5),
            ],
            vec![
                ("mwpm", 10_000, 82, Some("gkp_surface_d7")),
                ("uf", 10_000, 103, Some("gkp_surface_d5")),
                ("bp", 10_000, 157, Some("gkp_surface_d5")),
            ],
        );

        let metrics = derive_run_metrics(&run, &telemetry);

        assert_eq!(metrics.best_decoder.as_deref(), Some("mwpm"));
        assert_eq!(metrics.logical_error_rate_source.as_deref(), Some("exact"));
        assert_eq!(metrics.scientific_validation_ready, Some(true));
        assert_eq!(metrics.ler_per_gate_passed, Some(true));
        assert_eq!(metrics.ler_per_gate_triggered, Some(false));
        assert_eq!(
            metrics.best_encoder_state.as_deref(),
            Some("gkp_surface_d7")
        );
        assert!(
            metrics.logical_error_rate.unwrap_or(1.0) < metrics.physical_error_rate.unwrap_or(0.0)
        );
    }

    #[test]
    fn gate_triggers_for_high_residual_stream() {
        let run = test_run("ankaa_replay_fixture", &["bp"]);
        let telemetry = test_telemetry(
            vec![0.015, 0.016, 0.017],
            vec![("bp", 2, 9), ("bp", 2, 10), ("bp", 3, 10), ("bp", 2, 9)],
            vec![("bp", 5_000, 126, Some("surface_code_d3"))],
        );

        let metrics = derive_run_metrics(&run, &telemetry);

        assert_eq!(metrics.best_decoder.as_deref(), Some("bp"));
        assert_eq!(metrics.logical_error_rate_source.as_deref(), Some("exact"));
        assert_eq!(metrics.scientific_validation_ready, Some(true));
        assert_eq!(metrics.ler_per_gate_triggered, Some(true));
        assert_eq!(metrics.ler_per_gate_passed, Some(false));
        assert!(
            metrics.logical_error_rate.unwrap_or(0.0) >= metrics.physical_error_rate.unwrap_or(1.0)
        );
    }

    #[test]
    fn estimated_metrics_do_not_emit_gate_decision() {
        let run = test_run("ankaa_replay_fixture", &["mwpm", "uf"]);
        let telemetry = test_telemetry(
            vec![0.012, 0.013],
            vec![("mwpm", 4, 2), ("uf", 5, 3)],
            Vec::new(),
        );

        let metrics = derive_run_metrics(&run, &telemetry);
        assert_eq!(
            metrics.logical_error_rate_source.as_deref(),
            Some("estimated")
        );
        assert_eq!(metrics.scientific_validation_ready, Some(false));
        assert_eq!(metrics.ler_per_gate_triggered, None);
        assert_eq!(metrics.ler_per_gate_passed, None);
    }

    fn test_run(dataset_label: &str, decoders: &[&str]) -> Run {
        let now = Utc::now();
        Run {
            id: Uuid::new_v4(),
            job_id: None,
            provider_id: Uuid::new_v4(),
            dataset_label: dataset_label.to_string(),
            decoders: decoders.iter().map(|name| (*name).to_string()).collect(),
            status: RunStatus::Running,
            message: None,
            artifacts: Vec::new(),
            metrics: None,
            created_at: now,
            updated_at: now,
        }
    }

    fn test_telemetry(
        noise: Vec<f64>,
        entries: Vec<(&str, u32, u32)>,
        exact_entries: Vec<(&str, u64, u64, Option<&str>)>,
    ) -> RunTelemetry {
        let now = Utc::now();
        let noise_samples = noise
            .into_iter()
            .enumerate()
            .map(|(index, physical_error_rate)| NoiseSample {
                index: index as u32,
                physical_error_rate,
                displacement_sigma: 0.12,
                photon_loss_rate: 0.003,
            })
            .collect::<Vec<_>>();

        let syndrome_samples = (0..4)
            .flat_map(|round| {
                (0..5).map(move |stabilizer| {
                    let triggered = (round + stabilizer) % 4 == 0;
                    SyndromeSample {
                        round,
                        stabilizer: format!("S{:02}", stabilizer + 1),
                        value: if triggered { 1 } else { 0 },
                        is_triggered: triggered,
                    }
                })
            })
            .collect::<Vec<_>>();

        let decoder_interventions = entries
            .into_iter()
            .enumerate()
            .map(
                |(round, (decoder, flips, residual_weight))| DecoderIntervention {
                    decoder: decoder.to_string(),
                    round: round as u32,
                    flips,
                    residual_weight,
                },
            )
            .collect::<Vec<_>>();

        let decoder_exact_metrics = (!exact_entries.is_empty()).then(|| {
            exact_entries
                .into_iter()
                .map(
                    |(decoder, trials, logical_failures, encoder_state)| DecoderExactTelemetry {
                        decoder: decoder.to_string(),
                        trials,
                        logical_failures,
                        encoder_state: encoder_state.map(str::to_string),
                    },
                )
                .collect::<Vec<_>>()
        });

        RunTelemetry {
            run_id: Uuid::new_v4(),
            request_count: 20,
            rounds: 4,
            stabilizer_count: 5,
            warning_rate: Some(0.12),
            noise_samples,
            syndrome_samples,
            decoder_exact_metrics,
            decoder_interventions,
            updated_at: now,
        }
    }
}
