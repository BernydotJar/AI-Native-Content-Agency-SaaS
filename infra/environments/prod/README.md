# Production definition — human gate

Production is intentionally non-executable in this iteration. This directory contains no Terraform resources or backend configuration, and no workflow can plan or apply it.

Production requires a separate threat model, real authentication adapter, HA/backup and recovery objectives, cost approval, independent security/readiness evaluation, legal and operational gates, and explicit human authorization. Development-header identity is forbidden by the backend production configuration.
