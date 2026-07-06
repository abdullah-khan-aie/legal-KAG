# Lodestone FastAPI + KAG pipeline on EC2 (POC / phase-1 prod).
# Phase-2: replace with modules/lodestone-ecs (Fargate + ALB).

data "aws_ami" "al2023_amd64" {
  count = var.enabled ? 1 : 0

  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

resource "aws_security_group" "app" {
  count = var.enabled ? 1 : 0

  name        = "${var.name}-app-sg"
  description = "Lodestone app: HTTP API + /ui"
  vpc_id      = var.vpc_id

  ingress {
    description = "App port from within the VPC"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  dynamic "ingress" {
    for_each = var.allow_public_http ? [1] : []
    content {
      description = "App port from internet (POC demo — add auth before prod)"
      from_port   = var.app_port
      to_port     = var.app_port
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  dynamic "ingress" {
    for_each = var.allow_public_http ? [] : var.public_ingress_cidrs
    content {
      description = "App port from allowed CIDR"
      from_port   = var.app_port
      to_port     = var.app_port
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    description = "All outbound (git, Bedrock, Secrets Manager, SSM)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name}-app-sg" }
}

resource "aws_iam_role" "app" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "app_ssm" {
  count = var.enabled ? 1 : 0

  role       = aws_iam_role.app[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "app_bedrock_secrets" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-app-bedrock-secrets"
  role = aws_iam_role.app[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "BedrockInvoke"
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = "*"
      },
      {
        Sid      = "ReadLodestoneSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = "arn:aws:secretsmanager:${var.region}:*:secret:${var.secret_id}*"
      },
      {
        Sid      = "KmsDecryptSecrets"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:DescribeKey"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${var.region}.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  count = var.enabled ? 1 : 0

  name = "${var.name}-app-profile"
  role = aws_iam_role.app[0].name
}

resource "aws_ebs_volume" "app_data" {
  count = var.enabled ? 1 : 0

  availability_zone = var.availability_zone
  size              = var.data_volume_gb
  type              = "gp3"
  encrypted         = true

  tags = { Name = "${var.name}-app-ingest-data" }
}

resource "aws_instance" "app" {
  count = var.enabled ? 1 : 0

  ami                    = data.aws_ami.al2023_amd64[0].id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.app[0].id]
  iam_instance_profile   = aws_iam_instance_profile.app[0].name

  associate_public_ip_address = true

  root_block_device {
    volume_type = "gp3"
    volume_size = 30
    encrypted   = true
  }

  user_data = templatefile("${path.module}/templates/app_user_data.sh.tftpl", {
    region          = var.region
    secret_id       = var.secret_id
    neo4j_bolt_uri  = var.neo4j_bolt_uri
    app_port        = var.app_port
    scan_dir        = var.scan_dir
    git_repo_url    = var.git_repo_url
    git_ref         = var.git_ref
    llm_model       = var.bedrock_llm_model
    embed_model     = var.bedrock_embed_model
    max_concurrency = var.max_concurrency
  })

  user_data_replace_on_change = true

  tags = { Name = "${var.name}-app" }
}

resource "aws_volume_attachment" "app_data" {
  count = var.enabled ? 1 : 0

  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.app_data[0].id
  instance_id = aws_instance.app[0].id

  stop_instance_before_detaching = true
}
