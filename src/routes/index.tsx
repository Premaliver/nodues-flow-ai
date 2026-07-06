import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  Shield,
  Clock,
  Sparkles,
  FileCheck2,
  BadgeCheck,
  ScanLine,
  Bot,
  Building2,
  Bus,
  Utensils,
  GraduationCap,
  Landmark,
  BookOpenCheck,
  LayoutDashboard,
  QrCode,
  Bell,
  MoonStar,
  ChevronRight,
} from "lucide-react";

export const Route = createFileRoute("/")({
  component: LandingPage,
});

const ROLES = [
  { icon: GraduationCap, label: "Student", tone: "role-student" },
  { icon: Landmark, label: "Accounts", tone: "role-accounts" },
  { icon: Building2, label: "Hostel", tone: "role-hostel" },
  { icon: Utensils, label: "Mess", tone: "role-mess" },
  { icon: Bus, label: "Transport", tone: "role-transport" },
  { icon: BadgeCheck, label: "Scholarship", tone: "role-scholarship" },
  { icon: BookOpenCheck, label: "HOD", tone: "role-hod" },
  { icon: FileCheck2, label: "Examination", tone: "role-exam" },
  { icon: Shield, label: "Super Admin", tone: "role-admin" },
] as const;

const FEATURES = [
  {
    icon: ScanLine,
    title: "AI Receipt OCR",
    desc: "Semester and exam fee receipts are read, cross-verified, and duplicate-checked the moment they're uploaded.",
  },
  {
    icon: Bot,
    title: "Student AI Assistant",
    desc: "Ask 'Where is my application?' or 'Why was I rejected?' — answered in plain English with live context.",
  },
  {
    icon: LayoutDashboard,
    title: "Nine Role Dashboards",
    desc: "Each department gets a dashboard tuned to how they actually work — no shared, generic templates.",
  },
  {
    icon: Bell,
    title: "Realtime Notifications",
    desc: "Approvals, rejections, and admit-card events stream to students the instant a department decides.",
  },
  {
    icon: QrCode,
    title: "Signed Digital Admit Card",
    desc: "PDF admit card with a HMAC-signed QR code — scannable and verifiable at the exam hall.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    desc: "Row-level security, role-based access, audit logs, and CSRF-safe uploads — production grade by default.",
  },
];

const FLOWS = [
  { label: "Day Scholar", path: "Accounts → HOD → Examination" },
  { label: "Hosteller", path: "Accounts → Hostel → Mess → HOD → Examination" },
  { label: "Transport user", path: "Accounts → Transport → HOD → Examination" },
  { label: "Scholarship", path: "Accounts → Scholarship → HOD → Examination" },
  {
    label: "Hosteller + Transport",
    path: "Accounts → Hostel → Mess → Transport → HOD → Examination",
  },
];

function LandingPage() {
  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <NavBar />
      <Hero />
      <TrustStrip />
      <Features />
      <Workflow />
      <RolesSection />
      <AISection />
      <CTA />
      <Footer />
    </div>
  );
}

function NavBar() {
  return (
    <header className="sticky top-0 z-40 w-full">
      <div className="mx-auto mt-4 flex max-w-6xl items-center justify-between rounded-2xl glass px-4 py-3 shadow-soft md:px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl gradient-surface shadow-glow">
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-display text-base font-bold tracking-tight">Smart NoDues</span>
            <span className="text-[10px] font-medium tracking-widest text-muted-foreground uppercase">
              AI · Rayat Bahra
            </span>
          </div>
        </Link>
        <nav className="hidden items-center gap-7 text-sm font-medium text-muted-foreground md:flex">
          <a href="#features" className="transition hover:text-foreground">Features</a>
          <a href="#workflow" className="transition hover:text-foreground">Workflow</a>
          <a href="#roles" className="transition hover:text-foreground">For Departments</a>
          <a href="#ai" className="transition hover:text-foreground">AI</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="hidden rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition hover:text-foreground sm:inline-flex"
          >
            Sign in
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-lg gradient-surface px-4 py-2 text-sm font-semibold shadow-glow transition hover:opacity-95"
          >
            Get started <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="aurora-bg relative overflow-hidden px-4 pt-16 pb-24 md:pt-24 md:pb-32">
      <div className="absolute inset-0 grid-pattern opacity-60" aria-hidden />
      <div className="relative mx-auto max-w-6xl text-center">
        <span className="inline-flex items-center gap-2 rounded-full glass px-4 py-1.5 text-xs font-medium text-foreground shadow-soft">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
          </span>
          Live at Rayat Bahra University
        </span>
        <h1 className="mx-auto mt-6 max-w-4xl font-display text-4xl font-bold leading-[1.05] tracking-tight md:text-6xl lg:text-7xl">
          The end of the <span className="gradient-text">No-Dues queue.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground md:text-lg">
          Upload your semester &amp; exam receipts once. Our AI verifies them, routes approvals to
          every required department automatically, and hands you a digitally signed admit card —
          usually before your coffee gets cold.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/"
            className="group inline-flex items-center gap-2 rounded-xl gradient-surface px-6 py-3 text-sm font-semibold shadow-glow transition hover:opacity-95"
          >
            Start clearance
            <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </Link>
          <a
            href="#workflow"
            className="inline-flex items-center gap-2 rounded-xl glass px-6 py-3 text-sm font-semibold shadow-soft transition hover:bg-background/70"
          >
            See how it works
          </a>
        </div>

        <HeroStats />
        <HeroPreview />
      </div>
    </section>
  );
}

function HeroStats() {
  const stats = [
    { k: "3 hrs → 3 min", v: "Avg clearance time" },
    { k: "9", v: "Role dashboards" },
    { k: "AI-verified", v: "Every receipt" },
    { k: "0", v: "Paper forms" },
  ];
  return (
    <div className="mx-auto mt-12 grid max-w-4xl grid-cols-2 gap-3 md:grid-cols-4">
      {stats.map((s) => (
        <div key={s.v} className="glass rounded-xl px-4 py-3 text-left shadow-soft">
          <div className="font-display text-xl font-bold tracking-tight">{s.k}</div>
          <div className="text-xs text-muted-foreground">{s.v}</div>
        </div>
      ))}
    </div>
  );
}

function HeroPreview() {
  return (
    <div className="relative mx-auto mt-16 max-w-5xl">
      <div className="glass overflow-hidden rounded-3xl border border-border/40 shadow-elevated">
        <div className="flex items-center gap-1.5 border-b border-border/40 bg-muted/40 px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-destructive/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-warning" />
          <span className="h-2.5 w-2.5 rounded-full bg-success" />
          <span className="ml-3 text-xs text-muted-foreground">app.rayatbahra.edu · dashboard</span>
        </div>
        <div className="grid gap-4 p-5 md:grid-cols-3 md:p-6">
          <PreviewCard
            title="Application"
            subtitle="Semester 6 · B.Tech CSE"
            body={
              <div className="space-y-2">
                <ProgressLine label="Accounts" done />
                <ProgressLine label="Hostel" done />
                <ProgressLine label="Mess" active />
                <ProgressLine label="HOD" />
                <ProgressLine label="Examination" />
              </div>
            }
          />
          <PreviewCard
            title="AI Verification"
            subtitle="Semester fee receipt"
            body={
              <div className="space-y-2 text-xs">
                <Row k="Student" v="Aditi Sharma" />
                <Row k="Roll" v="RBU/22CSE/0142" />
                <Row k="Amount" v="₹ 62,500" />
                <Row k="Duplicate" v="No match found" />
                <div className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-success/15 px-2 py-1 text-[11px] font-semibold text-success">
                  <BadgeCheck className="h-3 w-3" /> Verified
                </div>
              </div>
            }
          />
          <PreviewCard
            title="Admit Card"
            subtitle="Signed & QR-verifiable"
            body={
              <div className="flex flex-col items-center justify-center gap-3 py-2">
                <div className="grid h-24 w-24 place-items-center rounded-lg bg-foreground text-background">
                  <QrCode className="h-16 w-16" />
                </div>
                <div className="text-center">
                  <div className="text-xs font-semibold">End Sem · Dec 2026</div>
                  <div className="text-[10px] text-muted-foreground">HMAC-signed payload</div>
                </div>
              </div>
            }
          />
        </div>
      </div>
      <div className="pointer-events-none absolute -inset-x-10 -bottom-10 h-40 bg-gradient-to-t from-background to-transparent" />
    </div>
  );
}

function PreviewCard({
  title,
  subtitle,
  body,
}: {
  title: string;
  subtitle: string;
  body: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border/50 bg-card p-4 shadow-soft">
      <div className="mb-3 flex items-baseline justify-between">
        <div>
          <div className="font-display text-sm font-semibold">{title}</div>
          <div className="text-[11px] text-muted-foreground">{subtitle}</div>
        </div>
      </div>
      {body}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-medium">{v}</span>
    </div>
  );
}

function ProgressLine({ label, done, active }: { label: string; done?: boolean; active?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className={`inline-flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold ${
          done
            ? "bg-success text-success-foreground"
            : active
              ? "bg-primary text-primary-foreground animate-pulse"
              : "bg-muted text-muted-foreground"
        }`}
      >
        {done ? "✓" : active ? "…" : ""}
      </span>
      <span className={`text-xs ${done || active ? "font-semibold" : "text-muted-foreground"}`}>
        {label}
      </span>
      {active && (
        <span className="ml-auto text-[10px] font-medium text-primary">In review</span>
      )}
    </div>
  );
}

function TrustStrip() {
  return (
    <section className="border-y border-border/60 bg-muted/30 py-6">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-4 text-xs font-medium text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><Shield className="h-3.5 w-3.5" /> Row-Level Security</span>
        <span className="inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> Realtime Approvals</span>
        <span className="inline-flex items-center gap-1.5"><ScanLine className="h-3.5 w-3.5" /> AI Document Verification</span>
        <span className="inline-flex items-center gap-1.5"><QrCode className="h-3.5 w-3.5" /> Signed Admit Cards</span>
        <span className="inline-flex items-center gap-1.5"><MoonStar className="h-3.5 w-3.5" /> Dark &amp; Light Mode</span>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="features" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeader
          eyebrow="Platform"
          title="Everything a modern university clearance needs"
          desc="Nine role-tuned dashboards, an AI verification pipeline, and a workflow engine that routes every application automatically — built to actually replace paper."
        />
        <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="group relative overflow-hidden rounded-2xl border border-border/60 bg-card p-6 shadow-soft transition hover:-translate-y-0.5 hover:shadow-elevated"
            >
              <div
                className="absolute -right-8 -top-8 h-32 w-32 rounded-full opacity-0 blur-2xl transition group-hover:opacity-60"
                style={{ background: "var(--gradient-primary)" }}
              />
              <div className="relative">
                <div className="inline-flex h-11 w-11 items-center justify-center rounded-xl gradient-surface shadow-glow">
                  <f.icon className="h-5 w-5 text-primary-foreground" />
                </div>
                <h3 className="mt-5 font-display text-lg font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Workflow() {
  return (
    <section id="workflow" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeader
          eyebrow="Automatic Routing"
          title="The right departments, in the right order — always"
          desc="Smart NoDues detects each student's category (day scholar, hosteller, transport, scholarship, or a combination) and materializes exactly the workflow they need. No manual assignment."
        />
        <div className="mt-14 grid gap-3 md:grid-cols-2">
          {FLOWS.map((flow) => (
            <div
              key={flow.label}
              className="flex items-center gap-3 rounded-xl border border-border/60 bg-card p-4 shadow-soft"
            >
              <span className="inline-flex shrink-0 items-center rounded-md bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
                {flow.label}
              </span>
              <span className="min-w-0 truncate text-sm text-muted-foreground">{flow.path}</span>
              <ChevronRight className="ml-auto h-4 w-4 text-muted-foreground" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function RolesSection() {
  return (
    <section id="roles" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHeader
          eyebrow="Nine dashboards"
          title="A workspace shaped to how each department actually works"
          desc="Accounts sees a financial control panel. Hostel sees room-scoped queues. The HOD sees only their department. Examination sees the final gate — with admit-card generation built in."
        />
        <div className="mt-14 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-9">
          {ROLES.map((r) => (
            <div
              key={r.label}
              className="group flex flex-col items-center gap-2 rounded-xl border border-border/60 bg-card p-4 text-center shadow-soft transition hover:-translate-y-0.5 hover:shadow-elevated"
            >
              <div
                className="flex h-11 w-11 items-center justify-center rounded-xl transition group-hover:scale-105"
                style={{ backgroundColor: `var(--${r.tone})`, color: "white" }}
              >
                <r.icon className="h-5 w-5" />
              </div>
              <span className="text-xs font-semibold">{r.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function AISection() {
  return (
    <section id="ai" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="glass grid gap-8 overflow-hidden rounded-3xl border border-border/60 p-8 shadow-elevated md:grid-cols-2 md:p-12">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3 w-3" /> AI-native
            </span>
            <h2 className="mt-4 font-display text-3xl font-bold tracking-tight md:text-4xl">
              An assistant that actually knows your file.
            </h2>
            <p className="mt-4 text-sm text-muted-foreground md:text-base">
              Every receipt is scanned by a multimodal model — student name, roll number, receipt
              number, amount, payment date and semester are extracted, cross-checked against your
              profile, and flagged for duplicates or edits. The student assistant then answers your
              questions in plain English, with live context.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm">
              {[
                "Where is my application right now?",
                "Which department is holding it up?",
                "Why was I rejected — and what do I fix?",
                "When will my admit card be ready?",
              ].map((q) => (
                <li key={q} className="flex items-start gap-2">
                  <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span className="text-muted-foreground">{q}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="relative">
            <div className="rounded-2xl border border-border/60 bg-card p-4 shadow-soft">
              <div className="flex items-center gap-2 border-b border-border/50 pb-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-surface">
                  <Bot className="h-4 w-4 text-primary-foreground" />
                </div>
                <div>
                  <div className="text-sm font-semibold">NoDues Assistant</div>
                  <div className="text-[10px] text-muted-foreground">Online · reads your live status</div>
                </div>
              </div>
              <div className="mt-4 space-y-3 text-sm">
                <div className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-primary-foreground">
                  Where is my application?
                </div>
                <div className="max-w-[90%] rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-foreground">
                  Your application is currently with <b>Mess Department</b>. Accounts and Hostel have
                  already approved. Estimated next step in ~1 hour. I'll ping you the moment it moves.
                </div>
                <div className="ml-auto max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-primary-foreground">
                  What should I upload next?
                </div>
                <div className="max-w-[90%] rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-foreground">
                  You're all set — all three documents are verified. Nothing more from your side
                  until Examination approves.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="px-4 pb-24">
      <div className="mx-auto max-w-6xl overflow-hidden rounded-3xl gradient-surface p-10 text-center shadow-elevated md:p-16">
        <h2 className="mx-auto max-w-3xl font-display text-3xl font-bold tracking-tight text-primary-foreground md:text-5xl">
          Ready to skip the paperwork?
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-sm text-primary-foreground/85 md:text-base">
          Sign in with your university email and start your clearance in under two minutes.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl bg-background px-6 py-3 text-sm font-semibold text-foreground shadow-soft transition hover:bg-background/95"
          >
            Student sign in <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl border border-primary-foreground/30 bg-transparent px-6 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary-foreground/10"
          >
            Authority sign in
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border/60 px-4 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 md:flex-row">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg gradient-surface">
            <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
          </div>
          <span className="text-sm font-semibold">Smart NoDues AI</span>
          <span className="text-xs text-muted-foreground">· Rayat Bahra University</span>
        </div>
        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} Smart NoDues AI. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

function SectionHeader({
  eyebrow,
  title,
  desc,
}: {
  eyebrow: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primary">
        {eyebrow}
      </span>
      <h2 className="mt-4 font-display text-3xl font-bold tracking-tight md:text-5xl">{title}</h2>
      <p className="mt-4 text-sm text-muted-foreground md:text-base">{desc}</p>
    </div>
  );
}
