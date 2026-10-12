resource "aws_ecr_repository" "app" {
  count = var.enabled ? 1 : 0

  name                 = "${var.name}"
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "${var.name}-ecr" }
}

resource "aws_ecs_cluster" "main" {
  count = var.enabled ? 1 : 0

  name = "${var.name}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "${var.name}-cluster" }
}

resource "aws_iam_role" "ecs_task_execution" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-ecs-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  count = var.enabled ? 1 : 0

  role       = aws_iam_role.ecs_task_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_bedrock_secrets" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-ecs-bedrock-secrets"
  role = aws_iam_role.ecs_task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = "arn:aws:secretsmanager:${var.region}:*:secret:${var.secret_id}*"
      }
    ]
  })
}

# TODO (prod): aws_lb, aws_lb_target_group, aws_ecs_task_definition,
# aws_ecs_service, aws_acm_certificate, Route53 — add when Dockerfile + CI push to ECR exist.
