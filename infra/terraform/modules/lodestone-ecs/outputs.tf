output "ecr_repository_url" {
  value = var.enabled ? aws_ecr_repository.lodestone[0].repository_url : null
}

output "ecs_cluster_name" {
  value = var.enabled ? aws_ecs_cluster.main[0].name : null
}

output "ecs_task_role_arn" {
  value = var.enabled ? aws_iam_role.ecs_task[0].arn : null
}
