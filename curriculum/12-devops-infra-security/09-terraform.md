# Terraform: Modules, State, Workspaces, Drift, terraform test

> **Track:** T12 DevOps, Infra & Security · **Time:** 3h · **Prereqs:** none
> **Module id:** `T12-terraform` · **Tags:** iac, critical

## The 30-second version

Terraform's entire value proposition rests on one file, the state file, and almost every real production incident with Terraform traces back to someone misunderstanding what it actually is: a cached mapping from your configuration's resource addresses to real-world resource IDs and their last-known attributes, not a source of truth about reality — it's a **belief** about reality that drifts the moment someone changes something outside Terraform (a console click, another pipeline, a manual `kubectl` command against a Terraform-managed cluster). Locking (via a DynamoDB table for S3 backends, or built-in on HCP Terraform/Terraform Cloud) exists purely to stop two concurrent `apply` runs from writing conflicting state simultaneously and corrupting it — it says nothing about drift, which is a completely separate problem solved by `terraform plan -refresh-only` or scheduled drift-detection, not locking. Modules are Terraform's only real reuse mechanism, and the mistake that burns teams every time is over-abstracting a module too early — a module with 40 optional variables trying to cover every team's use case is worse than three teams maintaining slightly different 10-variable modules, because the abstraction itself becomes the thing that's hard to change. `terraform test` (native since 1.6, matured further through 1.14) finally gave Terraform a first-class way to assert on plan output and real applied infrastructure without a separate tool, closing a real historical gap versus Pulumi/CDK's "it's just a programming language, use your normal test framework" advantage — though HCL's declarative nature still makes genuinely dynamic, loop-heavy logic (deeply conditional resource generation) more awkward than a general-purpose language, which is the honest, still-true reason some teams choose Pulumi or CDK instead, not a stale complaint.

## Why this gets asked

Because writing a Terraform resource block is a five-minute skill, and every senior interviewer has been on the incident where `terraform apply` did something catastrophic because state got out of sync with reality, or two engineers ran `apply` at the same time against unlocked state and corrupted it, or a "small refactor" (renaming a resource, splitting a module) silently planned to destroy and recreate a production database because nobody used `moved` blocks or `terraform state mv`. They want to know whether you understand state as a mechanism with real failure modes, not just "Terraform tracks what it created."

---

## Lineage: past → present → future

**What came before.** Before Terraform (HashiCorp, first released 2014), infrastructure was either provisioned by hand through cloud consoles (the classic "nobody knows why this security group exists or what depends on it" problem), or via imperative scripting (Chef/Puppet/Ansible, or raw Bash against cloud CLIs) that described *steps to take*, not a *desired end state* — meaning re-running the same script twice could have different effects depending on current state, and there was no built-in way to compute "what would change" before actually changing it. AWS CloudFormation (2011) got closer to Terraform's declarative model years earlier but was AWS-only, forcing multi-cloud or hybrid teams into separate, disconnected tooling per provider. The pain Terraform specifically addressed: a single declarative language, a provider plugin model letting the same workflow target any cloud or SaaS with an API, and critically, `terraform plan` — a dry-run diff against tracked state, computed *before* any change is applied, which CloudFormation's change-sets eventually converged toward but Terraform shipped as a core primitive from early on.

**Where it stands now.** HashiCorp's 2023 license change (BSL, moving Terraform away from a pure open-source license) triggered the OpenTofu fork (Linux Foundation, genuinely open-source, drop-in compatible with Terraform through roughly the 1.5.x line and tracking new features since) — a live, real fork that split the community, not a footnote; some teams have deliberately migrated to OpenTofu specifically over licensing concerns, and this is worth naming unprompted if asked about the ecosystem's current state rather than assuming "Terraform" is the only name in the room. Terraform itself (current mainline around **1.14** as of 2026) has continued adding first-class primitives that used to require workarounds: `terraform test` (native since 1.6) for real assertion-based testing, `import` blocks (declarative, code-reviewable import instead of the old imperative `terraform import` CLI command run by hand), and `moved`/`removed` blocks for safe refactors that used to require careful, error-prone `terraform state mv` sequences. HCP Terraform (the renamed/evolved Terraform Cloud) and alternatives (Spacelift, Atlantis, env0) now handle the operational half of the story — remote state, built-in locking, run pipelines with plan-then-approve gates — which most serious production setups use rather than hand-rolling S3+DynamoDB backend locking, though the S3+DynamoDB pattern remains extremely common and worth knowing mechanically since plenty of production infra still runs on it and it's the pattern interviewers most often ask about directly. Terragrunt remains the dominant answer to Terraform's lack of native cross-module/cross-environment DRY composition (avoiding copy-pasted backend config and variable wiring across dev/staging/prod), though `import`/variables-in-module-sources and other native improvements have narrowed, without eliminating, the gap Terragrunt exists to fill.

**Where it's heading.** The declarative-HCL-vs-general-purpose-language debate (Terraform/OpenTofu vs. Pulumi/CDK) is a genuinely live, unresolved disagreement rather than a settled question — Pulumi and CDK's "just write real code, use your normal test/CI tooling" pitch keeps gaining ground on teams with strong existing language preferences and complex conditional infra logic, while Terraform/OpenTofu's provider ecosystem breadth and the fact that HCL has become a broadly shared team vocabulary (not just infra engineers, but anyone touching a `.tf` file) keeps it the default recommendation for most teams, especially multi-cloud ones. Expect continued convergence on testing and safe-refactor primitives across all three ecosystems rather than any one clearly "winning" outright in the next few years — state this as a real, ongoing disagreement in an interview rather than picking a side as if it were obviously settled.

---

## Mental model

```
YOUR .tf FILES (desired state)          STATE FILE (believed current state)
   resource "aws_instance" "web" {         {
     instance_type = "t3.medium"             "resources": [{
   }                                            "type": "aws_instance",
                                                 "name": "web",
                                                 "instance_id": "i-0abc123",
                                                 "instance_type": "t3.medium",
                                                 ... last-known real attributes ...
                                               }]
                                             }
        │                                          │
        └──────────────► terraform plan ◄──────────┘
                                │
                    diffs desired vs. believed-current,
                    ALSO refreshes believed-current against
                    the REAL cloud API first (unless -refresh=false)
                                │
                                ▼
                    "+ create, ~ update, - destroy" plan
                                │
                                ▼
                    terraform apply (writes to real cloud API,
                    THEN updates state file to match new reality)

DRIFT = someone changes the REAL resource outside Terraform
        (console click, another pipeline) -> state file now LIES
        about current reality until the next refresh/plan catches it

LOCKING = stops two concurrent applies from writing state at the
          SAME TIME and corrupting the file. Says NOTHING about drift.
          Different problem, different mechanism.
```

---

## How it actually works

### State: what it actually contains, and why `terraform plan` refreshes it

The state file (`terraform.tfstate`, JSON) is a mapping from each resource's **address** (`aws_instance.web`, or `module.vpc.aws_subnet.private[0]`) to its **provider-reported attributes as of the last successful refresh or apply** — not a live query. Every `terraform plan` (unless run with `-refresh=false`) begins by calling each tracked resource's provider `Read` API to refresh state against real current values *before* computing the diff against your `.tf` configuration — this is why a `plan` can show unexpected changes even when nobody touched the `.tf` files: something changed the real resource outside Terraform, the refresh caught it, and the plan now proposes to revert it back to what the configuration says it should be. This refresh-then-diff sequence is the mechanism, not a detail — "Terraform detected drift" specifically means the refresh step found a mismatch between real-world attributes and what state believed, and the subsequent plan is proposing to correct it back toward the `.tf` configuration's desired state (since Terraform's model treats configuration, not the live resource, as the source of truth for what *should* be true).

### Locking, precisely

For the classic S3 backend, locking is implemented via a separate **DynamoDB table**: before writing state, Terraform attempts to acquire a lock by writing a specific item (keyed by the state file's path) to that table; if the item already exists (another `apply` is in progress), the new operation blocks or fails with a `ConditionalCheckFailedException`-flavored lock error rather than proceeding to write over in-flight state. S3 alone provides no locking mechanism on its own — pairing S3 (state storage) with DynamoDB (lock table) used to be a manual two-resource backend configuration; more recent Terraform/AWS provider tooling has simplified some of this, but the underlying two-part mechanism (object storage for state, a strongly-consistent key-value store for the lock) is what to understand, not just the specific resource names. HCP Terraform and most managed backends (Spacelift, env0) implement equivalent locking internally without exposing a separate lock-table resource to configure. **A stuck/stale lock** (a CI job killed mid-apply, holding a lock that's now abandoned) is a real, common operational annoyance — `terraform force-unlock <lock-id>` exists specifically for this, and using it safely requires confirming the process that held the lock is actually dead, not just slow, since force-unlocking a genuinely in-progress apply and then running a second concurrent apply is exactly the corruption scenario locking exists to prevent.

### Workspaces — what they solve, and what they don't

Terraform's built-in `terraform workspace` mechanism creates multiple, named state files from the *same configuration*, isolated by workspace name (`terraform workspace new staging`) — useful for spinning up genuinely parallel, structurally-identical environments (feature-branch preview environments, short-lived test stacks) from one config without duplicating `.tf` files. What it explicitly does **not** solve well: distinct environments with genuinely different configuration (different instance sizes, different provider regions, different resource counts between dev and prod) — workspaces share one configuration, so environment-specific differences have to be threaded through via `terraform.workspace`-conditional logic inside the `.tf` files themselves, which gets unreadable fast past two or three real differences. The far more common production pattern for dev/staging/prod is **separate state files via separate backend configs per environment** (directory-per-environment, or Terragrunt-managed), each with its own `.tfvars`, not built-in workspaces — this is a real, frequently-tested distinction: "workspaces" as a Terraform interview term almost always means the narrower built-in feature, and conflating it with "we have separate environments" is a common, telling imprecision.

### Modules — composition and the over-abstraction trap

A module is just a directory of `.tf` files referenced via a `module` block, with `variables.tf` as its input contract and `outputs.tf` as what it exposes to callers — composition is achieved by one module's `output` feeding another's `variable` (`module.vpc.outputs.subnet_ids` passed into `module.eks.variable.subnet_ids`), and Terraform builds its dependency graph from these references automatically, without needing explicit ordering. The real, senior-level judgment call is abstraction boundary placement: a module that starts narrow (one team, one specific use case, few variables) and gets pulled toward "generic enough for everyone" as more teams adopt it tends to accumulate boolean flags and deeply nested optional blocks until the module itself becomes harder to reason about than three teams each maintaining a smaller, purpose-built version — the module was supposed to reduce cognitive load and started adding it back once its variable surface got large enough that using it correctly required reading its internals anyway. The practical rule of thumb many teams converge on: a module earns broader reuse by being extracted *after* two or three teams have independently written nearly-identical resource blocks (proven, real duplication), not designed upfront for hypothetical future reuse.

### Refactoring safely — `moved`/`removed` blocks vs. the old `state mv` era

Renaming a resource, or moving one from the root module into a child module, changes its **address** in state — without telling Terraform the old and new addresses refer to the same real resource, a plan will show the old address as `- destroy` and the new address as `+ create`, and applying that plan destroys and recreates a resource that never actually needed to change (catastrophic for anything stateful — a database, a persistent volume, anything with real data or a non-trivial recreate cost). The old mitigation was running `terraform state mv <old address> <new address>` by hand, out-of-band, before applying the refactored config — correct but imperative, easy to get wrong, and invisible in code review since it's a CLI command, not a change to the `.tf` files themselves. `moved` blocks (declarative, part of the actual configuration, code-reviewable) solve this properly:

```hcl
# untested sketch — safely renaming aws_instance.web to aws_instance.app_server
moved {
  from = aws_instance.web
  to   = aws_instance.app_server
}
```

`terraform plan` reads this block, recognizes the two addresses as the same underlying resource, and produces a plan with **no destroy/create at all** for it — just an internal state address update. `removed` blocks (for cleanly dropping a resource from management without destroying the real thing, useful when handing a resource off to another team/tool) work the same way declaratively. The mechanical point worth being explicit about in an interview: **`terraform plan`'s destroy/create output is the actual safety check** — any refactor, no matter how "obviously safe" it looks in the diff, should be verified via `plan` output showing no unintended destroy before ever applying, full stop.

### `terraform test` — what it actually asserts

Native `terraform test` (`.tftest.hcl` files, `run` blocks) supports two real modes: **plan-only assertions** (fast, no real infrastructure created, asserting on the *plan's* computed values — "does this module produce exactly 3 subnets given these inputs") and **apply-and-assert** (`command = apply`, genuinely provisions real resources in a throwaway/test account, asserts against real provider-returned attributes, then tears down) — the second is real infrastructure testing, not a simulation, with real cost and real time cost per test run, which is the honest tradeoff against Pulumi/CDK's ability to unit-test pure logic in a general-purpose language without ever touching a cloud API for most of the test surface.

```hcl
# untested sketch — plan-only assertion, fast, no real infra
run "correct_subnet_count" {
  command = plan
  variables { az_count = 3 }
  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "expected 3 private subnets for az_count=3"
  }
}

# untested sketch — apply-and-assert, real infra, real teardown
run "instance_actually_reachable" {
  command = apply
  assert {
    condition     = aws_instance.web.instance_state == "running"
    error_message = "instance did not reach running state"
  }
}
```

---

## Build it from scratch

```hcl
# untested sketch — minimal module with a real input contract, output, and a moved block
# variables.tf
variable "environment" {
  type        = string
  description = "deployment environment name"
}
variable "instance_type" {
  type    = string
  default = "t3.micro"
}

# main.tf
resource "aws_instance" "app_server" {   # renamed from aws_instance.web at some point
  ami           = data.aws_ami.latest.id
  instance_type = var.instance_type
  tags          = { Environment = var.environment }
}

moved {
  from = aws_instance.web
  to   = aws_instance.app_server
}

# outputs.tf
output "instance_id" {
  value = aws_instance.app_server.id
}
```

```hcl
# untested sketch — S3 backend with the classic DynamoDB lock table pattern
terraform {
  backend "s3" {
    bucket         = "mycompany-tfstate"
    key            = "app/prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"    # separate table, strongly-consistent lock item writes
    encrypt        = true
  }
}
```

```bash
# real command sequence for a safe refactor
terraform plan -out=refactor.tfplan     # confirm the moved block produces NO destroy/create
terraform show refactor.tfplan | grep -E '^\s*[+-~]'   # eyeball the action summary
terraform apply refactor.tfplan          # apply the exact reviewed plan, not a fresh one
```

---

## How it's done in production

Production Terraform usage is almost never "run `terraform apply` from a laptop" — it's a CI-driven pipeline (GitHub Actions, Atlantis for PR-comment-triggered plan/apply, or HCP Terraform/Spacelift's managed run model) where every `plan` is posted for human review on the pull request *before* any `apply` runs, `apply` only happens on merge (or explicit approval) against the exact plan that was reviewed (not a freshly re-computed one, to avoid a TOCTOU-style gap between what was reviewed and what actually applies), and state lives in a remote backend with locking from day one, never local `terraform.tfstate` files. `terraform test` and `tflint`/`checkov`-style static analysis run in CI before `plan` is even attempted, catching structural issues (missing required tags, insecure security group rules, non-compliant resource configuration) cheaply and fast rather than surfacing them only in a slow `plan`/`apply` cycle. Terragrunt (where used) sits in front of raw Terraform specifically to DRY up backend configuration and variable wiring across many near-identical environment directories, generating the actual `.tf`/backend config Terraform consumes rather than replacing Terraform itself.

| Symptom | Cause | Fix |
|---|---|---|
| `terraform plan` shows unexpected changes with no `.tf` edits made | Drift — something changed the real resource outside Terraform (console, another pipeline) and the refresh step caught the mismatch | Investigate the drift's source before blindly applying (which reverts it to match config); if the out-of-band change should be kept, update the `.tf` config to match reality instead, or `terraform import`/adopt it properly |
| `apply` fails with a lock error, and the CI job that held it is confirmed dead | A CI job was killed mid-apply, leaving an abandoned lock in the DynamoDB table (or backend-equivalent) | `terraform force-unlock <lock-id>` — but only after confirming the holding process is genuinely dead, not just slow, to avoid two concurrent applies corrupting state |
| A "harmless rename" refactor's plan shows `- destroy` then `+ create` for a stateful resource | No `moved` block (or `state mv`) — Terraform sees the old and new addresses as unrelated resources | Add a `moved` block before applying, confirm the plan now shows no destroy/create for that resource, then apply |
| Two engineers' applies conflict / corrupt state | Local state files, or a backend without locking, used instead of a remote backend with real locking | Migrate to a remote backend (S3+DynamoDB, HCP Terraform, or equivalent) with locking enabled from the start; never use local state for anything beyond a personal sandbox |
| A module used by 6 teams has become unreadable, with 35+ variables and deep conditional blocks | Over-abstraction — the module tried to cover every team's use case upfront instead of being extracted from proven, real duplication | Consider splitting into smaller, more purpose-specific modules per common use-case cluster, rather than one maximally-generic module |
| `terraform plan` takes minutes even for a tiny config change | Refresh step querying provider APIs for every tracked resource, on a large/monolithic state file covering hundreds of resources | Split state by logical boundary (network, data, app-tier) via separate backends/root modules, so a change in one boundary doesn't require refreshing unrelated resources |

---

## Tradeoffs & when NOT to use it

- **Don't use built-in `terraform workspace` as your dev/staging/prod isolation strategy** once environments have genuinely different configuration, not just different state — it forces `terraform.workspace`-conditional logic into shared `.tf` files that gets unreadable past a couple of real differences; separate backend configs per environment (or Terragrunt) is the actual production pattern for that case.
- **Don't reach for Terraform/HCL when the infra logic is genuinely complex, loop-heavy, or needs real unit testing of conditional logic** — Pulumi or CDK's general-purpose-language model is a legitimate, honest better fit there, not a lesser choice; Terraform's declarative model fights you exactly where dynamic branching and computed logic get deep.
- **Don't design a module for hypothetical future reuse before real duplication exists.** Extracting a shared module after two or three teams have independently written nearly-identical resources produces a better-shaped abstraction than guessing upfront what every future consumer might need.
- **Don't run `terraform apply` against a freshly re-computed plan in CI** if a different plan was what got human-reviewed on the PR — apply the exact saved `.tfplan` artifact that was reviewed, or you've silently reintroduced the TOCTOU gap the review step was meant to close.
- **Don't treat `terraform test`'s apply-mode tests as free** — they provision real infrastructure with real cost and real time per run; reserve apply-mode tests for genuinely critical modules and lean on plan-only assertions for the bulk of test coverage.

---

## Interview questions

### Q1 — What actually is the Terraform state file, mechanically, and why does `terraform plan` refresh it before diffing?
**Testing:** whether state is understood as a cached belief, not a live source of truth.
**Answer:** State is a JSON mapping from each resource's configuration address to its provider-reported attributes as of the last refresh/apply — a cache, not a live query. `terraform plan` (unless `-refresh=false`) calls each tracked resource's provider `Read` API first to catch any drift between real-world state and what's cached, then diffs the refreshed state against the `.tf` configuration to compute the plan.
**Follow-up trap:** *"If you run `plan` with `-refresh=false`, what risk does that introduce?"* — the plan is computed against potentially stale cached state, so it can miss real drift entirely and produce a plan that looks like a no-op when the real resource has actually diverged — useful for speed in specific controlled scenarios (e.g., you already know state is current), risky as a default habit.

### Q2 — Explain exactly what state locking protects against, and what it does not.
**Testing:** the locking-vs-drift distinction, a very commonly conflated pair.
**Answer:** Locking prevents two concurrent `apply` (or state-writing) operations from writing to the state file at the same time and corrupting it — for an S3 backend, implemented via a DynamoDB table lock item keyed to the state path. It says nothing about drift — a resource changing outside Terraform entirely, with no concurrent Terraform operation involved at all, isn't something locking touches; that's caught by the refresh step in `plan`, a separate mechanism.
**Follow-up trap:** *"Someone force-unlocks a stuck state and then immediately runs `apply` — what's the risk if you're wrong about the original process being dead?"* — if the original process is actually still running (just slow, not dead), you now have two concurrent writers to the same state file with the lock no longer preventing it, exactly the corruption scenario locking exists to stop — `force-unlock` should only follow real confirmation (checking the CI system, not just guessing from elapsed time) that the original holder is gone.

### Q3 — A refactor renames `aws_instance.web` to `aws_instance.app_server` with no other changes to the resource. What does `terraform plan` show if you don't handle the address change, and how do you fix it correctly?
**Testing:** the address-vs-resource distinction, a real and costly mistake.
**Answer:** Terraform sees two unrelated addresses — the old one no longer present in config (`- destroy`) and the new one newly appearing (`+ create`) — even though it's conceptually the same underlying resource with no real attribute changes. A `moved` block (`from = aws_instance.web, to = aws_instance.app_server`) declares the equivalence; `plan` then shows no destroy/create, just an internal address update.
**Follow-up trap:** *"What did people do before `moved` blocks existed, and why was it worse?"* — `terraform state mv <old> <new>`, run imperatively out-of-band before applying — functionally similar, but invisible in code review (it's a CLI command against the state, not a change to the `.tf` files) and easy to get the ordering wrong relative to when the config change actually lands, versus a `moved` block which is declarative, versioned alongside the config, and reviewable in the same PR.

### Q4 — What's the actual difference between Terraform's built-in `workspace` feature and "having separate dev/staging/prod environments"?
**Testing:** a frequently conflated but genuinely distinct pair of concepts.
**Answer:** Built-in workspaces create multiple named state files from the *same* configuration, isolated only by state — good for structurally identical, short-lived parallel environments. Real dev/staging/prod separation, with genuinely different configuration (sizes, regions, resource counts), is typically implemented via separate backend configs per environment (directory-per-environment or Terragrunt-managed), each with its own variables — not built-in workspaces, which would force environment differences into `terraform.workspace`-conditional logic inside shared `.tf` files.
**Follow-up trap:** *"Could you use built-in workspaces for dev/staging/prod anyway? What breaks first?"* — technically yes for identical infra shapes, but the moment any environment needs a genuinely different resource count, instance type, or feature flag, you're forced into conditional expressions keyed on `terraform.workspace` scattered through the config, which becomes unreadable past a couple of real differences — this is the concrete failure mode, not a theoretical objection.

### Q5 — Why is a module with 40 optional variables often worse than three teams maintaining separately-owned, smaller modules?
**Testing:** the senior over-abstraction judgment call.
**Answer:** A maximally generic module built to cover every consumer's hypothetical need accumulates deep conditional logic and boolean flags until using it correctly requires reading its internals anyway — the abstraction stops reducing cognitive load and starts adding it. Smaller, purpose-built modules extracted from proven, real duplication (not designed upfront for imagined reuse) tend to stay legible and easy to reason about, even at the cost of some genuine duplication across teams.
**Follow-up trap:** *"When does the calculus flip back toward one shared module?"* — once real, observed duplication across teams (not hypothetical future need) shows the same 10-15 lines being copy-pasted nearly verbatim in three or more places — that's the signal to extract a shared module, ideally scoped narrowly to exactly what's actually duplicated rather than generalized further than the evidence supports.

### Q6 — What does `terraform test`'s `command = apply` mode actually do, and how is it different from `command = plan`?
**Testing:** whether "terraform now has tests" is understood mechanically, not just as a checkbox feature.
**Answer:** `command = plan` runs a fast, plan-only assertion against computed values with no real infrastructure created or destroyed. `command = apply` genuinely provisions real infrastructure (typically in a throwaway/test account), asserts against real provider-returned attributes after a real apply, then tears the infrastructure down — real infrastructure testing with real cost and real time per run, not a simulation.
**Follow-up trap:** *"Given the cost of apply-mode tests, how would you structure a test suite for a large module library?"* — lean on plan-only assertions for the bulk of coverage (fast, free, catches most logic errors — wrong counts, wrong computed values, missing required fields), reserving apply-mode tests for a small number of genuinely critical paths where you need to confirm real provider behavior, not just your own logic.

### Q7 — Compare Terraform/HCL against Pulumi's general-purpose-language model honestly — where does each genuinely win?
**Testing:** whether you'll state a real tradeoff instead of picking a side reflexively.
**Answer:** Terraform/HCL wins on ecosystem breadth (the largest module/provider library by far), a genuinely shared, learnable-in-a-day vocabulary across a team (not just infra specialists), and a declarative model that's easy to reason about for mostly-static infrastructure shapes. Pulumi wins where infra logic is genuinely complex or loop/conditional-heavy — real programming constructs, and the ability to unit-test pure logic in a normal test framework without touching a cloud API for most of that coverage, something HCL structurally fights you on.
**Follow-up trap:** *"Given Terraform now has `terraform test`, does that close the gap entirely?"* — no — `terraform test` closes the "we have no native testing at all" gap, but it still runs inside HCL's declarative model for expressing the infrastructure logic itself; genuinely complex conditional/loop-heavy infra generation remains more awkward in HCL than in a general-purpose language regardless of how good the test tooling around it gets — the two are separate axes (testing capability vs. expressiveness of the underlying logic), and closing one doesn't close the other.

### Q8 — A `terraform plan` shows changes to a security group's ingress rules that nobody on the team made in the `.tf` files. What's your first hypothesis, and how do you confirm it?
**Testing:** drift diagnosis as a real skill, not a definitional recall.
**Answer:** Drift — someone (a person via console, another automated process, an incident-response action) modified the real security group outside Terraform, and the refresh step in `plan` caught the mismatch, proposing to revert it back to match the `.tf` configuration. Confirm via cloud provider audit logs (CloudTrail for AWS) filtered to that resource around the relevant timeframe, which will show exactly who/what made the out-of-band change.
**Follow-up trap:** *"The drift turns out to be a legitimate, necessary emergency change made during an incident. What's the right way to reconcile it, rather than just applying the revert?"* — update the `.tf` configuration to match the new, correct desired state (codifying the emergency change properly) rather than letting `apply` silently revert a change that should actually be kept — applying blindly here would re-break whatever the emergency change fixed.

### Q9 — Why do teams pair Terraform with Atlantis, HCP Terraform, or a similar CI-driven workflow instead of running `apply` from individual laptops?
**Testing:** the human-review-before-apply discipline that separates safe production practice from ad hoc usage.
**Answer:** Running `apply` from a laptop means plans aren't consistently reviewed by anyone else before real infrastructure changes happen, local state/credentials handling is inconsistent and risky, and there's no reliable audit trail of who ran what, when, against what plan. CI-driven workflows post every `plan` for review on the pull request, gate `apply` on merge/approval, and apply the *exact reviewed plan artifact* rather than a freshly recomputed one — closing the review-then-drift gap.
**Follow-up trap:** *"Why does applying the exact saved `.tfplan` artifact matter, versus just re-running `apply` after merge?"* — re-running `plan`+`apply` fresh after merge can compute a *different* plan than what was actually reviewed if anything changed in the interim (another merge, real-world drift caught by a fresh refresh) — a classic TOCTOU (time-of-check to time-of-use) gap; applying the saved artifact guarantees what gets applied is exactly what a human approved.

### Q10 — What's OpenTofu, and why does it exist?
**Testing:** whether the ecosystem's actual current state (not just "Terraform") is known.
**Answer:** A Linux Foundation-hosted, genuinely open-source fork of Terraform, created after HashiCorp's 2023 license change (moving Terraform to BSL) — drop-in compatible with Terraform through roughly the 1.5.x line and independently tracking new features since. It's a real, live fork with real production adoption by teams specifically concerned about the licensing change, not a hypothetical or abandoned project.
**Follow-up trap:** *"If a team is deciding between Terraform and OpenTofu today, what's the actual decision criterion, beyond licensing philosophy?"* — practical concerns: HCP Terraform's managed platform features (if wanted) require mainline Terraform; provider/module ecosystem compatibility should be checked for any team-critical providers, since divergence between the two projects can grow over time; for most teams the HCL syntax and provider experience is functionally identical day-to-day, making licensing stance and platform-feature needs the actual deciding factors, not language/tooling differences.

### Q11 — A monolithic Terraform root module manages 400+ resources across networking, data, and application tiers. `plan` now takes several minutes even for a one-line change. Why, and what's the fix?
**Testing:** state-sizing as a real operational concern, not just a style preference.
**Answer:** Every `plan` refreshes *all* tracked resources in that state file against real provider APIs before computing any diff, regardless of how small the actual config change is — a 400-resource state means 400+ API calls on every single `plan`, even a one-line change to one resource. The fix is splitting state along logical/lifecycle boundaries (separate root modules/backends for networking, data, application tier), so a change in one boundary only requires refreshing the resources actually relevant to it.
**Follow-up trap:** *"What's the tradeoff of splitting state this way?"* — cross-boundary references now have to go through remote state data sources (`terraform_remote_state`) or explicit output/variable passing rather than direct in-config references, adding real coordination overhead between the split modules, and changes that genuinely span boundaries (a resource that needs both network and data-tier changes atomically) become a multi-step, multi-apply process instead of one atomic plan/apply — a real cost traded against faster, more isolated day-to-day plans.

---

## Red flags that fail you

- Describing the state file as "just a record of what Terraform created" without the cache/refresh/drift mechanism.
- Conflating state locking with drift protection — they solve different problems.
- Not knowing that renaming a resource without a `moved` block (or `state mv`) plans a destroy/create.
- Claiming built-in `terraform workspace` is the standard way to separate dev/staging/prod with genuinely different configuration.
- Recommending a maximally generic, heavily-parameterized module as the default design choice rather than extracting from proven duplication.
- Not knowing `terraform test`'s apply-mode provisions real infrastructure with real cost.
- Being unaware OpenTofu exists, or of why it forked from Terraform.
- Recommending running `apply` from individual laptops as an acceptable production pattern.

---

## Cheat card

```
STATE: JSON map of resource ADDRESS -> last-known real attributes. A CACHE, not live truth.
  terraform plan REFRESHES state (calls provider Read APIs) before diffing vs .tf config,
  unless -refresh=false. "Drift detected" = refresh found real-world mismatch vs state.

LOCKING: prevents CONCURRENT applies corrupting state (S3 backend: separate DynamoDB
  table, lock item keyed to state path). Does NOT detect or prevent drift — different
  mechanism entirely. Stuck lock -> terraform force-unlock <id>, ONLY after confirming
  the holding process is actually dead, not just slow.

WORKSPACES (built-in): multiple named STATE FILES from the SAME config. Good for
  identical parallel envs. NOT the standard pattern for dev/staging/prod w/ real config
  differences -> use separate backend configs per env, or Terragrunt, instead.

MODULES: variables.tf = input contract, outputs.tf = exposed values, deps auto-graphed
  from output->variable references. Over-abstraction trap: extract from PROVEN
  duplication (2-3 teams w/ near-identical blocks), not hypothetical future reuse.

REFACTOR SAFETY: renaming/moving a resource changes its ADDRESS -> plans destroy+create
  unless declared equivalent. moved { from = X, to = Y } block = declarative, reviewable,
  plan shows NO destroy/create. Old way: terraform state mv (imperative, invisible in PR).
  ALWAYS verify via plan output before applying any "obviously safe" refactor.

TERRAFORM TEST (native since 1.6, current mainline ~1.14 in 2026):
  command = plan  -> fast, plan-only assertions, no real infra
  command = apply -> REAL infra provisioned + torn down, real cost/time per run

TERRAFORM vs PULUMI/CDK: Terraform/HCL wins ecosystem breadth + shared team vocabulary +
  simple declarative reasoning. Pulumi/CDK win genuinely complex/loop-heavy conditional
  logic + real unit testing in a general-purpose language. Live, unresolved disagreement.

OPENTOFU: Linux Foundation fork after HashiCorp's 2023 BSL license change. Drop-in
  compatible through ~1.5.x, diverging feature set since. Real, live, production-used.

TERRAGRUNT: DRYs up backend config + variable wiring across many env directories,
  generates the Terraform config/backend it wraps, doesn't replace Terraform itself.

CI PATTERN: plan posted on PR for human review -> apply on merge against the EXACT
  reviewed .tfplan artifact (not a freshly recomputed one) -> avoids TOCTOU gap.
```

## Sources

- [Terraform in 2026: New Features and Best Practices — Francesco Oghabi](https://oghabi.it/en-us/blog/terraform-2026-features-best-practices/) — accessed 2026-08-03
- HashiCorp Developer documentation — Terraform state, backends, workspaces, `moved`/`removed` blocks, native testing (`terraform test`)
- [Terraform vs Pulumi vs CDK in 2026: What We Actually Use and Why — DEV Community](https://dev.to/lumyxtech/terraform-vs-pulumi-vs-cdk-in-2026-what-we-actually-use-and-why-4j3d) — accessed 2026-08-03
- OpenTofu project documentation (Linux Foundation) — fork rationale and compatibility
- Terragrunt official documentation — Gruntwork

## Changelog
- 2026-08-03 — created
