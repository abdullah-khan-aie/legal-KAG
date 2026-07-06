data "aws_ami" "al2023_arm64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-*-arm64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

resource "aws_security_group" "neo4j" {
  name        = "${var.name}-neo4j-sg"
  description = "Neo4j: Bolt/HTTP from within the VPC only"
  vpc_id      = var.vpc_id

  ingress {
    description = "Bolt from within the VPC"
    from_port   = 7687
    to_port     = 7687
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "HTTP (browser) from within the VPC"
    from_port   = 7474
    to_port     = 7474
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "All outbound (image pull, OS updates, SSM)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name}-neo4j-sg" }
}

resource "aws_iam_role" "neo4j" {
  name = "${var.name}-neo4j-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.neo4j.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "neo4j" {
  name = "${var.name}-neo4j-profile"
  role = aws_iam_role.neo4j.name
}

resource "aws_ebs_volume" "neo4j_data" {
  availability_zone = var.availability_zone
  size              = var.data_volume_gb
  type              = "gp3"
  encrypted         = true

  tags = { Name = "${var.name}-neo4j-data" }
}

resource "aws_instance" "neo4j" {
  ami                    = data.aws_ami.al2023_arm64.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.neo4j.id]
  iam_instance_profile   = aws_iam_instance_profile.neo4j.name

  associate_public_ip_address = true

  root_block_device {
    volume_type = "gp3"
    volume_size = 30
    encrypted   = true
  }

  user_data = templatefile("${path.module}/templates/user_data.sh.tftpl", {
    neo4j_image    = var.neo4j_image
    neo4j_password = var.neo4j_password
    heap_size      = var.heap_size
    pagecache_size = var.pagecache_size
  })

  user_data_replace_on_change = true

  tags = { Name = "${var.name}-neo4j" }
}

resource "aws_volume_attachment" "neo4j_data" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.neo4j_data.id
  instance_id = aws_instance.neo4j.id

  stop_instance_before_detaching = true
}
