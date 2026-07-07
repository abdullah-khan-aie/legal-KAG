output "api_endpoint" {
  description = "Public HTTPS URL for the Lodestone app."
  value       = var.enabled ? aws_apigatewayv2_stage.default[0].invoke_url : null
}

output "nlb_dns_name" {
  value = var.enabled ? aws_lb.app[0].dns_name : null
}
