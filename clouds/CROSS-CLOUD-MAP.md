# Cross-Cloud Equivalence Map

> Updated 2026-07-26 · maintained by `/tutor-update`

The single most useful cloud artifact in an interview. When someone says "we're on Azure" and your experience is AWS, this is what lets you answer anyway.

**The move:** name the equivalent, then immediately name the *difference*. "Cloud Run is roughly Fargate, except it scales to zero and bills per request — which changes how you think about cold starts." That second clause is the signal.

---

## Compute

| Capability | AWS | Azure | GCP | Watch out |
|---|---|---|---|---|
| VMs | EC2 | Virtual Machines | Compute Engine | GCP bills per-second w/ sustained-use discounts automatically; AWS needs Savings Plans |
| Autoscaling group | ASG | VM Scale Sets | Managed Instance Group | |
| Managed K8s | EKS | AKS | GKE (+ Autopilot) | GKE Autopilot is the most hands-off; EKS charges for the control plane |
| Serverless containers | Fargate / App Runner | Container Apps | **Cloud Run** | Cloud Run scales to zero and is request-billed — Fargate does not scale to zero |
| PaaS | Elastic Beanstalk | App Service | App Engine | |
| Batch | AWS Batch | Azure Batch | Cloud Batch | |
| FaaS | **Lambda** | **Functions** | **Cloud Functions** | See the serverless deep dives — execution models differ a lot |
| Stateful workflow | Step Functions | Durable Functions | Workflows | Durable Functions is code-first; Step Functions is state-machine-first |

## Storage

| Capability | AWS | Azure | GCP | Watch out |
|---|---|---|---|---|
| Object | S3 | Blob Storage | Cloud Storage | S3 is now strongly read-after-write consistent — old "eventual consistency" answers are stale |
| Block | EBS | Managed Disks | Persistent Disk / Hyperdisk | |
| File | EFS / FSx | Azure Files | Filestore | |
| Archive | Glacier / Deep Archive | Archive tier | Archive class | Retrieval latency and minimum-duration charges differ sharply |

## Databases

| Capability | AWS | Azure | GCP | Watch out |
|---|---|---|---|---|
| Managed relational | RDS | Azure SQL / Flexible Server | Cloud SQL | |
| Cloud-native relational | **Aurora** | Azure SQL Hyperscale | **AlloyDB** | All three separate compute from a distributed storage layer |
| Global relational | Aurora Global | Cosmos DB (SQL API) | **Spanner** | Spanner gives external consistency via TrueTime — genuinely unique |
| Key-value / document | **DynamoDB** | **Cosmos DB** | Firestore / **Bigtable** | Bigtable ≈ HBase (wide-column, no secondary indexes); Firestore ≈ document |
| Wide-column | Keyspaces | Cosmos (Cassandra API) | Bigtable | |
| In-memory | ElastiCache / MemoryDB | Azure Cache for Redis | Memorystore | MemoryDB is durable Redis — the others are caches |
| Graph | Neptune | Cosmos (Gremlin) | — | |
| Warehouse | Redshift | Synapse / Fabric | **BigQuery** | BigQuery is fully serverless and query-billed; Redshift is cluster-billed |
| Search | OpenSearch | AI Search | — (use Elastic on GKE) | |
| Vector | OpenSearch / Aurora pgvector / Kendra | AI Search vectors | Vertex AI Vector Search | See T17 for when a dedicated vector DB beats these |

## Networking

| Capability | AWS | Azure | GCP |
|---|---|---|---|
| Virtual network | VPC | VNet | VPC (global, not regional — key difference) |
| Firewall | Security Group + NACL | NSG | Firewall rules |
| L7 load balancer | ALB | Application Gateway | Cloud Load Balancing (global anycast) |
| L4 load balancer | NLB | Load Balancer | Cloud Load Balancing |
| CDN | CloudFront | Front Door / CDN | Cloud CDN |
| DNS | Route 53 | Azure DNS | Cloud DNS |
| Private service access | PrivateLink | Private Link | Private Service Connect |
| WAF | AWS WAF | Front Door WAF | Cloud Armor |
| Hybrid | Direct Connect | ExpressRoute | Interconnect |

> **Interview gold:** GCP VPCs are *global* — one VPC spans regions with subnets per region. AWS and Azure virtual networks are regional. This changes multi-region design.

## Identity & access

| Capability | AWS | Azure | GCP | Watch out |
|---|---|---|---|---|
| Model | IAM users/roles/policies | Entra ID + RBAC | IAM roles + members | AWS = policy attached to principal *and* resource; GCP = role bindings on a resource hierarchy |
| Workload identity | IAM role for EC2/EKS (IRSA) | Managed Identity | Workload Identity Federation | All three exist so you never ship a static key |
| Temp credentials | STS AssumeRole | Managed Identity token | Service account impersonation | |
| Org guardrails | SCPs (Organizations) | Azure Policy + Mgmt Groups | Org Policy + folders | |
| Secrets | Secrets Manager / SSM Param | Key Vault | Secret Manager | |
| Key management | KMS | Key Vault / Managed HSM | Cloud KMS | |

## Data & analytics

| Capability | AWS | Azure | GCP |
|---|---|---|---|
| Managed Spark | EMR / Glue | Synapse Spark / Databricks | Dataproc |
| Serverless ETL | Glue | Data Factory | Dataflow (Beam) |
| Streaming ingest | Kinesis | Event Hubs | Pub/Sub |
| Managed Kafka | MSK | Event Hubs (Kafka API) | Managed Kafka |
| Query-in-place | Athena | Synapse Serverless | BigQuery external tables |
| Orchestration | MWAA (Airflow) | Data Factory | Cloud Composer (Airflow) |
| BI | QuickSight | Power BI | Looker |

## Messaging & integration

| Capability | AWS | Azure | GCP |
|---|---|---|---|
| Queue | SQS | Service Bus / Storage Queue | Pub/Sub (pull) |
| Pub-sub | SNS | Event Grid | Pub/Sub |
| Event bus | EventBridge | Event Grid | Eventarc |
| API gateway | API Gateway | API Management | API Gateway / Apigee |

## AI / ML / GenAI

| Capability | AWS | Azure | GCP |
|---|---|---|---|
| ML platform | SageMaker | Azure ML | Vertex AI |
| Foundation-model API | **Bedrock** | **Azure OpenAI / AI Foundry** | **Vertex AI / Gemini API** |
| Agent framework | Bedrock Agents / AgentCore | AI Foundry Agents | Agent Builder / ADK |
| Managed RAG | Bedrock Knowledge Bases / Kendra | AI Search + Foundry | Vertex AI Search |
| Notebooks | SageMaker Studio | Azure ML Studio | Vertex AI Workbench / Colab Enterprise |
| Doc AI | Textract | Document Intelligence | Document AI |
| Speech | Transcribe / Polly | Azure Speech | Speech-to-Text / TTS |

## Observability & ops

| Capability | AWS | Azure | GCP |
|---|---|---|---|
| Metrics + logs | CloudWatch | Monitor + Log Analytics | Cloud Monitoring + Logging |
| Tracing | X-Ray | Application Insights | Cloud Trace |
| Audit | CloudTrail | Activity Log | Cloud Audit Logs |
| IaC (native) | CloudFormation / CDK | ARM / Bicep | Deployment Manager / Config Connector |
| Cost | Cost Explorer | Cost Management | Cloud Billing / FinOps Hub |

---

## The five differences worth memorizing

1. **GCP VPCs are global**; AWS/Azure networks are regional. Multi-region topology differs as a result.
2. **Spanner's external consistency** (TrueTime) has no direct AWS/Azure equivalent — Aurora Global has a read-replica lag; Cosmos offers five tunable consistency levels.
3. **BigQuery is query-billed and serverless**; Redshift and Synapse dedicated pools are cluster-billed. This flips cost modeling from "size the cluster" to "control the scan".
4. **Cloud Run scales to zero**; Fargate does not. For spiky, low-traffic services that is a large cost delta.
5. **IAM shape differs**: AWS evaluates identity policies *and* resource policies with an explicit-deny override; GCP binds roles onto a resource hierarchy that inherits downward; Azure layers RBAC assignments over Entra ID with Azure Policy as a separate guardrail.

## Changelog
- 2026-07-26 — created
