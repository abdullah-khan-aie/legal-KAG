# Public access path for the App app:
#   Internet -> API Gateway (REST API, response streaming) -> VPC Link
#     -> internal NLB -> EC2 :8080
#
# We use a REST API (not an HTTP API) so the proxy integration can set
# responseTransferMode = STREAM. STREAM makes API Gateway forward the backend's
# SSE / token output to the client as it is produced instead of buffering the
# whole response, and lifts the 29s timeout (up to 15 min / 5 min idle for a
# regional endpoint). This is what makes the live "steps"/streaming UI and the
# long deep_thought answers work through the public URL.
#
# The STREAM flag is applied by a null_resource running the AWS CLI, because the
# Terraform AWS provider does not yet expose responseTransferMode
# (hashicorp/terraform-provider-aws#45322 / #45168).
#
# The EC2 stays private (VPC-only SG); only API Gateway is internet-facing.

# --- Internal Network Load Balancer -------------------------------------------

resource "aws_lb" "app" {
  count = var.enabled ? 1 : 0

  name               = "${var.name}-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = var.subnet_ids

  tags = { Name = "${var.name}-nlb" }
}

resource "aws_lb_target_group" "app" {
  count = var.enabled ? 1 : 0

  name        = "${var.name}-tg"
  port        = var.app_port
  protocol    = "TCP"
  target_type = "instance"
  vpc_id      = var.vpc_id

  health_check {
    protocol            = "HTTP"
    path                = var.health_check_path
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 30
  }

  tags = { Name = "${var.name}-tg" }
}

resource "aws_lb_target_group_attachment" "app" {
  count = var.enabled ? 1 : 0

  target_group_arn = aws_lb_target_group.app[0].arn
  target_id        = var.app_instance_id
  port             = var.app_port
}

resource "aws_lb_listener" "app" {
  count = var.enabled ? 1 : 0

  load_balancer_arn = aws_lb.app[0].arn
  port              = 80
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app[0].arn
  }
}

# --- API Gateway VPC Link (REST / v1) -----------------------------------------
# A v1 VPC link binds directly to the NLB via target_arns and takes NO security
# group. The app EC2's SG already allows :8080 from the whole VPC CIDR, which
# covers the link's ENIs, so no SG plumbing is needed here.

resource "aws_api_gateway_vpc_link" "app" {
  count = var.enabled ? 1 : 0

  name        = "${var.name}-vpclink"
  target_arns = [aws_lb.app[0].arn]

  tags = { Name = "${var.name}-vpclink" }
}

# --- API Gateway REST API -----------------------------------------------------

resource "aws_api_gateway_rest_api" "app" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-api"

  # Regional (not edge-optimized): streaming idle timeout is 5 min vs 30s on edge.
  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = { Name = "${var.name}-api" }
}

# Greedy proxy resource: /{proxy+} forwards every path to the app unchanged.
resource "aws_api_gateway_resource" "proxy" {
  count = var.enabled ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.app[0].id
  parent_id   = aws_api_gateway_rest_api.app[0].root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  count = var.enabled ? 1 : 0

  rest_api_id        = aws_api_gateway_rest_api.app[0].id
  resource_id        = aws_api_gateway_resource.proxy[0].id
  http_method        = "ANY"
  authorization      = "NONE"
  request_parameters = { "method.request.path.proxy" = true }
}

resource "aws_api_gateway_integration" "proxy" {
  count = var.enabled ? 1 : 0

  rest_api_id             = aws_api_gateway_rest_api.app[0].id
  resource_id             = aws_api_gateway_resource.proxy[0].id
  http_method             = aws_api_gateway_method.proxy[0].http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_api_gateway_vpc_link.app[0].id
  uri                     = "http://${aws_lb.app[0].dns_name}/{proxy}"
  request_parameters      = { "integration.request.path.proxy" = "method.request.path.proxy" }

  # NOTE: responseTransferMode = STREAM is applied out-of-band by
  # null_resource.stream_mode (the provider doesn't model that attribute, so it
  # causes no Terraform drift here).
}

# Root "/" needs its own ANY method: /{proxy+} does not match the root path.
resource "aws_api_gateway_method" "root" {
  count = var.enabled ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.app[0].id
  resource_id   = aws_api_gateway_rest_api.app[0].root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "root" {
  count = var.enabled ? 1 : 0

  rest_api_id             = aws_api_gateway_rest_api.app[0].id
  resource_id             = aws_api_gateway_rest_api.app[0].root_resource_id
  http_method             = aws_api_gateway_method.root[0].http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  connection_type         = "VPC_LINK"
  connection_id           = aws_api_gateway_vpc_link.app[0].id
  uri                     = "http://${aws_lb.app[0].dns_name}/"
}

# Deployment snapshot. Redeploys whenever the API surface changes (triggers hash).
resource "aws_api_gateway_deployment" "app" {
  count = var.enabled ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.app[0].id

  triggers = {
    redeploy = sha1(jsonencode([
      aws_api_gateway_resource.proxy[0].id,
      aws_api_gateway_method.proxy[0].id,
      aws_api_gateway_integration.proxy[0].id,
      aws_api_gateway_method.root[0].id,
      aws_api_gateway_integration.root[0].id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "default" {
  count = var.enabled ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.app[0].id
  deployment_id = aws_api_gateway_deployment.app[0].id
  stage_name    = "prod"

  tags = { Name = "${var.name}-api-stage" }

  # null_resource.stream_mode redeploys via the CLI and repoints this stage to a
  # STREAM-enabled deployment; ignore that drift so Terraform doesn't revert it.
  lifecycle {
    ignore_changes = [deployment_id]
  }
}

# --- Flip the proxy integration to STREAM (provider-gap workaround) ------------
# Sets responseTransferMode = STREAM on the /{proxy+} integration and creates a
# fresh deployment so the prod stage serves the streaming config. Re-runs on any
# API change (keyed to the same redeploy hash) so STREAM is re-asserted after
# Terraform rewrites the integration back to its BUFFERED default.
resource "null_resource" "stream_mode" {
  count = var.enabled ? 1 : 0

  triggers = {
    redeploy = aws_api_gateway_deployment.app[0].triggers["redeploy"]
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws apigateway update-integration \
        --rest-api-id ${aws_api_gateway_rest_api.app[0].id} \
        --resource-id ${aws_api_gateway_resource.proxy[0].id} \
        --http-method ANY \
        --patch-operations "op='replace',path='/responseTransferMode',value=STREAM" \
        --region ${var.region}
      aws apigateway create-deployment \
        --rest-api-id ${aws_api_gateway_rest_api.app[0].id} \
        --stage-name prod \
        --region ${var.region}
    EOT
  }

  depends_on = [aws_api_gateway_stage.default]
}
