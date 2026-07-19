mock_provider "google" {}

run "bootstrap_is_keyless_and_repository_scoped" {
  command = plan

  variables {
    project_id              = "agency-bootstrap-test"
    create_project          = false
    region                  = "us-central1"
    state_bucket_name       = "agency-bootstrap-test-tfstate"
    github_repository_owner = "example-owner"
    github_repository       = "example-repository"
    github_allowed_ref      = "refs/heads/main"
    github_workflow_path    = ".github/workflows/deploy-dev.yml"
  }

  assert {
    condition     = output.project_id == "agency-bootstrap-test"
    error_message = "The bootstrap project must be explicit."
  }

  assert {
    condition     = alltrue([for condition in values(output.github_attribute_condition) : strcontains(condition, "assertion.repository_owner == 'example-owner'")])
    error_message = "WIF must restrict the exact repository owner."
  }

  assert {
    condition     = alltrue([for condition in values(output.github_attribute_condition) : strcontains(condition, "assertion.repository == 'example-owner/example-repository'")])
    error_message = "WIF must restrict the exact repository."
  }

  assert {
    condition     = alltrue([for condition in values(output.github_attribute_condition) : strcontains(condition, "assertion.ref == 'refs/heads/main'")])
    error_message = "WIF must restrict the exact Git ref."
  }

  assert {
    condition     = alltrue([for condition in values(output.github_attribute_condition) : strcontains(condition, "assertion.ref_type == 'branch'")])
    error_message = "WIF must reject tag and pull-request token contexts."
  }

  assert {
    condition = (
      strcontains(output.github_attribute_condition.build, "assertion.environment == 'dev-build'")
      && strcontains(output.github_attribute_condition.plan, "assertion.environment == 'dev-plan'")
      && strcontains(output.github_attribute_condition.apply, "assertion.environment == 'dev'")
    )
    error_message = "WIF must restrict each phase to its exact protected GitHub environment."
  }

  assert {
    condition     = alltrue([for condition in values(output.github_attribute_condition) : strcontains(condition, "assertion.workflow_ref == 'example-owner/example-repository/.github/workflows/deploy-dev.yml@refs/heads/main'")])
    error_message = "WIF must restrict the exact direct deployment workflow revision."
  }

  assert {
    condition = (
      google_storage_bucket_iam_member.terraform_apply_runtime.condition[0].expression == "resource.type == 'storage.googleapis.com/Object' && resource.name.startsWith('projects/_/buckets/agency-bootstrap-test-tfstate/objects/environments/dev-runtime/')"
      && strcontains(google_storage_bucket_iam_member.terraform_plan_lock.condition[0].expression, "resource.name.endsWith('.tflock')")
      && strcontains(google_storage_bucket_iam_member.terraform_state_read["apply"].condition[0].expression, "/objects/environments/dev/")
      && !strcontains(google_storage_bucket_iam_member.terraform_state_read["apply"].condition[0].expression, "/objects/environments/dev-runtime/")
    )
    error_message = "Plan lock and apply state writes must be confined to the dev-runtime prefix; apply may only read foundation state."
  }
}
