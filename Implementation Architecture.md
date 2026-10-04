IT Ops — Implementation Architecture

Version: 1.2

Status: Final — Implementation Ready

Source PRD: IT Ops PRD v1.2 — Final / Locked

Purpose: Implementation contract for the IT Ops AI Computer Operator.

1. Architecture Goal

Build a controlled AI computer operator that can:

Accept a natural-language IT onboarding goal.

Interpret the employee, role, and required access.

Determine the required applications from the access policy.

Operate the synthetic IT administration portal through a real browser.

Grant permitted application access.

Stop for human approval before privileged access.

Resume from the same workflow state after approval or rejection.

Recover from a controlled application-grant failure without duplicating completed actions.

Independently verify the final state.

Produce evidence of what happened.

The implementation must remain within the scope defined by PRD v1.2.

2. System Architecture

                      USER
                        |
                        v
              +-------------------+
              |    Next.js App    |
              |                   |
              |  IT Ops Dashboard |
              |  Execution View   |
              |  Synthetic Portal |
              +---------+---------+
                        |
                   HTTP / SSE
                        |
                        v
              +-------------------+
              |     FastAPI       |
              |  Backend / API    |
              +---------+---------+
                        |
          +-------------+-------------+
          |                           |
          v                           v
  +---------------+           +---------------+
  |   LangGraph   |           |    SQLite     |
  |  Orchestrator |           | Domain State  |
  +-------+-------+           +---------------+
          |                           |
          |                           |
          v                           |
  +---------------+                   |
  | Deterministic |-------------------+
  |     Tools     |
  +-------+-------+
          |
          v
  +---------------+
  |   Playwright  |
  | Browser Agent |
  +-------+-------+
          |
          v
  +---------------+
  | Synthetic IT  |
  |    Portal     |
  +---------------+

Supporting systems

LangGraph
|
v
checkpoints.db
(workflow state)

FastAPI / LangGraph / Tools
|
v
SSE Event Bus
|
v
Next.js Execution UI

Run
|
v
evidence/<run_id>/

3. Architectural Principles

The implementation follows these principles:

Browser interaction is real.

Playwright must interact with the synthetic portal through the UI.

The LLM does not directly mutate application state.

State-changing operations are performed through deterministic tools.

FastAPI is the single backend/API boundary.

Next.js never directly accesses SQLite.

SQLite is the source of truth for domain state.

LangGraph is the source of truth for workflow execution state.

LangGraph checkpoint state and domain state use separate SQLite files.

Human approval is the only execution pause mechanism.

Completed actions must never be unnecessarily replayed.

Verification is independent from the agent's internal assumptions.

Evidence must show what actually happened.

The architecture must remain small enough to implement within the assignment time budget.

4. Application Structure

The project consists of one Next.js application plus one Python/FastAPI backend.

it-ops/
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── run/
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   │
│   │   └── portal/
│   │       ├── page.tsx
│   │       ├── employees/
│   │       │   ├── page.tsx
│   │       │   └── [id]/
│   │       │       └── page.tsx
│   │       ├── applications/
│   │       │   └── page.tsx
│   │       ├── policies/
│   │       │   └── page.tsx
│   │       └── audit/
│   │           └── page.tsx
│   │
│   ├── components/
│   ├── lib/
│   └── ...
│
├── backend/
│   ├── api/
│   ├── agent/
│   ├── tools/
│   ├── browser/
│   ├── db/
│   ├── evidence/
│   ├── events/
│   └── ...
│
├── scripts/
│   ├── seed_db.py
│   └── reset_db.py
│
├── evidence/
│
├── tests/
│
├── .env.example
├── README.md
├── ENGINEERING_NOTES.md
└── ...

Exact filenames may vary during implementation, but responsibilities must remain separated.

5. Backend Ownership

FastAPI is the single backend/API boundary.

The frontend communicates only with FastAPI for backend operations.

FastAPI owns:

Run creation

Run status

LangGraph execution

HITL approval/rejection

SSE streaming

Portal data APIs

Portal mutations

Evidence serving

Health checks

The Next.js application must not:

Open SQLite directly

Modify permissions directly

Modify runs directly

Modify actions directly

Bypass the API to perform privileged operations

6. SQLite Architecture

Two separate SQLite databases are required.

6.1 Domain Database

it_ops.db

This database owns:

Employees

Roles

Applications

Access policies

Permissions

Runs

Actions

Audit records

It is the authoritative source for:

What has actually happened in the IT system?

6.2 LangGraph Checkpoint Database

checkpoints.db

This database owns persistent LangGraph checkpoint state.

It is the authoritative source for:

Where is the agent in its workflow?

The two databases must not be merged.

Required environment configuration

IT_OPS_DB_PATH=./data/it_ops.db
CHECKPOINT_DB_PATH=./data/checkpoints.db

7. State Ownership Boundary

This distinction is mandatory.

State

Owner

Workflow position

LangGraph

Agent execution context

LangGraph

HITL interruption state

LangGraph

HITL resume state

LangGraph

Thread/checkpoint state

LangGraph

Employees

SQLite

Roles

SQLite

Applications

SQLite

Access policies

SQLite

Permissions

SQLite

Runs

SQLite

Actions

SQLite

Audit history

SQLite

Simple rule

LangGraph answers: “Where is the agent?”

SQLite answers: “What actually happened?”

Neither system should become a duplicate owner of the same state.

8. Database Schema

8.1 roles

roles
-----
id
name

Example:

1 | Marketing Manager
2 | Finance Analyst

8.2 employees

employees
---------
id
name
role_id

8.3 applications

applications
------------
id
name
privileged
fails_on_grant

Example:

GitHub          | false | false
Slack           | false | false
CRM             | false | true
Admin Console   | true  | false

8.4 access_policies

access_policies
---------------
id
role_id
application_id
required

This defines which applications a role requires.

8.5 permissions

permissions
-----------
id
employee_id
application_id
status

Possible permission status:

granted
revoked

8.6 runs

runs
----
id
goal
status
employee_id
created_at
updated_at
completed_at
error

The id should preferably also function as the LangGraph thread_id.

If implementation requires separate identifiers, an explicit mapping must be stored.

8.7 actions

actions
-------
id
run_id
employee_id
application_id
action_type
status
requires_approval
approval_decision
recovery_attempts
error
started_at
completed_at
details

This table tracks the lifecycle of each intended operation.

It is separate from audit_log.

8.8 audit_log

audit_log
---------
id
run_id
employee_id
action
status
timestamp
details

The audit log records what happened.

The actions table records the lifecycle/state of the planned operation.

9. Database Seeding

A deterministic seed script is required.

scripts/seed_db.py

Run with:

python scripts/seed_db.py

The seed process must:

Create the domain database if necessary.

Create the required tables.

Insert deterministic employees.

Insert deterministic roles.

Insert deterministic applications.

Insert deterministic policies.

Reset/recreate deterministic test permissions where appropriate.

Preserve the controlled failure configuration.

The seed operation must be safe and repeatable for a fresh local environment.

The README must document:

python scripts/seed_db.py

10. LangGraph Checkpointer

The MVP must use persistent LangGraph checkpointing.

Do not use:

MemorySaver

for the final implementation.

Use a SQLite-backed LangGraph checkpointer compatible with the installed LangGraph version.

The checkpointer database is:

checkpoints.db

The implementation must configure LangGraph so that HITL interruptions survive the request boundary.

The exact checkpointer class may depend on the installed LangGraph version, but the architectural requirement is:

Persistent SQLite-backed LangGraph checkpointing.

11. Run ID and Thread ID

Preferred architecture:

run_id == thread_id

Example:

run_01HXYZ...

The same identifier is used for:

SQLite runs.id

LangGraph thread_id

SSE run identifier

Evidence directory

Therefore:

evidence/run_01HXYZ/

contains evidence for the corresponding LangGraph execution.

If separate IDs are introduced, an explicit persistent mapping must exist.

12. LangGraph Workflow

The graph represents the execution lifecycle.

START
|
v
Understand Goal
|
v
Identify Employee
|
v
Determine Role
|
v
Load Access Policy
|
v
Create Action Plan
|
v
Execute Next Action
|
v
Privileged?
/       
No       Yes
|        |
v        v
Grant    HITL
|        |
|    Approval?
|     /     
|   Yes     No
|    |       |
|    v       v
|  Grant   Reject
|    |       |
|    |       v
|    |     Skip
|    |
+----+
|
v
Verify Final State
|
v
Generate Evidence
|
v
Complete

13. LangGraph State

The graph state should contain only workflow/execution context.

Minimum conceptual state:

run_id
goal
employee_id
role_id
action_plan
current_action_id
approval_decision
verification_result
execution_status
error

Domain facts should not be duplicated unnecessarily in graph state.

For example, the graph may contain:

employee_id = emp_001

but the authoritative employee record remains in SQLite.

14. Action Plan Contract

Each action must use a predictable structure.

Minimum shape:

{
action_id,
employee_id,
application_id,
action_type,
requires_approval,
status
}

Example:

{
action_id: "act_003",
employee_id: "emp_001",
application_id: "app_github",
action_type: "grant_application",
requires_approval: false,
status: "pending"
}

The action plan must be deterministic enough for the execution layer to process safely.

15. Action State Machine

Valid action states:

pending
running
succeeded
failed
awaiting_approval
rejected
skipped

Valid transitions:

pending
|
v
running
|
+----> succeeded
|
+----> failed
|
+----> awaiting_approval
|
+----> running
|
+----> rejected
|
v
skipped

A rejected privileged operation must not transition through running.

Correct flow:

awaiting_approval
|
v
rejected
|
v
skipped

16. HITL Approval Architecture

When the agent reaches a privileged operation:

Identify the privileged application.

Persist the action as awaiting_approval.

Persist the workflow checkpoint.

Emit an approval-required event.

Interrupt the LangGraph execution.

Display the approval request in the dashboard.

Wait for the user decision.

The UI must show:

Application: Admin Console
Employee: Alex
Reason: Required by Marketing Manager access policy
Risk: Privileged access

Available actions:

Approve
Reject

There is no arbitrary user pause mechanism in MVP.

17. Approval Resume Mechanism

The approval API must resume the existing LangGraph execution rather than start a new run.

Conceptually:

POST /runs/{run_id}/approve

or:

POST /runs/{run_id}/reject

Backend process:

Find the run.

Confirm the run is awaiting approval.

Resolve its LangGraph thread_id.

Validate the requested decision.

Persist the decision/action state.

Resume the same checkpoint.

Continue execution.

Conceptually:

graph.invoke(
Command(resume="approved"),
config={
"configurable": {
"thread_id": run_id
}
}
)

Rejection:

graph.invoke(
Command(resume="rejected"),
config={
"configurable": {
"thread_id": run_id
}
}
)

The exact code may vary according to the installed LangGraph version, but the behavior must remain the same.

18. Approval Decision Contract

Valid approval decisions are exactly:

approved
rejected

No other decision values should be accepted.

19. Idempotency

Every action must be safe against workflow resumption and retry.

Before attempting a grant:

Read the action state.

If succeeded, do not repeat the action.

If skipped, do not execute it.

If awaiting_approval, wait for approval.

Otherwise continue execution.

This prevents completed operations from being duplicated after:

HITL resume

process retry

browser failure

graph recovery

20. Per-Action Recovery

Recovery attempts belong to individual actions.

Each action tracks:

recovery_attempts

Example:

Action A → recovery_attempts = 0
Action B → recovery_attempts = 1
Action C → recovery_attempts = 0

A global recovery counter must not be used to represent individual action recovery.

The MVP should allow a bounded retry, such as one controlled recovery attempt.

21. Deterministic Tools

The LLM should make decisions.

Deterministic tools should execute those decisions.

Examples:

find_employee()
get_role()
get_access_policy()
create_action_plan()
open_portal()
grant_application()
check_permission()
verify_permissions()
capture_evidence()

Tools must have typed inputs and outputs.

The LLM should not directly manipulate:

SQLite

browser internals

filesystem paths

raw HTTP requests

22. Playwright Browser Layer

Playwright is the computer-interaction layer.

The agent must interact with the synthetic portal through browser UI actions.

Examples:

navigate
click
fill
select
read visible text
wait for UI state
capture screenshot

The browser must not bypass the UI by directly calling the portal mutation endpoint.

For example, this is prohibited as the primary grant mechanism:

Agent → POST /portal/.../grant

The intended path is:

Agent
|
v
Playwright
|
v
Synthetic Portal UI
|
v
Portal API
|
v
SQLite

23. Playwright Configuration

Required environment variable:

PLAYWRIGHT_BASE_URL=http://localhost:3000

Local development:

http://localhost:3000

The demo should run Playwright in headed mode so evaluators can see the actual browser interaction.

Example configuration concept:

PLAYWRIGHT_HEADLESS=false

Headless execution may be used for automated tests.

24. Browser Result Contract

Browser operations should return a predictable result.

Minimum conceptual shape:

{
success,
error,
screenshot_path,
observed_state,
action_completed
}

Example:

{
success: true,
error: null,
screenshot_path: "evidence/run_123/action_003.png",
observed_state: "permission_granted",
action_completed: true
}

25. Synthetic Portal Architecture

The synthetic portal is part of the same Next.js application.

Routes:

/portal
/portal/employees
/portal/employees/:id
/portal/applications
/portal/policies
/portal/audit

It behaves like a small internal IT administration system.

The portal must provide enough UI for Playwright to:

Find employees.

View employee details.

View role/access information.

View applications.

Grant application access.

View permissions.

View audit history.

26. Portal API Boundary

FastAPI is responsible for portal data access and mutations.

Required conceptual endpoints:

GET  /portal/employees
GET  /portal/employees/{employee_id}

GET  /portal/applications

GET  /portal/policies

GET  /portal/audit

POST /portal/employees/{employee_id}/applications/{application_id}/grant

Next.js portal pages call these endpoints.

27. Portal Data Flow

Read:

Next.js Portal
|
v
FastAPI
|
v
SQLite
|
v
JSON response
|
v
Next.js Portal

Mutation:

Playwright
|
v
Portal UI
|
v
FastAPI
|
v
SQLite
|
+--> permissions
|
+--> audit_log

This keeps the portal realistic while preserving a single backend boundary.

28. Portal Grant Contract

The grant endpoint must:

Validate employee exists.

Validate application exists.

Check current permission state.

Apply deterministic failure injection if configured.

Update permission state.

Write an audit record.

Return the resulting state.

Example response:

{
success: true,
employee_id: "emp_001",
application_id: "app_github",
status: "granted"
}

29. Failure Injection

Controlled failure is implemented using:

applications.fails_on_grant

Example:

CRM
fails_on_grant = true

When Playwright attempts to grant CRM access:

Grant requested
|
v
Controlled failure
|
v
Browser observes failure

The failure must be:

deterministic

reproducible

visible

resettable

limited to the intended application

30. Recovery Authority

Recovery must use two sources of truth.

First: Browser-visible state

Playwright determines what the UI shows.

Example:

Application status: Granted

Second: SQLite state

Backend checks:

permissions.status

The recovery decision follows:

Browser = granted
SQLite  = granted
|
v
SUCCESSBrowser = unchanged
SQLite  = unchanged
|
v
SAFE RETRYBrowser != SQLite
|
v
FAIL SAFELY

The agent must not blindly repeat a grant when the previous outcome is uncertain.

31. Audit Trail

Every meaningful action must generate an audit record.

Examples:

Employee identified
Policy loaded
Application grant attempted
Application granted
Privileged access requested
Approval received
Approval rejected
Failure encountered
Recovery attempted
Verification completed

Audit records are stored in:

audit_log

32. Run API

Minimum conceptual endpoints:

POST /runs

GET /runs/{run_id}

GET /runs/{run_id}/events

POST /runs/{run_id}/approve

POST /runs/{run_id}/reject

GET /runs/{run_id}/evidence

GET /health

The exact REST naming can be finalized during implementation, but the capabilities are required.

33. Run Creation

When the user submits:

Onboard Alex as a Marketing Manager...

FastAPI should:

Generate run_id.

Create the runs row.

Create the LangGraph thread using the same ID.

Start graph execution.

Return the run identifier.

Allow the frontend to subscribe to execution events.

Conceptually:

POST /runs
|
v
Create run
|
v
Start LangGraph
|
v
Return run_id

34. SSE Event Architecture

The execution UI receives live updates through Server-Sent Events.

Flow:

LangGraph / Tools
|
v
Event Publisher
|
v
asyncio Queue
|
v
FastAPI SSE endpoint
|
v
Next.js

Events should be scoped by:

run_id

35. Thread-Safe SSE Publishing

LangGraph execution may be synchronous and blocking.

If:

graph.invoke()

runs inside a thread pool, it must not directly manipulate an asyncio.Queue from the worker thread.

This is a mandatory implementation rule.

The event publisher must use the event loop's thread-safe mechanism:

loop.call_soon_threadsafe(
queue.put_nowait,
event
)

Conceptually:

Worker Thread
|
| publish event
v
loop.call_soon_threadsafe(...)
|
v
Asyncio Event Loop
|
v
asyncio.Queue
|
v
SSE Client

This avoids unsafe cross-thread queue access.

36. SSE Event Contract

Events should contain enough information for the UI to update without reconstructing backend state.

Minimum:

{
run_id,
event_type,
timestamp,
status,
message,
action_id
}

Possible event types:

run_started
step_started
decision
action_started
action_succeeded
action_failed
approval_required
approval_received
recovery_started
recovery_completed
verification_started
verification_completed
run_completed
run_failed

37. CORS

FastAPI must explicitly allow the frontend origin during local development.

Example:

http://localhost:3000

Production origins should be configurable rather than hardcoded.

38. Environment Configuration

Minimum environment variables:

OPENAI_API_KEY=

IT_OPS_DB_PATH=./data/it_ops.db

CHECKPOINT_DB_PATH=./data/checkpoints.db

NEXT_PUBLIC_API_URL=http://localhost:8000

PLAYWRIGHT_BASE_URL=http://localhost:3000

PLAYWRIGHT_HEADLESS=false

LangSmith Observability

LangSmith is a lightweight observability layer for the AI agent and LangGraph execution.

It is used to:

Trace LangGraph execution.

Inspect LLM calls and agent decisions.

Debug workflow failures.

Inspect execution timing and errors.

Correlate LangSmith traces with the application's run_id.

LangSmith is not part of the core execution path.

The application must continue to function if LangSmith is unavailable or tracing is disabled.

The integration must remain intentionally small. Do not add custom observability infrastructure, complex LangSmith evaluation pipelines, datasets, or additional monitoring systems.

Required configuration

Add the following to .env.example:

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=it-ops

The implementation should use the installed LangChain/LangGraph/LangSmith-compatible tracing mechanism rather than building a custom tracing layer.

Run correlation

Where practical, LangGraph runs should be associated with the application's existing:

run_id

This allows the following to be correlated:

run_id
|
+--> LangGraph thread
+--> SQLite run/action state
+--> SSE execution events
+--> Evidence directory
+--> LangSmith trace

Architectural rule

LangSmith provides observability only.

It must not become the source of truth for:

Workflow state

Permissions

Actions

Runs

Audit records

Verification

Evidence

Those responsibilities remain with LangGraph and SQLite as defined elsewhere in this architecture.

39. Evidence Architecture

Evidence is stored locally for the MVP.

Structure:

evidence/
└── <run_id>/
├── action_001.png
├── action_002.png
├── action_003.png
├── verification.png
└── result.json

Evidence should include:

Browser screenshots

Action summaries

Verification results

Final permissions

Audit information

Final run result

FastAPI serves evidence to the frontend.

40. Evidence Deployment Limitation

Local evidence storage is the primary MVP implementation.

Therefore:

local development
|
v
evidence/<run_id>/

works reliably.

If deployed to an environment with ephemeral filesystem storage, evidence persistence is not guaranteed across restarts.

Persistent external object storage is explicitly out of MVP scope unless deployment requirements make it necessary.

41. result.json Contract

The final result should use a predictable structure.

Minimum:

{
"run_id": "...",
"goal": "...",
"status": "...",
"employee": {
"id": "...",
"name": "...",
"role": "..."
},
"actions_performed": [],
"permissions_granted": [],
"verification_result": {},
"timestamp": "..."
}

The result should provide enough information for the evaluator to understand what happened without inspecting internal logs.

42. Verification

Verification must occur after execution.

The verifier independently checks:

Correct employee.

Correct role.

Required applications.

Privileged authorization decision.

Final permissions.

Failure/recovery result.

Audit records.

Evidence availability.

The final status must reflect verification.

Example:

execution completed
|
v
verification
|
+----+----+
|         |
PASS       FAIL
|         |
v         v
complete    failed

43. Frontend Architecture

The dashboard provides:

Goal input

Enter onboarding goal...

Execution view

Shows:

Run status

Current step

Execution timeline

Decision summaries

Action states

Approval request

Recovery status

Final verification

Approval UI

Shows:

Privileged action requires approval

with:

Approve
Reject

Final result

Shows:

Employee

Role

Applications granted

Applications skipped

Failures/recovery

Verification

Evidence

There is no arbitrary pause button.

44. Agent Reasoning Visibility

The system must not expose hidden chain-of-thought.

Instead, it shows concise decision summaries.

Examples:

✓ Identified Alex — Marketing Manager

✓ Loaded Marketing access policy

✓ GitHub access required

✓ Granted GitHub access

⚠ Admin Console requires approval

👤 Approval received

✓ Granted Admin Console access

✓ Verified final permissions

These summaries are generated as user-facing execution events.

45. Adaptability

The same implementation must support different inputs without code changes.

Example 1:

Onboard Alex as a Marketing Manager.

Example 2:

Onboard Priya as a Finance Analyst.

The system should dynamically determine:

employee
↓
role
↓
policy
↓
required applications
↓
privileged applications

No employee-specific workflow should be hardcoded.

46. Security and Data Boundaries

All data is synthetic.

The project must not contain:

Real employee information

Real credentials

Production IAM credentials

Production API tokens

Real company access systems

Environment secrets belong in .env.

.env must not be committed.

The application is a controlled demonstration environment, not a production IAM system.

47. Testing Strategy

Testing should focus on the assignment's evaluation criteria.

Unit tests

Test:

Policy resolution

Action planning

Action state transitions

Failure injection

Verification logic

Recovery logic

Integration tests

Test:

FastAPI → SQLite

LangGraph → SQLite checkpoint

HITL interruption/resume

Approval/rejection

SSE events

Portal API

Browser tests

Test:

Employee lookup

Application lookup

Grant interaction

Visible failure

Recovery

Final permission verification

48. Critical End-to-End Test

The most important test should execute:

Natural-language goal
↓
Employee identification
↓
Policy resolution
↓
Browser interaction
↓
Normal access grant
↓
Privileged access detection
↓
HITL pause
↓
Approval
↓
Resume
↓
Privileged grant
↓
Independent verification
↓
Evidence

This must work without manual database manipulation.

49. Failure-Recovery Test

The second critical test:

Start onboarding
|
v
Grant Application A
|
v
SUCCESS
|
v
Grant Application B
|
v
CONTROLLED FAILURE
|
v
Detect failure
|
v
Inspect browser + SQLite state
|
v
Recover safely
|
v
Verify

The system must demonstrate that Application A is not granted twice.

50. Local Development Flow

Required setup sequence:

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Install frontend dependencies
npm install

# Seed deterministic database
python scripts/seed_db.py

# Start frontend
npm run dev

# Start backend
uvicorn backend.main --reload

The exact commands may be adjusted to the final repository structure, but the setup must include:

playwright install chromium

before browser execution.

51. Local Runtime

Expected local services:

Next.js
http://localhost:3000

FastAPI
http://localhost:8000

Database files:

data/it_ops.db
data/checkpoints.db

Browser:

Playwright → http://localhost:3000/portal

52. Deployment

Deployment is lower priority than core functionality.

Potential deployment:

Next.js → Vercel
FastAPI → suitable Python host

However, deployment must not delay:

Browser execution

Workflow correctness

HITL

Failure recovery

Verification

Evidence

Local execution is the primary acceptance environment.

53. Time-Conscious Implementation Strategy

Target:

~11 focused hours

with approximately:

Synthetic portal + seed data          2.5h
LangGraph + agent + tools             3.0h
FastAPI + SSE + HITL                  1.5h
Dashboard                             1.5h
Failure/recovery + verification      1.0h
README + Engineering Notes + demo    1.0h
Polish/debug buffer                   0.5h
------------------------------------------
Total                                11.0h

If time becomes constrained, prioritize in this order:

Browser execution

Correct workflow

HITL approval

Failure recovery

Verification/evidence

Adaptability

UI polish

Deployment

54. Engineering Documentation

The repository must contain:

README.md
ENGINEERING_NOTES.md

README

Must explain:

Product overview

Architecture

Repository structure

Prerequisites

Environment variables

Installation

Playwright browser installation

Database setup

Seed command

Backend startup

Frontend startup

Demo workflow

Model/account requirements

ENGINEERING_NOTES

Must explain:

Architecture decisions

Why each major technology was selected

Personal contribution

AI/Cursor assistance

Trade-offs

Known limitations

Failure/recovery approach

Future improvements

55. Assignment Alignment

Assignment Requirement

Architecture Implementation

Plain-English goal

Goal input + LLM interpretation

Computer operation

Playwright

Browser interaction

Synthetic portal

Multi-step workflow

LangGraph

Adaptability

Policy/employee-driven planning

Failure recovery

Controlled failure + per-action recovery

Avoid duplicate actions

SQLite action state + idempotency

Verification

Independent verification

Evidence

Screenshots + result.json + audit

Human control

HITL approval/rejection

Progress visibility

SSE + execution timeline

Synthetic data

Seeded SQLite dataset

Setup reproducibility

seed_db.py

Engineering explanation

ENGINEERING_NOTES.md

56. Architecture Invariants

The following rules must not be violated during implementation.

Invariant 1

Playwright must perform actual browser interaction.

Invariant 2

The agent must not bypass the portal UI to complete the workflow.

Invariant 3

FastAPI is the only backend/API boundary.

Invariant 4

Next.js must not directly access SQLite.

Invariant 5

Domain state lives in:

it_ops.db

Invariant 6

LangGraph checkpoint state lives in:

checkpoints.db

Invariant 7

LangGraph owns workflow position.

Invariant 8

SQLite owns actual domain/action state.

Invariant 9

HITL must resume the same checkpoint.

Invariant 10

Completed actions must not be replayed unnecessarily.

Invariant 11

Recovery must inspect actual state before retrying.

Invariant 12

Rejected privileged actions transition directly:

awaiting_approval → rejected → skipped

Invariant 13

Recovery attempts are tracked per action.

Invariant 14

SSE publishing from a worker thread must use:

loop.call_soon_threadsafe(...)

rather than directly manipulating an asyncio.Queue.

Invariant 15

The browser setup must install Chromium explicitly:

playwright install chromium

Invariant 16

The system must remain within the PRD v1.2 scope.

57. Implementation Decision Rule

If an implementation choice is unclear, use this order:

Does it satisfy PRD v1.2?

Does it preserve the architecture invariants?

Does it improve reliability?

Does it reduce implementation complexity?

Can it realistically be completed within the time budget?

If a proposed feature adds complexity without improving the assignment's core evaluation criteria, do not implement it.

58. Implementation Readiness Checklist

Before implementation begins, confirm:

One Next.js application

FastAPI backend

Synthetic IT portal

Playwright browser interaction

LangGraph orchestration

Persistent LangGraph checkpointer

Separate checkpoints.db

Separate it_ops.db

Runs table

Actions table

Audit table

Deterministic seed script

Controlled failure injection

Per-action recovery state

HITL interruption

HITL checkpoint resume

Approval/rejection contract

SSE event architecture

Thread-safe SSE publishing

CORS

Frontend API configuration

Playwright base URL configuration

Headed demo mode

Evidence storage

result.json

Independent verification

Adaptability

README

Engineering Notes

Browser installation documented

59. Final Architecture Principle

The architecture intentionally separates reasoning, execution, state, and verification.

LLM
↓
Decision / Planning
↓
LangGraph
↓
Deterministic Tools
↓
Playwright
↓
Synthetic IT Portal
↓
SQLite Domain State
↓
Independent Verification
↓
Evidence

With:

LangGraph → workflow state
SQLite    → actual domain/action state
Playwright → real computer interaction
FastAPI   → backend boundary
SSE       → execution visibility
HITL      → human authorization

The resulting system is intentionally narrow:

One useful IT operations workflow, executed through a real browser, with human approval, controlled failure recovery, independent verification, and evidence of completion.