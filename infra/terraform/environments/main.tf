terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Local state. Optional later: S3 backend (see infra/docs/deploy.md).
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile != "" ? var.aws_profile : null

  default_tags {
    tags = {
      Project   = var.project
      Env       = var.env
      ManagedBy = "terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "${var.project}-${var.env}"
  az   = data.aws_availability_zones.available.names[0]
}

module "network" {
  source = "../modules/network"

  name                 = local.name
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidr   = var.public_subnet_cidr
  private_subnet_cidr  = var.private_subnet_cidr
  availability_zone    = local.az
}

module "neo4j" {
  source = "../modules/neo4j"

  name              = local.name
  region            = var.region
  vpc_id            = module.network.vpc_id
  vpc_cidr          = module.network.vpc_cidr
  subnet_id         = module.network.public_subnet_id
  availability_zone = local.az

  instance_type  = var.neo4j_instance_type
  data_volume_gb = var.neo4j_data_volume_gb
  neo4j_image    = var.neo4j_image
  neo4j_password = var.neo4j_password
  heap_size      = var.neo4j_heap_size
  pagecache_size = var.neo4j_pagecache_size
}

module "lodestone_app" {
  source = "../modules/lodestone-app"

  name              = local.name
  region            = var.region
  enabled           = var.lodestone_app_enabled
  vpc_id            = module.network.vpc_id
  vpc_cidr          = module.network.vpc_cidr
  subnet_id         = module.network.public_subnet_id
  availability_zone = local.az
  neo4j_bolt_uri    = module.neo4j.bolt_uri

  instance_type        = var.lodestone_app_instance_type
  app_port             = var.lodestone_app_port
  git_repo_url         = var.lodestone_git_repo_url
  git_ref              = var.lodestone_git_ref
  bedrock_llm_model    = var.lodestone_bedrock_llm_model
  bedrock_embed_model  = var.lodestone_bedrock_embed_model
  max_concurrency      = var.lodestone_max_concurrency
  secret_id            = var.lodestone_secret_id
  scan_dir             = var.lodestone_scan_dir
  data_volume_gb       = var.lodestone_data_volume_gb
  allow_public_http    = var.lodestone_allow_public_http
  public_ingress_cidrs = var.lodestone_public_ingress_cidrs
}
