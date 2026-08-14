//! Deterministic semantic consolidation and retrieval-layout planning.

use crate::models::{
    AccessEvent, ConsolidationProposal, MemoryClass, MemoryError, MemoryRecord, RetrievalBucket,
    ScopeCompatibility,
};
use ravel_contracts::identity::hex_sha256;
use ravel_contracts::schema::SEMANTIC_CONSOLIDATION_METHOD;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

const STOP_WORDS: &[&str] = &[
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on",
    "or", "that", "the", "to", "was", "were", "with",
];

#[derive(Debug, Clone, PartialEq)]
pub struct ConsolidationPolicy {
    pub similarity_threshold: f64,
    pub minimum_cluster_size: usize,
    pub maximum_cluster_size: usize,
    pub retrieval_key_count: usize,
    pub method_version: String,
    pub scope_compatibility: ScopeCompatibility,
}

impl Default for ConsolidationPolicy {
    fn default() -> Self {
        Self {
            similarity_threshold: 0.72,
            minimum_cluster_size: 2,
            maximum_cluster_size: 64,
            retrieval_key_count: 8,
            method_version: SEMANTIC_CONSOLIDATION_METHOD.to_string(),
            scope_compatibility: ScopeCompatibility::default(),
        }
    }
}

impl ConsolidationPolicy {
    pub fn validate(&self) -> Result<(), MemoryError> {
        if !(0.0..=1.0).contains(&self.similarity_threshold) {
            return Err(MemoryError::Invalid(
                "similarity_threshold must be between 0 and 1".into(),
            ));
        }
        if self.minimum_cluster_size < 2 {
            return Err(MemoryError::Invalid(
                "minimum_cluster_size must be at least 2".into(),
            ));
        }
        if self.maximum_cluster_size < self.minimum_cluster_size {
            return Err(MemoryError::Invalid(
                "maximum_cluster_size must not be smaller than minimum".into(),
            ));
        }
        if self.retrieval_key_count < 1 {
            return Err(MemoryError::Invalid(
                "retrieval_key_count must be positive".into(),
            ));
        }
        Ok(())
    }
}

pub struct MemoryConsolidator {
    pub policy: ConsolidationPolicy,
}

impl MemoryConsolidator {
    pub fn new(policy: ConsolidationPolicy) -> Result<Self, MemoryError> {
        policy.validate()?;
        Ok(Self { policy })
    }

    pub fn propose(
        &self,
        records: Vec<MemoryRecord>,
        created_at: &str,
    ) -> Result<Vec<ConsolidationProposal>, MemoryError> {
        let mut ordered = records;
        ordered.sort_by(|left, right| left.record_id.cmp(&right.record_id));
        if ordered.is_empty() {
            return Ok(Vec::new());
        }
        let mut record_by_id = HashMap::new();
        for record in &ordered {
            if record_by_id
                .insert(record.record_id.clone(), record.clone())
                .is_some()
            {
                return Err(MemoryError::Invalid(
                    "record_id values must be unique".into(),
                ));
            }
        }
        let mut groups: Vec<Vec<MemoryRecord>> = Vec::new();
        for record in ordered {
            if let Some(group) = groups.iter_mut().find(|group| {
                group[0].memory_class == record.memory_class
                    && self
                        .policy
                        .scope_compatibility
                        .compatible(&group[0].scope, &record.scope)
            }) {
                group.push(record);
            } else {
                groups.push(vec![record]);
            }
        }
        let mut proposals = Vec::new();
        for group in groups {
            proposals.extend(self.propose_group(&group, &record_by_id, created_at));
        }
        proposals.sort_by(|left, right| left.proposal_id.cmp(&right.proposal_id));
        Ok(proposals)
    }

    fn propose_group(
        &self,
        records: &[MemoryRecord],
        record_by_id: &HashMap<String, MemoryRecord>,
        created_at: &str,
    ) -> Vec<ConsolidationProposal> {
        if records.len() < self.policy.minimum_cluster_size {
            return Vec::new();
        }
        let token_map: HashMap<String, BTreeSet<String>> = records
            .iter()
            .map(|record| (record.record_id.clone(), tokens(&record.statement)))
            .collect();
        let mut forest = UnionFind::new(token_map.keys().cloned());
        for (index, left) in records.iter().enumerate() {
            for right in &records[index + 1..] {
                let Some(left_tokens) = token_map.get(&left.record_id) else {
                    continue;
                };
                let Some(right_tokens) = token_map.get(&right.record_id) else {
                    continue;
                };
                let similarity = jaccard(left_tokens, right_tokens);
                if similarity >= self.policy.similarity_threshold {
                    forest.union(&left.record_id, &right.record_id);
                }
            }
        }
        let mut components: BTreeMap<String, Vec<MemoryRecord>> = BTreeMap::new();
        for record in records {
            components
                .entry(forest.find(&record.record_id))
                .or_default()
                .push(record.clone());
        }
        let mut proposals = Vec::new();
        for mut component in components.into_values() {
            if component.len() < self.policy.minimum_cluster_size {
                continue;
            }
            if component.len() > self.policy.maximum_cluster_size {
                component.sort_by(|left, right| left.record_id.cmp(&right.record_id));
                component.truncate(self.policy.maximum_cluster_size);
            }
            proposals.push(self.make_proposal(&component, record_by_id, &token_map, created_at));
        }
        proposals
    }

    fn make_proposal(
        &self,
        component: &[MemoryRecord],
        record_by_id: &HashMap<String, MemoryRecord>,
        token_map: &HashMap<String, BTreeSet<String>>,
        created_at: &str,
    ) -> ConsolidationProposal {
        let mut members = component.to_vec();
        members.sort_by(|left, right| left.record_id.cmp(&right.record_id));
        let member_ids: Vec<String> = members.iter().map(|item| item.record_id.clone()).collect();
        let mut contradicted = BTreeSet::new();
        let mut superseded = BTreeSet::new();
        for record in &members {
            if let Some(values) = record.relations.get("contradicts") {
                contradicted.extend(values.iter().cloned());
            }
            if let Some(values) = record.relations.get("supersedes") {
                superseded.extend(values.iter().cloned());
            }
        }
        let contradiction_ids: Vec<String> = contradicted
            .iter()
            .filter(|item| record_by_id.contains_key(*item))
            .cloned()
            .collect();
        let superseded_ids: Vec<String> = superseded
            .iter()
            .filter(|item| record_by_id.contains_key(*item))
            .cloned()
            .collect();
        let supporting_ids: Vec<String> = member_ids
            .iter()
            .filter(|item| !contradicted.contains(*item) && !superseded.contains(*item))
            .cloned()
            .collect();
        let Some(representative) = members.iter().max_by_key(|item| representative_rank(item))
        else {
            return ConsolidationProposal {
                proposal_id: stable_id("consolidation", &member_ids),
                method_version: self.policy.method_version.clone(),
                created_at: created_at.to_string(),
                memory_class: MemoryClass::Semantic,
                canonical_statement: String::new(),
                scope: BTreeMap::new(),
                member_ids,
                supporting_ids,
                contradicting_ids: contradiction_ids,
                superseded_ids,
                retrieval_keys: Vec::new(),
                clustering_confidence: 0.0,
                status: "proposed".into(),
                scope_contract_id: self.policy.scope_compatibility.contract_id.clone(),
                limitations: vec![
                    "Derived projection only; does not alter source status or authority.".into(),
                ],
            };
        };
        ConsolidationProposal {
            proposal_id: stable_id("consolidation", &member_ids),
            method_version: self.policy.method_version.clone(),
            created_at: created_at.to_string(),
            memory_class: representative.memory_class,
            canonical_statement: representative.statement.trim().to_string(),
            scope: representative.scope.clone(),
            member_ids,
            supporting_ids,
            contradicting_ids: contradiction_ids,
            superseded_ids,
            retrieval_keys: retrieval_keys(&members, self.policy.retrieval_key_count),
            clustering_confidence: round6(cluster_confidence(&members, token_map)),
            status: "proposed".into(),
            scope_contract_id: self.policy.scope_compatibility.contract_id.clone(),
            limitations: vec![
                "Derived projection only; does not alter source status or authority.".into(),
            ],
        }
    }
}

impl MemoryConsolidator {
    pub fn validate_completeness(
        proposal: &ConsolidationProposal,
        records: &[MemoryRecord],
    ) -> Result<(), MemoryError> {
        let known: std::collections::BTreeSet<_> =
            records.iter().map(|item| item.record_id.as_str()).collect();
        let listed: std::collections::BTreeSet<_> = proposal
            .contradicting_ids
            .iter()
            .map(String::as_str)
            .collect();
        for record in records {
            if !proposal
                .member_ids
                .iter()
                .any(|item| item == &record.record_id)
            {
                continue;
            }
            if let Some(targets) = record.relations.get("contradicts") {
                for target in targets {
                    if known.contains(target.as_str()) && !listed.contains(target.as_str()) {
                        return Err(MemoryError::Invalid(
                            "consolidation proposal omitted a known counterexample".into(),
                        ));
                    }
                }
            }
        }
        Ok(())
    }
}

pub struct RetrievalLayoutPlanner;

impl RetrievalLayoutPlanner {
    pub fn plan(
        events: &[AccessEvent],
        minimum_coaccess: i64,
    ) -> Result<Vec<RetrievalBucket>, MemoryError> {
        if minimum_coaccess < 1 {
            return Err(MemoryError::Invalid(
                "minimum_coaccess must be positive".into(),
            ));
        }
        let mut weights: BTreeMap<(String, String), i64> = BTreeMap::new();
        let mut all_ids = BTreeSet::new();
        for event in events {
            let source = if event.selected_ids.is_empty() {
                &event.retrieved_ids
            } else {
                &event.selected_ids
            };
            let chosen: Vec<String> = source
                .iter()
                .cloned()
                .collect::<BTreeSet<_>>()
                .into_iter()
                .collect();
            all_ids.extend(chosen.iter().cloned());
            for index in 0..chosen.len() {
                for right in chosen.iter().skip(index + 1) {
                    let left = &chosen[index];
                    *weights.entry((left.clone(), right.clone())).or_insert(0) += 1;
                }
            }
        }
        let eligible: BTreeMap<(String, String), i64> = weights
            .into_iter()
            .filter(|(_, weight)| *weight >= minimum_coaccess)
            .collect();
        if eligible.is_empty() {
            return Ok(Vec::new());
        }
        let mut forest = UnionFind::new(all_ids.iter().cloned());
        for (left, right) in eligible.keys() {
            forest.union(left, right);
        }
        let mut components: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        for record_id in &all_ids {
            components
                .entry(forest.find(record_id))
                .or_default()
                .insert(record_id.clone());
        }
        let mut buckets = Vec::new();
        for members in components.into_values() {
            if members.len() < 2 {
                continue;
            }
            let member_ids: Vec<String> = members.into_iter().collect();
            let member_set: HashSet<&String> = member_ids.iter().collect();
            let mut edges: Vec<(String, String, i64)> = eligible
                .iter()
                .filter(|((left, right), _)| {
                    member_set.contains(left) && member_set.contains(right)
                })
                .map(|((left, right), weight)| (left.clone(), right.clone(), *weight))
                .collect();
            edges.sort();
            buckets.push(RetrievalBucket {
                bucket_id: stable_id("retrieval-bucket", &member_ids),
                member_ids,
                weighted_edges: edges,
                reason: "frequent-co-access".into(),
            });
        }
        buckets.sort_by(|left, right| left.bucket_id.cmp(&right.bucket_id));
        Ok(buckets)
    }
}

fn tokens(text: &str) -> BTreeSet<String> {
    let folded = text.to_lowercase();
    let mut current = String::new();
    let mut out = BTreeSet::new();
    let flush = |current: &mut String, out: &mut BTreeSet<String>| {
        if current.is_empty() {
            return;
        }
        let first = current.chars().next();
        if first.is_some_and(|ch| ch.is_ascii_alphanumeric())
            && !STOP_WORDS.contains(&current.as_str())
        {
            out.insert(normalize_token(current));
        }
        current.clear();
    };
    for ch in folded.chars() {
        if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' {
            current.push(ch);
        } else {
            flush(&mut current, &mut out);
        }
    }
    flush(&mut current, &mut out);
    out
}

fn normalize_token(token: &str) -> String {
    if token.len() > 4 && token.ends_with('s') && !token.ends_with("ss") {
        token[..token.len() - 1].to_string()
    } else {
        token.to_string()
    }
}

fn jaccard(left: &BTreeSet<String>, right: &BTreeSet<String>) -> f64 {
    if left.is_empty() && right.is_empty() {
        return 1.0;
    }
    let intersection = left.intersection(right).count() as f64;
    let union = left.union(right).count() as f64;
    if union == 0.0 {
        0.0
    } else {
        intersection / union
    }
}

fn representative_rank(record: &MemoryRecord) -> (i32, i32, usize, String, String) {
    let status_rank = match record.status {
        crate::models::RecordStatus::Active => 1,
        crate::models::RecordStatus::Retired | crate::models::RecordStatus::Rejected => 0,
    };
    (
        status_rank,
        record.authority_class.rank(),
        record.source_ids.len(),
        record.created_at.clone(),
        record.record_id.clone(),
    )
}

fn retrieval_keys(records: &[MemoryRecord], limit: usize) -> Vec<String> {
    let mut counts: BTreeMap<String, i64> = BTreeMap::new();
    for record in records {
        for token in tokens(&record.statement) {
            *counts.entry(token).or_insert(0) += 1;
        }
        for tag in &record.tags {
            *counts.entry(tag.to_lowercase()).or_insert(0) += 1;
        }
    }
    let mut ordered: Vec<(String, i64)> = counts.into_iter().collect();
    ordered.sort_by(|left, right| right.1.cmp(&left.1).then_with(|| left.0.cmp(&right.0)));
    ordered
        .into_iter()
        .take(limit)
        .map(|(token, _)| token)
        .collect()
}

fn cluster_confidence(
    records: &[MemoryRecord],
    token_map: &HashMap<String, BTreeSet<String>>,
) -> f64 {
    if records.len() < 2 {
        return 0.0;
    }
    let mut similarities = Vec::new();
    for (index, left) in records.iter().enumerate() {
        for right in &records[index + 1..] {
            let Some(left_tokens) = token_map.get(&left.record_id) else {
                continue;
            };
            let Some(right_tokens) = token_map.get(&right.record_id) else {
                continue;
            };
            similarities.push(jaccard(left_tokens, right_tokens));
        }
    }
    similarities.iter().sum::<f64>() / similarities.len() as f64
}

fn round6(value: f64) -> f64 {
    (value * 1_000_000.0).round() / 1_000_000.0
}

pub fn stable_id(prefix: &str, values: &[String]) -> String {
    let mut ordered = values.to_vec();
    ordered.sort();
    let material = ordered.join("\u{1f}");
    format!("{prefix}:{}", &hex_sha256(material.as_bytes())[..24])
}

struct UnionFind {
    parent: HashMap<String, String>,
}

impl UnionFind {
    fn new(values: impl IntoIterator<Item = String>) -> Self {
        let parent = values
            .into_iter()
            .map(|value| (value.clone(), value))
            .collect();
        Self { parent }
    }

    fn find(&mut self, value: &str) -> String {
        let parent = self
            .parent
            .get(value)
            .cloned()
            .unwrap_or_else(|| value.to_string());
        if parent != value {
            let root = self.find(&parent);
            self.parent.insert(value.to_string(), root.clone());
            root
        } else {
            parent
        }
    }

    fn union(&mut self, left: &str, right: &str) {
        let left_root = self.find(left);
        let right_root = self.find(right);
        if left_root == right_root {
            return;
        }
        let (low, high) = if left_root < right_root {
            (left_root, right_root)
        } else {
            (right_root, left_root)
        };
        self.parent.insert(high, low);
    }
}

#[cfg(test)]
#[allow(clippy::expect_used, clippy::unwrap_used)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn record(record_id: &str, statement: &str) -> MemoryRecord {
        let mut scope = BTreeMap::new();
        scope.insert("repository".into(), "epi13/RAVEL".into());
        scope.insert("contract".into(), "mncs-memory-v1".into());
        MemoryRecord::new(
            record_id,
            MemoryClass::Semantic,
            statement,
            scope,
            "2026-08-04T16:00:00Z",
            "test-suite",
        )
        .expect("record")
    }

    #[test]
    fn near_duplicates_produce_provenance_preserving_proposal() {
        let consolidator = MemoryConsolidator::new(ConsolidationPolicy {
            similarity_threshold: 0.65,
            ..ConsolidationPolicy::default()
        })
        .expect("policy");
        let proposals = consolidator
            .propose(
                vec![
                    record(
                        "memory:1",
                        "RAVEL preserves negative memory during retrieval.",
                    ),
                    record(
                        "memory:2",
                        "During retrieval RAVEL must preserve negative memory.",
                    ),
                ],
                "2026-08-04T17:00:00Z",
            )
            .expect("propose");
        assert_eq!(proposals.len(), 1);
        assert_eq!(proposals[0].member_ids, ["memory:1", "memory:2"]);
        assert_eq!(proposals[0].supporting_ids, proposals[0].member_ids);
        assert_eq!(proposals[0].status, "proposed");
        assert!(
            proposals[0]
                .retrieval_keys
                .iter()
                .any(|key| key == "negative")
        );
    }

    #[test]
    fn scope_boundary_prevents_false_consolidation() {
        let mut other = record("memory:2", "The verifier result remains UNKNOWN.");
        other
            .scope
            .insert("repository".into(), "other/project".into());
        let proposals = MemoryConsolidator::new(ConsolidationPolicy::default())
            .expect("policy")
            .propose(
                vec![
                    record("memory:1", "The verifier result remains UNKNOWN."),
                    other,
                ],
                "2026-08-04T17:00:00Z",
            )
            .expect("propose");
        assert!(proposals.is_empty());
    }

    #[test]
    fn frequent_coaccess_forms_rebuildable_bucket() {
        let events = [
            AccessEvent {
                query_id: "query:1".into(),
                retrieved_ids: vec!["memory:a".into(), "memory:b".into(), "memory:c".into()],
                selected_ids: vec!["memory:a".into(), "memory:b".into()],
            },
            AccessEvent {
                query_id: "query:2".into(),
                retrieved_ids: vec!["memory:a".into(), "memory:b".into()],
                selected_ids: vec!["memory:a".into(), "memory:b".into()],
            },
            AccessEvent {
                query_id: "query:3".into(),
                retrieved_ids: vec!["memory:a".into(), "memory:c".into()],
                selected_ids: vec!["memory:a".into(), "memory:c".into()],
            },
        ];
        let buckets = RetrievalLayoutPlanner::plan(&events, 2).expect("plan");
        assert_eq!(buckets.len(), 1);
        assert_eq!(buckets[0].member_ids, ["memory:a", "memory:b"]);
        assert_eq!(
            buckets[0].weighted_edges,
            vec![("memory:a".into(), "memory:b".into(), 2)]
        );
    }
}
