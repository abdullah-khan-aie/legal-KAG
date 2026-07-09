output "api_endpoint" {
  description = "Public HTTPS URL for the Lodestone app (REST API stage invoke URL, e.g. https://<id>.execute-api.<region>.amazonaws.com/prod)."
  value       = var.enabled ? aws_api_gateway_stage.default[0].invoke_url : null
}

output "nlb_dns_name" {
  value = var.enabled ? aws_lb.app[0].dns_name : null
}
