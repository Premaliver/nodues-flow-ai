
# Smart NoDues AI — Architecture Plan (Option A)

Production-grade University No-Dues platform built on the Lovable-supported stack. Same product surface as the original brief (9 role dashboards, auto-routed approvals, OCR receipt verification, AI assistant, digitally signed admit cards) — implemented natively on this platform.

---

## 1. Technology Stack (fixed to this platform)

- **Frontend:** React 19 + TypeScript, TanStack Router/Start, Tailwind v4, shadcn/ui, GSAP, AOS, Chart.js, SweetAlert2, Lottie, Font Awesome. Design system in `src/styles.css` (oklch tokens, glass/aurora surfaces).
- **Backend:** TanStack `createServerFn` (app-internal RPC) + server routes under `src/routes/api/public/*` (webhooks / cron). Runs on Cloudflare Workers.
- **Database / Auth / Storage / Realtime:** Lovable Cloud (Postgres + RLS + Supabase Auth + Storage + Realtime channels). Replaces MongoDB and Flask-SocketIO.
- **AI / OCR:** Lovable AI Gateway (`google/gemini-3-flash-preview` for chat/assistant, `google/gemini-2.5-flash` for vision OCR + document validation, `openai/gpt-image-2` only if seals needed). Replaces EasyOCR/OpenCV — Gemini vision is more accurate on receipts and runs on Workers.
- **PDF + QR:** `pdf-lib` + `qrcode` inside a server function; signed with HMAC over payload; stored in Storage bucket `admit-cards`.
- **Email:** Lovable Cloud transactional email (OTP, approvals, rejections).

---

## 2. Folder Structure

```text
src/
  routes/
    __root.tsx                       # shell, providers, head metadata
    index.tsx                        # landing page
    auth/                            # login, register, otp, reset
    _authenticated/
      route.tsx                      # gate (managed)
      dashboard.student.tsx
      dashboard.accounts.tsx
      dashboard.hostel.tsx
      dashboard.mess.tsx
      dashboard.transport.tsx
      dashboard.scholarship.tsx
      dashboard.hod.tsx
      dashboard.exam.tsx
      dashboard.admin.tsx
      applications.$id.tsx           # detail + timeline
    api/public/
      webhooks.email-otp.ts
      cron.reminders.ts
  components/
    ui/                              # shadcn
    shell/                           # sidebar, topbar, theme toggle
    dashboards/<role>/               # per-role widgets
    approvals/{Timeline,ProgressBar,RemarksDialog,ReceiptViewer}.tsx
    ai/{Assistant,ReceiptUploader,ValidationBadge}.tsx
  lib/
    workflow.ts                      # route engine (pure)
    workflow.functions.ts            # server fns: submit, approve, reject
    applications.functions.ts        # queries per role
    ocr.functions.ts                 # AI OCR + validation
    assistant.functions.ts           # student AI chat
    admit-card.functions.ts          # PDF + QR + signature
    ai-gateway.server.ts             # gateway helper (see ai-sdk knowledge)
    pdf.server.ts, crypto.server.ts
  integrations/supabase/{client,client.server,auth-middleware,types}.ts
supabase/migrations/*.sql
```

---

## 3. Database Model (Postgres, all `public` schema, RLS on)

Enums:
- `app_role`: student, accounts, hostel, mess, transport, scholarship, hod, exam, super_admin
- `student_category`: day_scholar, hosteller, transport, hosteller_transport, scholarship, hosteller_scholarship, transport_scholarship
- `step_status`: pending, in_review, approved, rejected, skipped
- `application_status`: draft, submitted, in_progress, approved, rejected, admit_generated
- `doc_type`: nodues_form, semester_fee_receipt, exam_fee_receipt

Core tables:

| Table | Key columns | Purpose |
|---|---|---|
| `profiles` | id (=auth.users), roll_no, reg_no, email, name, phone, avatar_url | Student profile; auto-created via trigger on signup |
| `user_roles` | user_id, role (app_role) | Roles table (never on profile — enforced via `has_role()` security-definer fn) |
| `departments` | id, name, code | HOD scope |
| `students` | user_id, department_id, course, semester, category, hostel_id, room_no, bus_route, scholarship_id | Enrollment record; drives routing |
| `hostels` / `bus_routes` / `scholarships` | id, name, fee, warden_id/... | Master data |
| `authority_accounts` | user_id, role, must_change_password, created_by | Admin-provisioned staff; forces password change on first login |
| `applications` | id, student_id, semester, category_snapshot, status, current_step_id, created_at, submitted_at | One per semester per student |
| `application_steps` | id, application_id, seq, role, dept_id (nullable), status, actor_id, remarks, decided_at | Ordered workflow steps (materialized when app submitted) |
| `documents` | id, application_id, type (doc_type), storage_path, sha256, ocr_json, ai_validation, verified | Uploaded PDFs/images |
| `activity_log` | id, application_id, actor_id, action, meta jsonb, created_at | Immutable audit trail |
| `notifications` | id, user_id, application_id, title, body, kind, read_at | Fed to Realtime channel `user:{id}` |
| `admit_cards` | application_id, pdf_path, qr_payload, signature, issued_at, issued_by | Final artifact |
| `otp_codes` | email, code_hash, expires_at, attempts | Email OTP for registration/reset |
| `settings` | key, value jsonb | System settings (super admin) |

Indexes: `applications(student_id, semester)`, `application_steps(application_id, seq)`, `application_steps(role, status)` (fast per-role queues), `documents(sha256)` for duplicate detection, `activity_log(application_id, created_at)`.

Every `CREATE TABLE public.*` migration includes `GRANT SELECT,INSERT,UPDATE,DELETE … TO authenticated; GRANT ALL … TO service_role;` and enables RLS.

**RLS pattern:**
- `profiles`, `students`: user reads/updates own row; staff read via `has_role()`.
- `applications`: student reads own; step-role reads rows where `EXISTS(app_steps.role = current_role AND status IN ('pending','in_review'))`; HOD scoped to department; super_admin all.
- `application_steps`: same as parent; UPDATE allowed only when `role = current_role AND status IN ('pending','in_review')`.
- `documents`: student owner + any role currently on an open step of that application.
- `activity_log`, `admit_cards`: read own / role-scoped; INSERT via server fns only.

---

## 4. Workflow Engine

Pure function `computeRoute(student)` in `src/lib/workflow.ts` returns an ordered array of `{ seq, role, dept_id? }`:

```text
day_scholar                → accounts → hod → exam
hosteller                  → accounts → hostel → mess → hod → exam
transport                  → accounts → transport → hod → exam
scholarship                → accounts → scholarship → hod → exam
hosteller_transport        → accounts → hostel → mess → transport → hod → exam
hosteller_scholarship      → accounts → hostel → mess → scholarship → hod → exam
transport_scholarship      → accounts → transport → scholarship → hod → exam
```

Server fn `submitApplication` (auth: student):
1. Validate 3 documents uploaded + OCR passed.
2. Snapshot student category.
3. Insert `applications` row + all `application_steps` rows (seq 1..N), mark step 1 `in_review`.
4. Insert `activity_log`, broadcast Realtime `application:{id}` + notify next-role users.

Server fn `decideStep({stepId, decision, remarks})` (auth: role-guarded via middleware + `has_role`):
- Guard: step is current + role matches + status is `in_review`.
- Approve → mark step approved; if next step exists → set it `in_review` and notify that role; else set application `approved` and enqueue admit card generation.
- Reject → requires non-empty remarks; set step + application `rejected`; notify student.
- All writes in one transaction via `.rpc()`; log to `activity_log`; publish Realtime event.

Bulk approve (accounts/HOD): iterate `decideStep` server-side with a max batch size; each row still audited.

---

## 5. AI / OCR Pipeline

`extractReceipt(documentId)` server fn:
1. Fetch signed URL from Storage.
2. Call Gateway `/v1/chat/completions` with `google/gemini-2.5-flash`, message content = `[{type:'text', text: RECEIPT_SCHEMA_PROMPT}, {type:'image_url', image_url:{url}}]`. Use AI SDK `generateText` + `Output.object({schema})` with structured output.
3. Schema: `{student_name, roll_no, receipt_no, amount, currency, paid_on, semester, institute, confidence_0_1}`.
4. Persist to `documents.ocr_json`.

`validateDocument(documentId)`:
- Second Gemini vision call with a **forensics prompt**: detects blur, low resolution, cropping, digital edits, mismatched fonts, inconsistent alignment, watermark tampering. Returns `{blurry, edited_suspicion, low_quality, is_receipt, issues[]}` → `documents.ai_validation`.

`checkDuplicate(documentId)`:
- SHA-256 of file bytes stored on upload; `SELECT … WHERE sha256 = $1 AND id <> $1` — hard block on exact reuse.
- Semantic dup: `receipt_no` uniqueness per (student, semester, doc_type).

Cross-check step before submit: OCR `student_name`/`roll_no` fuzzy-matches profile (Levenshtein ≥ 0.85) and `semester` matches; else the Accounts dashboard sees a red "AI flagged" chip and must manually override with remarks.

**Student AI Assistant** (`assistant.functions.ts`):
- `streamText` with `google/gemini-3-flash-preview` behind a `/api/chat` route.
- Server-side context injection: current application state, per-step status, remarks, next expected upload — passed as a system message. The model never queries the DB directly; the server pre-fetches and templates it. Handles: "where is my application", "why rejected", "what to upload next", "ETA for admit card".

All Gateway calls use the helper from `ai-sdk-lovable-gateway` (run-id capture, structured errors). 429/402 surfaced via SweetAlert2.

---

## 6. Authentication & Authorization

- **Students:** Email/password sign-up via Supabase Auth. Registration form collects roll_no + reg_no + course + department + category → written to `students` via server fn after email OTP confirmation (Supabase built-in email confirm; OTP shown as 6-digit code in email template). Password reset via `resetPasswordForEmail` → `/auth/reset-password` route.
- **Authorities:** No public signup. Super Admin uses `createAuthority` server fn (loads `supabaseAdmin` inside handler): creates auth user with random password, inserts `user_roles` + `authority_accounts` with `must_change_password=true`. Sign-in redirects to `/auth/force-change-password` until flag cleared.
- **RBAC:** `has_role(uid, role)` security-definer function used in every RLS policy and re-checked at server-fn boundary.
- **Bearer token:** `attachSupabaseAuth` middleware in `src/start.ts` so every protected server fn call carries the JWT.
- **Audit:** every state change writes `activity_log` (actor, ip via `request.headers`, action, before/after).

---

## 7. Realtime & Notifications

- Supabase Realtime replaces Flask-SocketIO. Client subscribes on login:
  - `user-notifications:{userId}` — inserts on `notifications`.
  - `application:{applicationId}` — updates on `applications` + `application_steps` (student sees live timeline).
  - `queue:{role}` — inserts on `application_steps WHERE status='in_review' AND role=X` (staff dashboards).
- Email: Lovable Cloud email for OTP, submission received, each approval, rejection, admit card ready.

---

## 8. Admit Card Generation

`generateAdmitCard(applicationId)` server fn, triggered when final Exam approval lands:
1. Compose PDF with `pdf-lib` — university header, student photo (from profile), course/semester/roll, allowed exams table, watermark, footer with issued-by + timestamp.
2. Build QR payload: `{app_id, roll, semester, issued_at}` → sign HMAC-SHA256 with `ADMIT_SIGNING_KEY` (secret) → embed both payload and signature in QR (base64).
3. Generate QR PNG via `qrcode`, embed into PDF.
4. Upload to Storage bucket `admit-cards/{roll}/{semester}.pdf`, insert `admit_cards` row.
5. Verification route `/api/public/admit/verify?token=…` re-checks signature and returns JSON `{valid, student, semester}` — QR scannable at the exam hall.

---

## 9. Per-Role Dashboards (distinct layouts, shared design system)

Each dashboard is its own route with a unique layout composition — never a shared template:

| Role | Signature UI | Key widgets |
|---|---|---|
| Student | Friendly, aurora background, timeline hero | Progress ring, step timeline, upload dropzones with live OCR badges, AI chat FAB, admit-card download card |
| Accounts | Analytical, dense data grid | Fee-verification queue, receipt viewer split pane, KPI strip (approved today, avg time), bulk-approve toolbar |
| Hostel Warden | Card grid by hostel/room | Only hosteller pending list, room lookup, dues chip |
| Mess | Minimal list + confirm | Only hostellers post-hostel-approval; single action buttons |
| Transport | Route map (Leaflet static) + list | Grouped by bus route, fare status |
| Scholarship | Trust-focused, verification checklist | Scholarship record viewer, eligibility flags |
| HOD | Academic table with semester filter | Department-scoped, class/section grouping, analytics |
| Examination | Premium, authoritative | Final-stage queue, admit card preview, QR verify tool, exam analytics charts |
| Super Admin | Enterprise console | Authority CRUD, role assignment, audit log stream, system settings, global charts |

All share: floating sidebar, top command palette (⌘K), dark/light toggle wired to `class="dark"` on `<html>`.

---

## 10. Landing Page & SEO

Public routes: `/`, `/features`, `/how-it-works`, `/for-authorities`, `/contact`. Each with its own `head()` (title, description, og:*). Hero uses GSAP timeline + Lottie; aurora gradient mesh via CSS; sections animated on scroll with AOS. `sitemap.xml` route + `public/robots.txt` + `public/llms.txt` per platform conventions.

---

## 11. Security Architecture

- RLS on every table, `has_role()` for role checks.
- All privileged writes go through `createServerFn` — never client-side admin key.
- Zod validation on every `inputValidator`; length caps; `encodeURIComponent` for any URL param.
- File uploads: signed URL upload directly to Storage, server verifies content-type + size (< 10 MB) + runs Gemini `is_receipt` check before persisting `documents` row.
- HMAC-signed admit-card QRs; signing key in Cloud secrets.
- Rate limits on OCR + assistant endpoints (per user, sliding window in a `rate_limits` table).
- Audit log immutable (RLS: INSERT via service role only, no UPDATE/DELETE policies).
- Password policy + Have-I-Been-Pwned check enabled via `configure_auth`.

---

## 12. Build Order (proposed milestones)

1. Design system + landing page + auth (email OTP, reset).
2. DB migrations (all tables, RLS, `has_role`, triggers).
3. Student registration → profile + student record + upload flow.
4. OCR + validation + duplicate detection pipeline.
5. Workflow engine + application submission + step decisioning.
6. Realtime notifications + activity log.
7. Six staff dashboards (Accounts, Hostel, Mess, Transport, Scholarship, HOD).
8. Examination dashboard + admit-card PDF + QR verify endpoint.
9. Super Admin console (authority CRUD, audit, settings).
10. Student AI assistant, analytics charts, polish, mobile responsive pass.
11. Seed data via migration, security scan, publish.

---

## 13. Explicit Replacements vs Original Brief

| Original (Flask stack) | This platform | Why |
|---|---|---|
| Flask + Blueprints + JWT | TanStack `createServerFn` + Supabase JWT | Runtime is Cloudflare Workers |
| MongoDB + PyMongo | Postgres + RLS | Managed by Lovable Cloud; stronger consistency for workflow |
| Flask-SocketIO | Supabase Realtime | Workers have no persistent socket server |
| EasyOCR + OpenCV | Gemini vision (multimodal) | Higher accuracy on receipts, no native binaries |
| ReportLab | pdf-lib | Runs in Worker runtime |
| Flask-Mail | Lovable Cloud email | Native integration |

Product surface, roles, workflow, dashboards, and AI features are all preserved.

---

Reply **"build"** to start with Milestone 1 (design system + landing + auth), or tell me which milestone to start from / adjust.
