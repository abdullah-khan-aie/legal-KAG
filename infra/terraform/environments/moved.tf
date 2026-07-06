# State migration from flat terraform/ at repo root (pre-infra layout).
# Safe to keep after migration — no-op when old addresses are absent.

moved {
  from = aws_vpc.main
  to   = module.network.aws_vpc.main
}

moved {
  from = aws_internet_gateway.main
  to   = module.network.aws_internet_gateway.main
}

moved {
  from = aws_subnet.public
  to   = module.network.aws_subnet.public
}

moved {
  from = aws_subnet.private
  to   = module.network.aws_subnet.private
}

moved {
  from = aws_route_table.public
  to   = module.network.aws_route_table.public
}

moved {
  from = aws_route_table_association.public
  to   = module.network.aws_route_table_association.public
}

moved {
  from = aws_route_table.private
  to   = module.network.aws_route_table.private
}

moved {
  from = aws_route_table_association.private
  to   = module.network.aws_route_table_association.private
}

moved {
  from = aws_security_group.neo4j
  to   = module.neo4j.aws_security_group.neo4j
}

moved {
  from = aws_iam_role.neo4j
  to   = module.neo4j.aws_iam_role.neo4j
}

moved {
  from = aws_iam_role_policy_attachment.ssm
  to   = module.neo4j.aws_iam_role_policy_attachment.ssm
}

moved {
  from = aws_iam_instance_profile.neo4j
  to   = module.neo4j.aws_iam_instance_profile.neo4j
}

moved {
  from = aws_ebs_volume.neo4j_data
  to   = module.neo4j.aws_ebs_volume.neo4j_data
}

moved {
  from = aws_instance.neo4j
  to   = module.neo4j.aws_instance.neo4j
}

moved {
  from = aws_volume_attachment.neo4j_data
  to   = module.neo4j.aws_volume_attachment.neo4j_data
}

moved {
  from = aws_security_group.app[0]
  to   = module.lodestone_app.aws_security_group.app[0]
}

moved {
  from = aws_iam_role.app[0]
  to   = module.lodestone_app.aws_iam_role.app[0]
}

moved {
  from = aws_iam_role_policy_attachment.app_ssm[0]
  to   = module.lodestone_app.aws_iam_role_policy_attachment.app_ssm[0]
}

moved {
  from = aws_iam_role_policy.app_bedrock_secrets[0]
  to   = module.lodestone_app.aws_iam_role_policy.app_bedrock_secrets[0]
}

moved {
  from = aws_iam_instance_profile.app[0]
  to   = module.lodestone_app.aws_iam_instance_profile.app[0]
}

moved {
  from = aws_ebs_volume.app_data[0]
  to   = module.lodestone_app.aws_ebs_volume.app_data[0]
}

moved {
  from = aws_instance.app[0]
  to   = module.lodestone_app.aws_instance.app[0]
}

moved {
  from = aws_volume_attachment.app_data[0]
  to   = module.lodestone_app.aws_volume_attachment.app_data[0]
}
