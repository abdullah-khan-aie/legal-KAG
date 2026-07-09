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

  name                = local.name
  vpc_cidr            = var.vpc_cidr
  public_subnet_cidr  = var.public_subnet_cidr
  private_subnet_cidr = var.private_subnet_cidr
  availability_zone   = local.az
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
  project           = var.project
  region            = var.region
  enabled           = var.lodestone_app_enabled
  vpc_id            = module.network.vpc_id
  vpc_cidr          = module.network.vpc_cidr
  subnet_id         = module.network.public_subnet_id
  availability_zone = local.az
  neo4j_bolt_uri    = module.neo4j.bolt_uri

  instance_type        = var.lodestone_app_instance_type
  app_port             = var.lodestone_app_port
  git_repo_url                = var.lodestone_git_repo_url
  git_ref                     = var.lodestone_git_ref
  github_deploy_key_secret_id = var.lodestone_github_deploy_key_secret_id
  deploy_with_docker          = var.lodestone_deploy_with_docker
  ecr_enabled                 = var.lodestone_ecr_enabled
  bedrock_llm_model           = var.lodestone_bedrock_llm_model
  bedrock_embed_model  = var.lodestone_bedrock_embed_model
  max_concurrency      = var.lodestone_max_concurrency
  secret_id            = var.lodestone_secret_id
  scan_dir             = var.lodestone_scan_dir
  data_volume_gb       = var.lodestone_data_volume_gb
  allow_public_http    = var.lodestone_allow_public_http
  public_ingress_cidrs = var.lodestone_public_ingress_cidrs
}

module "lodestone_public_api" {
  source = "../modules/lodestone-public-api"

  name            = local.name
  region          = var.region
  enabled         = var.lodestone_app_enabled && var.lodestone_public_api_enabled
  vpc_id          = module.network.vpc_id
  subnet_ids      = [module.network.public_subnet_id]
  app_instance_id = module.lodestone_app.instance_id
  app_port        = var.lodestone_app_port
}

module "github_deploy" {
  source = "../modules/github-oidc-deploy"

  name                 = local.name
  enabled              = var.lodestone_app_enabled && var.github_deploy_enabled
  region               = var.region
  github_repo          = var.github_repo
  github_branch        = var.github_branch
  create_oidc_provider = var.github_create_oidc_provider
  ecr_repository_arn   = module.lodestone_app.ecr_repository_arn
  app_name_tag         = "${local.name}-app"
}
