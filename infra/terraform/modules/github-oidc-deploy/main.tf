# GitHub Actions OIDC deploy role: lets the CI/CD workflow push to ECR and
# redeploy the app on EC2 via SSM — without any long-lived AWS access keys.

data "aws_caller_identity" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  oidc_provider_arn = var.enabled ? (
    var.create_oidc_provider
    ? aws_iam_openid_connect_provider.github[0].arn
    : "arn:aws:iam::${local.account_id}:oidc-provider/token.actions.githubusercontent.com"
  ) : ""
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.enabled && var.create_oidc_provider ? 1 : 0

  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = { Name = "${var.name}-github-oidc" }
}

resource "aws_iam_role" "deploy" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-github-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:ref:refs/heads/${var.github_branch}"
        }
      }
    }]
  })

  tags = { Name = "${var.name}-github-deploy" }
}

resource "aws_iam_role_policy" "deploy" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-github-deploy"
  role = aws_iam_role.deploy[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "EcrPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
        ]
        Resource = var.ecr_repository_arn
      },
      {
        Sid      = "SsmSendToAppInstance"
        Effect   = "Allow"
        Action   = ["ssm:SendCommand"]
        Resource = "arn:aws:ec2:${var.region}:${local.account_id}:instance/*"
        Condition = {
          StringEquals = {
            "ssm:resourceTag/Name" = var.app_name_tag
          }
        }
      },
      {
        Sid      = "SsmRunShellScriptDoc"
        Effect   = "Allow"
        Action   = ["ssm:SendCommand"]
        Resource = "arn:aws:ssm:${var.region}::document/AWS-RunShellScript"
      },
      {
        Sid      = "SsmReadResult"
        Effect   = "Allow"
        Action   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
        Resource = "*"
      },
      {
        Sid      = "Ec2DescribeForLookup"
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
      }
    ]
  })
}
