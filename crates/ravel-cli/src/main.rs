//! JSON interchange CLI for RAVEL Rust/Python/C contract proofs.

use anyhow::{Context, Result, anyhow};
use clap::{Parser, Subcommand};
use ravel_contracts::canonical_json;
use ravel_contracts::schema::{CHECKPOINT_ABI, FOUNDATION_CONTRACT, INTERCHANGE_SCHEMA, WORLD_ABI};
use ravel_contracts::{IMPLEMENTATION_IDENTITY, Q20};
use ravel_core::c_observations::CTransactionObservation;
use ravel_core::checkpoint::CheckpointCodec;
use ravel_core::experience::ExperienceRecord;
use ravel_core::lifecycle::CandidateLedger;
use ravel_core::matched_compute::MatchedComputeObservation;
use ravel_core::mechanism::MechanismState;
use ravel_core::planning::plan;
use ravel_core::policy::{load_frozen_policy_from_root, policy_c_header};
use ravel_core::repository::discover_repository_root;
use ravel_core::transition::TransitionCompiler;
use ravel_core::world::provider_by_id;
use ravel_core::{
    RawObservation, RetentionConstraintPolicy, evaluate_constraints, run_transaction,
};
use ravel_memory::knowledge::{
    AttributionDisposition, AttributionRecord, KnowledgeRecord, KnowledgeStage, TransferStatus,
    TransferTestRecord, promote,
};
use ravel_memory::{
    AccessEvent, ConsolidationPolicy, MemoryConsolidator, MemoryRecord, RetrievalLayoutPlanner,
    ScopeCompatibility, compact,
};
use serde_json::{Value, json};
use std::io::{self, Read};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "ravel-rs", about = "RAVEL Rust foundation interchange")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Print implementation and contract identities.
    Identity,
    /// Dispatch a versioned interchange envelope from stdin.
    Interchange,
    /// Evaluate hard-gate constraints from stdin JSON.
    EvaluateConstraints,
    /// Encode a mechanism checkpoint from stdin JSON.
    EncodeCheckpoint,
    /// Load the frozen 0.6 policy and emit its identity.
    LoadPolicy {
        #[arg(long)]
        root: Option<PathBuf>,
    },
    /// Compile a toy world and plan a route.
    Plan {
        #[arg(long, default_value = "ravel-toy-branching/1")]
        provider: String,
        #[arg(long, default_value_t = 0)]
        start: i64,
        #[arg(long, default_value_t = 3)]
        goal: i64,
        #[arg(long, default_value_t = 32)]
        maximum_steps: i64,
    },
}

fn main() {
    let cli = Cli::parse();
    let result = match cli.command {
        Commands::Identity => print_identity(),
        Commands::Interchange => interchange(),
        Commands::EvaluateConstraints => evaluate_constraints_cmd(),
        Commands::EncodeCheckpoint => encode_checkpoint_cmd(),
        Commands::LoadPolicy { root } => load_policy_cmd(root),
        Commands::Plan {
            provider,
            start,
            goal,
            maximum_steps,
        } => plan_cmd(&provider, start, goal, maximum_steps),
    };
    match result {
        Ok(()) => {}
        Err(error) => {
            let payload = json!({
                "schema": INTERCHANGE_SCHEMA,
                "implementation": IMPLEMENTATION_IDENTITY,
                "operation_outcome": "ERROR",
                "error": error.to_string(),
            });
            println!(
                "{}",
                canonical_json(&payload).unwrap_or_else(|_| error.to_string())
            );
            std::process::exit(1);
        }
    }
}

fn print_identity() -> Result<()> {
    emit(&json!({
        "schema": INTERCHANGE_SCHEMA,
        "implementation": IMPLEMENTATION_IDENTITY,
        "foundation_contract": FOUNDATION_CONTRACT,
        "world_abi": WORLD_ABI,
        "checkpoint_abi": CHECKPOINT_ABI,
        "q20": Q20,
        "operation_outcome": "OK",
    }))
}

fn read_stdin_json() -> Result<Value> {
    let mut buffer = String::new();
    io::stdin().read_to_string(&mut buffer)?;
    serde_json::from_str(buffer.trim()).context("stdin is not JSON")
}

fn evaluate_constraints_cmd() -> Result<()> {
    let value = read_stdin_json()?;
    emit(&evaluate_constraints_value(&value)?)
}

fn encode_checkpoint_cmd() -> Result<()> {
    let value = read_stdin_json()?;
    emit(&encode_checkpoint_value(&value)?)
}

fn load_policy_cmd(root: Option<PathBuf>) -> Result<()> {
    let root = resolve_root(root)?;
    let policy = load_frozen_policy_from_root(&root)?;
    emit(&json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "policy.load",
        "operation_outcome": "OK",
        "policy": policy.to_value()?,
        "c_header": policy_c_header(&policy)?,
    }))
}

fn plan_cmd(provider_id: &str, start: i64, goal: i64, maximum_steps: i64) -> Result<()> {
    emit(&plan_value(provider_id, start, goal, maximum_steps)?)
}

fn interchange() -> Result<()> {
    let value = read_stdin_json()?;
    let schema = value.get("schema").and_then(Value::as_str);
    if schema == Some(ravel_contracts::schema::INTERCHANGE_SCHEMA_V1) {
        return Err(anyhow!(
            "unsupported interchange version: ravel-interchange/0.1; use ravel-interchange/0.2"
        ));
    }
    if schema != Some(INTERCHANGE_SCHEMA) {
        return Err(anyhow!("unsupported interchange schema"));
    }
    let surface = value
        .get("surface")
        .and_then(Value::as_str)
        .ok_or_else(|| anyhow!("interchange surface is required"))?;
    let input = value.get("input").cloned().unwrap_or(Value::Null);
    let output = match surface {
        "adaptation.evaluate_constraints" => evaluate_constraints_value(&input)?,
        "adaptation.run_transaction" => run_transaction_value(&input)?,
        "checkpoint.encode" => encode_checkpoint_value(&input)?,
        "world.compile_and_plan" => {
            let provider = input
                .get("provider_id")
                .and_then(Value::as_str)
                .unwrap_or("ravel-toy-branching/1");
            let start = input.get("start").and_then(Value::as_i64).unwrap_or(0);
            let goal = input.get("goal").and_then(Value::as_i64).unwrap_or(3);
            let maximum_steps = input
                .get("maximum_steps")
                .and_then(Value::as_i64)
                .unwrap_or(32);
            plan_value(provider, start, goal, maximum_steps)?
        }
        "policy.load" => {
            let root = input.get("root").and_then(Value::as_str).map(PathBuf::from);
            let root = resolve_root(root)?;
            let policy = load_frozen_policy_from_root(&root)?;
            json!({
                "schema": INTERCHANGE_SCHEMA,
                "surface": "policy.load",
                "operation_outcome": "OK",
                "policy": policy.to_value()?,
            })
        }
        "c_observations.evaluate" => evaluate_c_transaction(&input)?,
        "matched_compute.evaluate" => evaluate_matched_compute(&input)?,
        "experience.from_development_transaction" => experience_from_transaction(&input)?,
        "lifecycle.round_trip" => lifecycle_round_trip(&input)?,
        "memory.propose_consolidation" => propose_consolidation(&input)?,
        "memory.plan_retrieval" => plan_retrieval(&input)?,
        "knowledge.promote" => promote_knowledge(&input)?,
        "retention.compact" => compact_memory(&input)?,
        "memory.validate_proposal" => {
            let records = records_from_input(&input)?;
            let proposal = input
                .get("proposal")
                .ok_or_else(|| anyhow!("proposal is required"))?;
            let parsed = ravel_memory::ConsolidationProposal {
                proposal_id: proposal
                    .get("proposal_id")
                    .and_then(Value::as_str)
                    .unwrap_or("consolidation:incomplete")
                    .to_string(),
                method_version: "ravel-semantic-consolidation/0.1".into(),
                created_at: "t0".into(),
                memory_class: ravel_memory::MemoryClass::Semantic,
                canonical_statement: "candidate".into(),
                scope: Default::default(),
                member_ids: required_string_list(proposal, "member_ids")?,
                supporting_ids: required_string_list(proposal, "supporting_ids")?,
                contradicting_ids: required_string_list(proposal, "contradicting_ids")?,
                superseded_ids: Vec::new(),
                retrieval_keys: Vec::new(),
                clustering_confidence: 0.0,
                status: "proposed".into(),
                scope_contract_id: "ravel-scope-exact/1".into(),
                limitations: Vec::new(),
            };
            match MemoryConsolidator::validate_completeness(&parsed, &records) {
                Ok(()) => json!({
                    "schema": INTERCHANGE_SCHEMA,
                    "surface": "memory.validate_proposal",
                    "operation_outcome": "OK",
                }),
                Err(error) => json!({
                    "schema": INTERCHANGE_SCHEMA,
                    "surface": "memory.validate_proposal",
                    "operation_outcome": "ERROR",
                    "error": error.to_string(),
                }),
            }
        }
        "canonical.encode" => {
            let payload = input
                .get("value")
                .cloned()
                .ok_or_else(|| anyhow!("canonical value is required"))?;
            json!({
                "schema": INTERCHANGE_SCHEMA,
                "surface": "canonical.encode",
                "operation_outcome": "OK",
                "canonical": canonical_json(&payload)?,
                "digest": ravel_contracts::digest_canonical(&payload)?,
            })
        }
        other => return Err(anyhow!("unknown interchange surface: {other}")),
    };
    emit(&output)
}

fn evaluate_constraints_value(value: &Value) -> Result<Value> {
    let previous: RawObservation = serde_json::from_value(
        value
            .get("previous")
            .cloned()
            .ok_or_else(|| anyhow!("previous observation is required"))?,
    )?;
    let proposed: RawObservation = serde_json::from_value(
        value
            .get("proposed")
            .cloned()
            .ok_or_else(|| anyhow!("proposed observation is required"))?,
    )?;
    let policy: RetentionConstraintPolicy = serde_json::from_value(
        value
            .get("policy")
            .cloned()
            .ok_or_else(|| anyhow!("policy is required"))?,
    )?;
    let report = evaluate_constraints(&previous, &proposed, &policy)?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "adaptation.evaluate_constraints",
        "operation_outcome": "OK",
        "report": report.to_value(),
    }))
}

fn run_transaction_value(value: &Value) -> Result<Value> {
    let previous: RawObservation = serde_json::from_value(
        value
            .get("previous")
            .cloned()
            .ok_or_else(|| anyhow!("previous observation is required"))?,
    )?;
    let proposed: RawObservation = serde_json::from_value(
        value
            .get("proposed")
            .cloned()
            .ok_or_else(|| anyhow!("proposed observation is required"))?,
    )?;
    let policy: RetentionConstraintPolicy = serde_json::from_value(
        value
            .get("policy")
            .cloned()
            .ok_or_else(|| anyhow!("policy is required"))?,
    )?;
    let before = value
        .get("state_before")
        .and_then(Value::as_str)
        .unwrap_or("prior")
        .as_bytes();
    let candidate = value
        .get("state_candidate")
        .and_then(Value::as_str)
        .unwrap_or("prior-candidate")
        .as_bytes();
    let transaction = run_transaction(before, &previous, candidate, proposed, &policy)?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "adaptation.run_transaction",
        "operation_outcome": "OK",
        "transaction": transaction.to_value(),
    }))
}

fn encode_checkpoint_value(value: &Value) -> Result<Value> {
    let state: MechanismState = serde_json::from_value(value.clone())?;
    let codec = CheckpointCodec;
    let encoded = codec.encode(&state)?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "checkpoint.encode",
        "operation_outcome": "OK",
        "checkpoint": String::from_utf8(encoded.clone())?,
        "identity": codec.identity(&encoded),
    }))
}

fn plan_value(provider_id: &str, start: i64, goal: i64, maximum_steps: i64) -> Result<Value> {
    let provider =
        provider_by_id(provider_id).ok_or_else(|| anyhow!("unknown provider: {provider_id}"))?;
    let graph = TransitionCompiler::compile(provider.as_ref())?;
    let result = plan(&graph, start, goal, maximum_steps)?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "world.compile_and_plan",
        "operation_outcome": "OK",
        "provider_id": graph.provider_id,
        "world_abi": WORLD_ABI,
        "plan": {
            "status": result.status.as_str(),
            "actions": result.actions,
            "visited": result.visited,
            "reason": result.reason,
        }
    }))
}

fn evaluate_c_transaction(value: &Value) -> Result<Value> {
    let root = value.get("root").and_then(Value::as_str).map(PathBuf::from);
    let root = resolve_root(root)?;
    let policy = load_frozen_policy_from_root(&root)?;
    let observation = value
        .get("observation")
        .ok_or_else(|| anyhow!("C observation is required"))?;
    let parsed = CTransactionObservation::from_value(observation)?;
    let matched = match value.get("matched_compute") {
        Some(item) if !item.is_null() => Some(MatchedComputeObservation::from_value(item)?),
        _ => None,
    };
    let report = parsed.evaluate(&policy, matched.as_ref())?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "c_observations.evaluate",
        "operation_outcome": "OK",
        "threshold_identity": parsed.threshold_identity,
        "committed": parsed.committed,
        "rollback_byte_identical": parsed.rollback_byte_identical,
        "c_rejection_reason": parsed.rejection_reason,
        "report": report.to_value(),
    }))
}

fn evaluate_matched_compute(value: &Value) -> Result<Value> {
    let root = value.get("root").and_then(Value::as_str).map(PathBuf::from);
    let root = resolve_root(root)?;
    let observation = value
        .get("observation")
        .ok_or_else(|| anyhow!("matched-compute observation is required"))?;
    let parsed = MatchedComputeObservation::from_value(observation)?;
    let report = parsed.evaluate_from_root(&root)?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "matched_compute.evaluate",
        "operation_outcome": "OK",
        "report": report.to_value(),
    }))
}

fn experience_from_transaction(value: &Value) -> Result<Value> {
    let transaction = value
        .get("transaction")
        .ok_or_else(|| anyhow!("transaction is required"))?;
    let record = ExperienceRecord::from_development_transaction(
        value
            .get("candidate_id")
            .and_then(Value::as_str)
            .unwrap_or("ravel-0.6-candidate-001"),
        value
            .get("context_identity")
            .and_then(Value::as_str)
            .unwrap_or("transaction"),
        value
            .get("task_environment")
            .and_then(Value::as_str)
            .unwrap_or("ravel-toy-branching-c/1"),
        value
            .get("provider_id")
            .and_then(Value::as_str)
            .unwrap_or("ravel-candidate"),
        transaction,
        value.get("matched_compute"),
        value
            .get("partition_identity")
            .and_then(Value::as_str)
            .unwrap_or("ravel-0.6-development-adaptation-v1"),
        Default::default(),
    )?;
    let memory = record.to_memory_record(
        value
            .get("created_at")
            .and_then(Value::as_str)
            .unwrap_or("2026-08-08T00:00:00Z"),
    )?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "experience.from_development_transaction",
        "operation_outcome": "OK",
        "record_id": record.record_id(),
        "negative": record.negative(),
        "memory_class": memory.memory_class.as_str(),
        "statement": memory.statement,
    }))
}

fn lifecycle_round_trip(value: &Value) -> Result<Value> {
    let directory = value
        .get("path")
        .and_then(Value::as_str)
        .map(PathBuf::from)
        .ok_or_else(|| anyhow!("ledger path is required"))?;
    let ledger = CandidateLedger::new(&directory, 8)?;
    let created = ledger.create("dev-a", "t0")?;
    ledger.begin_development(&created.candidate_id)?;
    ledger.append_development_feedback(&created.candidate_id, "dev-result-1")?;
    let frozen = ledger.freeze(
        &created.candidate_id,
        "sha256:source",
        "sha256:evaluator",
        "sha256:threshold",
        "selection-a",
    )?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "lifecycle.round_trip",
        "operation_outcome": "OK",
        "candidate_id": created.candidate_id,
        "state": frozen.state.as_str(),
    }))
}

fn propose_consolidation(value: &Value) -> Result<Value> {
    let records = records_from_input(value)?;
    let created_at = value
        .get("created_at")
        .and_then(Value::as_str)
        .unwrap_or("2026-08-04T17:00:00Z");
    let consolidator = MemoryConsolidator::new(policy_from_input(value)?)?;
    let proposals = consolidator.propose(records, created_at)?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "memory.propose_consolidation",
        "operation_outcome": "OK",
        "proposals": proposals.iter().map(ConsolidationProposalValue::from).collect::<Vec<_>>(),
    }))
}

struct ConsolidationProposalValue;

impl ConsolidationProposalValue {
    fn from(proposal: &ravel_memory::ConsolidationProposal) -> Value {
        proposal.to_value()
    }
}

fn plan_retrieval(value: &Value) -> Result<Value> {
    let events = value
        .get("events")
        .and_then(Value::as_array)
        .ok_or_else(|| anyhow!("access events are required"))?;
    let parsed = events
        .iter()
        .map(|event| {
            Ok(AccessEvent {
                query_id: event
                    .get("query_id")
                    .and_then(Value::as_str)
                    .ok_or_else(|| anyhow!("query_id is required"))?
                    .to_string(),
                retrieved_ids: string_list(event, "retrieved_ids"),
                selected_ids: string_list(event, "selected_ids"),
            })
        })
        .collect::<Result<Vec<_>>>()?;
    let minimum = value
        .get("minimum_coaccess")
        .and_then(Value::as_i64)
        .unwrap_or(2);
    let buckets = RetrievalLayoutPlanner::plan(&parsed, minimum)?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "memory.plan_retrieval",
        "operation_outcome": "OK",
        "buckets": buckets.iter().map(|bucket| json!({
            "bucket_id": bucket.bucket_id,
            "member_ids": bucket.member_ids,
            "weighted_edges": bucket.weighted_edges.iter().map(|(left, right, weight)| json!([left, right, weight])).collect::<Vec<_>>(),
        })).collect::<Vec<_>>(),
    }))
}

fn promote_knowledge(value: &Value) -> Result<Value> {
    let current_value = value
        .get("current")
        .ok_or_else(|| anyhow!("current knowledge record is required"))?;
    let current = knowledge_from_value(current_value)?;
    let next_stage = KnowledgeStage::parse(
        value
            .get("next_stage")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("next_stage is required"))?,
    )?;
    match promote(
        &current,
        next_stage,
        value
            .get("next_id")
            .and_then(Value::as_str)
            .unwrap_or("knowledge:next"),
        value
            .get("statement")
            .and_then(Value::as_str)
            .unwrap_or(current.statement.as_str()),
        required_string_list(value, "evidence_ids")?,
        parse_optional_evidence_status(value.get("evaluation_status"))?,
        parse_optional_attribution(value.get("attribution_record"))?,
        parse_transfer_tests(value.get("transfer_tests"))?,
        value
            .get("created_at")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("created_at is required"))?,
    ) {
        Ok(record) => Ok(json!({
            "schema": INTERCHANGE_SCHEMA,
            "surface": "knowledge.promote",
            "operation_outcome": "OK",
            "record": record.to_value(),
        })),
        Err(error) => Ok(json!({
            "schema": INTERCHANGE_SCHEMA,
            "surface": "knowledge.promote",
            "operation_outcome": "ERROR",
            "error": error.to_string(),
        })),
    }
}

fn compact_memory(value: &Value) -> Result<Value> {
    let records = records_from_input(value)?;
    let created_at = value
        .get("created_at")
        .and_then(Value::as_str)
        .unwrap_or("2026-08-04T17:00:00Z");
    let proposals = compact(
        records,
        created_at,
        &ravel_memory::RetentionPolicy::default(),
        policy_from_input(value)?,
    )?;
    Ok(json!({
        "schema": INTERCHANGE_SCHEMA,
        "surface": "retention.compact",
        "operation_outcome": "OK",
        "deleted": 0,
        "proposals": proposals.iter().map(|item| item.to_value()).collect::<Vec<_>>(),
    }))
}

fn records_from_input(value: &Value) -> Result<Vec<MemoryRecord>> {
    let records = value
        .get("records")
        .and_then(Value::as_array)
        .ok_or_else(|| anyhow!("records are required"))?;
    records
        .iter()
        .map(MemoryRecord::from_value)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|error| anyhow!(error))
}

fn policy_from_input(value: &Value) -> Result<ConsolidationPolicy> {
    let policy = value.get("policy");
    let mut result = ConsolidationPolicy::default();
    if let Some(threshold) = policy
        .and_then(|item| item.get("similarity_threshold"))
        .and_then(Value::as_f64)
    {
        result.similarity_threshold = threshold;
    }
    if let Some(scope) = policy.and_then(|item| item.get("scope_compatibility")) {
        result.scope_compatibility = ScopeCompatibility {
            contract_id: scope
                .get("contract_id")
                .and_then(Value::as_str)
                .unwrap_or("ravel-scope-exact/1")
                .to_string(),
            equal_fields: string_list(scope, "equal_fields"),
            allow_extra_fields: scope
                .get("allow_extra_fields")
                .and_then(Value::as_bool)
                .unwrap_or(false),
        };
    }
    Ok(result)
}

fn knowledge_from_value(value: &Value) -> Result<KnowledgeRecord> {
    let scope = value
        .get("scope")
        .ok_or_else(|| anyhow!("scope is required"))?;
    let Value::Object(map) = scope else {
        return Err(anyhow!("scope must be an object"));
    };
    let mut parsed_scope = std::collections::BTreeMap::new();
    for (key, item) in map {
        let Some(text) = item.as_str() else {
            return Err(anyhow!("scope values must be strings"));
        };
        parsed_scope.insert(key.clone(), text.to_string());
    }
    Ok(KnowledgeRecord {
        record_id: value
            .get("record_id")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("record_id is required"))?
            .to_string(),
        stage: KnowledgeStage::parse(
            value
                .get("stage")
                .and_then(Value::as_str)
                .ok_or_else(|| anyhow!("stage is required"))?,
        )?,
        statement: value
            .get("statement")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("statement is required"))?
            .to_string(),
        scope: parsed_scope,
        parent_ids: required_string_list(value, "parent_ids")?,
        evidence_ids: required_string_list(value, "evidence_ids")?,
        evaluation_status: parse_optional_evidence_status(value.get("evaluation_status"))?,
        transfer_status: match value.get("transfer_status") {
            None => TransferStatus::Untested,
            Some(Value::String(text)) => TransferStatus::parse(text)?,
            Some(_) => return Err(anyhow!("transfer_status must be a string")),
        },
        attribution_id: match value.get("attribution_id") {
            None | Some(Value::Null) => None,
            Some(Value::String(text)) => Some(text.clone()),
            Some(_) => return Err(anyhow!("attribution_id must be a string")),
        },
        transfer_test_ids: required_string_list(value, "transfer_test_ids")?,
        challenged_ids: required_string_list(value, "challenged_ids")?,
        producer_id: value
            .get("producer_id")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("producer_id is required"))?
            .to_string(),
        created_at: value
            .get("created_at")
            .and_then(Value::as_str)
            .ok_or_else(|| anyhow!("created_at is required"))?
            .to_string(),
    })
}

fn parse_optional_evidence_status(
    value: Option<&Value>,
) -> Result<Option<ravel_contracts::status::EvidenceStatus>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(item)) => match item.as_str() {
            "PASS" => Ok(Some(ravel_contracts::status::EvidenceStatus::Pass)),
            "FAIL" => Ok(Some(ravel_contracts::status::EvidenceStatus::Fail)),
            "UNKNOWN" => Ok(Some(ravel_contracts::status::EvidenceStatus::Unknown)),
            other => Err(anyhow!("malformed evaluation_status: {other}")),
        },
        Some(_) => Err(anyhow!("evaluation_status must be a string")),
    }
}

fn parse_optional_attribution(value: Option<&Value>) -> Result<Option<AttributionRecord>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(item) => {
            let scope = item
                .get("scope")
                .and_then(Value::as_object)
                .ok_or_else(|| anyhow!("attribution scope is required"))?;
            Ok(Some(AttributionRecord {
                attribution_id: item
                    .get("attribution_id")
                    .and_then(Value::as_str)
                    .ok_or_else(|| anyhow!("attribution_id is required"))?
                    .to_string(),
                source_intervention_ids: required_string_list(item, "source_intervention_ids")?,
                evaluator_identity: item
                    .get("evaluator_identity")
                    .and_then(Value::as_str)
                    .ok_or_else(|| anyhow!("evaluator_identity is required"))?
                    .to_string(),
                evidence_ids: required_string_list(item, "evidence_ids")?,
                disposition: AttributionDisposition::parse(
                    item.get("disposition")
                        .and_then(Value::as_str)
                        .ok_or_else(|| anyhow!("attribution disposition is required"))?,
                )?,
                scope: scope
                    .iter()
                    .map(|(key, value)| {
                        value
                            .as_str()
                            .map(|text| (key.clone(), text.to_string()))
                            .ok_or_else(|| anyhow!("attribution scope values must be strings"))
                    })
                    .collect::<Result<_>>()?,
            }))
        }
    }
}

fn parse_transfer_tests(value: Option<&Value>) -> Result<Vec<TransferTestRecord>> {
    match value {
        None | Some(Value::Null) => Ok(Vec::new()),
        Some(Value::Array(items)) => items
            .iter()
            .map(|item| {
                Ok(TransferTestRecord {
                    test_id: item
                        .get("test_id")
                        .and_then(Value::as_str)
                        .ok_or_else(|| anyhow!("test_id is required"))?
                        .to_string(),
                    principle_id: item
                        .get("principle_id")
                        .and_then(Value::as_str)
                        .ok_or_else(|| anyhow!("principle_id is required"))?
                        .to_string(),
                    context_identity: item
                        .get("context_identity")
                        .and_then(Value::as_str)
                        .ok_or_else(|| anyhow!("context_identity is required"))?
                        .to_string(),
                    evidence_ids: required_string_list(item, "evidence_ids")?,
                    outcome: TransferStatus::parse(
                        item.get("outcome")
                            .and_then(Value::as_str)
                            .ok_or_else(|| anyhow!("transfer outcome is required"))?,
                    )?,
                })
            })
            .collect(),
        Some(_) => Err(anyhow!("transfer_tests must be an array")),
    }
}

fn required_string_list(value: &Value, key: &str) -> Result<Vec<String>> {
    match value.get(key) {
        None => Ok(Vec::new()),
        Some(Value::Array(items)) => items
            .iter()
            .map(|item| {
                item.as_str()
                    .map(str::to_string)
                    .ok_or_else(|| anyhow!("{key} entries must be strings"))
            })
            .collect(),
        Some(_) => Err(anyhow!("{key} must be an array")),
    }
}

fn string_list(value: &Value, key: &str) -> Vec<String> {
    required_string_list(value, key).unwrap_or_default()
}

fn resolve_root(root: Option<PathBuf>) -> Result<PathBuf> {
    if let Some(root) = root {
        return Ok(root);
    }
    discover_repository_root()
        .ok_or_else(|| anyhow!("RAVEL_ROOT or repository markers are required"))
}

fn emit(value: &Value) -> Result<()> {
    println!("{}", canonical_json(value)?);
    Ok(())
}
