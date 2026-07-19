mock_provider "google" {}

run "tagged_build_storage_is_bounded_while_deployments_use_digests" {
  command = plan

  variables {
    project_id    = "agency-dev-test"
    location      = "us-central1"
    repository_id = "agency-images"
  }

  assert {
    condition = (
      !google_artifact_registry_repository.images.docker_config[0].immutable_tags
      && !google_artifact_registry_repository.images.cleanup_policy_dry_run
    )
    error_message = "Disposable build tags must remain removable and cleanup must be active."
  }

  assert {
    condition = (
      one([
        for policy in google_artifact_registry_repository.images.cleanup_policies : policy
        if policy.id == "delete-old"
      ]).condition[0].tag_state == "ANY"
      && one([
        for policy in google_artifact_registry_repository.images.cleanup_policies : policy
        if policy.id == "delete-old"
      ]).condition[0].older_than == "604800s"
      && one([
        for policy in google_artifact_registry_repository.images.cleanup_policies : policy
        if policy.id == "keep-recent"
      ]).most_recent_versions[0].keep_count == 20
      && one([
        for policy in google_artifact_registry_repository.images.cleanup_policies : policy
        if policy.id == "keep-current-rollback"
      ]).condition[0].tag_state == "TAGGED"
      && toset(one([
        for policy in google_artifact_registry_repository.images.cleanup_policies : policy
        if policy.id == "keep-current-rollback"
      ]).condition[0].tag_prefixes) == toset(["rollback-current"])
    )
    error_message = "Cleanup must delete builds older than seven days, retain 20 recent versions, and retain the single moving rollback tag."
  }
}
