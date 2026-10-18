# Data Model

Schema version: `1` (recorded in `schema_version` table; create-all migration
for the assessment; Alembic is a documented upgrade path).

## Application plane

### `short_links`
| column | type | notes |
|---|---|---|
| id | integer PK | |
| code | text UNIQUE NOT NULL | 7-char base62 (FR-U04) |
| target_url | text NOT NULL | normalised (FR-U02) |
| created_at | datetime UTC NOT NULL | |
| expires_at | datetime UTC NULL | (FR-U06) |
| idempotency_key | text UNIQUE NULL | (FR-U09) |
| payload_hash | text NULL | sha256 of canonical create payload |

### `redirect_events`
| column | type | notes |
|---|---|---|
| id | integer PK | |
| code | text NOT NULL, indexed | no FK: analytics must survive link deletion semantics |
| occurred_at | datetime UTC NOT NULL, indexed | |
| referrer | text NULL | |
| ua_class | text NULL | `browser` / `bot` / `other` |

## Control plane

### `workflow_runs`
| column | type | notes |
|---|---|---|
| id | text PK | ULID-like, correlation ID |
| title | text | |
| scope | text | `greenfield` / `brownfield` / `ambiguous` |
| state | text | RunState |
| requirement_raw | text | |
| requirement_version | integer | bumps on clarification |
| policy_version | text | evaluated version |
| graph_version | integer | bumps on replan |
| created_at / updated_at | datetime | |
| terminal_reason | text NULL | |

### `workflow_stages`
| column | type | notes |
|---|---|---|
| run_id | text FK | |
| name | text | PK (run_id, name) |
| owner | text | `agent` / `human` |
| state | text | StageState |
| attempt | integer | |
| parallel_group | text NULL | |
| started_at / ended_at | datetime NULL | |
| failure_kind | text NULL | TRANSIENT / PERMANENT |
| fallback_used | boolean | |
| last_error | text NULL | |

### `workflow_edges`
| run_id, graph_version, from_stage, to_stage, kind (`hard`/`conditional`) |

### `workflow_artifacts`
| column | notes |
|---|---|
| id | integer PK |
| run_id, stage, kind | e.g. `normalized_requirement`, `decomposition`, `design`, `change_set`, `test_report`, `policy_report`, `summary` |
| version | integer; bumps on regeneration after replan |
| content | JSON |
| derived_from | JSON list of artifact ids |
| policy_version | text |
| invalidated | boolean |
| created_at | |

### `workflow_decisions`
| id, run_id, gate, actor, decision (`approve`/`reject`/`clarify`), reason, payload JSON, artifact_version, decided_at |

### `workflow_events` (append-only; no UPDATE/DELETE path in code)
| id (seq) | run_id | kind | actor_type (`agent`/`human`/`system`) | stage NULL | attempt NULL | target | result | reason | data JSON | at |

Event kinds: `run_created`, `stage_ready`, `stage_started`, `stage_succeeded`,
`stage_failed`, `failure_detected`, `retry_scheduled`, `recovery_started`,
`recovery_completed`, `stage_timed_out`, `fallback_used`, `gate_opened`,
`decision_recorded`, `compensation_started`, `compensation_completed`,
`rollback_completed`, `safe_stop`, `run_suspended`, `run_resumed`,
`replan`, `policy_evaluated`, `exception_requested`, `exception_approved`,
`run_completed`, `run_failed`, `run_rejected`.

### `replan_events`
| id, run_id, trigger, graph_before JSON, graph_after JSON, invalidated JSON, at |

### `policy_evaluations`
| id, run_id, stage, policy_id, policy_version, outcome, detail, at |

### `policy_exceptions`
| id, run_id, policy_id, scope, reason, approver, compensating_control, approved_at, expires_at, status |

## State machines

### RunState
```
CREATED → RUNNING
RUNNING → WAITING_APPROVAL | WAITING_CLARIFICATION | REPLANNING | SUSPENDED | SAFE_STOPPED | COMPLETED | FAILED
WAITING_APPROVAL → RUNNING (approve) | REJECTED (reject) | SAFE_STOPPED (timeout/stop)
WAITING_CLARIFICATION → REPLANNING (clarify) | SAFE_STOPPED (timeout/stop)
REPLANNING → RUNNING
SUSPENDED → RUNNING (resume) | SAFE_STOPPED (stop)
terminal: SAFE_STOPPED, COMPLETED, FAILED, REJECTED
```

### StageState
```
PENDING → READY → RUNNING → SUCCEEDED | FAILED | RETRYING
RETRYING → RUNNING
FAILED → FALLBACK (if fallback defined) | (run safe-stop)
SUCCEEDED | FALLBACK → COMPENSATING → COMPENSATED      (on rejection)
any non-terminal/terminal → INVALIDATED (on replan) → PENDING
PENDING → SKIPPED (condition false)
```
Any transition not listed raises `IllegalTransition` and the run safe-stops
with reason `ILLEGAL_TRANSITION`.
