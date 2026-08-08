# Incident Response, Blameless Postmortems, On-Call

> **Track:** T13 SDE Craft & Vibe Coding · **Time:** 1h · **Prereqs:** `T13-code-review` · **Updated:** 2026-08-05
> **Module id:** `T13-incidents` · **Tags:** incidents, on-call, sre, postmortem, incident-command, slo, critical

## The 30-second version

Incident command is a learnable, teachable role that is deliberately separate from debugging: the Incident Commander does not touch a terminal, because the moment the person coordinating starts typing they stop tracking the other four workstreams. The default rule is mitigate before you diagnose (fail over, roll back, drain the region, flip the feature flag) and the rule inverts in exactly two cases: when the mitigation is itself irreversible or data-destructive, and when you have no idea what the blast radius of the mitigation is, which is a diagnosis problem wearing a mitigation costume. Postmortems are blameless not because blame is unkind but because blame is *epistemically useless*: an engineer who fears the writeup gives you a sanitised timeline, and a sanitised timeline is a corrupted dataset for the only thing the exercise produces, which is a list of system changes. "Human error" is never a root cause, because it terminates the investigation exactly where it should start: the real finding is what made the wrong action look like the right action from where that person stood, with the information they actually had at 03:12. When an interviewer asks about my worst outage, the answer that gets a staff-level score narrates the *decisions* (when I declared, what I chose not to investigate, what I told customers at minute 12 while still not knowing the cause) and not the fix.

## Why this gets asked

"Tell me about your worst outage" is the single most reliable staff/principal filter in a behavioural loop, and the reason it works is that almost everyone answers the wrong question. Candidates narrate the debugging: the metric they noticed, the log line they grepped, the config they changed, the moment it recovered. That is a senior-engineer answer, and it caps you at senior, because it demonstrates only that you can debug, which the interviewer already assumed from your resume. What the interviewer is probing is whether you have ever been the person who has to *decide with incomplete information under a clock that everyone is watching*: whether to declare Sev1 at minute 4 when you're only 60% sure, whether to roll back a deploy that might not be the cause and will cost 20 minutes to redo, what to write in a public status update when the honest answer is "we don't know yet," and whether you can hold five parallel workstreams in your head without picking up a shell yourself.

The interviewer asking this has almost always personally lived through an incident that went badly for organisational reasons rather than technical ones: an outage where six engineers independently SSH'd into production and made conflicting changes because nobody was in command, or where the actual fix was known at minute 15 and the customer comms didn't go out until minute 90 because the only person who knew was head-down in a debugger, or where the postmortem produced 14 action items and 11 of them were still open a year later when the same failure recurred. They are checking whether you have internalised that in an incident over about 20 minutes, coordination becomes the bottleneck, not diagnosis. The second thing they're probing, especially at principal level, is whether you can talk about an incident you were partly responsible for without either defensiveness or performative self-flagellation, because both of those predict how you'll behave in *their* postmortems.

---

## Lineage: past → present → future

**What came before.** Before roughly 2003, software operations had no standard incident structure at all: an outage was whoever was awake plus whoever they phoned, and the coordination model was an unmoderated conference bridge. The specific pain that killed this was documented over and over in the same shape: parallel uncoordinated remediation. Multiple engineers, each individually competent, each with root, making simultaneous changes to the same system with no shared state about who had already tried what, which routinely turned a 15-minute incident into a 4-hour one and occasionally caused a second, worse outage on top of the first. The fix was borrowed from outside software entirely: the US Incident Command System, formalised by fire services in the 1970s after the 1970 California wildfires, where the same failure (multiple agencies, no unified command, conflicting orders) had killed people. Google adapted ICS into IMAG (Incident Management at Google) and published it in the 2016 SRE book; PagerDuty published its internal ICS-derived process publicly in 2016 at `response.pagerduty.com`, which is why the IC/Deputy/Scribe/Liaison vocabulary is nearly identical across companies that never coordinated on it. On the analysis side, the ancestor was Toyota-derived Five Whys root-cause analysis imported from manufacturing, and the pain that killed *that* was named by John Allspaw in 2014: Five Whys walks a single causal chain backwards and terminates on a person, so a method designed to find system defects reliably produced the finding "operator should have been more careful," which changes nothing and teaches the operator to say less next time.

**Where it stands now.** The ICS-derived role split (Incident Commander, Communications Lead, Operations Lead, Scribe) is settled consensus at any company past ~200 engineers, and the non-negotiable part everyone agrees on is that the IC does not debug. Blameless postmortems are equally settled as stated policy and much less settled in practice: the live disagreement is whether "blameless" survives contact with regulated industries, security incidents with an insider component, and repeat offenders, and the honest current position (Etsy/Allspaw's original framing, echoed by most SRE orgs) is that blameless means *no punitive consequence attaches to the account you give*, not that accountability disappears. The second live disagreement is over root cause itself. The resilience-engineering camp (Allspaw, Sidney Dekker, Richard Cook, the Learning From Incidents community) argues that complex systems have no single root cause and that the term should be abolished in favour of contributing factors; the pragmatist camp argues that a postmortem that refuses to prioritise causes produces a list nobody can act on. What is actually deployed at scale is a hybrid: most large orgs still have a "root cause" field in the template because incident-management tooling and executive reporting demand one, while the analysis section underneath is a multi-factor narrative. On alerting, the settled position is symptom-based, SLO-driven paging using multiwindow multi-burn-rate alerts (Google SRE Workbook, `sre.google/workbook/alerting-on-slos/`), and the settled load target is a maximum of about two paging events per 8-to-12-hour shift; the widely-ignored-in-practice part is that most orgs measure alert volume and never measure alert *actionability*, so pager fatigue is diagnosed only after someone quits.

**Where it's heading.** Three directions, at descending confidence. High confidence: LLM-assisted incident summarisation and timeline construction is already deployed (incident.io, Rootly, PagerDuty and Datadog all shipped auto-generated incident timelines and draft postmortems by 2025), and it is genuinely good at the mechanical Scribe layer (assembling the timeline from Slack, deploys, and alerts) and genuinely bad at the analytical layer, for the same reason AI code review is good at import checks and bad at design fit: the causal analysis requires organisational context that is not in any log. Expect the Scribe role to be substantially automated and the IC role to be untouched. Medium confidence: SLO-driven paging keeps displacing threshold-driven paging, and the friction is that error-budget policy requires an executive who will actually honour "we stop feature work when the budget is exhausted," which most orgs will not do, so error budgets degrade into a dashboard nobody enforces. Speculative, flagged as such: several people are arguing for retiring "root cause" from templates entirely in favour of a causal-graph artifact, and I would not bet on that winning inside the next five years, because the pressure keeping the single-cause field alive is regulatory and executive reporting, not engineering preference. For an AI-heavy stack specifically, the emerging and under-standardised area is incident response for nondeterministic systems: there is no settled severity vocabulary for "the model is still up and answering, and the answers got 8% worse," and the honest answer in an interview is that this is an open problem rather than a solved one.

---

## Mental model

```
THE INCIDENT AS TWO SEPARATE MACHINES RUNNING IN PARALLEL

  COORDINATION MACHINE                    DIAGNOSIS MACHINE
  (Incident Commander owns)               (Operations Lead owns)
  ────────────────────────                ─────────────────────
  who is doing what                       what is broken
  what have we already tried               why is it broken
  what is the current hypothesis           what fixes it
  when is the next comms update
  do we need more people
  is the mitigation safe to apply

  THE ONE RULE:  the IC does not type into a terminal.
  The moment the coordinator debugs, the coordination machine
  halts, and nobody notices for 20 minutes.

ROLE SPLIT (ICS-derived; scale it DOWN for small incidents, never up)

   INCIDENT COMMANDER ──┬── OPERATIONS LEAD ── SMEs (the only people with prod access)
   decides. does not    │   the only person who makes changes / delegates them
   touch prod.          │
                        ├── COMMUNICATIONS LEAD ── status page, customers, execs
                        │   owns the external clock. shields the IC from "any update?"
                        │
                        └── SCRIBE ── timestamps every decision, in the channel, live
                            NOT investigating. NOT fixing. Just writing.

   Sev3: one person wears all four hats. That is fine and correct.
   Sev1: four different people. If one person wears two of these at Sev1,
         the one that silently gets dropped is always the Scribe, and you
         find out 3 days later when nobody can reconstruct the timeline.

THE INCIDENT CLOCK — what the two machines are doing minute by minute

  t=0    alert fires (symptom-based, ideally SLO burn rate)
  t=2    human ack. FIRST QUESTION IS NOT "why". It is "how bad, how wide".
  t=4    DECLARE. severity + IC named out loud in the channel.
         Declaring late is the #1 process failure. Declaring is cheap.
  t=6    first comms update. Contains NO cause. "Investigating, impact is X."
  t=8    MITIGATE. roll back / fail over / flag off / drain.
         You are not trying to understand. You are trying to stop the bleeding.
  t=20   impact stopped. NOW the clock slows down and diagnosis starts.
  t=30   comms cadence continues at fixed interval until "resolved".
  +24h   postmortem draft. +5d   review meeting. +30d  action items closed.

  MITIGATE-BEFORE-DIAGNOSE INVERTS WHEN:
    (a) the mitigation is irreversible or destroys data
        (failover that loses unreplicated writes, truncating a queue)
    (b) you cannot state the blast radius of the mitigation itself
        (that is a diagnosis problem, not a mitigation)
    (c) the mitigation IS the suspected cause's twin
        (rolling back a schema migration mid-flight)

WHY "HUMAN ERROR" TERMINATES THE INVESTIGATION

   "engineer ran the wrong command"   <- a STOP sign. Nothing to fix.
                                          Next incident is identical.
   "the capacity-removal tool accepted an argument that would take a
    subsystem below its minimum viable capacity, and gave no confirmation
    prompt showing how many hosts would be removed"
                                       <- a system defect. Fixable. Testable.
                                          This is the SAME event, written usefully.
```

## How it actually works

### The four roles, and the specific failure each one prevents

The role split is not bureaucracy, it is a fix for four distinct observed failures. Each role exists because a real incident went badly without it.

**Incident Commander.** Owns decisions and owns the state of the incident. Does not fix anything. PagerDuty's public docs state this flatly: the IC is the highest-ranking individual on the call regardless of day-to-day rank, and their decisions are final for the duration ([PagerDuty Incident Response: Incident Commander](https://response.pagerduty.com/training/incident_commander/) — accessed 2026-08-05). The failure this prevents is *parallel uncoordinated remediation*: three engineers restarting three things at once, so when it recovers nobody knows which change did it, and when it gets worse nobody knows which change caused that. The observable symptom that your IC has silently stopped commanding: the incident channel goes quiet for six minutes, and when it resumes it is a technical thread between two engineers with no status line. That silence is the IC having picked up a shell.

**Operations Lead.** The only person who executes changes on production, or explicitly delegates a named change to a named SME. The failure this prevents is the untracked change: a mitigation applied by someone who then leaves the call, which the postmortem cannot reconstruct and which is still in place three days later.

**Communications Lead.** Owns the external clock and shields the IC from status requests. This is the role that most engineering-heavy orgs cut first and should not: without it, the IC personally fields "any update?" from a VP every four minutes, and the observable symptom is a status page whose last update is 55 minutes old while the internal channel has 300 messages. At AWS in February 2017 the comms failure was structural rather than human: the Service Health Dashboard's admin console had a dependency on S3 in the affected region, so from the start of the event until 11:37 PST they could not update per-service status and fell back to posting on the `@AWSCloud` Twitter feed ([Summary of the Amazon S3 Service Disruption in US-EAST-1](https://aws.amazon.com/message/41926/) — accessed 2026-08-05). That is the single best argument for hosting your status page on infrastructure with zero shared dependencies with your product.

**Scribe.** Timestamps decisions in the channel, live. Not investigating, not checking graphs, not reading logs; PagerDuty's docs are explicit that those tasks get delegated to SMEs by the IC, not absorbed by the Scribe ([PagerDuty Incident Response: Scribe](https://response.pagerduty.com/training/scribe/) — accessed 2026-08-05). The failure this prevents is the unreconstructable timeline. Three days later, writing the postmortem, "we tried a rollback at some point" is worthless; "13:37 IC decided to prioritise config rollback over proxy restart; 14:24 rollback verified on canary" is the entire analytical value of the document. This is also the role LLM tooling is genuinely eating, and correctly so, because it is mechanical.

Scale *down*, never up. A Sev3 where one engineer wears all four hats is correct. The anti-pattern is the reverse: at Sev1 someone doubles up, and the role that silently gets dropped is always Scribe, because it is the only one with no immediate feedback if you stop doing it.

### Severity, and who is allowed to declare

Severity is not a measure of how alarming the graph looks. It is a routing decision: it determines who gets woken up, how fast comms go out, and whether you are allowed to break process (skip code review on the fix, roll back without approval). A workable definition set:

| Sev | Definition (user-visible, not internal) | Page | Comms |
|---|---|---|---|
| Sev1 | Core flow unavailable or wrong for a material share of users; or any confirmed data loss/corruption; or a confirmed security breach | Page IC + on-call + escalate to leadership immediately | Public status page within 15 min, updates every 30 min |
| Sev2 | Core flow degraded (elevated errors/latency past SLO burn threshold) but functioning; or a single large customer fully down | Page on-call; IC assigned | Status page if externally visible; internal updates every 60 min |
| Sev3 | Non-core feature broken, or degradation with a working user-visible workaround | Ticket during business hours | Internal only |
| Sev4 | Cosmetic, internal tooling, no user impact | Backlog | None |

Two rules matter more than the exact thresholds. First, **anyone can declare, and declaring is cheap while not declaring is expensive**. The single most common process failure in the industry is late declaration: an engineer spends 25 minutes trying to fix something alone because declaring feels like an admission of scale, and by the time they declare there are 25 minutes of untracked changes and no timeline. The correct policy is that declaring a Sev1 that turns out to be a Sev3 has zero career consequence, and it must be visibly true, not merely written down. Second, **severity is re-evaluated, not fixed at declaration**. It goes up when new impact is confirmed and down when impact is mitigated but not yet root-caused. Cloudflare on 18 November 2025 is a clean example of severity being *right* but the diagnosis being wrong for over an hour: the first automated test detected the issue at 11:31, manual investigation started at 11:32, the incident call was created at 11:35 (a fast declaration, roughly 7 minutes after impact started at 11:28), and yet from 11:32 to 13:05 the team was investigating the wrong thing, chasing elevated Workers KV errors as the cause when they were a downstream symptom ([Cloudflare outage on November 18, 2025](https://blog.cloudflare.com/18-november-2025-outage/) — accessed 2026-08-05).

### Mitigate before diagnose, and the three cases where that rule is wrong

The default is correct and most engineers get it backwards: your job during impact is to stop impact, not to understand it. Understanding is what the postmortem is for. Concretely, the mitigation menu, in preference order, is: roll back the most recent change, flip the feature flag off, fail over to the other region/replica, drain or shed load, scale up, restart. Notice that all six can be executed without knowing the cause, and four of them are reversible in under 60 seconds. A team whose first move is "let's look at the logs" is optimising for the wrong thing, and the observable cost is measured directly in impact-minutes.

The rule inverts in three cases, and being able to name them is the actual staff-level signal, because the default is a slogan and the exceptions are judgement:

1. **The mitigation is irreversible or data-destructive.** Failing over a primary database when replication lag is unknown may lose unreplicated writes permanently. GitHub's 21 October 2018 incident is the canonical case: a 43-second network partition during scheduled maintenance let the US East Coast primary accept writes that had not replicated to the West Coast, and the automated failover (Orchestrator) promoted West Coast. Once that happened, the East Coast writes could not simply be replayed, and the "fast" mitigation of failing back would have destroyed them. The result was 24 hours 11 minutes of degraded service, the overwhelming majority of it spent not fixing a broken system but *safely reconciling data*, deliberately choosing consistency over availability ([October 21 post-incident analysis](https://github.blog/news-insights/company-news/oct21-post-incident-analysis/) — accessed 2026-08-05). Note what the numbers say: the technical fault lasted 43 seconds, the incident lasted 24 hours. That ratio is the whole lesson.
2. **You cannot state the blast radius of the mitigation itself.** "Restart the fleet" is not a mitigation if you do not know whether the fleet comes back. Cloudflare hit this on 18 November 2025: the fix required not only replacing the bad feature file but forcing a restart of the core proxy, and services that had entered a bad state needed individually restarting afterwards, which is why main impact ended at 14:30 but full resolution was 17:06, two and a half hours later.
3. **The suspected cause is a stateful, in-flight operation.** Rolling back a schema migration halfway through is usually worse than letting it finish. Same for a partially-completed data backfill.

There is a fourth, softer case: if a rollback would destroy the evidence needed to prevent recurrence *and* impact is bounded and low, capture state first (heap dump, query log, a snapshot of the config that is live) and then mitigate. That should cost 90 seconds, not 20 minutes, and if someone proposes it during a Sev1 the IC should say no.

### Writing a status update under pressure

The status update is a mechanical artifact with a fixed shape, and getting it wrong is a leadership failure that engineers routinely make in both directions: they either say nothing for 45 minutes because they have nothing conclusive, or they publish a cause at minute 10 that turns out to be wrong and have to retract it.

The shape, four parts, in this order: **what users see, when it started, what we are doing, when we will next update.** Cause is optional and should be omitted until confirmed. A concrete first update at t=6 minutes:

```
[INVESTIGATING] Elevated error rates on the search API
Since 14:12 UTC, a portion of requests to /v1/search are returning HTTP 500.
Other endpoints are unaffected. We are investigating and have engineers engaged.
Next update by 14:45 UTC.
```

That contains no cause, no ETA to resolution, no speculation, and one hard promise: the next update time. The next-update commitment is the load-bearing element, because it is what stops the "any update?" traffic that otherwise consumes the IC. Two failure modes to name explicitly. Publishing a cause early: Cloudflare's team initially believed 18 November 2025 was a hyper-scale DDoS attack, partly because their status page (hosted entirely off Cloudflare infrastructure) coincidentally went down at the same time; had they published "we are under attack" at minute 10, they would have spent the recovery retracting it. And promising an ETA you cannot keep: "resolved within the hour" at minute 20 of an incident that runs six hours does more reputational damage than four hours of honest "still investigating, next update in 30 minutes."

The internal update is a different artifact from the external one and should be sent on the same cadence: current hypothesis (labelled as a hypothesis), what has been tried and ruled out, what each workstream is doing, and what the IC needs that they do not have.

### SLO-driven paging, error budgets, and why symptom alerts beat cause alerts

Page on symptoms, not causes. A cause alert ("CPU on host-7 is at 92%") fires whether or not users are affected, which produces exactly the two failures you cannot afford: pages at 03:00 for conditions that harm nobody, and no page at all for user-visible breakage whose cause you did not think to instrument. A symptom alert ("the fraction of `/v1/search` requests completing in under 400ms has dropped below the SLO burn threshold") fires if and only if users are affected, by any cause including ones you have never seen. Cause metrics belong on dashboards, for the person already looking; symptom metrics belong on the pager.

The production shape of this is multiwindow, multi-burn-rate alerting from the Google SRE Workbook. Error budget is `1 - SLO`: a 99.9% availability target over 30 days gives 0.1% of requests, or about 43.2 minutes of full unavailability, as budget. Burn rate is the multiple of nominal budget consumption: burn rate 1 exhausts the budget exactly at the end of the window, burn rate 14.4 exhausts it in 1/14.4 of the window. The Workbook's recommended configuration is three tiers ([Alerting on SLOs, Google SRE Workbook](https://sre.google/workbook/alerting-on-slos/) — accessed 2026-08-05):

| Tier | Long window | Short window | Burn rate | Budget consumed before firing | Action |
|---|---|---|---|---|---|
| 1 | 1 hour | 5 min | 14.4x | 2% | Page |
| 2 | 6 hours | 30 min | 6x | 5% | Page |
| 3 | 3 days | 6 hours | 1x | 10% | Ticket |

The short window exists to stop an alert staying lit after the burn has stopped: both windows must exceed the threshold for the alert to fire, so recovery clears it in minutes instead of hours. The tradeoff being made explicitly: a 14.4x burn-rate page catches a total outage in roughly 2 minutes but will not fire for a slow 0.2% error-rate elevation, which is exactly right, because that belongs in a ticket, not on a pager at 03:00.

The error budget's second job is political, not technical: it converts "are we shipping too fast?" from an argument into an arithmetic fact. Budget remaining means ship; budget exhausted means reliability work takes priority until it refills. The honest caveat is that this only works if an executive will actually honour the freeze, and in orgs where they will not, the error budget degrades into a dashboard that nobody enforces, which is worse than not having one because it provides the appearance of a control.

### Alert quality and pager fatigue, with numbers

The load target from the Google SRE book is a maximum of about **two paging events per 8-to-12-hour on-call shift**, averaged, and the reasoning given is operational rather than humanitarian: below that number the on-call engineer has time to handle the event accurately, restore service, clean up, and write the postmortem; above it, incidents stop being investigated properly and the team stops learning from them ([Google SRE Book: Being On-Call](https://sre.google/sre-book/being-on-call/) — accessed 2026-08-05). A team taking 15 pages a week is not a team with a busy pager, it is a team whose postmortems have quietly stopped happening.

The metric almost nobody tracks and everybody should is **actionability rate**: of pages fired in the last 30 days, what fraction resulted in a human taking a corrective action. If that number is under about 50%, the pager is training the on-call engineer to ignore it, and the failure mode is not that they miss a page in some abstract future; it is that the median ack time creeps from 2 minutes to 11 minutes and nobody notices until a real Sev1 sits unacknowledged. The standard remediations, in order of effect: delete alerts that have never once been actioned (measure first, then delete, and expect to remove 30-50% of a mature alert set), convert cause alerts to tickets, add hysteresis and `for:` durations to flapping alerts, and route by burn rate rather than raw threshold. Deleting alerts feels dangerous and is not, because an alert nobody acts on provides zero coverage while consuming the pager's credibility budget.

## Two real postmortems, dissected

Reading published postmortems is the cheapest available training for this skill, and quoting one accurately in an interview is a strong signal because it demonstrates you read incident writeups when you are not personally on fire. Two below, chosen because the interesting failures are process failures, not engineering ones.

### Cloudflare, 18 November 2025: 3h 10m of core impact, and 93 minutes spent on the wrong hypothesis

All times UTC, from the published timeline ([Cloudflare outage on November 18, 2025](https://blog.cloudflare.com/18-november-2025-outage/) — accessed 2026-08-05).

| Time | Event |
|---|---|
| 11:05 | ClickHouse database access-control change deployed. No impact yet. |
| 11:28 | Deployment reaches customer environments. First 5xx errors on customer HTTP traffic. |
| 11:31 | First automated test detects the issue. |
| 11:32 | Manual investigation starts. |
| 11:35 | Incident call created. |
| 11:32–13:05 | Team investigates elevated errors on Workers KV, attempts traffic manipulation and account limiting. Wrong hypothesis. |
| 13:05 | Workers KV and Access bypassed to a prior proxy version. Impact reduced, not resolved. |
| 13:37 | Focus shifts to rolling back the Bot Management config file. |
| 14:24 | New feature-file generation stopped; known-good file test complete. |
| 14:30 | Correct config deployed globally. Main impact resolved. |
| 17:06 | All downstream services restarted. Impact ends. |

The causal chain is a gift for anyone who has worked with ClickHouse. Cloudflare was rolling out explicit grants so that distributed subqueries would run under the initiating user rather than a shared system account. ClickHouse distributed tables live in a `default` database and the `Distributed` engine queries underlying shard-local tables in a database called `r0`. Users already had implicit access to `r0`; the change made that access *explicit*. Downstream, the Bot Management feature-file generator ran a query against `system.columns` that did not filter on database name, an assumption that had been silently true for years. After the grant change, that query started returning the `r0` columns as well, more than doubling the row count, so the generated feature file doubled in size. The bot module preallocates memory for a maximum of 200 features against a normal usage of about 60; the oversized file exceeded 200, and the Rust code hit an unhandled `Result`, producing `thread fl2_worker_thread panicked: called Result::unwrap() on an Err value` and a 5xx for every request that depended on the module.

What makes this worth studying is not the bug, it is the **saw-tooth**. The feature file regenerated every five minutes, and the ClickHouse cluster was being updated node by node, so for over an hour the query sometimes ran on an updated node (bad file) and sometimes on a not-yet-updated node (good file). The system therefore recovered and failed repeatedly. Three process consequences follow directly:

- **Intermittent recovery is a diagnostic trap that reads as an attack.** Cloudflare's team explicitly believed they might be under a hyper-scale DDoS, reinforced by their status page (hosted off Cloudflare with no Cloudflare dependencies) going down coincidentally at the same time. The lesson to state in an interview: when a system oscillates between healthy and broken on a fixed period, look for a periodic job, not an adversary. A five-minute oscillation is a five-minute cron.
- **The team chased a symptom for 93 minutes.** Workers KV errors were real and were downstream of the core proxy. Mitigating them at 13:05 reduced impact and did not resolve the incident. The generalisable move: when a mitigation reduces impact but does not eliminate it, that is evidence your hypothesis is downstream of the cause, and the IC should force a hypothesis reset rather than let the team keep tuning the same lever.
- **The failure was in a change that was correct.** The permissions change was a security improvement. Nothing about it was wrong. The defect was an unstated assumption in a *different* system, written years earlier, about what `system.columns` returns. That is what a contributing factor looks like, and it is why "who deployed the change" is a useless question here.

### GitHub, 21 October 2018: 43 seconds of network fault, 24 hours 11 minutes of incident

During planned maintenance replacing failing 100G optical equipment, connectivity between GitHub's US East Coast network hub and its primary US East Coast data centre dropped for 43 seconds. Orchestrator, the automated MySQL topology manager, detected the partition and promoted the US West Coast cluster. In those 43 seconds the East Coast primary had accepted writes that had not replicated to the West Coast. The result was two divergent write sets. GitHub deliberately chose data integrity over availability and ran degraded for 24 hours 11 minutes while reconciling, with webhooks undelivered and GitHub Pages builds stopped for most of the period ([October 21 post-incident analysis](https://github.blog/news-insights/company-news/oct21-post-incident-analysis/) — accessed 2026-08-05).

Four things to take from it:

- **Automation optimised for the local failure made the global failure worse.** Orchestrator did exactly what it was configured to do. The gap was that its failover logic was not constrained by physical topology, so a cross-continent promotion was as available a move as a same-datacentre one. Automation whose blast radius is not bounded by the same constraints a human would apply is a contributing factor in a large share of long incidents.
- **The recovery time was dominated by data reconciliation, not by fixing the fault.** The fault self-healed in 43 seconds. If you narrate this incident as "a network cable broke," you have said nothing. If you narrate it as "an automated failover created a split write set, and 24 hours of the incident was the cost of choosing correctness," you have described a decision.
- **The choice was made explicitly and communicated.** Serving stale-but-consistent data with degraded features, rather than serving fast and wrong, is a Sev1 judgement call with product implications. This is exactly the class of decision the "worst outage" interview question is fishing for.
- **Same lesson as AWS S3 in 2017:** a subsystem that "supports removal of significant capacity" in theory had not actually been fully restarted at that scale in years, so recovery took far longer than anyone modelled. GitHub had not exercised a cross-region promotion under real write load. Untested recovery paths are contributing factors that exist before the incident starts.

### The AWS S3 one-liner worth memorising

On 28 February 2017 at 09:37 PST an authorised S3 team member, following an established playbook to debug the billing system, executed a command to remove a small number of servers. One input was entered incorrectly and a larger set was removed, including capacity supporting the index subsystem (metadata and location for every object in the region) and the placement subsystem. Both required full restarts. GET/LIST/DELETE returned at 13:18 PST, PUT at 13:54 PST: roughly four hours ([Summary of the Amazon S3 Service Disruption in US-EAST-1](https://aws.amazon.com/message/41926/) — accessed 2026-08-05).

Read the remediation AWS published, because it is the model answer for "human error is not a root cause." They did not write "engineer will be more careful." They wrote that the tool allowed too much capacity to be removed too quickly, modified it to remove capacity more slowly, added a safeguard preventing removal below any subsystem's minimum required capacity, and audited every other operational tool for the same class of missing check. The finding is a property of the tool. It is testable, it generalises to tools nobody has typo'd yet, and it does not depend on anyone's future carefulness.

## The blameless postmortem: structure, and where people go wrong

The document has one purpose: produce a prioritised list of system changes that reduce the probability or the cost of recurrence. Everything in it that does not serve that purpose is ceremony. A working structure:

1. **Summary.** Three sentences a VP can read: what users experienced, for how long, and the one-line cause. Written last.
2. **Impact, quantified.** Not "some users affected." Requests failed, error rate peak, duration of each severity phase, revenue or SLA credit exposure, and the error budget consumed as a percentage. If you cannot quantify impact, your observability, not your writing, is the finding.
3. **Timeline.** Timestamped, timezone-labelled, including detection, declaration, every mitigation attempted (including the ones that failed), every comms update, and resolution. The failed attempts are the most valuable rows and the most commonly omitted.
4. **Detection.** How you found out, and how long it took. Split explicitly: time-to-detect, time-to-declare, time-to-mitigate, time-to-resolve. If a customer told you before your monitoring did, that is a finding by itself.
5. **Analysis: contributing factors.** Multiple, not one. See below.
6. **What went well.** Not morale filler. It identifies which existing controls actually worked, which protects them from being cut in the next cost review.
7. **Action items.** Owned, dated, prioritised, ticketed. See below.

**Blameless means the account you give carries no punitive consequence.** It does not mean nobody is accountable and it does not mean the writeup is vague about what happened. It exists for an unsentimental reason: the person who took the action that triggered the incident is the only person who knows what their screen looked like and what they believed at the time, and if giving that account is dangerous, you get a sanitised version, and your analysis is then built on corrupted data. State it that way in an interview. "Blame is bad because it makes the timeline unreliable" is a stronger answer than "blame is bad because it's demoralising," even though both are true.

### Root cause vs contributing factors

A root cause implies a single defect whose removal prevents the outcome. Real distributed-systems incidents rarely have one. Cloudflare 18 November 2025 had at least five contributing factors, each individually insufficient:

1. A query against `system.columns` written without a database-name filter, relying on an implicit behaviour.
2. A permissions change (correct in itself) that altered that implicit behaviour.
3. A gradual, node-by-node rollout that made the fault intermittent, delaying diagnosis.
4. A hard 200-feature preallocation limit with no graceful degradation path.
5. Rust error handling that propagated a failed `Result` into a panic instead of falling back to the last-known-good file.

Remove any one and the outage does not happen in that form. Number 5 is the one most worth acting on, because it converts an entire *class* of bad-config failures from a global outage into a stale-config degradation. This is the discipline: enumerate factors, then rank by *how many future incidents this fix prevents*, not by proximity to the trigger. The factor closest in time to the failure is almost never the most valuable one to fix.

Keep the word "root cause" in the template if your org requires it, and treat the field as "the factor we chose to prioritise." Fighting the vocabulary is a losing battle that costs you the actual argument.

### Why "human error" is never a root cause, and what to write instead

"Human error" is not an explanation, it is the point at which the investigation stopped. It has three specific defects. It is not actionable: there is no code change, test, or alert corresponding to "be more careful." It is counterfactual: "they should have noticed the alert" describes a world that did not exist, one where the alert was not the fortieth firing that hour or routed to a channel nobody reads. And it is predictive of nothing, because the next engineer with the same tool and the same information will make the same choice.

The replacement question, from Allspaw's critique of Five Whys, is not "why were they careless" but **"what made the wrong path look like the right path from where they stood?"** ([The Infinite Hows, John Allspaw](https://www.kitchensoap.com/2014/11/14/the-infinite-hows-or-the-dangers-of-the-five-whys/) — accessed 2026-08-05). Concrete rewrites:

| Do not write | Write instead |
|---|---|
| "Engineer ran the wrong command" | "The capacity-removal tool accepted a host count that would take a subsystem below its minimum viable capacity, with no confirmation step displaying the resulting count. Fix: enforce a floor, require confirmation above N hosts." |
| "The on-call missed the page" | "The page was one of 41 fired in that 8-hour shift, of which 4 were actionable. Fix: delete the 17 alerts with zero actions in 90 days, convert 12 cause-alerts to tickets." |
| "Reviewer approved a bad config" | "The config had no schema validation and no canary stage; review was the only gate. Fix: schema-validate at build time, canary to 1% of the fleet for 10 minutes before global propagation." |
| "Someone forgot to update the runbook" | "The runbook lives in a wiki with no ownership or review cadence and was last edited 14 months ago. Fix: assign an owner, and add a postmortem action item template step that checks the relevant runbook." |
| "Team didn't follow the process" | "The documented process required 6 steps under time pressure and the team skipped 2 in every recent incident. Fix: the process is wrong; reduce it to the 4 steps people actually perform." |

Every right-hand cell describes a property of a system and implies a specific change. That is the test: **if the finding cannot be falsified by a code change, it is not a finding.**

### Five Whys vs causal graphs

Five Whys is popular because it is teachable in 30 seconds, and its failure mode is structural rather than a matter of applying it badly. It walks *one* chain backwards, which forces a single-cause model onto a multi-factor event, and because each "why" narrows, it converges reliably on either a person or a platitude ("we didn't have enough tests"). Allspaw's critique, drawing on Dekker, Conklin and Leveson, is that this is not merely limited but actively dangerous, because it produces the confident feeling of having found *the* cause.

The alternative is a causal graph: draw the failure, then draw every condition that had to hold for it to occur, then repeat for each of those, and stop when you reach conditions you can change. You get a DAG, not a chain, and you rank the nodes by how many downstream paths a fix cuts. Applied to Cloudflare, the graph makes it immediately visible that fixing the unfiltered query prevents *this* outage and fixing the panic-on-bad-config prevents *every* outage of that shape.

The honest counter-argument, which you should state rather than pretending it does not exist: causal graphs cost more to produce, do not fit an executive summary, and for genuinely simple incidents (an expired certificate, an unrenewed domain) a chain is adequate and a graph is theatre. The pragmatic policy is chain for Sev3, graph for Sev1, and never let either method's output be a person's name.

### Action items that actually get done

The measurable failure of postmortem culture is not that postmortems are not written, it is that their action items are not completed. The failure modes are consistent and each has a mechanical fix:

- **Unowned.** "The platform team will add validation" has no owner. Every item needs a named individual, not a team.
- **Unticketed.** An action item that lives only in the postmortem document does not appear in any sprint and will not be done. It must exist as a ticket in the normal backlog, linked to the postmortem, with a priority that competes fairly with feature work.
- **Undated and unbounded.** "Improve monitoring" cannot be completed. "Add a burn-rate alert on the search SLO at 14.4x/1h, by 2026-09-01" can.
- **Too many.** A postmortem producing 14 action items will complete 3. Cap Sev1 postmortems at 5, ranked, and explicitly write "considered and not doing" for the rest with a one-line reason. That list is more honest than a backlog of items everyone knows are dead.
- **No recurrence check.** Track the fraction of incidents in the last 12 months whose contributing factors match a prior incident's. If that number is above about 20%, your action items are not landing, and no amount of postmortem-writing quality will fix it.

Split items into two classes and prioritise accordingly: those that reduce *probability* of recurrence (the validation, the test, the type change) and those that reduce *cost* of recurrence (the alert, the runbook, the kill switch, the canary). Cost-reduction items are usually cheaper, generalise to failures you have not imagined yet, and are systematically under-prioritised because they feel less like fixing the bug.

## On-call rotation design

- **Rotation size.** A sustainable primary rotation is 6-8 engineers. Below 5, the shift frequency (one week in four or worse) drives attrition; above 10, individuals are on call so rarely they lose familiarity with the tooling and the first 40 minutes of every incident is spent relearning it.
- **Primary and secondary.** Secondary exists to cover a missed ack and to be the escalation for the primary, not to be a second pair of hands by default. If the secondary is routinely engaged, the pager load is too high.
- **Shift length.** One week is standard; 12-hour follow-the-sun shifts are better for humans and require ~3 geographic regions and genuinely duplicated expertise in each. Follow-the-sun eliminates night pages entirely, which is its whole point, and it introduces a handoff at every boundary, which is where it fails: a follow-the-sun rotation with a bad handoff is worse than a single-region rotation, because an in-flight incident crossing a handoff with no state transfer restarts diagnosis from zero.
- **Handoff.** Write it down, do not just say it. A handoff note covering open incidents and their current hypothesis, anything degraded but not incident-worthy, alerts that fired and were dismissed with the reason, deploys in flight or frozen, and anything expected to fire in the next shift. 10 minutes synchronous, overlapping, not an async message posted at end of shift.
- **Compensation.** Practice varies widely and is worth knowing for negotiation: publicly reported US ranges cluster around $200-$500 per week for on-call stipends, with SaaS commonly $350-$600/week and financial services running higher, plus per-incident or night-call bonuses at some firms; some companies pay nothing and treat it as part of salary, and some offer time-in-lieu instead of cash ([Oncall Compensation for Software Engineers, The Pragmatic Engineer](https://blog.pragmaticengineer.com/oncall-compensation/) — accessed 2026-08-05). The second-order effect is the one to name in an interview: uncompensated on-call correlates with slower acks and weaker alert hygiene, because nobody has an incentive to reduce a load they are not paid for.
- **The rule that matters more than any of the above.** The team that owns the code carries the pager for it. Every model where a separate ops team is paged for someone else's service produces the same outcome: the people who can fix the alert quality are not the people suffering from it, so alert quality never improves.

## Practical exercise

Write a blameless postmortem for the ClickHouse OOM you actually fixed. Not a summary, the real document, in the structure below, in under 900 words. Time-box it to 45 minutes. The point is not to produce a nice artifact; it is that the *next* time an interviewer says "walk me through your worst incident," you will already have the timeline, the numbers, and the contributing-factor list in your head, and you will narrate decisions instead of debugging.

Constraint that makes it useful: **you may not use the words "human error," "should have," or "obviously" anywhere in the document**, and every action item must be falsifiable by a code, config, or alert change.

```markdown
# Postmortem: ClickHouse OOM, <date>

**Status:** final
**Authors:** <you>   **Reviewers:** <two names>
**Incident duration:** <detect → resolve>, HH:MM
**Severity:** Sev<n>

## Summary
<3 sentences. What users experienced, for how long, the prioritised cause.
Write this LAST.>

## Impact
- User-visible: <queries failed / p99 latency went from X ms to Y ms / N% of
  requests to <endpoint> returned 5xx>
- Duration by phase: detected HH:MM, declared HH:MM, mitigated HH:MM, resolved HH:MM
- Error budget consumed: <X%> of the 30-day budget for <SLO>
- Blast radius: <which downstream services, which customers, which regions>

## Timeline (all times <TZ>)
| Time | Actor | Event |
|---|---|---|
| | | alert fired / customer reported / you noticed |
| | | acknowledged |
| | | DECLARED, severity, IC named |
| | | first comms update sent, to whom |
| | | mitigation attempt 1 — INCLUDING THE ONES THAT DIDN'T WORK |
| | | hypothesis revised, and what evidence forced the revision |
| | | mitigation applied, impact stops |
| | | resolved |

## Detection
- Time to detect: <min>. How? (alert / dashboard / customer / a colleague)
- Would a symptom-based SLO burn alert have caught it sooner? By how long?
- If a human noticed before monitoring did, that is finding #1.

## Contributing factors
<At least 4. Each one a property of the system, not a property of a person.
For each: what it is, and what a fix would prevent.>
1. Memory limit configuration: <what `max_memory_usage` /
   `max_bytes_before_external_group_by` / `max_server_memory_usage` were set to,
   and why those values existed>
2. Query shape: <the aggregation / JOIN / ORDER BY that grew unboundedly,
   and what made its memory profile data-dependent>
3. Absence of a guard: <no per-query memory ceiling? no query complexity limit?
   no spill-to-disk configured? no quota per user?>
4. Observability: <what signal existed before OOM, and why nobody was paged on it —
   was there a memory-pressure metric at all, and was it a symptom or a cause alert?>
5. Blast radius: <why did one query take down the server / the node / the cluster,
   rather than failing just that query?>

## Analysis
<Which contributing factor did you prioritise and WHY. Rank by how many FUTURE
incidents the fix prevents, not by proximity to the trigger. Name the
counterfactual you are deliberately NOT writing.>

## What went well
<Which existing control actually worked. Be specific — this protects it from
being removed in the next cleanup.>

## Action items
| # | Action | Owner | Class | Ticket | Due |
|---|---|---|---|---|---|
| 1 | | | probability | | |
| 2 | | | cost | | |
<Max 5. "class" is probability-of-recurrence or cost-of-recurrence.
Then a "considered and not doing" list with one-line reasons.>

## Recurrence check
<Has a factor here appeared in a prior incident? If yes, why did that action
item not land?>
```

### Grading rubric

Score yourself out of 20. Below 14, rewrite before you use this story in an interview.

| # | Criterion | 0 | 1 | 2 |
|---|---|---|---|---|
| 1 | Impact quantified | "some queries failed" | duration only | requests, duration by phase, error budget %, downstream blast radius |
| 2 | Timeline includes failed attempts | only the successful fix | one dead end | every mitigation tried, with the evidence that killed each hypothesis |
| 3 | Detection split out | not mentioned | "we got alerted" | TTD/TTDeclare/TTM/TTR as four separate numbers, plus whether a symptom alert would have been faster |
| 4 | ≥4 contributing factors, all system properties | one root cause | 2-3 | 4+, none of which is a person, each implying a distinct fix |
| 5 | No counterfactuals or blame | "we should have set the limit" | one slip | zero instances of should-have / human error / obviously |
| 6 | Prioritisation is argued | items listed in discovery order | ranked, no reason | ranked by future incidents prevented, with the reasoning written down |
| 7 | Action items falsifiable | "improve monitoring" | some specific | every item names a config value, a code change, or an alert expression, with an owner and a date |
| 8 | Cost-of-recurrence items present | all probability-reduction | one | at least 2 items that make the *next* occurrence cheaper (memory ceiling per query, spill to disk, symptom alert, kill switch) |
| 9 | Decisions narrated, not just the fix | pure debugging story | some decisions | states what you chose not to investigate, and why, under the clock |
| 10 | Under 900 words | over 1500 | 900-1500 | under 900 and a VP could read the summary alone |

The two rows people lose points on are 5 and 9. Row 5 because "we should have had a memory limit" feels humble and is actually a counterfactual with no owner; the fixed version is "there was no per-query memory ceiling; `max_memory_usage` was unset, so a single aggregation could consume the server's whole heap. Setting it to N GB caps this class of failure to a single failed query." Row 9 because narrating the fix is the reflex, and the interview scores the decisions.

## How it's done in production

The tooling layer (PagerDuty, incident.io, Rootly, FireHydrant, Opsgenie, plus Slack-native workflows) adds four things worth naming, and none of them is the part that matters. It adds: a declared-incident object with a severity field and an automatically created channel and bridge; automatic timeline capture from Slack, deploy events and alert state, which is genuine Scribe-role automation; status-page integration so an incident state change publishes externally without a human copy-pasting; and postmortem templating with action items auto-created as tickets in the tracker, which is the single highest-leverage integration because it fixes the "unticketed item never gets done" failure mechanically. By 2025 all the major vendors also ship LLM-drafted incident summaries and timelines. Treat those as a strong first draft of sections 3 and 4 of the postmortem and never of section 5, for the same reason AI code review is trusted on imports and not on design fit: the causal analysis needs organisational context that exists in nobody's logs.

The part the tooling does not add is the part that decides how your incidents go: whether someone declares at minute 4, whether the IC keeps their hands off the keyboard, and whether the action items compete honestly with feature work.

### Failure modes of the incident *process* (not of the system)

| Symptom | Cause | Fix |
|---|---|---|
| 25 minutes of activity in a channel with no severity, no IC, and no comms update; postmortem timeline starts at the point someone finally declared | Late declaration. Declaring felt like admitting scale, or the org has punished over-declaration before | Make declaring explicitly free: anyone can declare, a Sev1 that downgrades to Sev3 is a *good* outcome, and say so in the retro out loud. Add an automatic prompt when an alert stays unacked or unresolved past 10 minutes |
| Channel goes quiet for 6+ minutes, then resumes as a deep technical thread with no status line | The IC picked up a shell and stopped commanding | IC hands the keyboard to the Ops Lead, or explicitly hands off IC to someone else and announces it. Never both roles at once above Sev2 |
| Two engineers roll back different things within 60 seconds; nobody can tell which change recovered the service | No Ops Lead; parallel uncoordinated remediation | All production changes go through one named person who announces each change before it is applied and after it completes |
| Status page last updated 55 minutes ago while the internal channel has 300 messages | No Comms Lead, or the Comms Lead is also debugging | Separate the role at Sev1/Sev2 and give it a hard cadence with a next-update-by promise in every post |
| Status page itself is down during the outage | Status page shares infrastructure or a control-plane dependency with the product (AWS SHD depended on S3 in-region in 2017) | Host the status page on a different provider with zero shared dependencies, and test it during a game day by blocking your own network |
| Postmortem timeline cannot be reconstructed; "we tried a few things" | Scribe role dropped, which is what always happens when someone doubles up at Sev1 | Assign the Scribe explicitly and separately at Sev1. Automate the mechanical capture (deploys, alerts, Slack) so the human only records *decisions* |
| Mitigation reduces error rate but does not resolve; team keeps tuning the same lever for another hour | The hypothesis is downstream of the cause and nobody forced a reset (Cloudflare 11:32-13:05) | IC rule: a mitigation that reduces but does not eliminate impact is evidence against the current hypothesis. Force an explicit "what else could produce this?" round |
| System oscillates between healthy and broken on a fixed period; team suspects an attack | A periodic job is regenerating bad state (Cloudflare's 5-minute feature-file cycle during a rolling cluster update) | Match the oscillation period against cron/scheduler intervals before reaching for the adversary hypothesis |
| Postmortem root cause reads "engineer ran the wrong command" | Five Whys walked one chain and terminated on a person | Rewrite as a property of the tool: what did it accept, what did it not display, what floor did it not enforce. Compare against AWS's 2017 remediation as the model |
| 14 action items, 11 still open a year later, and the same failure recurs | Items unowned, unticketed, undated, and not competing with feature work | Cap at 5, ranked; each has a named individual, a ticket in the normal backlog, and a date. Explicitly write "considered and not doing" for the rest |
| On-call median ack time drifts from 2 min to 11 min over two quarters | Pager fatigue. Alert volume past ~2 events/shift and actionability under 50% | Measure actionability rate over 90 days, delete zero-action alerts (expect to remove 30-50%), convert cause alerts to tickets, move paging to SLO burn rate |
| Incident crosses a follow-the-sun handoff and diagnosis restarts from zero | Handoff is an async end-of-shift message with no in-flight incident state | 10-minute overlapping synchronous handoff with a written note: open incidents + current hypothesis, degraded-but-not-incident items, alerts dismissed and why, deploys in flight |
| Error budget exhausted, feature work continues unchanged, nobody mentions it | No error-budget policy with executive commitment; the budget is a dashboard | Either get a written policy that a freeze is honoured, or stop calling it an error budget. A budget nobody enforces is worse than none, because it looks like a control |

## Tradeoffs & when NOT to use it

- **Do not run full incident command for a Sev3.** Naming an IC, a Comms Lead, a Scribe and an Ops Lead for a broken internal dashboard costs four people's afternoon and produces nothing. The structure scales down to one person wearing all four hats, and that is the correct configuration for most incidents. The anti-pattern is a process so heavy that people avoid declaring, which produces exactly the late-declaration failure the process exists to prevent.
- **Do not mitigate before diagnosing when the mitigation is irreversible.** Failing over a primary with unknown replication lag, truncating a queue, or rolling back a half-applied migration can convert a 20-minute availability incident into a permanent data-loss incident. GitHub's 2018 incident is the instance: 43 seconds of fault, 24 hours 11 minutes of deliberate, correct, slow reconciliation. If you cannot state the mitigation's blast radius, you are not mitigating, you are gambling.
- **Blameless does not mean consequence-free in every domain.** In a security incident with a possible insider component, in a regulated environment with a legal duty to report, or in a case of deliberate policy circumvention, the blameless postmortem is the wrong instrument and the honest move is to say so rather than pretend. The workable split most orgs land on: the technical postmortem stays blameless and is the artifact used for system learning; any accountability process runs separately, is not fed by the postmortem, and everyone is told that up front. Pretending there is no separate track when there is destroys the trust the whole practice depends on.
- **Do not run a causal-graph analysis on a trivial incident.** An expired TLS certificate does not need a DAG. A chain is adequate, and producing a graph anyway is theatre that trains people to see postmortems as busywork. Reserve the heavier method for Sev1 and for any incident whose factors overlap a previous one.
- **Do not adopt SLO-driven paging without an SLO you can defend.** A burn-rate alert on a badly chosen SLI is worse than a threshold alert, because it carries the authority of a formal system while measuring the wrong thing. If you cannot state what fraction of user-visible requests the SLI covers and what a user notices when it degrades, fix that first. This matters more for AI systems than for CRUD services: "the model is up and answering, and answers got 8% worse on the eval set" fits no availability SLI, and pretending it does is how quality regressions run for weeks unpaged.
- **Do not use follow-the-sun with fewer than three regions of genuinely duplicated expertise.** Two regions produces uncovered hours and a handoff; three produces real 24/7 coverage with no night pages. A follow-the-sun rotation where one region has to escalate to another region's expert at 03:00 has all the handoff costs and none of the sleep benefits.
- **Do not let postmortem quality become the metric.** Well-written postmortems with uncompleted action items are a more expensive way of having the same outage twice. The number that tells you whether the practice works is the fraction of incidents in the last 12 months whose contributing factors recur from an earlier one, and if that is above about 20%, invest in action-item completion rather than in better writing.

---

## Interview questions

### Q1 — Tell me about the worst production outage you've been involved in.
**Testing:** whether you narrate decisions or debugging. This is the filter. Most candidates fail it by giving a competent debugging story, which caps them at senior.
**Answer:** Structure it as: impact first (what users saw, how long, how many), then the decision points, then the fix, then what changed afterwards. For the ClickHouse OOM: "A memory-unbounded aggregation OOM'd the node serving vector search. Impact was X% of search requests failing for HH:MM. I declared at minute N because the error rate crossed the SLO burn threshold rather than because I understood the cause. I chose to restart and cap `max_memory_usage` before diagnosing the query, because the mitigation was reversible and the diagnosis wasn't going to be fast. I explicitly did not chase the query shape until impact stopped. What changed permanently was a per-query memory ceiling and spill-to-disk, which converts this class of failure from a node-down into a single failed query." Give the number for every claim. Impact-minutes, not adjectives.
**Follow-up trap:** *"What would you have done differently?"* The trap is answering with a counterfactual about yourself ("I should have noticed sooner"), which sounds humble and signals that you still think in terms of individual carefulness. Answer with a system change instead: "Nothing about my actions given what I knew at 03:12. The system change is that there was no symptom-based alert on query memory pressure, so detection depended on a human noticing an error-rate graph. A burn-rate alert would have cut time-to-detect from N minutes to about 2."

### Q2 — Why does the Incident Commander not debug?
**Testing:** whether you understand the role split as a fix for a specific observed failure, or as generic process.
**Answer:** Because coordination and diagnosis both consume full attention and the coordinator's failure is silent. The IC tracks who is doing what, what has been ruled out, when the next comms update is due, and whether the mitigation is safe. The moment they open a terminal, all of that halts and nobody notices for 20 minutes; the observable symptom is the incident channel going quiet and then resuming as a technical thread with no status line. PagerDuty's public docs state the IC is the highest-ranking person on the incident regardless of their day-to-day rank, precisely so the most senior engineer, who is usually also the best debugger, is either commanding or debugging and never both.
**Follow-up trap:** *"You're the only person on the call who understands this system. Now what?"* Do not answer "then I do both." Hand IC to someone less technical who can run a call (a manager, a TPM, another on-call engineer) and become the Ops Lead yourself, announcing the handoff explicitly in the channel. The IC role needs coordination skill, not domain expertise; that is the whole reason the split works.

### Q3 — Walk me through mitigate-before-diagnose. When is it wrong?
**Testing:** the default is a slogan everyone knows; the exceptions are the staff-level signal.
**Answer:** Default: your job during impact is to stop impact, and the menu (roll back, flag off, fail over, shed load, scale, restart) can all be executed without knowing the cause, most of them reversibly in under 60 seconds. It is wrong in three cases. One, the mitigation is irreversible or data-destructive: failing over a primary with unknown replication lag can permanently lose unreplicated writes. Two, you cannot state the mitigation's own blast radius, which means you have a diagnosis problem disguised as a mitigation. Three, the suspect is a stateful in-flight operation, like a half-applied schema migration, where stopping it is worse than finishing it.
**Follow-up trap:** *"Your mitigation would destroy the only evidence of the cause. Do you still apply it?"* Yes, if impact is ongoing and material, and you spend at most 90 seconds capturing state first (heap dump, the live config, the query log). The trap is the candidate who trades impact-minutes for forensic completeness. Say the tradeoff out loud: an unexplained but stopped outage is a strictly better position than an ongoing one you understand.

### Q4 — What's the difference between a symptom alert and a cause alert, and which pages?
**Testing:** whether alerting philosophy is understood mechanically.
**Answer:** A cause alert fires on an internal condition ("CPU on host-7 at 92%," "replication lag 40s") and produces both false positives (fires when nobody is harmed) and false negatives (misses user-visible breakage whose cause you never instrumented). A symptom alert fires on user-visible degradation ("the fraction of `/v1/search` requests under 400ms dropped below the SLO burn threshold") and therefore catches causes you have never seen. Symptoms page; causes go on dashboards for whoever is already looking, or become tickets.
**Follow-up trap:** *"Then how do you catch a disk filling up before it causes user impact?"* That is the legitimate exception: slow, predictable, saturating resources with a known time-to-failure. Alert on the *projection*, not the level ("this volume reaches 100% in under 4 hours at the current rate"), and route it to a ticket during business hours rather than the pager, unless the projected time-to-failure is shorter than the next business day. The general rule holds: page on symptoms; the exception is bounded to predictable saturation with lead time.

### Q5 — Explain error budgets and multiwindow multi-burn-rate alerting.
**Testing:** whether you can do the arithmetic, not just recite the vocabulary.
**Answer:** Error budget is `1 - SLO` over a window. 99.9% over 30 days is 0.1% of requests, about 43.2 minutes of full unavailability. Burn rate is the multiple of nominal consumption: at burn rate 1 you exhaust the budget exactly at the window's end; at 14.4 you exhaust it in 1/14.4 of it. The Google SRE Workbook's recommended tiers are 14.4x over 1 hour (2% of budget consumed, page), 6x over 6 hours (5%, page), and 1x over 3 days (10%, ticket), each paired with a short window (5 min, 30 min, 6 hours) that must also be over threshold. The short window's job is to clear the alert quickly once burning stops, so a recovered incident doesn't leave a page lit for hours.
**Follow-up trap:** *"Your error budget is exhausted and the VP wants the feature shipped anyway. What do you do?"* Do not say "I enforce the freeze," which signals you have never had this conversation. The budget is a decision-support tool, not a veto: present the cost concretely ("shipping this consumes budget we don't have, which means the next incident this quarter breaches our customer SLA and costs $N in credits"), let the accountable person make the call, and write down what was decided. Then say the real point: an error budget nobody will ever honour is worse than not having one, because it provides the appearance of a control, and if that is the situation you should escalate the *policy*, not each individual ship decision.

### Q6 — What does "blameless" actually mean, and where does it break down?
**Testing:** whether you can defend it on epistemic grounds rather than emotional ones, and whether you know its limits.
**Answer:** Blameless means the account you give during the postmortem carries no punitive consequence. The reason is not kindness, it is data quality: the person who took the triggering action is the only one who knows what their screen showed and what they believed at the time, and if that account is dangerous to give, you get a sanitised timeline and every conclusion downstream is built on it. It breaks down in three places: security incidents with a possible insider component, regulated environments with legal reporting duties, and deliberate policy circumvention as opposed to a mistake. The workable arrangement is that the technical postmortem stays blameless and is used for system learning, any accountability process runs entirely separately and is not fed by the postmortem, and everyone is told this up front.
**Follow-up trap:** *"Isn't that just protecting people from consequences?"* No, and the distinction is precise: accountability attaches to the role and the follow-through (did the owner complete the action items, did they escalate a known risk), not to the account of what happened. Then invert the question: an org that punishes the account gets fewer reported near-misses, which is the leading indicator that goes dark first, and you find out you had none only when the actual outage arrives.

### Q7 — Why is "human error" not a root cause? What do you write instead?
**Testing:** the single most-quoted principle in this space, and whether you can execute it rather than recite it.
**Answer:** Because it terminates the investigation at the point it should start. It has three concrete defects: it is not actionable (no code change corresponds to "be more careful"), it is counterfactual (it describes a world where the alert wasn't the fortieth that hour), and it predicts nothing, since the next person with the same tool and information makes the same choice. The replacement question is "what made the wrong path look like the right path from where they stood?" The model example is AWS's February 2017 S3 writeup: an authorised engineer following an established playbook mistyped an input and removed more capacity than intended, taking down the index and placement subsystems for about four hours. AWS did not write "engineer will be more careful." They wrote that the tool allowed too much capacity to be removed too quickly, then added a floor preventing removal below a subsystem's minimum required capacity, and audited every other operational tool for the same missing check.
**Follow-up trap:** *"What if the same engineer causes three incidents in six months?"* That is a real management question and refusing to engage with it looks naive. Answer: it is still not a postmortem finding. Three incidents from one person is a signal about onboarding, about which tasks that person is being given, about whether they are the only one holding a dangerous system, or about capability, and every one of those is a manager's conversation held outside the postmortem. Putting it in the document buys nothing and costs you every future honest timeline.

### Q8 — Critique the Five Whys.
**Testing:** whether you have thought about analysis methodology rather than adopting the first one you were taught.
**Answer:** Two structural problems, not usage problems. It walks a single chain backwards, which forces a single-cause model onto multi-factor events, and because each step narrows it converges reliably on either a person or a platitude. Allspaw's 2014 critique, drawing on Dekker, Conklin and Leveson, is that the danger isn't that it's limited but that it produces the confident sensation of having found *the* cause. The alternative is a causal graph: draw the failure, draw every condition that had to hold, recurse, stop at conditions you can change, then rank nodes by how many downstream paths a fix cuts. On Cloudflare's November 2025 outage the graph makes it obvious that fixing the unfiltered `system.columns` query prevents that outage while fixing the panic-on-oversized-config prevents every outage of that shape.
**Follow-up trap:** *"So should we stop using Five Whys?"* Do not say yes. Chain for a Sev3 (an expired certificate genuinely has one cause and a DAG is theatre), graph for a Sev1 or for any incident whose factors overlap a prior one. And keep the word "root cause" in the template if your tooling or your regulator demands the field, treating it as "the factor we chose to prioritise"; fighting the vocabulary loses you the argument you actually care about, which is that the list should have more than one item.

### Q9 — How do you decide severity, and who's allowed to declare?
**Testing:** whether severity is understood as a routing decision rather than a measure of alarm.
**Answer:** Severity determines who gets woken, how fast comms go out, and what process you're allowed to skip. Define it by user-visible impact, not internal state: Sev1 is core flow unavailable or wrong for a material share of users, or confirmed data loss, or a confirmed breach. Sev2 is core flow degraded past the SLO burn threshold, or one large customer fully down. Sev3 has a working workaround. Anyone can declare, declaring is cheap, and a Sev1 that downgrades to Sev3 must have literally zero career consequence and be visibly seen to have none. Severity is re-evaluated continuously, up on confirmed impact and down on mitigation.
**Follow-up trap:** *"Someone on your team keeps declaring Sev1 for things that turn out to be Sev3. How do you handle it?"* The trap is answering with a correction that reintroduces the fear of declaring. Do not tell them to stop. Look at what they're seeing: if the same signal repeatedly looks like a Sev1 and isn't, your severity definitions are ambiguous or your dashboards make small impact look large, and both are system fixes. Over-declaration costs an hour of a few people's time; under-declaration cost GitHub 43 seconds of fault and 24 hours of incident, and the asymmetry is not close.

### Q10 — Write the first status update, at minute 6, when you have no idea what's wrong.
**Testing:** comms under pressure. Frequently asked as a live exercise, and engineers usually fail it by either saying nothing or speculating.
**Answer:** Four parts, in order: what users see, when it started, what we're doing, when we'll next update. No cause, no ETA to resolution, no speculation. "Since 14:12 UTC, a portion of requests to /v1/search are returning HTTP 500. Other endpoints are unaffected. We are investigating and have engineers engaged. Next update by 14:45 UTC." The next-update commitment is the load-bearing part: it's what stops the "any update?" traffic that otherwise consumes the IC's attention.
**Follow-up trap:** *"The VP is convinced it's the vendor and wants that in the update. Do you put it in?"* No, and say why concretely rather than on principle: Cloudflare's team on 18 November 2025 genuinely believed they were under a hyper-scale DDoS for the first stretch, reinforced by their independently-hosted status page going down coincidentally. Publishing an unconfirmed cause means spending the recovery retracting it, and a retraction costs more credibility than an hour of honest "still investigating." Offer the compromise: name the cause internally as a labelled hypothesis, keep it out of the external update until confirmed.

### Q11 — Your on-call is burning out. Diagnose it with numbers.
**Testing:** whether you measure pager health or just sympathise with it.
**Answer:** Two numbers. Pager load: paging events per shift, against Google's stated target of at most about two per 8-to-12-hour shift, and the reason for that number is operational rather than humane, because above it the on-call has no time to investigate properly or write the postmortem, so the team stops learning. And actionability rate: of pages in the last 90 days, what fraction produced a corrective human action. Under about 50% and the pager is training people to ignore it; the observable symptom is median ack drifting from ~2 minutes to ~11 over a couple of quarters. Remediation in order: delete alerts with zero actions in 90 days (expect to remove 30-50% of a mature set), convert cause alerts to tickets, add `for:` durations to flapping alerts, move paging to SLO burn rate.
**Follow-up trap:** *"Isn't deleting alerts just reducing coverage?"* No, and the reason is precise: an alert nobody has ever acted on provides zero coverage already, while spending the pager's credibility, which is a shared and finite resource. The thing being deleted is noise that degrades response to the alerts that do matter. Measure first, delete second, and keep the deleted expressions in version control so re-adding one is a one-line revert if a gap shows up.

### Q12 — Design an on-call rotation for a 12-person team owning 4 services across two time zones.
**Testing:** concrete rotation design, not principles.
**Answer:** One primary rotation of 6-8, not 12: below 5 the shift frequency drives attrition, above 10 people lose tooling familiarity and spend the first 40 minutes of every incident relearning it. So run two rotations aligned to service ownership rather than one 12-person rotation. Primary plus secondary, where secondary covers missed acks and escalation only, not routine second-pair-of-hands, since routine secondary engagement means pager load is too high. One-week shifts, handoff as a 10-minute overlapping synchronous call with a written note (open incidents and current hypothesis, degraded-but-not-incident items, alerts dismissed and why, deploys in flight or frozen). The team that owns the code carries its pager, always: any model where a separate ops team is paged for someone else's service means the people who could fix alert quality aren't the ones suffering from it.
**Follow-up trap:** *"Two time zones. Why not follow-the-sun and eliminate night pages entirely?"* Because two regions isn't enough. Follow-the-sun needs roughly three regions with genuinely duplicated expertise; with two you get uncovered hours plus a handoff, which is all of the handoff cost and none of the sleep benefit. And name the failure mode: a follow-the-sun rotation with a weak handoff is worse than single-region, because an in-flight incident crossing a boundary with no state transfer restarts diagnosis from zero.

### Q13 — Principal level: your org writes excellent postmortems and keeps having the same outages. Where's the failure?
**Testing:** whether you measure the practice by its output or by its artifact.
**Answer:** Action-item completion, not postmortem quality. The measurable failure is the fraction of incidents in the last 12 months whose contributing factors match an earlier one; above about 20% the writing isn't the problem. The mechanical causes are consistent: items owned by a team rather than a person, items living only in the postmortem document and never entering the backlog where they'd compete with feature work, items phrased so they can't be completed ("improve monitoring"), and too many of them, because a postmortem with 14 items completes about 3. Fix: cap Sev1 postmortems at 5 ranked items, each with a named individual, a real ticket, and a date, plus an explicit "considered and not doing" list with one-line reasons, which is more honest than a backlog everyone knows is dead.
**Follow-up trap:** *"Which action items would you cut first when you cap at 5?"* Not the cheap ones. Split by class: probability-of-recurrence items (the validation, the test, the type change) versus cost-of-recurrence items (the alert, the runbook, the kill switch, the canary, the graceful-degradation path). Cost-reduction items are systematically under-prioritised because they feel less like fixing the bug, and they're usually cheaper and generalise to failures nobody has imagined yet. Cloudflare's most valuable single fix wasn't the query filter, it was making the bot module fall back to last-known-good instead of panicking, because that one converts an entire class of bad-config events from a global outage into a stale-config degradation.

### Q14 — Principal level: how does incident response change for an AI system where the model is up and answering, but answering worse?
**Testing:** whether you can reason about incidents in a domain where the settled playbook doesn't apply. Increasingly asked for AI-platform roles.
**Answer:** Say plainly that this is an open problem rather than pretending the standard playbook covers it. Availability SLIs don't fire: the service is up, latency is normal, error rate is zero, and quality dropped 8% on the eval set. Three practical moves. Define a quality SLI that can actually be paged on (a continuously-scored canary eval set, or a proxy like abstention rate, retrieval-hit rate, or a downstream user-behaviour signal such as regeneration rate), accepting it will be noisier than an availability SLI. Second, severity has to include a "silently wrong" class, because wrong-and-confident output can be worse than an error page and there's no HTTP status for it. Third, mitigation is different: rollback means pinning the previous model or prompt or index version, which requires those to be versioned and independently pinnable in the first place, and if they aren't, that's the finding before any incident happens.
**Follow-up trap:** *"How do you set a burn-rate threshold on a metric that's this noisy?"* Don't page on a single eval score. Use the same multiwindow structure but require both a short and a long window to breach, so run-to-run variance can't fire a page, and set the threshold from measured baseline variance rather than a round number. Then admit the cost: this means detection latency is hours, not minutes, and the honest mitigation for that is stronger pre-deploy gating (eval gates on the release, canary at 1% of traffic) rather than pretending you can page in 2 minutes on a signal with that much noise.

---

## Red flags that fail you

- Narrating the debugging instead of the decisions when asked about your worst outage. This is the single most common way the question is failed.
- No numbers. "It was down for a while and a lot of users were affected" instead of impact-minutes, error rate, percentage of requests, and error budget consumed.
- Writing or saying "human error," "should have," or "someone forgot" as a cause.
- Describing yourself as the IC while also describing the debugging you personally did during the same incident.
- Treating mitigate-before-diagnose as an absolute with no exceptions, or not being able to name the irreversible-mitigation case.
- "We do blameless postmortems" with no ability to explain why blamelessness improves the *data* rather than just morale.
- Claiming you'd enforce an error-budget freeze over a VP's objection, which signals the conversation has never actually happened to you.
- Answering "what would you have done differently" with a counterfactual about your own attentiveness rather than a system change.
- No mention of comms at all in an outage story. A staff-level incident story that never mentions what customers were told is incomplete.
- Postmortem action items phrased as "improve monitoring" or "be more careful with deploys," with no owner, ticket, or date.
- Not knowing your own pager load or actionability rate when describing an on-call rotation you own.
- Presenting a single root cause for a complex distributed-systems failure with total confidence.

## Cheat card

```
IC does NOT touch a terminal. Ever. Roles: IC / Ops Lead / Comms Lead / Scribe.
  Scale DOWN (one person, all 4 hats at Sev3). Never double up at Sev1 --
  the role that silently drops is always Scribe.

DECLARE EARLY. Declaring is cheap; late declaration is the #1 process failure.
  Sev1 that downgrades to Sev3 = good outcome, and must cost nothing.

MITIGATE > DIAGNOSE. Menu: roll back / flag off / fail over / shed / scale / restart.
  INVERTS when: (a) mitigation is irreversible or destroys data
                (b) you can't state the mitigation's own blast radius
                (c) suspect is a stateful in-flight op (half-applied migration)

STATUS UPDATE, 4 parts: what users see / when it started / what we're doing /
  NEXT UPDATE BY <time>. No cause until confirmed. No ETA you can't keep.

PAGE ON SYMPTOMS, NOT CAUSES. Causes -> dashboards/tickets.
  Exception: predictable saturation -> alert on the PROJECTION, route to ticket.

ERROR BUDGET = 1 - SLO. 99.9%/30d = 43.2 min. Burn rate N = exhaust in 1/N of window.
  SRE Workbook tiers: 14.4x/1h (2% budget) PAGE | 6x/6h (5%) PAGE | 1x/3d (10%) TICKET
  Each paired w/ short window (5m / 30m / 6h): both must breach -> clears fast.

PAGER HEALTH: <= ~2 paging events per 8-12h shift (Google SRE).
  Actionability rate < 50% -> pager is training people to ignore it.
  Symptom: median ack drifts 2 min -> 11 min. Delete zero-action alerts (30-50%).

"HUMAN ERROR" IS NEVER A CAUSE. Ask: what made the wrong path look right
  from where they stood, with what they knew, at 03:12?
  Model answer = AWS S3 2017: fixed the TOOL (capacity floor + confirmation),
  not the person.

FIVE WHYS: one chain, converges on a person or a platitude (Allspaw 2014).
  Causal GRAPH for Sev1: rank nodes by how many downstream paths a fix cuts.
  Chain is fine for Sev3. Keep "root cause" field = "the factor we prioritised."

ACTION ITEMS: max 5, ranked. Named individual (not a team) + real ticket + date.
  Classes: probability-of-recurrence vs COST-of-recurrence (alert, runbook,
  kill switch, canary, graceful degradation). Cost items are under-prioritised
  and generalise further. Metric: % of incidents recurring from a prior factor;
  >20% means action items aren't landing.

ON-CALL: primary rotation 6-8 (not 12). Team that owns the code carries the pager.
  Handoff = 10 min SYNCHRONOUS overlap + written note (open incidents + hypothesis,
  degraded-not-incident, alerts dismissed & why, deploys in flight).
  Follow-the-sun needs ~3 regions w/ duplicated expertise. 2 regions = worst of both.
  US stipends commonly $200-500/wk; SaaS $350-600/wk.

REAL NUMBERS TO QUOTE:
  Cloudflare 18 Nov 2025: 11:05 ClickHouse grant change -> 11:28 impact ->
    11:35 incident call -> 93 min on the WRONG hypothesis (Workers KV) ->
    14:30 main impact resolved -> 17:06 all clear. ~60 features normal,
    hard limit 200, file doubled, Rust unwrap() panic. 5-min regen = saw-tooth.
  GitHub 21 Oct 2018: 43 SECONDS of network partition -> 24h 11m incident.
    Orchestrator promoted West Coast; split write set; chose consistency.
  AWS S3 28 Feb 2017: 09:37 PST mistyped input -> index+placement subsystems
    restarted -> GET/LIST/DELETE back 13:18, PUT 13:54 (~4h).
    Status dashboard depended on in-region S3; couldn't update until 11:37.
```

## Sources

- [Cloudflare outage on November 18, 2025 — Matthew Prince, Cloudflare Blog](https://blog.cloudflare.com/18-november-2025-outage/) — accessed 2026-08-05
- [Summary of the Amazon S3 Service Disruption in the Northern Virginia (US-EAST-1) Region — AWS](https://aws.amazon.com/message/41926/) — accessed 2026-08-05
- [October 21 post-incident analysis — GitHub Blog](https://github.blog/news-insights/company-news/oct21-post-incident-analysis/) — accessed 2026-08-05
- [Details of the Cloudflare outage on July 2, 2019 — Cloudflare Blog](https://blog.cloudflare.com/details-of-the-cloudflare-outage-on-july-2-2019/) — accessed 2026-08-05
- [Managing Incidents — Google SRE Book, ch. 14](https://sre.google/sre-book/managing-incidents/) — accessed 2026-08-05
- [Postmortem Culture: Learning from Failure — Google SRE Book, ch. 15](https://sre.google/sre-book/postmortem-culture/) — accessed 2026-08-05
- [Being On-Call — Google SRE Book, ch. 11](https://sre.google/sre-book/being-on-call/) — accessed 2026-08-05
- [Alerting on SLOs — Google SRE Workbook, ch. 5](https://sre.google/workbook/alerting-on-slos/) — accessed 2026-08-05
- [Incident Response — Google SRE Workbook, ch. 9](https://sre.google/workbook/incident-response/) — accessed 2026-08-05
- [PagerDuty Incident Response Documentation: Different Roles](https://response.pagerduty.com/before/different_roles/) — accessed 2026-08-05
- [PagerDuty Incident Response Documentation: Incident Commander](https://response.pagerduty.com/training/incident_commander/) — accessed 2026-08-05
- [PagerDuty Incident Response Documentation: Scribe](https://response.pagerduty.com/training/scribe/) — accessed 2026-08-05
- [The Infinite Hows (or, the Dangers Of The Five Whys) — John Allspaw, 2014](https://www.kitchensoap.com/2014/11/14/the-infinite-hows-or-the-dangers-of-the-five-whys/) — accessed 2026-08-05
- [The infinite hows — John Allspaw, O'Reilly Radar](https://www.oreilly.com/radar/the-infinite-hows/) — accessed 2026-08-05
- [Oncall Compensation for Software Engineers — The Pragmatic Engineer](https://blog.pragmaticengineer.com/oncall-compensation/) — accessed 2026-08-05
- [On-call best practices: handoffs, schedules, and alert fatigue — incident.io](https://incident.io/blog/on-call-best-practices-guide-2026) — accessed 2026-08-05
- `T13-code-review` — blast radius and hidden coupling as review categories, which are the same failure classes that show up as contributing factors here (this repo)
- `T21-resilience-catalogue` — the mitigation primitives referenced above (circuit breaker, bulkhead, load shedding, graceful degradation) in mechanical detail (this repo)

## Changelog
- 2026-08-05 — created
