# Jenkins From Scratch: Declarative Pipelines, Shared Libraries, Agents, Best Practices

> **Track:** T12 DevOps, Infra & Security · **Time:** 3h · **Prereqs:** T12-cicd
> **Module id:** `T12-jenkins` · **Tags:** cicd, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Jenkins is a controller-agent automation server where the **controller** owns scheduling, the web UI, and build state, and never runs your actual build steps in a properly configured setup — build work executes on **agents** (static long-lived VMs, or dynamic containers/Kubernetes pods spun up per-build), connected back to the controller over JNLP/the inbound-agent protocol or SSH. A `Jenkinsfile`'s **declarative pipeline** (the modern default over the older, more powerful but far messier **scripted pipeline**) is Groovy running inside the **Groovy CPS sandbox** — a continuation-passing-style transform that lets a running pipeline be serialized to disk and survive a controller restart mid-build, which is also exactly why plain Groovy idioms that don't survive CPS transformation (certain closures, some standard library calls) throw confusing `NotSerializableException`-flavored errors that trip up anyone who's written normal Groovy before. **Shared libraries** are Jenkins's actual reuse mechanism — a separate Git repo of Groovy code (`vars/` for pipeline-callable steps, `src/` for supporting classes) loaded into any Jenkinsfile via `@Library`, the direct analog to a Terraform module or a GitHub Actions reusable workflow, with the same over-abstraction risk. The honest, current answer on Jenkins vs. GitHub Actions: Jenkins wins on self-hosted/air-gapped compliance requirements, deep customization via 1,800+ plugins, and genuinely complex multi-branch/multi-repo orchestration that predates and often exceeds what GitHub Actions natively expresses — but for a team starting fresh on GitHub with normal compliance needs, GitHub Actions is very often simply the better choice today: zero infrastructure to patch and secure, a much smaller operational burden, and a plugin-CVE attack surface Jenkins has struggled with for years that a hosted runner model sidesteps entirely. Recommending Jenkins by default for a greenfield GitHub-hosted project in 2026 without naming this tradeoff is a real, gettable-wrong interview signal.

## Why this gets asked

Because Jenkins has been running in production for over a decade at a huge number of companies, and most candidates either learned it as "the CI tool" without ever questioning it, or dismiss it reflexively as legacy without understanding why it's still the right choice in specific, real environments. The interviewer has likely either inherited a Jenkins controller with 400 unpatched plugins and a CVE nobody's gotten around to fixing, or migrated a genuinely complex Jenkins pipeline to GitHub Actions and hit real friction doing it, or both. They want to see whether you understand the architecture well enough to debug a stuck build or a starved executor queue, and whether you can make an honest, non-tribal recommendation about which tool fits a given team's actual constraints.

---

## Lineage: past → present → future

**What came before.** Jenkins started as **Hudson** (Sun Microsystems, 2004), forked and renamed Jenkins in 2011 after an Oracle-Sun trademark/governance dispute split the community — one of open source's more consequential fork stories, and worth knowing the name if asked about Jenkins's history. Early Jenkins jobs were configured entirely through the web UI (freestyle jobs) with no version control at all for the pipeline definition itself — the build logic lived only in Jenkins's own XML config, invisible to code review, impossible to diff meaningfully, and trivially lost or drifted between what was documented and what was actually configured. The pain this caused (an incident traced back to "someone changed a build step in the UI six months ago and nobody wrote it down") drove the Pipeline plugin (2016) and the `Jenkinsfile`-as-code model: pipeline definitions checked into the same repo as the code they build, versioned, reviewable, and reproducible from source rather than living only in a GUI's database.

**Where it stands now.** Declarative pipeline syntax (a more restricted, structured DSL layered on top of the older, more flexible-but-messier scripted pipeline) is the standard recommendation for new Jenkinsfiles today — predefined directives (`pipeline`, `agent`, `stages`, `stage`, `steps`, `post`) make pipelines easier to read, validate before running (a syntax-only lint pass can catch structural errors without executing anything), and approachable for developers who aren't Groovy experts, at some cost in flexibility versus scripted pipeline's arbitrary Groovy control flow. Kubernetes-based dynamic agents (the Kubernetes plugin, spinning up a fresh pod per build, torn down after) have become the dominant agent model at any real scale, replacing the older pattern of a fixed pool of static VM agents that had to be pre-provisioned, patched, and kept in sync with whatever toolchains builds needed — dynamic agents mean each build gets a clean, disposable environment and capacity scales with demand rather than sitting pre-allocated. The live, real disagreement in the ecosystem isn't really "is Jenkins good" so much as "does a *new* project need Jenkins at all" — GitHub Actions, GitLab CI, and CircleCI's hosted, zero-infrastructure models have captured most greenfield projects, especially anything already hosted on GitHub, and Jenkins's remaining core strength is genuinely deep customizability, on-prem/air-gapped operation, and multi-repo/multi-branch orchestration patterns that took years to mature and that some organizations have deep, working investment in — not a claim that Jenkins is simply obsolete.

**Where it's heading.** Jenkins's plugin ecosystem (1,800+ plugins as commonly cited) remains both its biggest strength and its biggest liability — the sheer surface area of community-maintained plugins with varying maintenance quality is a persistent, real source of CVEs, and "Jenkins security" as a topic is dominated by plugin-vetting and patching discipline rather than core-server vulnerabilities. Expect continued, gradual migration of greenfield projects toward hosted CI (GitHub Actions being the largest beneficiary given GitHub's own market position) while Jenkins retains a durable, non-trivial footprint in large enterprises with genuine on-prem/compliance/legacy-integration requirements — this is a stable, multi-year trend rather than Jenkins disappearing, and stating "Jenkins is dying" flatly in an interview is roughly as imprecise as claiming it's still the obvious default for every new project.

---

## Mental model

```
┌─────────────────────────────────────────────────────────────┐
│  CONTROLLER (the "master")                                    │
│    - web UI, REST API                                          │
│    - job/pipeline SCHEDULING (build queue)                      │
│    - build HISTORY, artifacts, logs storage                      │
│    - does NOT run your build steps (in a correctly configured    │
│      setup — running builds directly on the controller is a       │
│      known anti-pattern: resource contention + a security risk)    │
└─────────────────────────────────────────────────────────────┘
                   │  assigns queued builds to an available
                   │  agent matching required labels
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  AGENTS (the actual executors)                                 │
│    static: long-lived VM, pre-provisioned toolchain,              │
│            connects via JNLP/inbound-agent or SSH                  │
│    dynamic: Kubernetes pod per build (Kubernetes plugin),          │
│             spun up on demand, torn down after — CLEAN env          │
│             every time, capacity scales with demand                  │
└─────────────────────────────────────────────────────────────┘

Jenkinsfile (checked into repo) declares:
  agent { ... }        <- WHERE this runs (label, docker image, k8s pod template)
  stages { stage(...) {steps {...}} }   <- WHAT runs, in order
  post { success{} failure{} always{} } <- notification/cleanup, regardless of outcome

SHARED LIBRARY (separate git repo):
  vars/deployApp.groovy   <- callable directly as a pipeline STEP: deployApp(...)
  src/org/myorg/Utils.groovy  <- supporting CLASSES, imported normally
  loaded via: @Library('my-shared-lib@v2') _   at the top of any Jenkinsfile
```

---

## How it actually works

### Declarative vs. scripted pipeline, and why CPS matters

**Declarative pipeline** is a constrained, structured DSL — `pipeline { agent {...} stages {...} post {...} }` — validated for structural correctness before any step actually runs, and readable by anyone regardless of Groovy fluency. **Scripted pipeline** is arbitrary Groovy wrapped in a `node {}` block, giving full programming-language flexibility (real loops, conditionals, try/catch anywhere) at the cost of readability and safety guardrails — declarative can still drop into scripted Groovy via a `script {}` block for the specific cases that genuinely need it, which is the standard, correct way to get scripted's flexibility without abandoning declarative's structure everywhere else.

Both run inside Jenkins's **Groovy CPS (Continuation-Passing Style) sandbox** — every pipeline execution is transformed so that its entire call stack and local state can be serialized to disk at any point (this is what lets a multi-hour pipeline survive a controller restart and resume exactly where it left off, rather than having to start over). The direct, very real consequence: not all normal Groovy code survives this transformation cleanly. Certain closures, some standard Java/Groovy library method calls that aren't CPS-transformable, and non-serializable objects held across a step boundary can throw a `NotSerializableException`-flavored error or fail with a cryptic CPS-related message — a real, common source of confusion for anyone who writes what looks like completely normal Groovy and can't understand why it fails only inside a pipeline, never in a plain Groovy script run standalone. The practical mitigation: keep genuinely complex logic in `@NonCPS`-annotated methods (opting a specific method out of CPS transformation, at the cost of that method being unable to pause/resume mid-execution) or, better, push complex logic into a shared library's `src/` classes where it's easier to structure around this constraint deliberately rather than discovering it by trial and error inside a Jenkinsfile.

### Shared libraries, mechanically

A shared library is a normal Git repository with a specific directory convention: `vars/<name>.groovy` defines a global variable/callable step (a file `vars/deployApp.groovy` with a `call(Map config)` method becomes usable as `deployApp(env: 'prod', version: '1.2.3')` directly in any Jenkinsfile that loads the library), and `src/` holds regular Groovy classes under normal package structure for anything more complex than a single callable step.

```groovy
// untested sketch — vars/deployApp.groovy in a shared library repo
def call(Map config) {
    sh "kubectl set image deployment/${config.app} app=${config.image}:${config.tag} -n ${config.env}"
    sh "kubectl rollout status deployment/${config.app} -n ${config.env} --timeout=120s"
}
```

```groovy
// untested sketch — a Jenkinsfile consuming the shared library
@Library('platform-shared-lib@v3') _   // pins a specific tag, not a floating branch

pipeline {
    agent { kubernetes { yaml libraryResource('pod-templates/node-build.yaml') } }
    stages {
        stage('Build') {
            steps { sh 'npm ci && npm run build' }
        }
        stage('Deploy') {
            steps {
                deployApp(app: 'checkout-api', image: 'myrepo/checkout-api', tag: env.GIT_COMMIT, env: 'staging')
            }
        }
    }
    post {
        failure { slackSend(channel: '#ci-alerts', message: "Build failed: ${env.BUILD_URL}") }
    }
}
```

`@Library('platform-shared-lib@v3')` pinning to a specific tag (rather than a floating branch like `@master`) is the same discipline as pinning a Terraform module version or a GitHub Actions reusable workflow's ref — an unpinned shared library reference means every pipeline using it can silently start behaving differently the moment someone merges a change to the library's default branch, a genuinely common source of "nothing changed in our Jenkinsfile but the build broke" incidents.

### Agents — static vs. dynamic, and the security-relevant distinction

A **static agent** is a long-lived VM (or bare-metal host) registered once with the controller, connected persistently via the JNLP/inbound-agent protocol (the agent process initiates the connection outward to the controller, useful when the agent sits behind a firewall/NAT the controller can't reach inbound) or via SSH (the controller connects out to the agent instead). Static agents accumulate state across builds unless explicitly cleaned — a real, recurring source of "works on this agent, fails on that one" flakiness when build artifacts, cached dependencies, or leftover processes from a previous build bleed into the next one on the same host.

**Dynamic agents** via the Kubernetes plugin solve this directly: a pod is created fresh per build (or per pipeline stage, with pod templates definable per-stage for different toolchain needs within one pipeline), runs the build, and is torn down afterward — no state persists between builds by default, and capacity scales with actual demand rather than sitting pre-provisioned. The real operational tradeoff: dynamic agents pay a cold-start cost (pulling images, pod scheduling) on every build that a warm, already-running static agent doesn't, which matters for teams optimizing for fast iteration on frequent small builds.

**Executors** (the configurable concurrency unit per agent — how many builds a given agent node can run simultaneously) are a common, easy-to-miss capacity bottleneck: a controller can have a healthy fleet of agents but still show builds stuck `Pending` in the queue if the *number of executors* across matching agents is lower than concurrent build demand — this is a distinct constraint from raw CPU/memory capacity and is diagnosed from the build queue view, not from agent resource graphs.

### Security surface — plugins, crumbs, and the controller as a high-value target

Jenkins's plugin ecosystem is its defining strength and its most persistent security liability simultaneously — with 1,800+ community-maintained plugins of widely varying maintenance quality, CVEs in individual plugins (not Jenkins core) are the dominant source of real Jenkins vulnerabilities reported year over year, and a Jenkins security posture is realistically dominated by plugin inventory discipline (removing unused plugins, tracking CVEs against installed versions, and controlling who can install new plugins at all) rather than core-server hardening alone. CSRF protection (the "crumb" — a per-session token Jenkins requires on state-changing requests) is enabled by default in modern Jenkins and is a common trip-up for anyone scripting against the Jenkins REST API without first fetching a crumb token, producing a `403`-flavored rejection that's frequently misdiagnosed as an auth/permissions problem rather than a missing CSRF token. The controller itself is a genuinely high-value target precisely because it typically holds credentials (via the Credentials plugin) for deploying to production across every pipeline it runs — a compromised controller is potentially a compromise of every system every pipeline it runs has access to, which is the direct argument for never running arbitrary/untrusted build steps directly on the controller and for treating controller access as tightly as production infrastructure access itself.

---

## Build it from scratch

```groovy
// untested sketch — a realistic declarative pipeline: build, test, conditional deploy,
// with a Kubernetes dynamic agent and post-build notification
pipeline {
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: node
    image: node:20-alpine
    command: ['cat']
    tty: true
'''
        }
    }
    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()          // avoid two builds racing on the same branch
    }
    stages {
        stage('Install & Test') {
            steps {
                container('node') {
                    sh 'npm ci'
                    sh 'npm test -- --ci --reporters=default --reporters=jest-junit'
                }
            }
            post {
                always { junit 'reports/junit.xml' }
            }
        }
        stage('Build') {
            steps { container('node') { sh 'npm run build' } }
        }
        stage('Deploy to staging') {
            when { branch 'main' }          // only deploy from main, not every PR branch
            steps {
                withCredentials([string(credentialsId: 'kubeconfig-staging', variable: 'KUBECONFIG')]) {
                    sh 'kubectl apply -f k8s/staging/'
                }
            }
        }
    }
    post {
        failure {
            slackSend(channel: '#ci-alerts', color: 'danger',
                      message: "FAILED: ${env.JOB_NAME} #${env.BUILD_NUMBER} — ${env.BUILD_URL}")
        }
    }
}
```

---

## How it's done in production

Production Jenkins deployments near-universally run **multibranch pipeline jobs** (automatically discovering and building every branch/PR in a repo that contains a `Jenkinsfile`, rather than hand-configuring one job per branch), pin shared library references to specific tags rather than floating branches, and run all real build work on dynamic Kubernetes agents with per-stage pod templates rather than a shared pool of static VMs. Controller high availability and backup discipline matters more than it might seem — the controller's on-disk state (`JENKINS_HOME`: job configs, build history, credentials store, plugin state) is the entire operational memory of the system, and losing it without a recent backup is a genuinely severe incident, not just an inconvenience, given how much organizational build/deploy knowledge tends to live only in Jenkins job configuration over years of accumulated pipelines.

| Symptom | Cause | Fix |
|---|---|---|
| A pipeline step throws a `NotSerializableException`-flavored error that never happens running the same Groovy standalone | Code inside the pipeline isn't CPS-transformable (certain closures, some non-serializable objects held across a step boundary) | Move the offending logic into an `@NonCPS`-annotated method, or better, into a shared library's `src/` class structured to avoid the constraint |
| Builds sit `Pending` in the queue despite agents showing healthy CPU/memory headroom | Executor count on matching agents is lower than concurrent build demand — a distinct constraint from raw resource capacity | Increase executor count per agent, add more agent capacity, or use `disableConcurrentBuilds()`/queue-shaping to reduce concurrent demand for jobs that don't need it |
| "Nothing changed in our Jenkinsfile" but a build starts failing or behaving differently | An unpinned shared library reference (`@Library('lib@master')`) picked up a new commit to the library's default branch | Pin `@Library` references to specific, immutable tags, not floating branches |
| A build passes on one static agent and fails identically-configured on another | Leftover state (cached dependencies, stray processes, disk artifacts) from a previous build bled into this one on a long-lived agent | Migrate to dynamic Kubernetes agents for a clean environment per build, or add explicit workspace-cleaning steps if static agents must be kept |
| A script calling the Jenkins REST API gets a `403` that looks like an auth failure but credentials are confirmed correct | Missing CSRF crumb token on a state-changing request — Jenkins requires it by default | Fetch a crumb via the crumb issuer endpoint first and include it in the request headers, rather than assuming it's a permissions misconfiguration |
| A security review finds Jenkins has dozens of plugins nobody remembers installing, several with known CVEs | No plugin inventory/lifecycle discipline — plugins accumulated over years with no periodic review | Audit installed plugins against actual usage, remove unused ones, track CVEs against installed versions, and restrict who can install new plugins |

---

## Tradeoffs & when NOT to use it

- **Don't default to Jenkins for a new, GitHub-hosted project with normal (non-air-gapped, non-exotic-compliance) requirements.** GitHub Actions genuinely wins there today — zero infrastructure to patch and secure, tight native integration, a large marketplace of actions, and none of Jenkins's plugin-CVE attack surface to manage. Recommending Jenkins reflexively here, without naming this, is an outdated instinct, not a neutral default.
- **Don't run build steps directly on the Jenkins controller**, ever, as a shortcut. It's both a resource-contention problem (the controller's job is scheduling and UI, not executing arbitrary workloads) and a real security anti-pattern, since the controller typically holds credentials for every pipeline's deploy targets — compromising a build running on the controller is a much shorter path to compromising everything than compromising an isolated, disposable agent.
- **Don't use scripted pipeline by default "because it's more powerful."** Declarative's structure and pre-execution validation are worth the reduced flexibility for the vast majority of pipelines; drop into a `script {}` block only for the specific logic that genuinely needs scripted's control flow, rather than writing the whole Jenkinsfile in scripted style from the start.
- **Don't treat static, long-lived agents as the default for anything at real scale.** The state-bleed and toolchain-drift problems they introduce are real and compound over time; dynamic Kubernetes agents cost a per-build cold-start penalty but eliminate an entire class of "works on agent A, not agent B" flakiness.
- **Don't leave shared library references unpinned.** It's a small amount of extra discipline (using tags, bumping them deliberately) against a real, recurring "silent behavior change" incident class that's easy to avoid entirely.
- **Do reach for Jenkins deliberately, not by default,** when the actual requirements are genuinely air-gapped/on-prem execution, deep customization via specific plugins with no hosted-CI equivalent, or complex multi-repo/multi-branch orchestration patterns a team already has mature, working investment in — these are real, still-current reasons to choose or keep Jenkins, not legacy inertia.

---

## Interview questions

### Q1 — What does the Jenkins controller actually do, and why shouldn't it run build steps directly?
**Testing:** the controller/agent separation as a real architectural and security boundary, not just terminology.
**Answer:** The controller handles scheduling (the build queue), the web UI/REST API, and build history/artifact storage — it doesn't execute build workloads in a correctly configured setup. Running builds on the controller directly creates resource contention with its scheduling/UI responsibilities and is a security anti-pattern, since the controller typically holds credentials (via the Credentials plugin) for every pipeline's deploy targets — a build compromise there has a much larger blast radius than a compromise on an isolated, disposable agent.
**Follow-up trap:** *"If an agent is compromised instead, is the blast radius the same?"* — no, meaningfully smaller, especially for a dynamic Kubernetes agent that only holds whatever credentials were explicitly injected for that specific build/stage and is torn down afterward — this is exactly the argument for scoping credentials narrowly per pipeline/stage rather than giving every agent broad access "just in case."

### Q2 — Why does a pipeline step sometimes throw a serialization-related error for Groovy code that runs completely fine as a standalone script?
**Testing:** the CPS sandbox mechanism, a genuinely non-obvious but real trap.
**Answer:** Jenkins pipelines run inside a Groovy CPS (Continuation-Passing Style) sandbox specifically so a running pipeline's state can be serialized to disk and survive a controller restart mid-build. Not all normal Groovy constructs survive this transformation — certain closures and non-CPS-transformable library calls can throw a `NotSerializableException`-flavored error inside a pipeline that never occurs running the same code as a plain Groovy script.
**Follow-up trap:** *"What's the practical fix, and what does it cost?"* — mark the offending method `@NonCPS` to opt it out of the transformation, at the cost of that method no longer being able to pause/resume mid-execution (it must run to completion without a durability checkpoint) — or, better, push the complex logic into a shared library's `src/` classes structured deliberately around the constraint rather than hitting it by trial and error inline in a Jenkinsfile.

### Q3 — What's the direct analog between a Jenkins shared library and a concept from Terraform or GitHub Actions, and what risk do they all share?
**Testing:** cross-tool pattern recognition, a real senior-level signal.
**Answer:** A shared library is Jenkins's reuse mechanism, directly analogous to a Terraform module or a GitHub Actions reusable workflow — separate, versioned code loaded into many pipelines/configs to avoid duplication. All three share the same over-abstraction risk: a shared library/module/workflow designed to cover every consumer's use case upfront accumulates enough parameters and conditional branches that using it correctly requires reading its internals anyway.
**Follow-up trap:** *"What's the shared-library-specific version of Terraform's 'unpinned module version' risk?"* — an unpinned `@Library('lib@master')` reference (a floating branch instead of a tag) means every pipeline using it can silently change behavior the moment someone merges to the library's default branch — the exact same class of risk as an unpinned Terraform module source, with the same fix: pin to specific, immutable versions/tags.

### Q4 — Builds are stuck `Pending` in the queue, but every agent's CPU/memory graphs show healthy headroom. What's the likely cause?
**Testing:** the executor-count-vs-resource-capacity distinction, a real and specific operational trap.
**Answer:** Executor count (the configurable concurrency limit per agent — how many builds that agent can run simultaneously) is a separate constraint from raw CPU/memory capacity, and can be the actual bottleneck even when resource graphs look fine. Diagnosis comes from the build queue view (which shows *why* a build is waiting), not agent resource dashboards.
**Follow-up trap:** *"Why not just set executor count very high on every agent to avoid this entirely?"* — executors sharing one agent's actual CPU/memory/disk still contend for those real resources regardless of the configured executor count — setting it too high just moves the bottleneck from "queued, waiting for a slot" to "running, but starved and slow," which is often worse and harder to diagnose since builds appear to be progressing rather than obviously blocked.

### Q5 — A team wants to migrate off Jenkins to GitHub Actions. What's the honest case for and against, specific to their situation, not a generic "GitHub Actions is newer" argument?
**Testing:** whether you'll give a real, situational answer instead of picking a side reflexively.
**Answer:** For: if they're already hosted on GitHub with normal compliance needs, GitHub Actions eliminates infrastructure patching/securing entirely, removes Jenkins's plugin-CVE surface, and integrates natively with PRs/checks/deployments with less operational overhead. Against: if they have genuinely air-gapped/on-prem requirements, deep dependency on specific Jenkins plugins with no hosted equivalent, or complex multi-repo/multi-branch orchestration built up over years that would require real re-architecture to replicate in Actions, migration cost can easily outweigh the benefit, and Jenkins remains the right tool for them.
**Follow-up trap:** *"If cost is cited as the deciding factor either way, what's the actual comparison?"* — it's not simply "free hosted CI vs. paying for servers" — Jenkins has real, often underestimated operational cost (the engineering time spent patching, securing, and maintaining controller/agent infrastructure), while GitHub Actions' generous free tier can get expensive fast at real build volume/concurrency for a larger team — a genuine total-cost comparison needs both dimensions, not just sticker price on either side.

### Q6 — What's the difference between declarative and scripted pipeline, and when is dropping into a `script {}` block the right call inside a declarative pipeline?
**Testing:** whether the two are understood as complementary, not simply "old vs. new."
**Answer:** Declarative is a structured, validated DSL (`pipeline { agent {} stages {} post {} }`) that's easier to read and safer for less Groovy-fluent contributors, at the cost of flexibility. Scripted is arbitrary Groovy in a `node {}` block with full control-flow flexibility but far less structure/safety. A `script {}` block inside declarative is the standard, correct escape hatch for the specific logic that genuinely needs scripted's flexibility (complex conditional branching, dynamic stage generation) without abandoning declarative's structure for the rest of the pipeline.
**Follow-up trap:** *"Is writing an entire Jenkinsfile in scripted style ever the right default choice today?"* — rarely, for new pipelines — declarative's validation and readability benefits are worth it for the vast majority of cases; scripted-by-default is more often inherited from an older Jenkinsfile written before declarative matured than a deliberate current choice, and migrating incrementally (declarative shell with `script{}` blocks for the genuinely complex parts) is usually better than a full rewrite or staying scripted wholesale.

### Q7 — Why are static, long-lived Jenkins agents considered a real operational liability at scale, and what specifically replaces them?
**Testing:** the state-bleed problem and its concrete fix.
**Answer:** Static agents accumulate state across builds unless explicitly cleaned — cached dependencies, leftover processes, disk artifacts from a previous build can bleed into the next one on the same host, producing "works on agent A, fails identically-configured on agent B" flakiness that's genuinely hard to root-cause. Dynamic agents via the Kubernetes plugin replace them by spinning up a fresh pod per build (or per stage, with per-stage pod templates for different toolchain needs), torn down afterward — no persisted state by default.
**Follow-up trap:** *"What's the real cost dynamic agents introduce that static agents don't have?"* — cold-start latency per build (image pull, pod scheduling) that an already-running static agent doesn't pay — a genuine tradeoff for teams optimizing hard for fast iteration on frequent small builds, sometimes mitigated with image pre-pulling/caching strategies but not eliminated entirely.

### Q8 — A script hitting the Jenkins REST API gets a `403` even though the credentials used are confirmed correct and have the right permissions. What's the likely cause?
**Testing:** a specific, real, frequently-misdiagnosed Jenkins security mechanic.
**Answer:** A missing CSRF "crumb" token — Jenkins requires a per-session crumb on state-changing REST API requests by default, and its absence produces a `403`-flavored rejection that looks identical to an auth/permissions failure on the surface but is actually a missing-token problem, not a credentials or permission-scope issue.
**Follow-up trap:** *"How would you distinguish a missing-crumb 403 from a genuine permissions 403 without guessing?"* — check the actual response body/headers — Jenkins's crumb-related rejection typically includes distinguishing text (referencing the crumb/CSRF check specifically) versus a generic permissions-denied message; the reliable fix either way is to explicitly fetch a crumb from the crumb issuer endpoint first and include it on the request, which resolves the CSRF case and leaves a genuine permissions problem still visibly failing afterward for separate diagnosis.

### Q9 — Why is Jenkins's plugin ecosystem described as both its biggest strength and its biggest security liability?
**Testing:** a nuanced, non-tribal understanding of the actual tradeoff, not "plugins are bad."
**Answer:** The 1,800+ plugin ecosystem is what makes Jenkins deeply customizable and able to integrate with essentially anything — but plugins are community-maintained with widely varying quality and update cadence, and the large majority of real Jenkins CVEs reported over the years are plugin vulnerabilities, not Jenkins core. A real Jenkins security posture is dominated by plugin inventory discipline (removing unused plugins, tracking CVEs against installed versions, restricting who can install new ones) rather than core-server hardening alone.
**Follow-up trap:** *"Does minimizing plugin count entirely eliminate this risk?"* — it reduces but doesn't eliminate it — even a small, carefully-chosen plugin set still needs active CVE tracking and update discipline over time, since a plugin that was safe and well-maintained at install time can develop a vulnerability or go unmaintained later; plugin minimization reduces surface area, it isn't a one-time fix that removes the need for ongoing review.

### Q10 — Your Jenkins controller's disk dies with no warning. What's actually lost, and how do you design against it?
**Testing:** whether the candidate treats the controller as a stateful system requiring real DR planning, not a stateless service you just redeploy.
**Answer:** Everything that makes Jenkins *Jenkins* lives on the controller's `$JENKINS_HOME`: job configs, build history and artifacts, credentials (encrypted with `master.key` — losing that key makes `credentials.xml`'s encrypted values permanently unrecoverable, not just inaccessible), and plugin state — none of it is reconstructable from the Jenkinsfiles in source control alone, since those only define pipeline *logic*, not job configuration, credentials, or history. The real DR design: back up `$JENKINS_HOME` (or at minimum `master.key`, `credentials.xml`, and `jobs/`) on a real schedule to storage outside the controller itself, and treat Jenkins-as-code tooling (JCasC — Jenkins Configuration as Code — for system/job config, not just pipeline logic) as the way to make the controller itself reconstructable from version control rather than depending on point-in-time backups alone.
**Follow-up trap:** *"If you'd adopted JCasC for everything, do you still need to back up `$JENKINS_HOME`?"* — yes, for two things JCasC doesn't cover: credentials (JCasC can reference where secrets come from, but the encrypted values and their encryption key still live on-disk and need their own backup/rotation strategy) and build history/artifacts, which are runtime data, not declarative config — JCasC solves reconstructability of *configuration*, not preservation of *history and secrets*, and conflating the two is the trap.

---

## Red flags that fail you

- Recommending Jenkins by default for a new, GitHub-hosted project without naming the real GitHub Actions tradeoff, or dismissing Jenkins entirely as "legacy" without naming where it's still the right call.
- Running build steps directly on the controller, or not knowing why that's an anti-pattern.
- Not knowing the difference between declarative and scripted pipeline, or claiming declarative can't drop into scripted logic via `script {}`.
- Leaving shared library references unpinned (`@Library('lib@master')`) without recognizing the risk.
- Misdiagnosing a missing-CSRF-crumb `403` as a permissions problem.
- Treating Jenkins's plugin CVEs as a fixable one-time cleanup rather than an ongoing inventory/tracking discipline.
- Not knowing that executor count is a distinct capacity constraint from raw agent CPU/memory.

---

## Cheat card

```
ARCHITECTURE: Controller = scheduling, UI, build history, credentials store. Does NOT
  run builds in a correct setup — that's the AGENTS' job.
  static agent: long-lived VM, JNLP(inbound)/SSH connection, state persists across builds
    (real flakiness risk: cross-build state bleed)
  dynamic agent: Kubernetes plugin, fresh pod per build, torn down after, no state
    persistence, pays cold-start cost per build vs. always-warm static

PIPELINE: declarative (structured DSL, validated pre-run, readable) is the modern
  default over scripted (raw Groovy in node{}, more flexible, less safe). script{}
  block = the correct escape hatch inside declarative for genuinely complex logic.
  Both run inside Groovy CPS SANDBOX (enables serialize-to-disk / controller-restart
  survival) -> non-CPS-transformable code throws NotSerializableException-flavored
  errors that never occur in plain Groovy. Fix: @NonCPS method, or push logic to
  shared library src/ classes.

SHARED LIBRARIES: vars/<name>.groovy = callable pipeline step, src/ = supporting
  classes. @Library('name@TAG') _ loads it. PIN TO A TAG, not a floating branch —
  unpinned = silent behavior change risk, same class as an unpinned Terraform module.
  Direct analog: Terraform module / GitHub Actions reusable workflow. Same
  over-abstraction risk if over-parameterized.

EXECUTORS: per-agent concurrency limit, a DISTINCT bottleneck from raw CPU/memory.
  Pending builds + healthy resource graphs = check executor count, not agent resources.

SECURITY: 1,800+ plugins = biggest strength AND biggest CVE source (plugin CVEs, not
  core, dominate real Jenkins vulnerabilities). CSRF "crumb" required by default on
  state-changing REST calls -> missing crumb = 403 that LOOKS like a permissions error
  but isn't. Controller holds deploy credentials for every pipeline -> high-value
  compromise target, never run untrusted/arbitrary builds on it directly.

HISTORY: forked from Hudson (Sun Microsystems, 2004) in 2011 after an Oracle
  trademark/governance dispute.

HONEST vs GITHUB ACTIONS: Actions wins for greenfield GitHub-hosted projects, normal
  compliance needs — zero infra to patch, no plugin-CVE surface, tight native
  integration. Jenkins still right for genuine air-gapped/on-prem requirements, deep
  plugin-specific customization w/ no hosted equivalent, or mature complex multi-repo/
  multi-branch orchestration already built out. NOT a "Jenkins is dead" call either way.
```

## Sources

- [Jenkins vs GitHub Actions: Best CI/CD Pipeline Tool in 2026 — learnmandu](https://learnmandu.com/blog/tech/jenkins-vs-github-actions-cicd) — accessed 2026-08-03
- [Jenkins vs GitHub Actions vs GitLab CI (2026) — SquareOps](https://squareops.com/blog/jenkins-vs-github-actions-vs-gitlab-ci-2026/) — accessed 2026-08-03
- [Extending with Shared Libraries — Jenkins official documentation](https://www.jenkins.io/doc/book/pipeline/shared-libraries/) — accessed 2026-08-03
- Jenkins official documentation — Pipeline syntax (declarative/scripted), Kubernetes plugin, Groovy CPS, CSRF protection
- Jenkins project history — Hudson/Jenkins fork (2011)

## Changelog
- 2026-08-03 — created
