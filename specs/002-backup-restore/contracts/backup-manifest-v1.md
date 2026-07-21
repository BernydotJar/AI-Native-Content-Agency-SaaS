# `agency-runtime-backup.v1`

- Unknown top-level fields are rejected during restore.
- `backup_file` must be a basename and must resolve next to the manifest.
- `bytes` must be positive and equal the file size.
- `sha256` must be lowercase hexadecimal and equal the file digest.
- `backend` must match the restore subcommand.
- `validation` must match the backend's successful creation validation.
