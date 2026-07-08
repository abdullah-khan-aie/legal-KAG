variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "aws_profile" {
  type    = string
  default = "sandbox"
}

variable "project" {
  type    = string
  default = "lodestone"
}

variable "env" {
  description = "Resource name prefix (lodestone-{env}). Keep 'poc' — matches deployed Neo4j; do not change or Neo4j will be replaced."
  type        = string
  default     = "poc"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.20.1.0/24"
}

variable "private_subnet_cidr" {
  type    = string
  default = "10.20.2.0/24"
}

# --- Neo4j (graph store) -----------------------------------------------------

variable "neo4j_instance_type" {
  type    = string
  default = "r7g.large"
}

variable "neo4j_data_volume_gb" {
  type    = number
  default = 50
}

variable "neo4j_image" {
  type    = string
  default = "neo4j:5"
}

variable "neo4j_password" {
  type      = string
  sensitive = true
}

variable "neo4j_heap_size" {
  type    = string
  default = "4g"
}

variable "neo4j_pagecache_size" {
  type    = string
  default = "9g"
}

# --- Lodestone app (FastAPI + KAG pipeline) ----------------------------------

variable "lodestone_app_enabled" {
  type    = bool
  default = false
}

variable "lodestone_app_instance_type" {
  description = "Pipeline EC2 — t3.large (2 vCPU / 8 GiB RAM)."
  type        = string
  default     = "t3.large"
}

variable "lodestone_app_port" {
  type    = number
  default = 8080
}

variable "lodestone_git_repo_url" {
  type    = string
  default = "git@github.com:abdullah-khan-aie/lodestone-graphrag.git"
}

variable "lodestone_github_deploy_key_secret_id" {
  description = "Secrets Manager id for GitHub deploy key private key (see infra/scripts/setup_github_deploy_key.sh)."
  type        = string
  default     = "lodestone/github-deploy-key"
}

variable "lodestone_deploy_with_docker" {
  type    = bool
  default = false
}

variable "lodestone_ecr_enabled" {
  type    = bool
  default = false
}

variable "lodestone_git_ref" {
  type    = string
  default = "feat/kag-rag-engine"
}

variable "lodestone_bedrock_llm_model" {
  type    = string
  default = "anthropic.claude-sonnet-4-6"
}

variable "lodestone_bedrock_embed_model" {
  type    = string
  default = "cohere.embed-v4:0"
}

variable "lodestone_max_concurrency" {
  type    = number
  default = 1
}

variable "lodestone_secret_id" {
  type    = string
  default = "lodestone/env"
}

variable "lodestone_scan_dir" {
  type    = string
  default = "/data/ingest"
}

variable "lodestone_data_volume_gb" {
  type    = number
  default = 20
}

variable "lodestone_allow_public_http" {
  type    = bool
  default = false
}

variable "lodestone_public_ingress_cidrs" {
  type    = list(string)
  default = []
}

variable "lodestone_public_api_enabled" {
  description = "Create public API Gateway -> VPC Link -> internal NLB -> app EC2."
  type        = bool
  default     = false
}

# --- CI/CD (GitHub Actions OIDC deploy) --------------------------------------

variable "github_deploy_enabled" {
  description = "Create GitHub Actions OIDC deploy role (ECR push + SSM redeploy)."
  type        = bool
  default     = false
}

variable "github_repo" {
  description = "GitHub repo (owner/name) allowed to assume the deploy role."
  type        = string
  default     = "abdullah-khan-aie/lodestone-graphrag"
}

variable "github_branch" {
  type    = string
  default = "main"
}

variable "github_create_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if the account already has one."
  type        = bool
  default     = true
}
