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
