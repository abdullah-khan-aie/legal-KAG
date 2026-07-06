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

# Lodestone app
output "lodestone_app_enabled" {
  value = module.lodestone_app.enabled
}

output "lodestone_app_instance_id" {
  value = module.lodestone_app.instance_id
}

output "lodestone_app_url" {
  value = module.lodestone_app.url
}

output "lodestone_app_ssm_session_command" {
  value = module.lodestone_app.instance_id != null ? "aws ssm start-session --target ${module.lodestone_app.instance_id} --region ${var.region}" : null
}

output "lodestone_app_ingest_curl" {
  value = module.lodestone_app.instance_id != null ? "curl -X POST http://127.0.0.1:${module.lodestone_app.app_port}/ingest" : null
}
