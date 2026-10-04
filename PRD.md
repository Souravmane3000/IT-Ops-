**IT Ops — Product Requirements Document (PRD)** 

**Version:** 1.2 

**Status:** Final — Ready for Architecture 

**Project:** IT Ops 

**Product:** AI Computer Operator for IT Operations 

**Primary Workflow:** Employee Onboarding & Access Provisioning 

**1\. Product Overview** 

**IT Ops** is an AI-powered computer operator that receives an employee onboarding/access-management goal in plain English and operates a synthetic internal IT administration portal through a real browser. 

The system must: 

1.  Understand the user's goal. 
    
2.  Determine the required actions. 
    
3.  Operate the IT portal through Playwright. 
    
4.  Respect authorization boundaries. 
    
5.  Pause for human approval when privileged access is requested. 
    
6.  Recover safely from a meaningful failure. 
    
7.  Verify the final state independently. 
    
8.  Produce evidence of what happened. 
    

The project is designed around the Hulchul AI Engineering Internship Build Assignment, which evaluates actual application interaction, adaptability, failure recovery, verified completion, and human control. 

**2\. Problem Statement** 

IT onboarding involves repetitive operational work: 

*   Finding an employee. 
    
*   Determining their role. 
    
*   Looking up access requirements. 
    
*   Granting application access. 
    
*   Handling privileged-access requests. 
    
*   Verifying that permissions were actually applied. 
    

IT Ops demonstrates how an AI agent can perform this workflow through a computer interface instead of simply recommending what a human should do. 

**3\. Product Goal** 

Build a **reliable AI computer operator for employee onboarding and access provisioning** within the assignment's limited development window. 

Example: 

**"Onboard Alex, who is joining as a Marketing Manager. Give Alex the applications required by the company's access policy, but ask me for approval before granting any privileged access."** 

The system must execute the workflow, request approval when required, recover from failure, and verify the final state. 

**4\. Target User** 

**Primary user:** IT administrator / IT operations manager. 

The user can: 

*   Enter an operational goal. 
    
*   Start execution. 
    
*   Monitor progress. 
    
*   Approve or reject privileged actions. 
    
*   Review the final result and evidence. 
    

**Arbitrary user-initiated mid-execution pause is out of scope for the MVP.** 

The supported pause mechanism is the agent's human-approval checkpoint. 

**5\. Core Workflow** 

The MVP focuses on **Employee Onboarding & Access Provisioning**. 

Natural-language goal         ↓ Understand request         ↓ Identify employee         ↓ Determine role         ↓ Read access policy         ↓ Create execution plan         ↓ Open IT administration portal         ↓ Grant permitted application access         ↓ Privileged action?       ↙       ↘     No         Yes     ↓           ↓ Continue    Pause for approval                 ↓           Human approves/rejects                 ↓           Resume / stop action                 ↓         Verify final state                 ↓         Generate evidence                 ↓             Complete 

**6\. Example Goals** 

**Primary scenario** 

"Onboard Alex, who is joining as a Marketing Manager. Give Alex the applications required by the company's access policy, but ask me for approval before granting any privileged access." 

**Variation** 

"Onboard Priya as a Finance Analyst and give her the applications required by policy." 

The same implementation must handle different employees, roles, and policies without code changes. 

**7\. Synthetic IT Portal** 

The project will contain a controlled **synthetic internal IT administration portal**. 

The portal will be implemented **inside the same Next.js application** as the IT Ops dashboard. 

/                       → IT Ops Dashboard /run/:id                → Execution View /portal                 → Synthetic IT Portal /portal/employees       → Employees /portal/employees/:id   → Employee Details /portal/applications    → Applications /portal/policies        → Access Policies /portal/audit           → Audit History 

The agent must interact with the portal through **Playwright browser automation**, including navigation, clicks, forms, and state verification. 

It must not bypass the browser by directly modifying the portal's database to complete actions. 

The assignment explicitly requires actual application interaction and execution. 

**8\. Data Model** 

SQLite will provide persistence for the synthetic environment. 

**employees** 

*   id 
    
*   name 
    
*   role\_id 
    

**roles** 

*   id 
    
*   name 
    

**applications** 

*   id 
    
*   name 
    
*   privileged 
    
*   fails\_on\_grant 
    

**access\_policies** 

*   id 
    
*   role\_id 
    
*   application\_id 
    
*   required 
    

**permissions** 

*   id 
    
*   employee\_id 
    
*   application\_id 
    
*   status 
    

**audit\_log** 

*   id 
    
*   run\_id 
    
*   employee\_id 
    
*   action 
    
*   status 
    
*   timestamp 
    
*   details 
    

The detailed schema and relationships will be defined in ARCHITECTURE.md. 

**9\. Database Seeding** 

The synthetic environment must have deterministic initial data. 

A seed script will populate: 

*   Employees. 
    
*   Roles. 
    
*   Applications. 
    
*   Access policies. 
    
*   Initial permissions. 
    
*   Demo/failure configuration. 
    

Example: 

scripts/ └── seed\_db.py 

Run with: 

python scripts/seed\_db.py 

The seed process must be: 

*   Deterministic. 
    
*   Repeatable. 
    
*   Safe to run against a fresh local database. 
    
*   Suitable for resetting the demo environment. 
    

The README must document database initialization and seeding. 

This ensures the reviewer can reproduce the same environment used for development and demonstration. 

**10\. Failure Injection & Recovery** 

Failure recovery is a core MVP capability. 

A deterministic failure mechanism will be implemented through the synthetic application data. 

Example: 

applications  Slack privileged = false fails\_on\_grant = true 

When the agent attempts to grant access to that application, the portal intentionally fails the operation. 

The failure must be: 

*   Deterministic. 
    
*   Reproducible. 
    
*   Resettable. 
    
*   Visible to the agent. 
    

**Recovery** 

When an action fails, the agent must: 

1.  Detect the failure. 
    
2.  Determine which actions have already succeeded. 
    
3.  Preserve successful state. 
    
4.  Avoid duplicating completed actions. 
    
5.  Retry the failed action when safe. 
    
6.  Verify the result. 
    
7.  Continue if recovered. 
    
8.  Report a blocker if recovery fails. 
    

**11\. Action State & Idempotency** 

Each significant operation has an explicit state: 

pending running succeeded failed awaiting\_approval skipped 

The system must be able to determine what has already happened before retrying an operation. 

This state model is used specifically to prevent duplicate or unintended actions during recovery. 

**12\. State Ownership: LangGraph vs SQLite** 

The system deliberately separates **workflow state** from **action/domain state**. 

**LangGraph owns workflow state** 

LangGraph's checkpointer is responsible for: 

*   Current graph position. 
    
*   Agent workflow state. 
    
*   Human-approval interruption state. 
    
*   Resume state. 
    
*   Thread/run execution context. 
    

It answers: 

**"Where is the agent in the workflow?"** 

**SQLite owns persistent application/action state** 

SQLite is responsible for: 

*   Employees. 
    
*   Roles. 
    
*   Applications. 
    
*   Policies. 
    
*   Permissions. 
    
*   Audit history. 
    
*   Individual action execution state. 
    

It answers: 

**"What has actually happened?"** 

**Ownership rule** 

LangGraph     ↓ Workflow position + execution context  SQLite     ↓ Domain state + action state 

Neither system should duplicate ownership of the other's state. 

During recovery, LangGraph determines where the workflow resumes, while SQLite determines which individual actions have already succeeded, failed, or remain pending. 

**13\. Human Approval & Authorization** 

The agent may autonomously perform: 

*   Employee lookup. 
    
*   Role/policy lookup. 
    
*   Standard application access. 
    
*   Verification. 
    
*   Non-destructive navigation. 
    

The agent must request human approval before: 

*   Granting privileged application access. 
    
*   Performing an action explicitly marked as approval-required. 
    

**Approval flow** 

Detect privileged action         ↓ Persist workflow state         ↓ Pause at HITL checkpoint         ↓ Display approval request         ↓ Approve / Reject         ↓ Resume same workflow state 

Previously completed actions must not be replayed after resumption. 

The assignment explicitly requires human control when an action exceeds the agent's authority. 

**14\. Agent Responsibilities** 

The agent must: 

1.  Understand the natural-language goal. 
    
2.  Identify the employee. 
    
3.  Determine the employee's role. 
    
4.  Load the relevant policy. 
    
5.  Determine required applications. 
    
6.  Create an execution plan. 
    
7.  Navigate the portal. 
    
8.  Execute authorized actions. 
    
9.  Detect privileged operations. 
    
10.  Request human approval. 
    
11.  Resume after approval/rejection. 
    
12.  Detect failures. 
    
13.  Recover safely. 
    
14.  Track action state. 
    
15.  Verify final permissions. 
    
16.  Produce an execution summary and evidence. 
    

**15\. Agent Reasoning Visibility** 

The UI will display **concise decision summaries**, not hidden chain-of-thought. 

Example: 

✓ Identified Alex — Marketing Manager ✓ Loaded Marketing access policy ✓ GitHub access required ✓ Granted GitHub access ⚠ Admin Console requires approval 👤 Approval received ✓ Granted Admin Console access ✓ Verified final permissions 

This gives the reviewer visibility into meaningful agent decisions without exposing private internal reasoning. 

**16\. Verification** 

The agent's claim of success is not sufficient proof. 

After execution, the system must independently verify: 

*   Correct employee was modified. 
    
*   Required applications are present. 
    
*   Privileged access was authorized. 
    
*   Failed actions were recovered or reported. 
    
*   Final permissions match the intended result. 
    
*   Relevant audit records exist. 
    

**17\. Evidence** 

Each run must produce evidence of execution and completion. 

Evidence can include: 

*   Execution timeline. 
    
*   Agent action summaries. 
    
*   Final permission state. 
    
*   Verification result. 
    
*   Audit records. 
    
*   Browser screenshots. 
    

**Storage** 

For the MVP: 

evidence/ └── /     ├── action-01.png     ├── action-02.png     └── final-state.png 

FastAPI will serve evidence files to the frontend. 

No external object-storage system will be introduced unless required for deployment. 

**18\. Dashboard** 

The dashboard contains: 

**Goal Input** 

Enter your IT operations goal...  \[ Start Run \] 

**Execution View** 

*   Current status. 
    
*   Current agent step. 
    
*   Action timeline. 
    
*   Concise decision summaries. 
    
*   Approval request. 
    
*   Failure/recovery status. 
    

**Final Result** 

*   Completed / Blocked / Rejected. 
    
*   Actions performed. 
    
*   Final access state. 
    
*   Verification result. 
    
*   Evidence. 
    

There is **no arbitrary user pause button** in the MVP. 

**19\. Real-Time Execution Updates** 

The dashboard must receive execution updates during active runs. 

The intended mechanism is **Server-Sent Events (SSE)**: 

LangGraph / Tools        ↓ Execution events        ↓ FastAPI        ↓ SSE        ↓ Next.js Dashboard 

The detailed event schema and lifecycle will be defined in ARCHITECTURE.md. 

**20\. Technical Stack** 

**Layer** 

**Technology** 

Frontend 

Next.js 

Language 

TypeScript 

Styling 

Tailwind CSS 

Backend 

Python + FastAPI 

Agent orchestration 

LangGraph 

LLM 

OpenAI API 

Browser automation 

Playwright 

Database 

SQLite 

Observability 

LangSmith —\\ — lightweight observability/debugging 

Development 

Cursor 

Version control 

Git + GitHub 

Deployment 

Vercel if time permits 

**Explicitly excluded** 

*   shadcn/ui 
    
*   Multi-agent architecture 
    
*   External database infrastructure 
    
*   External object storage 
    
*   Complex deployment infrastructure 
    

**21\. Engineering Decisions** 

**Single-agent architecture** 

One LangGraph agent is sufficient for the bounded workflow. A multi-agent architecture would add complexity without improving the MVP. 

**LLM + deterministic tools** 

The LLM handles interpretation and decision-making. 

Deterministic tools handle: 

*   Browser operations. 
    
*   State updates. 
    
*   Verification. 
    
*   Controlled recovery. 
    

The LLM should not directly generate unrestricted browser commands. 

**Playwright** 

Playwright provides actual browser-based computer interaction required by the assignment. 

**LangGraph** 

LangGraph provides explicit workflow state, HITL interruption, persistence, and recovery. 

**LangSmith Observability** 

LangSmith will be integrated as a lightweight observability and debugging layer for the AI agent. It will be used to trace LangGraph execution and LLM interactions, inspect failures, and correlate agent runs with the application's run\_id. LangSmith is not part of the core execution path and must not be required for the application to function. The integration should remain minimal and must not introduce custom observability infrastructure, evaluation pipelines, or additional product scope. 

Required configuration should be documented through environment variables, including the LangSmith API key and project/tracing configuration. LangSmith traces should use the application's run\_id where practical so that agent execution can be correlated with SQLite state, SSE events, and evidence. 

**Scope:** Development observability, debugging, and execution tracing only. 

**SQLite** 

SQLite keeps the synthetic environment simple, reproducible, and local. 

**OpenAI** 

OpenAI is selected because of existing implementation familiarity, straightforward API integration, and reduced development risk within the assignment's limited time. 

The model provider should remain replaceable through a small abstraction where practical. 

**Single Next.js application** 

The dashboard and synthetic IT portal share one application to minimize development, deployment, and integration overhead. 

**22\. Adaptability** 

The implementation must support different employees, roles, and policies without code changes. 

Example: 

Alex Marketing Manager     ↓ Marketing Policy     ↓ Required Applications 

and: 

Priya Finance Analyst     ↓ Finance Policy     ↓ Required Applications 

The workflow remains constant while the underlying data determines the actions. 

**23\. Submission Deliverables** 

Source Code README.md ENGINEERING\_NOTES.md Demo Video 

**README** 

Must contain: 

*   Overview. 
    
*   High-level architecture. 
    
*   Setup. 
    
*   Environment variables. 
    
*   Database setup. 
    
*   Seed instructions. 
    
*   Run instructions. 
    
*   Demo instructions. 
    
*   Model/account requirements. 
    

**ENGINEERING\_NOTES** 

Must document: 

*   Engineering decisions. 
    
*   Reasons for those decisions. 
    
*   Personal contribution. 
    
*   AI/Cursor assistance. 
    
*   Limitations. 
    
*   Trade-offs. 
    
*   Future improvements. 
    

The assignment explicitly requests source/setup instructions and an engineering note covering these areas. 

**24\. Demo Plan** 

The demo must remain within the assignment's **5-minute limit**. 

**Segment** 

**Target** 

Introduction + goal 

20 sec 

Full workflow + HITL 

2:00 

Variation 

1:00 

Failure + recovery 

1:20 

Final evidence 

20 sec 

**Total** 

**5:00** 

The demo prioritizes actual execution over explanation. 

**25\. MVP Success Criteria** 

The MVP is successful when a reviewer can: 

*   Enter a plain-English onboarding goal. 
    
*   See the agent interpret it. 
    
*   See actual browser interaction. 
    
*   See multiple operational steps execute. 
    
*   See privileged access trigger human approval. 
    
*   Approve/reject the action. 
    
*   See execution resume correctly. 
    
*   See a controlled failure. 
    
*   See safe recovery without duplicate actions. 
    
*   See final state independently verified. 
    
*   Inspect evidence. 
    
*   Run a different employee/role scenario without changing code. 
    
*   Recreate the same environment using the seed script. 
    

**26\. Non-Goals** 

The MVP will not attempt to build: 

*   Real enterprise IAM integration. 
    
*   Real employee accounts. 
    
*   Real credentials. 
    
*   Production security infrastructure. 
    
*   A generalized autonomous desktop agent. 
    
*   Multi-agent architecture. 
    
*   Complex authentication/billing. 
    
*   Large-scale enterprise deployment. 
    
*   Multiple unrelated IT workflows. 
    
*   Arbitrary browser automation across external websites. 
    
*   External storage infrastructure unless deployment requires it. 
    

The objective is a **reliable demonstration of one useful computer-operator workflow**, not a production SaaS platform. 

**27\. Time & Scope Constraints** 

The assignment targets approximately **8–12 focused hours**. 

**Target allocation** 

**Component** 

**Target** 

Synthetic portal + seed data 

2.5 h 

LangGraph + agent + tools 

3 h 

FastAPI + SSE + HITL 

1.5 h 

Dashboard 

1.5 h 

Failure/recovery + verification 

1 h 

Demo + engineering notes + polish 

1.5 h 

**Total** 

**11 h** 

Approximately **1 hour remains for debugging**. 

**Priority order** 

1\. Browser execution 2. Correct workflow 3. HITL 4. Failure recovery 5. Verification/evidence 6. Adaptability 7. UI polish 8. Deployment 

If time runs short, deployment and visual polish are sacrificed before core execution capabilities. 

**28\. Assignment Traceability** 

**Assignment Requirement** 

**IT Ops Implementation** 

Plain-English goal 

Natural-language onboarding request 

Multi-step work 

Employee → policy → apps → provisioning → verification 

Browser interaction 

Playwright + synthetic IT portal 

Adaptability 

Different employees, roles, and policies 

Failure recovery 

Deterministic failure injection 

Avoid duplicate actions 

SQLite action state + recovery logic 

Verified completion 

Independent verification 

Evidence 

Timeline, audit records, permissions, screenshots 

Human control 

Privileged-access approval 

Pause/resume 

Persistent LangGraph HITL checkpoint 

Progress visibility 

SSE execution events 

Synthetic data 

Controlled IT environment 

Reproducibility 

Deterministic database seed 

Source/setup 

GitHub + README 

Engineering explanation 

ENGINEERING\_NOTES.md 

Demo 

Full workflow + variation + failure recovery 

These capabilities directly map to the assignment's requirements around usefulness, execution, adaptability, reliability, verification, and human control. 

**29\. Definition of Done** 

IT Ops is ready for submission when a reviewer can: 

1.  Enter a natural-language employee onboarding request. 
    
2.  Watch the agent operate the browser. 
    
3.  See multiple decisions and actions execute. 
    
4.  See privileged access trigger an approval checkpoint. 
    
5.  Approve or reject the action. 
    
6.  See execution resume without replaying completed actions. 
    
7.  Observe a controlled failure. 
    
8.  See safe recovery. 
    
9.  See the final state independently verified. 
    
10.  Inspect evidence showing what actually happened. 
    
11.  Run a different employee/role scenario without modifying code. 
    
12.  Recreate the demo environment using the seed script.