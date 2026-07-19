mock_provider "google" {}

override_resource {
  target = google_project.bootstrap
  values = {
    project_id = "agency-bootstrap-adopt"
  }
}

run "existing_project_adoption_is_imported_and_provenanced" {
  command = plan

  variables {
    project_id                = "agency-bootstrap-adopt"
    project_provisioning_mode = "ADOPT_EXISTING"
    existing_project_adoption = {
      schema_version     = "gcp-project-adoption.v1"
      project_id         = "agency-bootstrap-adopt"
      evidence_sha256    = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      decision_reference = "https://example.invalid/review/adopt"
      acknowledgement    = "I_ACKNOWLEDGE_TERRAFORM_WILL_MANAGE_THIS_EXISTING_PROJECT"
    }
    billing_account            = "AAAAAA-BBBBBB-CCCCCC"
    region                     = "us-central1"
    state_bucket_name          = "agency-bootstrap-adopt-tfstate"
    github_repository_owner    = "example-owner"
    github_repository_owner_id = "12345678"
    github_repository          = "example-repository"
    github_repository_id       = "87654321"
  }

  assert {
    condition = (
      output.project_provisioning_mode == "ADOPT_EXISTING"
      && can(regex("^[0-9a-f]{64}$", output.project_provenance_sha256))
    )
    error_message = "An adopted project must expose a versioned provenance digest."
  }
}

run "adoption_without_provenance_is_rejected" {
  command = plan

  variables {
    project_id                 = "agency-bootstrap-missing"
    project_provisioning_mode  = "ADOPT_EXISTING"
    billing_account            = "AAAAAA-BBBBBB-CCCCCC"
    region                     = "us-central1"
    state_bucket_name          = "agency-bootstrap-missing-tfstate"
    github_repository_owner    = "example-owner"
    github_repository_owner_id = "12345678"
    github_repository          = "example-repository"
    github_repository_id       = "87654321"
  }

  expect_failures = [terraform_data.authorization_gate]
}

run "reserved_project_labels_are_rejected" {
  command = plan

  variables {
    project_id                 = "agency-bootstrap-label"
    project_provisioning_mode  = "CREATE_NEW"
    billing_account            = "AAAAAA-BBBBBB-CCCCCC"
    region                     = "us-central1"
    state_bucket_name          = "agency-bootstrap-label-tfstate"
    github_repository_owner    = "example-owner"
    github_repository_owner_id = "12345678"
    github_repository          = "example-repository"
    github_repository_id       = "87654321"
    additional_labels = {
      environment = "production"
    }
  }

  expect_failures = [var.additional_labels]
}
