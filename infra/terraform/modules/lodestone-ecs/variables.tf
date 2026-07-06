# Phase-2: Fargate + ECR (not wired in environments/main.tf yet).

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

variable "secret_id" {
  type    = string
  default = "lodestone/env"
}

variable "ecr_image_tag" {
  description = "Container image tag pushed to ECR (e.g. git sha)."
  type        = string
  default     = "latest"
}
