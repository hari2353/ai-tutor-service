# ECR vs Artifactory vs Nexus vs GHCR: Promotion, Retention, Signing, SBOM

> **Track:** T12 DevOps, Infra & Security · **Time:** 2h · **Prereqs:** T12-docker, T12-eks-ecs-ecr
> **Module id:** `T12-artifact-registries` · **Tags:** containers, security, supply-chain

## The 30-second version

Registry choice is rarely the interesting decision (ECR if you're AWS-native and want zero-ops IAM-integrated pulls, Artifactory or Nexus if you need one registry for containers *and* Maven/npm/PyPI/Helm across a polyglot org, GHCR if you're already GitHub-centric and want free public storage) — the interesting decisions are what you do around the registry. Promote by retagging or copying the same digest through dev to staging to prod (never rebuild per environment — a rebuild can silently pull a different base-image layer or a newer transitive dependency even with identical source, which is exactly the "it passed staging" surprise that burns people), enforce lifecycle policies from day one because every registry retains pushed images indefinitely by default and unbounded retention is a slow, compounding storage-cost leak, sign every image with cosign/Sigstore keyless signing (OIDC identity plus a short-lived Fulcio cert plus a Rekor transparency-log entry, not a long-lived private key you now have to rotate and protect) and verify that signature at admission control so an unsigned image is a structural deploy-block, and generate an SBOM (Syft/Trivy, CycloneDX or SPDX format) on every build — but treat the SBOM as a starting inventory, not a vulnerability guarantee, because none of the mainstream generators reliably resolve transitive dependencies for compiled/shaded artifacts, and a clean SBOM scan says "no known CVEs in what we could enumerate," not "no vulnerabilities."

## Why this gets asked

Because "we scan our images" is a sentence every team says and a much smaller fraction actually means in a way that blocks a bad deploy. The interviewer has likely either audited a registry that had 40,000 untagged images going back three years costing real money nobody noticed, found a critical CVE in a base image that had been sitting unscanned for months because scan-on-push only fires once and nobody re-scans old layers as new CVEs publish, or watched a supply-chain incident (the xz-utils backdoor, March 2024, is the reference case cited in nearly every 2026 SBOM/signing pitch) make leadership suddenly care about "can we prove what's actually running and who built it." They want to know if you've operated the mechanics — promotion without rebuild, lifecycle policies with real numbers, signing wired into admission control, not bolted on as a compliance checkbox nobody enforces.

---

## Lineage: past → present → future

**What came before.** Early container registries were just Docker Hub or a self-hosted `registry:2` instance with essentially no policy layer — push, pull, maybe basic auth, no lifecycle rules, no scanning, no signing. Retention meant "we never delete anything," which was fine until storage bills and audit findings both grew past ignorable. Promotion across environments was frequently done by *rebuilding* the same Dockerfile against a different environment's config, which quietly broke reproducibility: a "rebuild for staging" three days after the dev build could resolve a different `apt` package version, a different base-image digest if `FROM node:20` wasn't pinned to a digest, or a newer transitive npm/pip dependency — so "staging passed" and "prod broke" stopped meaning "the same artifact behaved differently" and started meaning "we never actually tested the artifact we shipped." Image signing barely existed operationally before Notary v1 (Docker Content Trust, 2015) which was clunky enough (root/targets/snapshot/timestamp key hierarchy, poor UX) that almost nobody outside a few security-forward shops actually turned it on.

**Where it stands now.** Promote-the-artifact, don't-rebuild is now the settled consensus — the image (identified by its immutable digest, not a mutable tag) is built once, tested, and the *same bytes* move through dev → staging → prod via retag or cross-registry copy (`skopeo copy`, `crane copy`, or a registry's native promotion feature), which is what actually gives you the guarantee that what passed staging is what runs in prod. Lifecycle policies (ECR, GHCR, Artifactory, Nexus all support some form of rule-based expiration) are considered baseline hygiene, not an optimization — real numbers: pruning untagged images older than 14 days typically cuts ECR storage by 50-80%, and as of a January 2026 ECR change, layers are now deduplicated across repositories within the same private registry rather than stored once per repository, which further reduces the "everyone's base image is stored N times" waste. Signing has moved from Notary v1's key-management pain to Sigstore/cosign's keyless model (OIDC-backed short-lived Fulcio certificates plus Rekor transparency-log entries instead of long-lived private keys you have to guard and rotate) — this is the actually-deployed pattern in 2026, with Notary v2 (rebranded and continued as the CNCF **Notation** project) as a second, OCI-native signing spec that some enterprises use where the client tooling story is more mature, but cosign/Sigstore is the dominant default in most stacks reporting real adoption. SBOM generation (Syft, Trivy's built-in SBOM mode, CycloneDX-CLI) is now routinely wired into CI, but a 2026 empirical study on SBOM-based vulnerability management found real, measurable gaps: none of the mainstream generators reliably resolve transitive dependencies for compiled artifacts, and shaded/bundled/relocated dependencies in Java and JavaScript specifically remain a weak spot — an SBOM is an inventory of what a tool could statically identify, not a certified complete bill of materials.

**Where it's heading.** SLSA provenance attestations (verifiable, signed claims about *how* an artifact was built — which pipeline, which source commit, which builder identity — not just what's inside it) are the direction admission-control policy is moving, layered on top of signature verification rather than replacing it; expect "unsigned image" and "no SBOM/provenance attached" to keep becoming hard blocks in more pipelines, following the same trajectory CISA supply-chain guidance and SLSA level 2+ compliance have been pushing since roughly 2023-2024, though this is still far from universal outside finance, healthcare, and government-adjacent shops. Registry-level deduplication (ECR's January 2026 shared-layer-storage change) is a plausible template other registries follow as storage-cost pressure from ever-growing scan/SBOM/attestation metadata compounds the base image-storage problem. SBOM tooling accuracy for transitive and compiled dependencies is an active, unresolved research area (the November 2025 arXiv "Reality Check on SBOM-based Vulnerability Management" study is a useful citation if pressed on this) — expect incremental accuracy improvements, not a near-term fix, so "treat SBOM as inventory, not proof" will likely remain the honest framing for a while.

---

## Mental model

```
REGISTRY CHOICE (rarely THE decision — pick by ecosystem fit, not features):

  ECR        AWS-native, zero-ops IAM auth for EKS/ECS nodes, containers only
             (ECR doesn't do Maven/npm/PyPI) -- see T12-eks-ecs-ecr
  Artifactory/Nexus   ONE registry for containers + Maven + npm + PyPI + Helm +
             generic artifacts, polyglot-org standard, consumption-based
             pricing ($/GB storage+transfer combined -- Nexus ~$0.90-1.10/GB
             beyond included tier, Artifactory Pro $150/mo base + consumption)
  GHCR       already GitHub-centric, free storage for public images, tightly
             coupled to GitHub Actions OIDC for keyless signing

PROMOTION: the SAME DIGEST moves through environments, never a rebuild.

  build once -> sha256:9f2e... tagged myapp:dev  -> push to dev repo
       |
       v  (tests pass -> RETAG or CROSS-REGISTRY COPY, same digest)
  sha256:9f2e... tagged myapp:staging -> push to staging repo
       |
       v  (approval -> RETAG again, still same digest)
  sha256:9f2e... tagged myapp:v1.2.0, myapp:prod -> push to prod repo

  REBUILDING per environment breaks this: same Dockerfile + different day
  = different resolved base-image layer / transitive dep = "staging passed,
  prod broke" even though "nothing changed" in source.

SIGNING + ADMISSION CONTROL (the part that makes signing MEAN something):

  CI builds image -> cosign sign (OIDC identity -> Fulcio short-lived cert
  -> signature -> Rekor transparency log entry) -> push signed image
       |
       v
  Kubernetes admission controller (Kyverno/Connaisseur) verifies signature
  at deploy time -> unsigned or tampered image = HARD REJECT, not a warning

SBOM: an INVENTORY, not a vulnerability guarantee.
  Syft/Trivy -> CycloneDX/SPDX SBOM -> Grype/Trivy scans SBOM against CVE DB
  CATCHES: known-CVE'd direct dependencies with clean manifest metadata
  MISSES: transitive deps in compiled/shaded artifacts (Java uber-jars, JS
  bundles), version ranges instead of pins, anything not statically resolvable
```

---

## How it actually works

### Promotion: digest immutability is the whole mechanism

A tag (`myapp:staging`) is a mutable pointer; a digest (`sha256:9f2e...`) is the actual, immutable content address of the image manifest. Promotion pipelines that are correct always reason in digests and treat tags as labels applied *to* a digest after the fact:

```bash
# untested sketch — promote by digest, not by rebuilding
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' myapp:ci-build-142)

# retag within the same registry (ECR: same repo, different tag)
docker tag "$DIGEST" 123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:staging
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:staging

# OR cross-registry / cross-account copy without a local pull, via skopeo or crane
crane copy 123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp@$DIGEST \
           987654321098.dkr.ecr.us-east-1.amazonaws.com/myapp:prod
```

The concrete failure this prevents: a `FROM node:20` (not pinned to a digest) rebuilt three days after the original dev build can resolve `node:20.11.2` instead of `node:20.11.0` because the tag moved upstream, silently changing the runtime under test-passed code. Pinning base images by digest in the Dockerfile is a related, complementary discipline — it doesn't replace promote-not-rebuild, but it makes even an accidental rebuild reproducible.

### Retention and lifecycle policies: real numbers

Every registry retains pushed images indefinitely unless you configure otherwise. ECR storage runs $0.10/GB-month; a repository accumulating years of CI pushes (tagged release images, untagged intermediate build layers, PR-preview images nobody cleans up) is a slow, easy-to-miss cost leak that shows up as a steadily climbing storage line item with no corresponding growth in active usage. A concrete, real-world number: pruning untagged images older than 14 days typically cuts ECR storage 50-80% in an unmanaged repository, because CI systems routinely push far more untagged intermediate images than anyone ever references again. Artifactory/Nexus's consumption-based pricing (storage **and** data transfer combined, commonly $0.90-1.10/GB beyond an included tier for Nexus Pro, and JFrog's advertised $150/month base rarely reflecting the real consumption-driven bill) makes retention discipline a direct line-item cost lever in a way ECR's flat per-GB storage pricing doesn't as sharply, since egress/transfer is billed too.

```json
// untested sketch — ECR lifecycle policy: keep last 10 tagged, expire untagged after 14d
{
  "rules": [
    {
      "rulePriority": 1,
      "description": "expire untagged images older than 14 days",
      "selection": { "tagStatus": "untagged", "countType": "sinceImagePushed",
                      "countUnit": "days", "countNumber": 14 },
      "action": { "type": "expire" }
    },
    {
      "rulePriority": 2,
      "description": "keep only the last 10 tagged images",
      "selection": { "tagStatus": "tagged", "tagPrefixList": ["v"],
                      "countType": "imageCountMoreThan", "countNumber": 10 },
      "action": { "type": "expire" }
    }
  ]
}
```

A related, easy-to-miss ECR detail (change as of January 2026): ECR now stores each unique layer once across all repositories in the same private registry, deduplicating shared base-image layers rather than storing them once per repository — a meaningful storage reduction for orgs with many services sharing a common base image, and worth knowing as a current fact rather than assuming pre-2026 per-repository storage behavior still holds.

### Signing: why keyless beats long-lived keys, mechanically

Docker Content Trust / Notary v1 (2015) required managing a root/targets/snapshot/timestamp key hierarchy per repository — real key material you had to generate, distribute to every signer, protect, and rotate, and the UX friction was high enough that adoption stayed low outside security-forward shops. Sigstore/cosign's keyless model replaces long-lived keys with a short-lived, identity-bound flow: the signer authenticates via OIDC (a CI system's workload identity, a developer's SSO), Fulcio (Sigstore's certificate authority) issues a certificate valid for minutes binding that OIDC identity to an ephemeral signing keypair, cosign signs the image manifest with that ephemeral key, and Rekor (Sigstore's transparency log) permanently records the signature event — so verification later checks "was this signed by a certificate Fulcio issued to this specific CI identity, and is that signature durably logged in Rekor," not "do I trust whoever currently holds this long-lived private key."

```bash
# untested sketch — keyless sign in CI (GitHub Actions OIDC identity), then verify
cosign sign --yes 123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp@$DIGEST

cosign verify \
  --certificate-identity "https://github.com/org/repo/.github/workflows/build.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp@$DIGEST
```

Signing without admission-time verification is theater — the signature exists but nothing checks it before deploy. The mechanism that makes it real:

```yaml
# untested sketch — Kyverno ClusterPolicy: reject unsigned images at admission
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata: { name: verify-image-signatures }
spec:
  validationFailureAction: Enforce   # not Audit -- a real block, not a log line
  rules:
  - name: check-signature
    match: { resources: { kinds: [Pod] } }
    verifyImages:
    - imageReferences: ["123456789012.dkr.ecr.us-east-1.amazonaws.com/*"]
      attestors:
      - entries:
        - keyless:
            subject: "https://github.com/org/repo/.github/workflows/build.yml@refs/heads/main"
            issuer: "https://token.actions.githubusercontent.com"
```

`validationFailureAction: Audit` instead of `Enforce` is the specific, checkable trap — a policy in audit mode logs violations but lets unsigned images through, which is indistinguishable from "we have signing" in a slide deck and indistinguishable from "we have no enforcement" in an actual incident.

### SBOM: what it catches, what it structurally cannot

An SBOM (Software Bill of Materials, CycloneDX or SPDX format) is a structured inventory of every component a generator could statically identify in an image or artifact — direct dependencies from manifest files (`package.json`, `requirements.txt`, `pom.xml`), OS packages from the base image's package manager database, and (with varying reliability) transitive dependencies resolved from lockfiles. Syft (Anchore) and Trivy's built-in SBOM mode are the two dominant generators; Grype (Anchore) and Trivy's scan mode consume an SBOM and match its component list against a CVE database (NVD, GitHub Advisories, vendor feeds) to produce the actual vulnerability report.

The catch: an SBOM answers "what did we find," not "what's actually in the image." Real, checkable gaps: Trivy and Syft both encounter parsing failures on `requirements.txt` when a dependency is specified as a bare package name or a version range rather than a pinned `==` version, silently under-reporting; transitive dependency resolution is measurably weaker for compiled/shaded artifacts (Java uber-jars that bundle relocated dependencies, JavaScript bundles produced by webpack/esbuild that flatten and rename imports) where the original dependency graph isn't statically recoverable from the built artifact alone. A November 2025 empirical study on SBOM-based vulnerability management found these gaps aren't edge cases — they're common enough to materially undercount real vulnerability exposure in typical CI-generated SBOMs. The honest framing for an interview: a clean Grype/Trivy scan against an SBOM means "no known CVE matched what we could statically enumerate," which is a real, useful signal and not the same claim as "no vulnerabilities," and the gap between those two claims is exactly where compiled-artifact and version-range blind spots live.

---

## Build it from scratch

A minimal CI stage chaining build, SBOM, sign, and promotion together — the sequence most worth being able to describe cold in an interview:

```bash
# untested sketch — one CI job: build, SBOM, sign, push; a later job promotes by digest
docker build -t myapp:ci-$COMMIT_SHA .
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' myapp:ci-$COMMIT_SHA)

# SBOM generation, CycloneDX format
syft "myapp:ci-$COMMIT_SHA" -o cyclonedx-json > sbom.cdx.json

# scan the SBOM (not the raw image) against known CVEs
grype sbom:sbom.cdx.json --fail-on high

# push, then sign the pushed digest with a keyless OIDC identity
docker push "$REGISTRY/myapp@$DIGEST"
cosign sign --yes "$REGISTRY/myapp@$DIGEST"

# attach the SBOM itself as a signed attestation, not just a side artifact
cosign attest --yes --predicate sbom.cdx.json --type cyclonedx "$REGISTRY/myapp@$DIGEST"

# --- separate, later promotion job, no rebuild ---
cosign verify --certificate-identity-regexp ".*" --certificate-oidc-issuer "https://token.actions.githubusercontent.com" "$REGISTRY/myapp@$DIGEST"
crane tag "$REGISTRY/myapp@$DIGEST" staging
```

`cosign attest` binding the SBOM to the image as a signed in-toto attestation (rather than storing it as an unsigned side file someone could swap) is the detail that turns "we generate SBOMs" into something admission control could actually verify later.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Registry storage costs climb steadily with no corresponding growth in active image usage | No lifecycle policy — every registry retains pushed images indefinitely by default, and CI pushes far more untagged intermediate images than anyone references again | Attach a lifecycle policy pruning untagged images after ~14 days and capping tagged image count per repo; commonly cuts storage 50-80% |
| "It passed staging" but prod behaves differently on what looks like identical code | Environment-specific *rebuild* instead of promotion — an unpinned base image tag or a resolved transitive dependency differed between the staging build and the prod build | Promote the same digest via retag/cross-registry copy; never rebuild per environment; pin base images by digest in the Dockerfile as a complementary safeguard |
| A Kyverno/admission-control signing policy exists, but an unsigned image still deployed | Policy set to `validationFailureAction: Audit` instead of `Enforce` — violations are logged, not blocked | Set the policy to `Enforce` for any image reference pattern that's actually meant to be a hard gate; treat `Audit` as a rollout stage, not a steady state |
| A base image with a critical CVE sat in the registry for months undetected after passing scan-on-push clean | Scan-on-push only scans once, at push time; it doesn't re-scan already-pushed images as new CVEs are published against the same package versions | Use continuous/enhanced scanning (ECR enhanced scanning + Inspector, or a scheduled Grype/Trivy re-scan job) rather than relying on the one-time push-time scan alone |
| A Grype/Trivy scan against a generated SBOM reports zero vulnerabilities, but a manual audit finds a known-CVE'd transitive dependency | The SBOM generator failed to resolve a transitive dependency inside a compiled/shaded artifact (a Java uber-jar, a bundled JS artifact), or parsed a `requirements.txt` version range/bare package name incorrectly | Treat a clean SBOM scan as "no known CVE in what was statically enumerable," not proof of absence; supplement with source-level (pre-build) dependency scanning where the full, unflattened dependency graph is still visible |
| Two teams both push `myapp:latest` and a deploy pulls the wrong build | Mutable tags used as the actual deploy reference instead of immutable digests | Deploy manifests should reference the image by digest (`myapp@sha256:...`), with tags used only as human-readable labels layered on top, not as the source of truth |
| A polyglot org runs three different artifact tools (a container registry, a separate Maven repo, a separate npm registry) with three different retention/scanning policies | Registry choice made per-team/per-language rather than as a deliberate org-wide decision | Consolidate onto Artifactory or Nexus specifically when the pain of policy fragmentation (three retention configs, three scanning setups, three sets of credentials) exceeds the cost of a single consumption-billed platform |

---

## Tradeoffs & when NOT to use it

- **Don't pick ECR for a polyglot org that also needs Maven/npm/PyPI artifact management.** ECR is containers-only; forcing a second, separate artifact tool for everything else just to save on ECR's simplicity is usually a net loss versus Artifactory/Nexus's single consumption-billed platform, once you account for the operational cost of running and securing two systems instead of one.
- **Don't rebuild per environment "just this once" for a hotfix.** The entire value of promotion is that the digest deployed to prod is *provably* the digest that passed every prior gate — a single exception breaks that guarantee exactly when it matters most (an urgent, under-pressure fix is the worst time to introduce an unverified artifact).
- **Don't treat scan-on-push as sufficient for anything long-lived.** A clean scan at push time says nothing about CVEs published against the same package versions six months later; anything handling sensitive data needs continuous/enhanced rescanning, not a one-time check.
- **Don't adopt keyless signing without also wiring admission-control verification.** A signed-but-unverified image is no more secure at deploy time than an unsigned one — the enforcement point is what makes signing meaningful, not the signing step alone.
- **Don't treat an SBOM as a completeness guarantee, especially for compiled/shaded Java or bundled JavaScript artifacts.** If a compliance requirement genuinely needs full transitive visibility, pair the built-artifact SBOM with a source-level dependency scan (before compilation/bundling flattens the graph) rather than trusting the built artifact's SBOM alone.
- **Don't set signing/SBOM policy to audit-only and call it done.** Audit mode is a legitimate rollout stage (measure violation rate before breaking builds), but it is not equivalent to enforcement, and presenting it as equivalent in an incident review is a real, checkable gap.

---

## Interview questions

### Q1 — Why is "promote by rebuild" considered wrong, given the source code is identical?
**Testing:** whether the digest-immutability argument is understood, not just the slogan "don't rebuild."
**Answer:** A rebuild re-resolves everything not pinned by digest at build time — an unpinned base image tag (`FROM node:20`) can resolve a different point release days later, and transitive dependencies resolved from a lockfile range can shift. Identical source doesn't guarantee an identical resulting image; only promoting the actual built digest does.
**Follow-up trap:** *"If every base image and dependency were pinned exactly, would rebuilding be safe?"* — closer to safe, but still not equivalent: you'd also need bit-for-bit reproducible builds (deterministic timestamps, build IDs, compiler output) to guarantee an identical digest, which most toolchains don't provide out of the box — promoting the actual artifact avoids depending on that guarantee at all.

### Q2 — What does ECR charge for storage, and what's the real-world number for how much a lifecycle policy typically saves?
**Testing:** concrete cost numbers, not "it depends on usage."
**Answer:** $0.10/GB-month for image storage. A lifecycle policy pruning untagged images older than roughly 14 days typically cuts ECR storage 50-80% in an unmanaged repository, since CI pushes far more untagged intermediate images than get referenced again.
**Follow-up trap:** *"Does a lifecycle policy risk deleting an image still referenced by a running deployment?"* — a properly scoped policy (tagged-image count limits, untagged-only expiration by age) shouldn't touch images still tagged and in active use, but a policy that's too aggressive on tagged-image retention count can delete an older tagged release still referenced by a rollback plan — size the tagged-image retention count to cover your actual rollback window, not an arbitrary small number.

### Q3 — Explain Sigstore/cosign keyless signing mechanically. What problem does it solve versus Notary v1/Docker Content Trust?
**Testing:** the actual cryptographic/operational flow, not just "cosign does keyless signing."
**Answer:** The signer authenticates via OIDC; Fulcio issues a short-lived certificate binding that OIDC identity to an ephemeral keypair; cosign signs with the ephemeral key; Rekor durably logs the signature event in a transparency log. This replaces Notary v1's requirement to generate, distribute, protect, and rotate long-lived root/targets/snapshot/timestamp keys per repository — verification checks identity-and-transparency-log provenance instead of long-lived key custody.
**Follow-up trap:** *"If the ephemeral key only lives minutes, how does verification work months later?"* — verification doesn't need the ephemeral key to still exist; it checks the Fulcio-issued certificate (itself signed by Sigstore's root CA and bound to the OIDC identity, with a defined validity window) plus the durable Rekor log entry recording that the signing event happened at a specific time by a specific identity — the transparency log, not the key, is what persists.

### Q4 — A Kyverno policy exists to verify image signatures at admission, but an unsigned image still deployed successfully. What's the most likely misconfiguration?
**Testing:** the specific, checkable enforcement-mode trap.
**Answer:** `validationFailureAction` set to `Audit` instead of `Enforce` — the policy logs the violation but doesn't block the admission request. This is easy to miss because the policy "exists and works" in the sense that it correctly identifies the violation; it just doesn't act on it.
**Follow-up trap:** *"Why would a team deliberately run in Audit mode at all?"* — as a rollout stage: enabling Enforce immediately on an existing fleet with unsigned legacy images in flight would break deployments outright; Audit mode lets a team measure the violation rate and fix real deploys first, then flip to Enforce once the violation rate is at or near zero — the trap is treating Audit as a permanent steady state rather than a temporary rollout phase.

### Q5 — What does an SBOM actually contain, and name a concrete case where a clean SBOM-based scan misses a real vulnerability.
**Testing:** whether SBOM limitations are understood specifically, not just "SBOMs are good practice."
**Answer:** An SBOM lists components a generator could statically identify — direct manifest dependencies, OS packages, and (with varying reliability) resolved transitive dependencies. A concrete miss: a Java uber-jar that shades/relocates a vulnerable transitive dependency into renamed packages, or a webpack/esbuild-bundled JS artifact that flattens imports — the generator can't statically recover the original, un-flattened dependency graph from the built artifact, so a genuinely vulnerable component simply doesn't appear in the SBOM, and a scan against that SBOM reports clean.
**Follow-up trap:** *"How would you catch what the built-artifact SBOM misses?"* — generate a second SBOM/dependency scan at the source level, before compilation/bundling flattens the graph (scanning `pom.xml`'s full resolved dependency tree, or the pre-bundle `package-lock.json`), since the full dependency graph is still recoverable there even though it won't be in the final compiled/bundled artifact.

### Q6 — Why does ECR authentication for EKS/ECS need no `imagePullSecrets` for same-account pulls, while Artifactory/Nexus typically does?
**Testing:** cross-module synthesis with T12-eks-ecs-ecr's IAM coverage, applied to registry choice.
**Answer:** ECR authenticates same-account, same-region pulls automatically via the node's own IAM role (or Fargate task execution role) — no separate credential object needed. Artifactory/Nexus have no native AWS IAM integration; they need an explicit Kubernetes `imagePullSecrets`-referenced Secret holding registry credentials, the same mechanism required for any third-party registry.
**Follow-up trap:** *"Does this make ECR strictly better for a team also needing Maven/npm artifact management?"* — no — it's a real, concrete simplicity advantage specifically for container pulls in an AWS-native cluster, but it doesn't offset ECR's complete lack of non-container artifact support; a polyglot org would still end up running Artifactory/Nexus alongside ECR (or instead of it) for everything else, at which point the IAM-simplicity advantage applies to only one slice of the org's artifact needs.

### Q7 — What's the actual pricing model difference between Artifactory/Nexus and ECR, and why does it matter for a team with high pull volume?
**Testing:** whether "it's more expensive" is backed by the actual mechanism.
**Answer:** ECR bills storage only ($0.10/GB-month); data transfer/egress is billed separately under standard AWS data transfer pricing. Artifactory and Nexus Pro bill storage *and* data transfer combined as a single consumption number (commonly $0.90-1.10/GB for Nexus beyond an included tier) — so a team with high pull volume (many CI runners re-pulling the same images repeatedly, or many developer machines pulling directly) sees transfer volume hit the same consumption meter as storage, which can make the bill grow with usage pattern, not just stored data volume.
**Follow-up trap:** *"How would you reduce that consumption bill without changing registries?"* — reduce redundant pulls: cache images on CI runners/self-hosted agents so repeated pipeline runs don't re-pull an unchanged base layer, and consider a pull-through cache or regional mirror so distributed developer/CI pulls hit a local cache instead of round-tripping to the primary registry on every pull.

### Q8 — Your org's ECR bill has grown steadily for a year with no corresponding growth in deployed workload count. Walk through the diagnosis.
**Testing:** an applied version of the retention-symptom failure mode.
**Answer:** Check for the absence of lifecycle policies first — pull the per-repository storage size and untagged-image count; a large ratio of untagged-to-tagged images pushed by CI over time with no expiration rule is the most common cause. Also check for the pre-2026 per-repository layer storage behavior if the registry predates the January 2026 cross-repository layer deduplication change — many services sharing an unpinned base image previously stored that base image's layers once *per repository* rather than once per registry.
**Follow-up trap:** *"After adding a lifecycle policy, the bill barely drops. What else could be going on?"* — check whether the policy's rules actually match the images accumulating (e.g., a rule targeting `tagStatus: untagged` doesn't touch a large number of *tagged* CI-preview images like `pr-1042`, `pr-1043` that nobody ever untags or deletes) — the rule needs to target the actual accumulation pattern, not just exist.

### Q9 — Design a CI pipeline stage that builds, SBOMs, signs, and promotes an image, and explain why the SBOM should be attached as a signed attestation rather than a plain file.
**Testing:** synthesis of the whole module into one pipeline design, plus the specific reasoning for attestation over a side artifact.
**Answer:** Build once, generate an SBOM (Syft/Trivy) against the built image, scan the SBOM for known CVEs and fail the build above a severity threshold, push the image, sign the pushed digest with cosign (keyless, OIDC-bound), and attach the SBOM as a `cosign attest` in-toto attestation tied to that same digest rather than storing it as an unsigned file next to the image. A later promotion stage retags/copies the same verified digest through environments without rebuilding. Attaching the SBOM as a signed attestation means admission control (or an auditor) can verify the SBOM itself hasn't been swapped or tampered with after the fact — a plain SBOM file sitting in an artifact store has no cryptographic binding to the specific image digest it claims to describe.
**Follow-up trap:** *"What happens if the SBOM generation step finds a critical CVE after the image is already pushed but before signing?"* — fail the pipeline before the sign step, ideally before push at all — signing an image known to contain a critical CVE and shipping it anyway defeats the entire purpose of scanning; the correct gate order is build → SBOM/scan (fail here on policy violation) → sign → push → promote, not sign-then-scan.

### Q10 — A team argues that since they use Docker Content Trust (Notary v1), they already have image signing covered and don't need to adopt cosign/Sigstore. Evaluate that claim.
**Testing:** whether the practical, not just theoretical, gap between Notary v1 and Sigstore is understood.
**Answer:** Notary v1/DCT is real signing, but its key-management model (a root/targets/snapshot/timestamp key hierarchy the team must generate, distribute to every signer, and protect/rotate itself) is exactly the operational friction that kept adoption low and that Sigstore's keyless, OIDC-identity-bound model was built to remove. If the team is actually operating DCT correctly today, that's a legitimate existing control, not nothing — but it's worth checking whether "we have DCT enabled" actually means keys are properly rotated and distributed, versus a root key generated once in 2019 sitting in one engineer's laptop, which is a common, quiet failure mode of the DCT model in practice.
**Follow-up trap:** *"Is Notary v2/Notation a reasonable alternative to cosign instead, if the team wants to stay closer to the Notary lineage?"* — Notation (the CNCF-continued Notary v2 successor) is a legitimate, OCI-native signing spec some enterprises use, and it's a reasonable choice where its specific tooling/ecosystem fit is better — but cosign/Sigstore's keyless model and broader ecosystem adoption (Kyverno, Connaisseur, most admission-control tooling) make it the more common default to reach for absent a specific reason to prefer Notation.

### Q11 — What's the difference between what Grype/Trivy report when scanning a live image directly versus scanning a pre-generated SBOM?
**Testing:** whether the two-step (generate SBOM, then scan the SBOM) versus one-step (scan the image directly) distinction is understood as more than a workflow preference.
**Answer:** Scanning a live image directly re-derives the component inventory at scan time from the image's actual filesystem/package metadata; scanning a pre-generated SBOM matches against whatever the SBOM generator already captured, which could be stale if the SBOM was generated earlier and the image was modified afterward (unlikely for immutable digests, but real if someone re-tags or re-pushes under the same tag). The practical reason to prefer the SBOM-based path in CI is speed and reuse — one SBOM generation feeds multiple downstream scans (a CVE scan now, a license-compliance check later, an attestation) without re-parsing the image each time.
**Follow-up trap:** *"Does scanning a pre-generated SBOM ever catch something a direct image scan misses, or vice versa?"* — a direct image scan can sometimes catch runtime-installed packages or files an SBOM generator's static analysis missed (e.g., something installed via a script rather than a package manager the generator understands); an SBOM-based scan is bounded strictly by whatever the generator successfully enumerated — so for a genuinely high-assurance scan, running both and reconciling differences is more thorough than trusting either alone.

### Q12 — A regulated-industry client requires "verifiable provenance," not just signed images. What's the difference, and what closes that gap?
**Testing:** whether SLSA-style provenance attestations are understood as a distinct, additional layer beyond signature verification.
**Answer:** Signature verification proves "this specific artifact wasn't tampered with after signing, and the signer's identity is known" — it says nothing about *how* the artifact was built (which source commit, which build pipeline, whether the build environment itself could have been compromised). A SLSA provenance attestation is a separate, signed claim about the build process itself — the exact source revision, builder identity, and build parameters — attached to the artifact the same way an SBOM attestation is, verifiable independently at admission time.
**Follow-up trap:** *"If an image is signed and has a valid SBOM attestation, is that sufficient for SLSA level 2+?"* — not by itself; SLSA levels are about the build process's integrity guarantees (a trusted build service, generated provenance, tamper resistance of the build platform), not solely about what's attached to the final artifact — a signed image and SBOM are necessary supporting evidence, but the actual SLSA level achieved depends on properties of the build pipeline that produced them, which needs separate verification.

---

## Red flags that fail you

- Recommending rebuilding a fresh image per environment instead of promoting a single built digest, without naming what breaks (unpinned base image drift, transitive dependency drift).
- Not knowing that every registry retains images indefinitely by default, or having no real number for how much a lifecycle policy typically saves.
- Describing image signing as "done" once a signature exists, without mentioning admission-control verification as the actual enforcement point.
- Confusing scan-on-push (a one-time check) with continuous rescanning, or assuming a clean scan at push time stays valid indefinitely.
- Treating an SBOM as a complete, guaranteed inventory rather than naming the transitive-dependency/compiled-artifact gap explicitly.
- Not knowing the difference between Notary v1 (Docker Content Trust) and Sigstore/cosign's keyless model, or why keyless signing reduces operational key-management burden.
- Picking ECR for a polyglot org's full artifact strategy without acknowledging it's containers-only.
- Setting a signing/SBOM policy to audit-only and treating that as equivalent to enforcement.

---

## Cheat card

```
REGISTRY CHOICE: ECR (AWS-native, IAM-integrated, containers ONLY, $0.10/GB-mo
  storage) | Artifactory/Nexus (polyglot: containers+Maven+npm+PyPI+Helm,
  consumption billing ~$0.90-1.10/GB storage+transfer combined) | GHCR
  (GitHub-centric, free public storage, native GH Actions OIDC signing)

PROMOTION: promote the SAME DIGEST (retag / skopeo / crane copy), NEVER
  rebuild per environment -- rebuild can silently resolve a different
  base-image layer or transitive dep even with identical source.

RETENTION: every registry retains pushed images FOREVER by default.
  Lifecycle policy pruning untagged images >14d typically cuts ECR
  storage 50-80%. ECR (Jan 2026+): layers deduped ACROSS repos in a
  registry, not per-repo.

SIGNING: cosign/Sigstore KEYLESS = OIDC identity -> Fulcio short-lived
  cert -> sign -> Rekor transparency log. Replaces Notary v1/DCT's
  long-lived root/targets/snapshot/timestamp key management pain.
  Notation (Notary v2 successor, CNCF) = alternative, less dominant.
  SIGNING WITHOUT ADMISSION-CONTROL VERIFICATION = theater. Kyverno
  validationFailureAction: Enforce (not Audit) is the actual gate.

SBOM: Syft/Trivy generate (CycloneDX/SPDX), Grype/Trivy scan against
  CVE DB. CATCHES: known-CVE direct deps with clean manifest metadata.
  MISSES: transitive deps in compiled/shaded Java (uber-jars) or
  bundled JS -- graph not statically recoverable post-build. Clean
  SBOM scan = "no known CVE in what we could enumerate," NOT "no vulns."
  Attach SBOM as a cosign ATTESTATION (signed, digest-bound), not a
  loose file -- otherwise it can be swapped undetected.

SLSA PROVENANCE: a separate signed claim about HOW an artifact was
  built (source commit, builder identity) -- layered ON TOP of
  signature verification, not a replacement for it.
```

## Sources

- [Amazon ECR Pricing: What $0.10/GB Doesn't Tell You — Cloud Burn](https://cloudburn.io/blog/amazon-ecr-pricing) — accessed 2026-08-03
- [ECR Storage Cost Optimization and Image Management — DEV Community](https://dev.to/safdarwahid/ecr-storage-cost-optimization-and-image-management-27k3) — accessed 2026-08-03
- [AWS ECR: Container Registry, Image Scanning and Lifecycle Policies (2026)](https://techoral.com/aws/aws-ecr-guide.html) — accessed 2026-08-03
- [Sigstore Keyless Signing and Cosign Verification: Fulcio, Rekor, and Policy Enforcement](https://www.systemshardening.com/articles/cicd/sigstore-keyless-signing/) — accessed 2026-08-03
- [Sigstore | Kyverno docs](https://main.kyverno.io/docs/policy-types/cluster-policy/verify-images/sigstore/) — accessed 2026-08-03
- [A Reality Check on SBOM-based Vulnerability Management: An Empirical Study and A Path Forward — arXiv](https://arxiv.org/html/2511.20313v1) — accessed 2026-08-03
- [SBOM Generation Tools Compared: Syft, Trivy, cdxgen, and More — Sbomify](https://sbomify.com/2026/01/26/sbom-generation-tools-comparison/) — accessed 2026-08-03
- [JFrog Artifactory Pricing Guide 2026 — CloudRepo](https://www.cloudrepo.io/articles/jfrog-artifactory-pricing-guide) — accessed 2026-08-03
- [Best Sonatype Nexus Repository Alternatives in 2026 — CloudRepo](https://www.cloudrepo.io/articles/best-nexus-alternatives) — accessed 2026-08-03
- [Docker Image Build and Promotion Pipeline: A Production Guide — devopscube](https://devopscube.com/docker-image-build-and-promotion-pipeline/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
