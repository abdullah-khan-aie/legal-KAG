# Lodestone / Lodestone — AWS Infrastructure

Terraform for the **KAG RAG pipeline**: Neo4j graph store + Lodestone FastAPI app (ingest + query + `/ui`).

| | |
|---|---|
| **AWS account** | `123456789012` (sandbox) |
| **Region** | `eu-west-2` (London) |
| **CLI profile** | `sandbox` |
| **App branch** | `feat/kag-rag-engine` |

---

## Architecture

```
                    Internet (egress only for EC2)
                              │
┌─────────────────────────────▼─────────────────────────────────┐
│  VPC 10.20.0.0/16  (lodestone-poc)                            │
│                                                                 │
│  ┌─────────────────────┐      ┌─────────────────────────────┐  │
│  │  Neo4j EC2          │      │  Lodestone app EC2          │  │
│  │  r7g.large (16 GiB) │◄─────│  t3.large (8 GiB)           │  │
│  │  Bolt :7687         │ Bolt │  FastAPI :8080 + /ui        │  │
│  │  GDS plugin         │      │  Bedrock via instance role   │  │
│  │  ✅ DEPLOYED        │      │  ⬜ optional (tfvars flag)  │  │
│  └─────────────────────┘      └─────────────────────────────┘  │
│                                                                 │
│  Private subnet (reserved)                                      │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
   SSM (admin shell)              Secrets Manager: lodestone/env
   No SSH / no public Bolt         LODESTONE_* runtime config
```

**Access model:** Neo4j and the app are **not** open to the internet by default. Admin access is via **SSM Session Manager**. The query UI is reachable only if you allow your IP or public HTTP in tfvars.

---

## Repository layout

```
infra/
├── README.md                          ← this file
├── scripts/                           ← ops helpers (run from repo root)
│   ├── check_terraform_prereqs.sh     pre-flight before terraform apply
│   ├── bootstrap_secrets_lodestone.sh   push .env → Secrets Manager
│   ├── app_pull_and_restart.sh        git pull + restart on app EC2
│   ├── enable_neo4j_gds_on_ec2.sh     manual GDS fix (usually not needed)
│   └── migrate_legacy_terraform_state.sh
└── terraform/
    ├── environments/                  ← **run terraform here**
    │   ├── main.tf                    wires modules together
    │   ├── variables.tf               all tunables
    │   ├── outputs.tf                 Bolt URI, SSM commands, app URL
    │   ├── moved.tf                   state migration (do not delete)
    │   ├── terraform.tfvars           your secrets (gitignored)
    │   └── terraform.tfvars.example
    └── modules/
        ├── network/                   VPC, subnets, internet gateway
        ├── neo4j/                     graph DB EC2 + EBS + GDS
        ├── lodestone-app/             pipeline EC2 (8 GiB RAM)
        └── lodestone-ecs/             future Fargate (not wired yet)
```

### What each module does

| Module | Creates | Status |
|--------|---------|--------|
| **network** | VPC `10.20.0.0/16`, public + private subnet, IGW. No NAT (~$33/mo saved). | Live |
| **neo4j** | `r7g.large`, 50 GB EBS, Docker Neo4j 5 + GDS, Bolt `7687` VPC-only | **Live — do not change** |
| **lodestone-app** | `t3.large` (8 GiB), clones git repo, uvicorn on `:8080`, 20 GB ingest disk | Off until enabled |
| **lodestone-ecs** | ECR + ECS skeleton for a later Docker migration | Not used |

---

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5
- AWS CLI + SSO: `aws sso login --profile sandbox`
- [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) (for SSM shells)
- IAM on sandbox: EC2, VPC, `CreateRole`, `PassRole`, SSM

```bash
./infra/scripts/check_terraform_prereqs.sh
```

---

## First-time setup

```bash
aws sso login --profile sandbox

cd infra/terraform/environments
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set neo4j_password to match the deployed instance

terraform init
terraform plan    # expect: 0 to add, 0 to change, 0 to destroy
```

> **Important:** Keep `env = "poc"` in tfvars. It matches the live resource names (`lodestone-poc`). Changing it would make Terraform **replace Neo4j**.

---

## Deploy the pipeline (Lodestone app EC2)

Neo4j is already running. To add the **ingest + query API**:

**1. Enable in `terraform.tfvars`:**

```hcl
lodestone_app_enabled       = true
lodestone_app_instance_type = "t3.large"   # 8 GiB RAM
lodestone_git_ref           = "feat/kag-rag-engine"
# lodestone_allow_public_http = true        # only for short external /ui demos
```

**2. Apply:**

```bash
cd infra/terraform/environments
terraform plan
terraform apply
```

**3. Push runtime secrets** (from repo root `.env` with `LODESTONE_*` keys):

```bash
AWS_PROFILE=sandbox AWS_REGION=eu-west-2 \
  ./infra/scripts/bootstrap_secrets_lodestone.sh
```

Required in `.env`: at minimum `LODESTONE_NEO4J_PASSWORD`. Bedrock uses the **instance role** on EC2 — no `AWS_PROFILE` on the box.

---

## Day-2 operations

### Terraform outputs

```bash
cd infra/terraform/environments

terraform output -raw neo4j_bolt_uri
terraform output -raw ssm_session_command              # Neo4j shell
terraform output -raw ssm_bolt_port_forward_command    # local Bolt tunnel
terraform output -raw lodestone_app_ssm_session_command
terraform output -raw lodestone_app_url
```

### Ingest documents

1. SSM into the app instance
2. Copy files to `/data/ingest` (or `LODESTONE_SCAN_DIR`)
3. Trigger ingest:

```bash
curl -X POST http://127.0.0.1:8080/ingest
```

### Deploy new app code (without Terraform)

On the app EC2 (or via SSM):

```bash
./infra/scripts/app_pull_and_restart.sh
```

Pulls latest `feat/kag-rag-engine` and restarts `lodestone-app.service`.

### Query UI

After ingest completes, open `/ui/` on port `8080` (same origin as the API — no separate frontend build).

---

## Configuration reference

| Variable | Default | Notes |
|----------|---------|-------|
| `lodestone_app_enabled` | `false` | Set `true` to create pipeline EC2 |
| `lodestone_app_instance_type` | `t3.large` | 2 vCPU / **8 GiB RAM** |
| `lodestone_app_port` | `8080` | API + `/ui` |
| `lodestone_git_ref` | `feat/kag-rag-engine` | Branch cloned on boot |
| `lodestone_max_concurrency` | `1` | Lower = less Bedrock throttling |
| `lodestone_secret_id` | `lodestone/env` | Secrets Manager JSON |
| `lodestone_scan_dir` | `/data/ingest` | Ingest document folder |
| `neo4j_instance_type` | `r7g.large` | **Leave as deployed** |

App runtime env vars use the **`LODESTONE_`** prefix — see `src/lodestone/config/settings.py`.

---

## Cost estimate (24/7, eu-west-2)

| Resource | ~Monthly |
|----------|----------|
| Neo4j `r7g.large` | $92 |
| Neo4j EBS 70 GB | $7 |
| App `t3.large` (when enabled) | $60 |
| App EBS 50 GB | $4 |
| Public IPv4 ×2 | $7 |
| VPC / SSM / Bedrock | usage-based |
| **Total (both EC2)** | **~$170/mo** |

Stop instances when idle; EBS volumes still bill (~$11/mo).

---

## Warnings

1. **Do not change Neo4j** instance type, `env`, or password in Terraform without planning for replacement / data migration.
2. **Do not open** Neo4j ports (`7687` / `7474`) to the internet — VPC + SSM only.
3. **Private GitHub repos** need a deploy key on the app EC2 — Terraform does not manage that yet.
4. `terraform.tfvars` and `terraform.tfstate` are **gitignored** — never commit passwords.

---

## Roadmap (not implemented)

| Item | Module / action |
|------|-----------------|
| Docker + Fargate | `modules/lodestone-ecs` |
| HTTPS + ALB | new ALB module |
| Remote Terraform state | S3 + DynamoDB in `main.tf` |
| Neo4j in private subnet | NAT Gateway or VPC endpoints |

---

## Quick command cheat sheet

```bash
# Login
aws sso login --profile sandbox

# Plan / apply
cd infra/terraform/environments && terraform plan && terraform apply

# Secrets
AWS_PROFILE=sandbox ./infra/scripts/bootstrap_secrets_lodestone.sh

# Neo4j admin
eval $(terraform output -raw ssm_session_command)

# App admin
eval $(terraform output -raw lodestone_app_ssm_session_command)
```
