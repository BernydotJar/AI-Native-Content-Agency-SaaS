# Staging definition — human gate

Staging is intentionally non-executable in this iteration. This directory contains no Terraform resources or backend configuration. The dev deployment workflow has no staging input or path.

Before staging can be implemented, a human must authorize the environment, select an isolated project and billing account, approve its cost envelope and access policy, and require a new Producer → Critic → Fixer → Independent Evaluator sequence. Dev state, identities, databases, and buckets must not be reused.
