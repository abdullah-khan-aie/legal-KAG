variable "name" {
  type = string
}

variable "project" {
  description = "Short project prefix for IAM policy names (without env suffix)."
  type        = string
}

variable "region" {
  type = string
}

variable "enabled" {
  type    = bool
  default = false
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "availability_zone" {
  type = string
}

variable "neo4j_bolt_uri" {
  type = string
}

variable "app_port" {
  type    = number
  default = 8080
}

variable "instance_type" {
  description = "Pipeline EC2 instance type (default t3.large = 8 GiB RAM)."
  type        = string
  default     = "t3.large"
}

variable "git_repo_url" {
  description = "SSH URL when using a GitHub deploy key, e.g. git@github.com:org/repo.git"
  type        = string
  default     = "git@github.com:abdullah-khan-aie/lodestone-graphrag.git"
}

variable "git_ref" {
  type    = string
  default = "feat/kag-rag-engine"
}

variable "github_deploy_key_secret_id" {
  description = "Secrets Manager secret id holding the GitHub deploy key private key (PEM). Empty = skip git clone."
  type        = string
  default     = ""
}

variable "bedrock_llm_model" {
  type    = string
  default = "anthropic.claude-sonnet-4-6"
}

variable "bedrock_embed_model" {
  type    = string
  default = "cohere.embed-v4:0"
}

variable "max_concurrency" {
  type    = number
  default = 1
}

variable "secret_id" {
  type    = string
  default = "lodestone/env"
}

variable "scan_dir" {
  type    = string
  default = "/data/ingest"
}

variable "data_volume_gb" {
  type    = number
  default = 20
}

variable "allow_public_http" {
  type    = bool
  default = false
}

variable "public_ingress_cidrs" {
  type    = list(string)
  default = []
}

variable "deploy_with_docker" {
  description = "When true, bootstrap via Docker + ECR (no git clone). Requires ecr_enabled."
  type        = bool
  default     = false
}

variable "ecr_enabled" {
  description = "Create ECR repository for the Lodestone image."
  type        = bool
  default     = false
}

variable "ecr_image_tag" {
  type    = string
  default = "latest"
}

variable "cloudwatch_logs_enabled" {
  description = "Create a CloudWatch log group and grant the app instance permission to ship Docker logs."
  type        = bool
  default     = true
}

variable "cloudwatch_log_retention_days" {
  description = "Retention for Lodestone container logs in CloudWatch Logs."
  type        = number
  default     = 7
}
