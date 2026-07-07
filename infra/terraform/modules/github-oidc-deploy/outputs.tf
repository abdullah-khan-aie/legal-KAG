output "deploy_role_arn" {
  description = "IAM role ARN for the GitHub Actions deploy workflow (role-to-assume)."
  value       = var.enabled ? aws_iam_role.deploy[0].arn : null
}

output "oidc_provider_arn" {
  value = local.oidc_provider_arn
}
