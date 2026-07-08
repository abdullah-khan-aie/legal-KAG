# Public access path for the Lodestone app:
#   Internet -> API Gateway (HTTP API, public) -> VPC Link -> internal NLB -> EC2 :8080
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

# --- API Gateway VPC Link -----------------------------------------------------

resource "aws_security_group" "vpc_link" {
  count = var.enabled ? 1 : 0

  name        = "${var.name}-vpclink-sg"
  description = "API Gateway VPC Link ENIs"
  vpc_id      = var.vpc_id

  egress {
    description = "All outbound to reach the internal NLB"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name}-vpclink-sg" }
}

resource "aws_apigatewayv2_vpc_link" "app" {
  count = var.enabled ? 1 : 0

  name               = "${var.name}-vpclink"
  subnet_ids         = var.subnet_ids
  security_group_ids = [aws_security_group.vpc_link[0].id]

  tags = { Name = "${var.name}-vpclink" }
}

# --- API Gateway HTTP API -----------------------------------------------------

resource "aws_apigatewayv2_api" "app" {
  count = var.enabled ? 1 : 0

  name          = "${var.name}-api"
  protocol_type = "HTTP"

  tags = { Name = "${var.name}-api" }
}

resource "aws_apigatewayv2_integration" "app" {
  count = var.enabled ? 1 : 0

  api_id             = aws_apigatewayv2_api.app[0].id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  integration_uri    = aws_lb_listener.app[0].arn
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.app[0].id
}

resource "aws_apigatewayv2_route" "proxy" {
  count = var.enabled ? 1 : 0

  api_id    = aws_apigatewayv2_api.app[0].id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.app[0].id}"
}

resource "aws_apigatewayv2_route" "root" {
  count = var.enabled ? 1 : 0

  api_id    = aws_apigatewayv2_api.app[0].id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.app[0].id}"
}

resource "aws_apigatewayv2_stage" "default" {
  count = var.enabled ? 1 : 0

  api_id      = aws_apigatewayv2_api.app[0].id
  name        = "$default"
  auto_deploy = true

  tags = { Name = "${var.name}-api-stage" }
}
