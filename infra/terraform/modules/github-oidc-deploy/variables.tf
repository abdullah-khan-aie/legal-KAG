variable "name" {
  type = string
}

variable "enabled" {
  type    = bool
  default = false
}

variable "region" {
  type = string
}

variable "github_repo" {
  description = "GitHub repo in owner/name form, e.g. abdullah-khan-aie/legal-kag."
  type        = string
}

variable "github_branch" {
  description = "Branch allowed to assume the deploy role."
  type        = string
  default     = "main"
}

variable "ecr_repository_arn" {
  description = "ARN of the ECR repo the workflow pushes to."
  type        = string
}

variable "app_name_tag" {
  description = "Value of the Name tag on the app EC2; SSM SendCommand is scoped to instances with this tag so CI/CD survives instance replacement."
  type        = string
}

variable "create_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if the account already has one."
  type        = bool
  default     = true
}
