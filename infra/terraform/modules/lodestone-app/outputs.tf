output "enabled" {
  value = var.enabled
}

output "instance_id" {
  value = var.enabled ? aws_instance.app[0].id : null
}

output "private_ip" {
  value = var.enabled ? aws_instance.app[0].private_ip : null
}

output "public_ip" {
  value = var.enabled ? aws_instance.app[0].public_ip : null
}

output "url" {
  value = var.enabled ? "http://${aws_instance.app[0].public_ip}:${var.app_port}/ui/" : null
}

output "app_port" {
  value = var.app_port
}

output "ecr_repository_url" {
  value = var.enabled && var.ecr_enabled ? aws_ecr_repository.lodestone[0].repository_url : null
}

output "ecr_image" {
  value = var.enabled && var.ecr_enabled ? local.ecr_image : null
}

output "cloudwatch_log_group_name" {
  value = var.enabled && var.cloudwatch_logs_enabled ? aws_cloudwatch_log_group.lodestone[0].name : null
}

output "cloudwatch_logs_console_url" {
  value = var.enabled && var.cloudwatch_logs_enabled ? "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#logsV2:log-groups/log-group/${replace(aws_cloudwatch_log_group.lodestone[0].name, "/", "$252F")}" : null
}
