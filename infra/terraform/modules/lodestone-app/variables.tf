variable "name" {
  type = string
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
  type    = string
  default = "https://github.com/abdullah-khan-aie/lodestone-graphrag.git"
}

variable "git_ref" {
  type    = string
  default = "feat/kag-rag-engine"
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
