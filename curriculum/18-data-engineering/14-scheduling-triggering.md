# Scheduling & Auto-Triggering: Cron vs Event vs Sensor, EventBridge, Step Functions, S3 Events

> **Track:** T18 Data Engineering & Warehousing · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T18-scheduling-triggering` · **Tags:** orchestration, critical

## The 30-second version

What starts a pipeline run is a distinct design decision from what the run does, and there are exactly three ways to make it: time-based, event-driven, and sensor/poll-based, each with its own honest failure mode. Cron is a lie about data readiness — the job runs at 2am whether or not upstream actually finished, and when it hasn't, the pipeline processes incomplete data with zero errors thrown. Event-driven triggers (S3 events, EventBridge, SQS) fix the readiness problem by reacting to an actual completion signal instead of a guessed clock time, but they introduce a worse failure mode: they can silently stop firing with no error at all, so every event-driven pipeline needs an independent freshness check as a backstop. Every trigger mechanism discussed here is at-least-once delivery, which means the consumer it triggers has to be idempotent regardless of how strong any single layer's execution guarantee looks.

## Why this gets asked

Because "the pipeline runs at 2am" is a design decision most engineers inherit rather than make, and the interviewer wants to know if you understand what that decision actually assumes: that upstream data is guaranteed to be ready at 2am, which is a claim about the world, not about your job scheduler. They've been paged because a nightly load ran at its scheduled time against an upstream table that landed 40 minutes late that one night, producing a report built on incomplete data with no error anywhere. They want to hear you reason about *what starts a run* as a distinct, first-class design question from *what the run does once started* — this module is scoped to exactly that question; see `T18-ingestion` for how data actually gets extracted and `T18-airflow` for how Airflow specifically implements the scheduling primitives discussed here.

---

## Lineage: past → present → future

**What came before.** Cron (1975, Unix) is the original answer to "run this at a fixed time," and it is still, honestly, the right answer for an enormous fraction of scheduling needs — its failure mode is simply that it has no concept of *readiness*. A cron-triggered job at 02:00 runs at 02:00 whether or not the data it depends on has actually landed; cron cannot express "run when X is done," only "run when the clock says so." The pain this caused at scale: as pipelines grew more interdependent, teams either padded schedules with large, wasteful safety margins ("upstream usually finishes by 1am, so run at 3am to be safe") or occasionally, and unpredictably, ran against incomplete data with no error, just a wrong answer. This is the exact motivation for building dependency-aware, event-driven triggering rather than pure time-based scheduling.

**Where it stands now.** The field has converged on three complementary triggering models rather than one replacing the others: **time-based** (cron/fixed schedule) for anything with a genuinely predictable, bounded readiness window; **event-driven/push-based** (S3 event notifications, EventBridge rules, Kafka/SQS message arrival) for anything where "the moment data lands" is knowable and worth reacting to immediately; and **sensor/poll-based** (an orchestrator repeatedly checking a condition) as the fallback when neither a clean schedule nor a native push mechanism is available. AWS's own internal recommendation pattern — batch ETL triggered by EventBridge kicking off Step Functions — reflects this: EventBridge for the "when/what triggers" layer, Step Functions for the "what happens next, with retries and state" layer, deliberately separated. Airflow's own evolution mirrors this industry-wide shift: Datasets (renamed Assets in Airflow 3.0, see `T18-airflow`) formalize "trigger the downstream DAG when this data asset updates" as a first-class scheduling primitive rather than a workaround built from sensors.

**Where it's heading.** Event-driven, data-aware scheduling (Airflow Assets, EventBridge Scheduler's newer feature set with millions of one-time schedules, native retries, and DLQs) is displacing a meaningful share of cron-based scheduling for new pipelines, with high confidence given the direction of both Airflow's and AWS's own roadmaps. **EventBridge Scheduler** specifically (distinct from the older EventBridge Rules) is becoming the default recommendation over legacy `cron`-in-Lambda or CloudWatch Events Rules for anything needing per-invocation state, retries, or a very large number of independent one-time/recurring schedules, given its native support for millions of concurrently scheduled tasks. More speculative: fully automated SLA-aware scheduling (a system that infers the right trigger time or condition from historical upstream landing patterns rather than a human setting a fixed cron expression or a manually-defined sensor condition) exists in early vendor observability tooling but isn't yet a mainstream default.

---

## Mental model

```
  TIME-BASED (cron)          EVENT-DRIVEN (push)           SENSOR/POLL
  ┌────────────────┐        ┌────────────────┐        ┌────────────────┐
  │ "run at 02:00"  │        │ "run when file  │        │ "check every    │
  │                 │        │  lands in S3"   │        │  60s until file │
  │ FAILURE MODE:   │        │                 │        │  lands, or      │
  │ runs regardless │        │ FAILURE MODE:   │        │  timeout"       │
  │ of whether data │        │ event lost/     │        │                 │
  │ is actually     │        │ silently stops  │        │ FAILURE MODE:   │
  │ ready — "cron   │        │ firing (broken  │        │ costs a worker  │
  │ is a lie about  │        │ subscription,   │        │ slot / poll     │
  │ data readiness" │        │ IAM drift) —    │        │ budget for the  │
  │                 │        │ NOTHING runs,   │        │ whole wait;     │
  │                 │        │ silently        │        │ times out if    │
  │                 │        │                 │        │ condition never │
  │                 │        │                 │        │ arrives         │
  └────────────────┘        └────────────────┘        └────────────────┘

  The fix for cron's lie: don't schedule the CONSUMER on a guessed time.
  Schedule the PRODUCER's completion to trigger the consumer (event-driven),
  or have the consumer actively wait on a real readiness signal (sensor/
  Airflow Assets), rather than a clock that has no idea what actually happened.
```

---

## How it actually works

### Cron vs event-driven vs sensor/poll — the honest tradeoff and each one's failure mode

**Cron/time-based.** Simple, predictable, zero infrastructure beyond a scheduler. Its failure mode is structural, not incidental: **cron is a lie about data readiness** — the job runs at 02:00 whether upstream landed at 01:45 or is still running at 02:30. There is no error when this happens; the job simply processes whatever is there, which for an incremental/append pattern might mean partial data silently treated as complete (see the watermark-drift failure mode in `T18-ingestion`). Cron is the right choice when the upstream's completion time has a genuinely tight, well-understood, and rarely-violated bound — for example, an hourly extract from a system with a hard cutoff and monitored SLA.

**Event-driven/push-based.** A producer emits an event the moment something happens (a file lands in S3, a row is written to a CDC topic, a message hits a queue), and a consumer reacts immediately. This eliminates the readiness-guessing problem entirely — you trigger on the actual completion signal, not a guessed time — at the cost of a new failure mode: **the trigger can silently stop firing** with no obvious symptom. A misconfigured S3 event notification, a Lambda permission that drifted, an EventBridge rule with a pattern that stopped matching after an upstream event schema changed slightly — all of these produce the same symptom: nothing runs, no error, because there's nothing actively checking "should something have happened by now." This is why event-driven triggers need their own freshness/liveness monitoring (see `T18-data-quality`) — a downstream table's staleness check is often the *only* thing that catches a silently-broken event trigger.

**Sensor/poll-based.** An active check, repeated on an interval, until a condition is true or a timeout is hit. This is the fallback when there's no native push mechanism (a legacy system with no event hooks, a partner's SFTP drop with no notification), and it has real, measurable cost: **polling consumes resources proportional to how long you wait and how often you check** — in Airflow specifically, a non-deferrable sensor holds a worker slot for its entire wait unless it's deferrable or `mode="reschedule"` (see `T18-airflow`), and even a deferrable sensor still costs API calls/requests against whatever it's polling, which matters for rate-limited APIs.

| | Cron | Event-driven | Sensor/poll |
|---|---|---|---|
| Latency to react | fixed, potentially wasteful (safety margin) | near-immediate | bounded by poll interval |
| Failure mode | runs on incomplete data, silently | stops firing silently | times out (at least this is loud) or wastes resources waiting |
| Infra cost | lowest | moderate (event bus, rules) | scales with wait duration × poll frequency |
| Best for | tight, well-understood upstream SLA | any producer that can emit a completion signal | no native push mechanism available, and a bounded/acceptable wait |

### S3 Event Notifications vs EventBridge for S3

S3's native **Event Notifications** (the original mechanism) let a bucket push directly to a single destination (SQS, SNS, Lambda) per notification configuration, filtered only by object key prefix/suffix. **EventBridge for S3** routes the same underlying events through EventBridge instead, unlocking richer capabilities: **filtering on arbitrary event fields** (not just prefix/suffix — object size, full key pattern, time-based fields), **fan-out to many independent targets** from one event (the same "file landed" event can simultaneously trigger a Step Functions workflow, a Lambda for a quick transform, and an SNS notification, without each needing its own S3 notification configuration), and **archive-and-replay** (EventBridge can archive events and replay them later, useful for reprocessing after a bug in a downstream consumer, or for adding a new consumer that needs to catch up on historical events). The tradeoff is a small amount of added latency and one more hop versus a direct S3-to-Lambda notification, which is negligible for almost every batch pipeline use case.

### EventBridge Scheduler vs EventBridge Rules vs Step Functions

- **EventBridge Rules** — the original cron-and-pattern-matching mechanism: match events against a pattern (or a fixed cron/rate expression) and route to a target. Good for simple time-based triggers and event routing.
- **EventBridge Scheduler** — the newer, purpose-built scheduling service: supports one-time and recurring schedules at very large scale (documented support for scheduling millions of tasks, invoking over 270 AWS services), with native retries, dead-letter queues, and time zone handling built in — capabilities that had to be hand-rolled on top of Rules previously. This is now the better default for anything that's fundamentally "run this at a time (or times)" rather than "route this event based on a pattern."
- **Step Functions** — a state-machine orchestrator for multi-step workflows with explicit state, branching, retries, and error handling per step. **Standard** workflows support long-running executions (up to a year), keep full execution history for audit/compliance/debugging, and guarantee exactly-once execution semantics — appropriate when you need a durable, inspectable audit trail (a financial reconciliation workflow, anything with compliance requirements). **Express** workflows are built for short-lived (up to 5 minutes historically, extended in newer versions), high-throughput, at-least-once execution, without retaining full execution history beyond CloudWatch Logs — appropriate for high-volume, short, non-audit-critical work where the per-transition cost of Standard would be prohibitive at scale. The pricing gap is real and large: Standard is priced per state transition and gets expensive fast at high volume (documented comparisons put a busy Standard workload in the range of ~$2,000/month where an equivalent Express workload runs a small fraction of that), which is itself a common reason teams pick Express even when they'd prefer Standard's execution history.

The common, AWS-recommended composition: **EventBridge (Scheduler or Rules) decides *when/what* triggers; Step Functions handles *what happens next*** — the sequencing, retries, and state of the actual multi-step workflow. Using EventBridge alone for a multi-step workflow means hand-rolling state and retry logic across multiple Lambda invocations with no built-in visibility into where a failure occurred; using Step Functions alone for pure time-based triggering means paying for and maintaining a state machine that never actually branches.

### SQS-triggered work and backpressure

An SQS queue decouples a producer's emission rate from a consumer's processing rate — the producer never blocks on the consumer being ready, and the consumer pulls at its own sustainable pace. This is the natural backpressure mechanism for event-driven pipelines: if the consumer (a Lambda, an ECS task, a data-loading service) falls behind, messages simply queue rather than being dropped or overwhelming the consumer, up to the queue's retention period (SQS default message retention is 4 days, configurable up to 14). **Visibility timeout** governs how long a message is hidden from other consumers after being picked up — set it too short relative to actual processing time and the same message gets picked up by a second consumer before the first finishes, producing duplicate processing; set it too long and a genuinely failed/crashed consumer's messages sit invisible (and unprocessed) for the full timeout before becoming available for retry.

### Why cron is a lie about data readiness — and what to do instead

Restating the core point precisely: a cron schedule encodes an assumption ("upstream is always done by X") that is true until the one day it isn't, and cron has no mechanism to detect or react to that day being different. Three concrete alternatives, each already covered in more depth elsewhere in this track:

1. **Data-aware scheduling** (Airflow Assets/Datasets, see `T18-airflow`) — the downstream DAG is triggered by the upstream task's completion signal, not a guessed clock time.
2. **A sensor with a real readiness check** — rather than trusting the clock, actively verify the condition ("does this file exist," "is this table's max timestamp past X") before proceeding, accepting the sensor's own tradeoffs (worker cost unless deferrable, timeout risk).
3. **Push from the producer** (S3 event notification, EventBridge rule, a message on a queue) — the producer itself announces completion, and nothing downstream has to guess or poll at all.

All three share the same underlying fix: **stop encoding an assumption about the world into a fixed clock time, and instead react to (or actively verify) the actual event.**

### Idempotent triggers and duplicate-delivery handling

Every trigger mechanism discussed here — SQS, EventBridge, S3 event notifications — is at-least-once delivery, same as the ingestion delivery guarantees in `T18-ingestion`. A retried Lambda invocation from an EventBridge rule, or an SQS message redelivered after a visibility timeout expires before processing finished, means the triggered pipeline can start twice for the same logical event. The fix is the same idempotency discipline as `T18-ingestion`: the triggered job itself must be safe to run twice for the same input (merge/upsert on a natural key, or an idempotency key checked before any side-effecting work begins), because the trigger layer cannot itself guarantee exactly-once execution of what it triggers.

### Debugging a trigger that silently stopped firing

This is the single most common real incident in event-driven scheduling, and it has a repeatable diagnostic path: (1) confirm the producer actually emitted the event — check the source's own logs/metrics for the expected action (did the file actually land in S3?); (2) check the event bus/notification configuration itself for drift — an IAM permission change, a modified event pattern that no longer matches, a notification configuration silently removed by an unrelated infrastructure change; (3) check the consumer's own invocation metrics (Lambda invocation count, Step Functions execution count) for a sudden drop to zero at a specific time, which usually pinpoints exactly when the break happened; (4) if nothing obviously changed, check for a quota/throttling issue (EventBridge and Lambda both have account-level quotas that can silently throttle without an obvious global outage signal). The reason this needs its own runbook: unlike a crashed job, which announces itself with an error, a silently-broken trigger produces *nothing* — no logs, no errors, just an absence, and absence is much harder to notice than failure.

---

## Build it from scratch

A minimal illustration of the "producer pushes, consumer reacts idempotently" pattern versus the cron alternative, showing why the event-driven version doesn't have the readiness-guessing problem.

```python
# untested sketch — illustrates event-driven trigger + idempotent consumer,
# not a deployable AWS Lambda/EventBridge configuration
import hashlib

def handle_s3_event(event: dict, processed_store) -> None:
    """Consumer triggered by an S3 event notification (via EventBridge).
    Must be idempotent: EventBridge/S3 notifications are at-least-once."""
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        event_id = record.get("eventID") or hashlib.sha256(f"{bucket}/{key}".encode()).hexdigest()

        if processed_store.already_handled(event_id):
            return  # safe no-op on redelivery — this is the idempotency guard

        try:
            load_file_idempotent(bucket, key)   # itself idempotent, e.g. merge/upsert
            processed_store.mark_handled(event_id)
        except Exception:
            # do NOT mark handled on failure — let it be retried/redelivered
            raise


def compare_with_cron_polling(bucket: str, expected_prefix: str, s3_client) -> bool:
    """The pattern this replaces: a cron job polling 'has the file landed yet,'
    which either wastes a poll budget waiting or, worse, runs on a fixed
    schedule with NO check at all and just assumes readiness."""
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=expected_prefix)
    return response.get("KeyCount", 0) > 0
```

The comparison worth making explicit to an interviewer: `handle_s3_event` reacts the moment the file lands, with no guessed schedule and no polling cost, but it must defend against redelivery itself; `compare_with_cron_polling` represents the pattern being replaced — either a blind cron job with zero readiness check, or a polling sensor that costs resources for the entire wait. Full version wired to a real EventBridge rule and Step Functions state machine: `labs/py/18-scheduling-lab/`.

---

## How it's done in production

**Airflow Assets/Datasets** (see `T18-airflow`) implement data-aware scheduling natively inside the orchestrator: a downstream DAG's schedule is expressed as "trigger when these Assets update" rather than a cron expression, removing the guessed-time problem for pipelines fully inside Airflow's own scope.

**AWS-native event-driven ETL**: S3 Event Notifications or EventBridge (for richer filtering/fan-out) trigger a Lambda or directly start a Step Functions execution the moment a file lands; Step Functions Standard orchestrates the actual multi-step ETL (validate → transform → load → notify) with per-step retries and a durable, auditable execution history; EventBridge Scheduler handles any genuinely time-based components (a nightly full-reconciliation job, for instance, that isn't triggered by any single file landing).

**SQS as the buffering layer** between a bursty producer (many files landing near-simultaneously) and a rate-limited or capacity-constrained consumer, providing backpressure without the producer needing to know or care about the consumer's current load.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Pipeline runs on time, output is subtly incomplete, no error | Cron-triggered job ran against upstream data that hadn't fully landed yet | Replace with event-driven trigger (upstream signals completion) or a readiness-checking sensor, not a guessed clock time |
| Downstream pipeline stops running entirely, no errors anywhere | Event trigger silently stopped firing (IAM drift, notification config removed, event pattern no longer matches) | Add a freshness/liveness check on the downstream table itself (T18-data-quality) as a backstop that doesn't depend on the trigger mechanism working |
| A file is processed twice, producing duplicate records | At-least-once delivery (SQS redelivery after visibility timeout, EventBridge retry) into a non-idempotent consumer | Idempotency guard keyed on event ID or content hash before any side-effecting work; merge/upsert on the actual data write |
| SQS messages processed by two consumers simultaneously | Visibility timeout set shorter than actual processing time | Increase visibility timeout comfortably above p99 processing time, or use a heartbeat/extend-visibility pattern for long-running work |
| A Standard Step Functions workflow's AWS bill spikes unexpectedly | High-volume, short-lived work routed through Standard's per-state-transition pricing instead of Express | Move short, high-throughput, non-audit-critical work to Express workflows |
| A sensor times out waiting for a file that already landed | Poll interval or timeout misconfigured, or the sensor is checking the wrong path/condition after an upstream change | Verify the exact condition being checked matches the actual upstream contract; alert on sensor timeout as its own signal, don't just silently retry the whole DAG |
| Reprocessing after a downstream bug fix requires re-triggering every file manually | No event archive/replay capability (using plain S3 notifications instead of EventBridge) | Use EventBridge's archive-and-replay to reprocess historical events without manually re-listing and re-invoking for every file |

---

## Tradeoffs & when NOT to use it

- **Do not replace every cron schedule with event-driven triggering reflexively.** A pipeline with a genuinely tight, monitored, rarely-violated upstream SLA gains little from the added infrastructure (event bus, rules, archive) of a push-based trigger, and cron's simplicity is a real advantage when the readiness assumption actually holds.
- **Do not use a sensor/poll pattern against a rate-limited third-party API without a generous poll interval and a hard timeout.** Aggressive polling against an external API can trip rate limits or get your integration throttled/banned, turning a scheduling choice into an availability incident with a partner.
- **Do not use Step Functions Standard for high-volume, short-lived, non-audit-critical work.** The per-state-transition pricing makes Standard genuinely expensive at scale for workloads that don't need its exactly-once guarantee or full execution history; Express exists specifically for this case.
- **Do not use Express workflows for anything needing a durable audit trail or executions longer than a few minutes.** Express doesn't retain full execution history beyond CloudWatch Logs and isn't built for long-running work; a financial reconciliation or compliance-relevant workflow needs Standard's guarantees regardless of the cost difference.
- **Do not rely solely on an event trigger with no independent freshness/liveness check on the consumer side.** Every event-driven design in this module needs a backstop (a staleness alert on the downstream table) precisely because the trigger's own failure mode is silence, not an error — belt-and-suspenders here isn't over-engineering, it's compensating for a failure mode that produces no signal on its own.

---

## Interview questions

### Q1 — Explain precisely what "cron is a lie about data readiness" means, with a concrete failure scenario.
**Testing:** whether this is understood as a structural property, not just a slogan.
**Answer:** A cron schedule encodes a fixed-time assumption about when upstream data will be ready; it has no mechanism to verify that assumption at run time. Concretely: a nightly load scheduled for 02:00 assumes an upstream extract always finishes by then; the one night the upstream extract runs 40 minutes late, the 02:00 job runs anyway, processes whatever partial data exists, and produces a plausible but incomplete result with zero errors thrown anywhere in the pipeline.
**Follow-up trap:** *"Why not just move the schedule to 04:00 to be safe?"* — padding the schedule doesn't fix the structural problem, it just moves the threshold at which the same failure recurs (what happens the night upstream is 3 hours late instead of 40 minutes), and it costs latency every single night to hedge against a rare event. The actual fix is triggering on the upstream's real completion signal, not a bigger guess.

### Q2 — Compare the failure modes of event-driven and sensor/poll-based triggering. Which is "louder" when it breaks?
**Answer:** A sensor/poll-based trigger that never sees its condition become true eventually times out — a loud, visible failure that shows up as a task failure in the orchestrator. An event-driven trigger that silently stops firing (IAM drift, a notification configuration removed, an event pattern that no longer matches after an upstream schema change) produces no signal at all — nothing runs, no error, no timeout, just an absence that's only noticed when someone eventually checks whether the downstream table is stale.
**Follow-up trap:** *"So does that mean sensors are safer than event-driven triggers?"* — not overall; sensors have their own resource-cost failure mode (worker-slot starvation if non-deferrable, per `T18-airflow`) and don't scale as cleanly to many independent triggers. The right conclusion isn't "prefer sensors," it's "event-driven triggers need their own independent freshness/liveness monitoring as a backstop, precisely because their failure mode is silent."

### Q3 — When would you choose EventBridge for S3 events over native S3 Event Notifications?
**Answer:** When you need filtering beyond prefix/suffix (object size, arbitrary metadata fields), fan-out to multiple independent targets from one event without configuring multiple separate notification rules, or archive-and-replay capability for reprocessing historical events after a downstream bug fix or adding a new consumer that needs to catch up. Native S3 Event Notifications are simpler and lower-latency for the basic case of one bucket pushing to one destination filtered only by prefix/suffix.
**Follow-up trap:** *"What's the cost of routing through EventBridge instead of direct notifications?"* — a small amount of added latency and one more hop/moving part in the architecture, which is negligible for almost any batch pipeline but is a real (if usually acceptable) tradeoff to name rather than pretend doesn't exist.

### Q4 — Standard vs Express Step Functions: what's the actual guarantee difference, and give a scenario for each.
**Answer:** Standard guarantees exactly-once execution and retains full execution history for up to a year, appropriate for long-running (up to a year) or audit/compliance-relevant workflows — a financial reconciliation pipeline where you need to prove exactly what happened and when. Express is at-least-once, built for short-lived, high-throughput execution, and doesn't retain execution history beyond CloudWatch Logs — appropriate for a high-volume, short transformation step (e.g., resizing an image on upload) where the per-transition cost and audit trail of Standard would be wasteful.
**Follow-up trap:** *"Since Express is at-least-once, doesn't that mean your workflow steps need to be idempotent?"* — yes, exactly, same discipline as any at-least-once trigger discussed in this module and in `T18-ingestion`; picking Express is not just a cost/latency decision, it's implicitly accepting the idempotency burden that Standard's exactly-once guarantee would have absorbed for you.

### Q5 — A pipeline triggered by an S3 event processes the same file twice, producing duplicate rows. Diagnose it.
**Answer:** S3 event notifications and the Lambda/Step Functions they trigger are at-least-once by design — a retry after a transient failure, or a redelivery, can invoke the consumer twice for the same underlying file-landed event. If the consumer's write path is a plain insert with no idempotency guard, both invocations produce a row. Fix: an idempotency check (event ID or content hash of the file, checked against a dedup store before any write) plus a merge/upsert on the actual data load, same discipline as `T18-ingestion`'s idempotent-load pattern.
**Follow-up trap:** *"Doesn't Step Functions Standard's exactly-once guarantee prevent this?"* — Standard guarantees exactly-once *execution of the state machine*, not exactly-once delivery of the *triggering event* into that state machine — if the upstream EventBridge rule or S3 notification itself redelivers, you can still get two separate, each-exactly-once state machine executions for the same logical event. The idempotency burden doesn't disappear just because one layer of the stack has a strong guarantee; it needs to hold at the actual data-write boundary.

### Q6 — Design the triggering for a pipeline where 200 partner files land in S3 throughout the day at unpredictable times, each needing the same multi-step transform, and the transform step has a hard rate limit against a downstream API.
**Testing:** synthesizing event-driven triggering with backpressure.
**Answer:** S3 Event Notifications (or EventBridge, if richer filtering/fan-out is needed) push a message to SQS the moment each file lands, decoupling arrival rate from processing rate. A consumer (Lambda or an ECS task) pulls from SQS at a rate that respects the downstream API's rate limit, with the queue naturally absorbing bursts — if 50 files land in the same minute, they queue rather than triggering 50 simultaneous rate-limit-violating calls. Step Functions (Standard, if the transform's audit trail matters for partner SLAs, or Express if it doesn't) orchestrates the actual multi-step transform per file with per-step retries.
**Follow-up trap:** *"What if the SQS visibility timeout is shorter than the transform actually takes under load?"* — a message becomes visible to another consumer before the first one finishes, causing duplicate processing; either extend the visibility timeout comfortably above p99 processing time, or implement a heartbeat pattern that extends visibility while work is genuinely still in progress, and ensure the transform itself is idempotent regardless, since visibility timeout tuning reduces but doesn't eliminate duplicate-delivery risk.

### Q7 — Your event-driven pipeline (S3 event → Lambda → Step Functions) has processed zero files in the last 6 hours, but partners confirm they've been uploading normally. Walk through your debugging steps.
**Answer:** First confirm the producer side: check S3 access logs or CloudTrail to verify files are actually landing in the expected bucket/prefix. Second, check the event notification/EventBridge rule configuration itself for drift — an IAM permission change, a modified event pattern, or a notification configuration that got silently overwritten by an unrelated infrastructure change (a common cause: someone updated the bucket's notification config for an unrelated purpose and clobbered the existing one). Third, check Lambda/Step Functions invocation metrics for the exact time invocations dropped to zero, which usually pinpoints the change that broke it. Fourth, rule out account-level throttling/quotas on EventBridge or Lambda.
**Follow-up trap:** *"What would you put in place so you don't have to do this manual debugging next time?"* — an independent freshness/liveness check on the downstream table or system that alerts based on staleness, completely decoupled from whether the trigger mechanism itself reports success — since the trigger's failure mode is silence, the only reliable backstop is monitoring the *outcome* (is data landing downstream) rather than the trigger's own health signals, which by definition go quiet along with it.

### Q8 — What's the actual difference between EventBridge Rules and EventBridge Scheduler, and why would you pick the newer one?
**Answer:** EventBridge Rules match events against a pattern (or a basic cron/rate expression) and route to a target — it's fundamentally an event-routing mechanism with scheduling as one capability. EventBridge Scheduler is purpose-built for scheduling at scale: native support for a very large number of independent one-time and recurring schedules, built-in retries, dead-letter queues, and time zone handling that previously had to be hand-rolled on top of Rules. Pick Scheduler when the need is fundamentally "run this (or these many independent things) at specific times" rather than "route events matching a pattern."
**Follow-up trap:** *"If you already have EventBridge Rules working fine for your current schedules, is it worth migrating?"* — not automatically; migration is worth it when you hit Rules' practical limits (needing per-schedule retry/DLQ configuration, scaling to a very large number of independent schedules, or needing per-invocation state Rules doesn't provide) rather than as a reflexive upgrade — "the newer service" isn't sufficient justification on its own.

### Q9 — Why does an SQS-based architecture provide backpressure, and what happens if you get the visibility timeout wrong in either direction?
**Answer:** SQS decouples producer emission rate from consumer processing rate — messages queue rather than overwhelming a consumer that's temporarily behind, up to the queue's retention period. Visibility timeout governs how long a message is hidden after being picked up: set too short relative to actual processing time, a second consumer picks up the same message before the first finishes, causing duplicate processing; set too long, a consumer that crashed mid-processing leaves that message invisible (and effectively stuck) for the full timeout duration before it becomes available for anyone to retry.
**Follow-up trap:** *"How do you handle work whose duration is unpredictable and sometimes exceeds any reasonable fixed visibility timeout?"* — use a heartbeat/extend-visibility pattern, where the consumer periodically calls `ChangeMessageVisibility` while work is genuinely still in progress, rather than trying to guess one fixed timeout that has to cover both the fast and slow cases; this avoids the false choice between "too short causes duplicates" and "too long delays legitimate retries."

### Q10 — When would you deliberately choose cron over any event-driven or sensor-based alternative, even knowing cron's readiness limitation?
**Answer:** When the upstream's completion time has a genuinely tight, well-understood, and rarely-violated bound with active monitoring on its own SLA — for example, an internal system with a hard, enforced cutoff time and its own alerting if it runs late. In that case, the infrastructure cost of event-driven triggering (an event bus, rules, archive/replay, its own failure-mode monitoring) buys protection against a risk that's already independently controlled, and cron's simplicity (one line, no additional moving parts) is the honestly better engineering tradeoff.
**Follow-up trap:** *"Isn't that just accepting the same risk you spent this whole module describing as dangerous?"* — no, because the risk is being managed at the *source* (the upstream system's own monitored SLA) rather than assumed silently; the distinction that matters is between "cron with no verification of any kind" (the dangerous default) and "cron against an upstream with its own independently monitored, enforced completion guarantee" (a deliberate, informed choice) — the senior signal is naming which one you're doing and why.

---

## Red flags that fail you

- Describing "the job runs at 2am" without acknowledging what that assumes about upstream readiness.
- Not knowing that event-driven triggers can fail silently, or having no answer for how you'd detect it.
- Proposing Step Functions Standard for a high-volume, short-lived, cost-sensitive workload with no mention of Express.
- Not recognizing that every trigger mechanism discussed here (SQS, EventBridge, S3 notifications) is at-least-once, requiring idempotent consumers.
- Suggesting aggressive polling against a rate-limited third-party API with no regard for their rate limits.
- Treating "add an event trigger" as strictly safer than cron with no discussion of its own failure mode or added complexity.

---

## Cheat card

```
CRON         simple, zero infra, LIES about readiness — runs at 02:00
             regardless of whether upstream actually finished. Failure is
             SILENT (plausible but incomplete output, no error).
             Right when upstream has a tight, MONITORED SLA.

EVENT-DRIVEN push-based (S3 event, EventBridge, SQS message). Near-immediate,
             no readiness-guessing. FAILURE MODE: can silently STOP FIRING
             (IAM drift, notif config removed, pattern stops matching) —
             produces NOTHING, no error. Needs an independent freshness/
             liveness check as a backstop.

SENSOR/POLL  active check on an interval until true or timeout. Fallback
             when no native push exists. Cost scales with wait x poll
             frequency. Non-deferrable = holds a worker slot the whole wait
             (see T18-airflow). At least LOUD when it fails (timeout).

S3 EVENTS vs EVENTBRIDGE   native: 1 dest, prefix/suffix filter only.
             EventBridge: filter on ANY field, FAN-OUT to many targets,
             ARCHIVE+REPLAY for reprocessing. Small extra latency/hop.

EVENTBRIDGE SCHEDULER vs RULES   Rules = pattern match + basic cron, routes
             to a target. Scheduler = purpose-built: millions of schedules,
             native retries + DLQ + timezones, built in (not hand-rolled).

STEP FUNCTIONS   Standard: exactly-once EXECUTION, full history up to 1yr,
             long-running (up to 1yr) — audit/compliance workloads.
             Express: at-least-once, short (~5min), high-throughput, NO
             full history beyond CloudWatch Logs — cheap, high-volume,
             non-audit work. Standard $$$ at scale (~$2k/mo range vs a
             fraction for Express at the same volume) — real cost driver.
             PATTERN: EventBridge decides WHEN/WHAT triggers, Step
             Functions handles WHAT HAPPENS NEXT (sequencing, retries, state).

SQS BACKPRESSURE   decouples producer rate from consumer rate, messages
             queue instead of overwhelming consumer. retention 4d default
             (up to 14d). Visibility timeout too SHORT -> duplicate
             processing (2nd consumer grabs it before 1st finishes).
             Too LONG -> crashed consumer's msgs stuck invisible till
             timeout expires. Fix for unpredictable duration: heartbeat /
             extend-visibility pattern.

IDEMPOTENT TRIGGERS   EVERY mechanism here (SQS, EventBridge, S3 notif) is
             AT-LEAST-ONCE. Consumer must be idempotent regardless of which
             layer's execution guarantee looks strong (Standard's exactly-
             once execution != exactly-once event delivery INTO it).

DEBUG A DEAD TRIGGER   1) confirm producer actually emitted (source logs)
             2) check event bus/notif config for drift (IAM, pattern match)
             3) check consumer invocation metrics for the exact drop time
             4) check account-level quota/throttling

CROSS-REF   what gets extracted once triggered -> T18-ingestion
            Airflow's own scheduling primitives (Assets, sensors) -> T18-airflow
            re-running safely after a gap -> T18-backfill-replay
```

## Sources

- [EventBridge vs. Step Functions: When to choreograph and when to orchestrate — Medium](https://medium.com/@naeemulhaq/eventbridge-vs-step-functions-when-to-choreograph-and-when-to-orchestrate-4cc5e6780dde) — accessed 2026-08-01
- [Using EventBridge — Amazon Simple Storage Service Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventBridge.html) — accessed 2026-08-01
- [A Complete Guide to Amazon S3 Event Notifications — Medium](https://medium.com/@akashkola321/a-complete-guide-to-amazon-s3-event-notifications-ordering-duplicates-filters-integrations-8191b9304d2c) — accessed 2026-08-01
- [Delayed Event Triggers with AWS - EventBridge Scheduler vs Step Functions](https://beabetterdev.com/2023/09/20/delayed-events-aws-eventbridge-stepfunctions/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
