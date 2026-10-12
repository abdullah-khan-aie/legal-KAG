# Neo4j
output "neo4j_instance_id" {
  value = module.neo4j.instance_id
}

output "neo4j_private_ip" {
  value = module.neo4j.private_ip
}

output "neo4j_bolt_uri" {
  value = module.neo4j.bolt_uri
}

output "ssm_session_command" {
  value = "aws ssm start-session --target ${module.neo4j.instance_id} --region ${var.region}"
}

output "ssm_bolt_port_forward_command" {
  value = join(" ", [
    "aws ssm start-session --target ${module.neo4j.instance_id} --region ${var.region}",
    "--document-name AWS-StartPortForwardingSession",
    "--parameters '{\"portNumber\":[\"7687\"],\"localPortNumber\":[\"7687\"]}'",
  ])
}

# App app
output "app_enabled" {
  value = module.app.enabled
}

output "app_instance_id" {
  value = module.app.instance_id
}

output "app_url" {
  value = module.app.url
}

output "app_ssm_session_command" {
  value = module.app.instance_id != null ? "aws ssm start-session --target ${module.app.instance_id} --region ${var.region}" : null
}

output "app_ingest_curl" {
  value = module.app.instance_id != null ? "curl -X POST http://127.0.0.1:${module.app.app_port}/ingest" : null
}

output "ecr_repository_url" {
  value = module.app.ecr_repository_url
}

output "ecr_image" {
  value = module.app.ecr_image
}

output "cloudwatch_log_group" {
  value = module.app.cloudwatch_log_group_name
}

output "cloudwatch_logs_console_url" {
  value = module.app.cloudwatch_logs_console_url
}

output "public_api_url" {
  value = module.public_api.api_endpoint
}

output "github_deploy_role_arn" {
  description = "Set as GitHub secret AWS_DEPLOY_ROLE_ARN for the deploy workflow."
  value       = module.github_deploy.deploy_role_arn
}
