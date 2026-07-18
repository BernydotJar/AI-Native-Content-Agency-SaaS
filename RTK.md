# RTK (Repository Toolkit) — Guide For This Repo

Source: [rtk-ai/rtk](https://github.com/rtk-ai/rtk)

## What RTK Is

`rtk` filters and compresses command output before it reaches the LLM context.
It is a single Rust binary with low runtime overhead (typically <10ms per command)
and broad command support.

In practice, RTK reduces token usage by removing noise, grouping repeated patterns,
truncating redundant output, and deduplicating logs.

## Typical Token Savings

| Operation | Frequency | Standard | `rtk` | Savings |
|---|---:|---:|---:|---:|
| `ls` / `tree` | 10x | 2,000 | 400 | -80% |
| `cat` / read | 20x | 40,000 | 12,000 | -70% |
| `grep` / `rg` | 8x | 16,000 | 3,200 | -80% |
| `git status` | 10x | 3,000 | 600 | -80% |
| `git diff` | 5x | 10,000 | 2,500 | -75% |
| `git log` | 5x | 2,500 | 500 | -80% |
| `git add/commit/push` | 8x | 1,600 | 120 | -92% |
| `cargo test` / `npm test` | 5x | 25,000 | 2,500 | -90% |
| `ruff check` | 3x | 3,000 | 600 | -80% |
| `pytest` | 4x | 8,000 | 800 | -90% |
| `go test` | 3x | 6,000 | 600 | -90% |
| `docker ps` | 3x | 900 | 180 | -80% |
| **Total** |  | **~118,000** | **~23,900** | **-80%** |

> Estimates are from medium-sized TypeScript/Rust projects. Actual savings vary.

## Installation

### Homebrew (recommended)

```bash
brew install rtk
```

### Quick install (Linux/macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
```

Adds binary to `~/.local/bin`. If needed:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

### Cargo

```bash
cargo install --git https://github.com/rtk-ai/rtk
```

### Prebuilt binaries

Download from GitHub Releases:
- macOS: `rtk-x86_64-apple-darwin.tar.gz`, `rtk-aarch64-apple-darwin.tar.gz`
- Linux: `rtk-x86_64-unknown-linux-musl.tar.gz`, `rtk-aarch64-unknown-linux-gnu.tar.gz`
- Windows: `rtk-x86_64-pc-windows-msvc.zip`

## Verify Installation

```bash
rtk --version
rtk gain
```

Expected version example: `rtk 0.28.2`.

Name collision warning: another crates.io package named `rtk` exists.
If `rtk gain` fails, reinstall using:

```bash
cargo install --git https://github.com/rtk-ai/rtk
```

## Quick Start For Codex

```bash
# Install hook/instructions for Codex
rtk init -g --codex

# Restart your AI tool, then test
git status
```

RTK intercepts shell commands and rewrites them (e.g. `git status` -> `rtk git status`) so the model receives compact output.

### Important scope note

Hook rewriting applies to shell/Bash tool calls.
Built-in non-shell tools may bypass rewriting. In those cases, call shell commands or explicit `rtk` commands directly.

## How RTK Compresses Output

RTK applies four strategies per command type:
1. Smart filtering
2. Grouping
3. Truncation
4. Deduplication

## High-Value Commands

### Files

```bash
rtk ls .
rtk read file.rs
rtk read file.rs -l aggressive
rtk smart file.rs
rtk find "*.rs" .
rtk grep "pattern" .
rtk diff file1 file2
```

### Git

```bash
rtk git status
rtk git log -n 10
rtk git diff
rtk git add
rtk git commit -m "msg"
rtk git push
rtk git pull
```

### Test runners

```bash
rtk jest
rtk vitest
rtk playwright test
rtk pytest
rtk go test
rtk cargo test
rtk test <cmd>
rtk err <cmd>
```

### Build/lint

```bash
rtk lint
rtk tsc
rtk next build
rtk cargo build
rtk cargo clippy
rtk ruff check
rtk golangci-lint run
```

### Containers / cloud / data

```bash
rtk docker ps
rtk docker logs <container>
rtk kubectl pods
rtk aws sts get-caller-identity
rtk json config.json
rtk log app.log
rtk curl <url>
```

### Analytics

```bash
rtk gain
rtk gain --graph
rtk gain --history
rtk gain --daily
rtk discover
rtk session
```

## Auto-Rewrite Hook

Recommended setup:

```bash
rtk init -g
rtk init -g --hook-only
rtk init --show
```

After install, restart the AI tool.

## Windows Notes

- Best experience: WSL (full hook support)
- Native Windows supports filters, but auto-rewrite hook is limited
- Do not double-click `rtk.exe`; run it from terminal

WSL install:

```bash
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
rtk init -g
```

## Basic Configuration

Config path:
- Linux: `~/.config/rtk/config.toml`
- macOS: `~/Library/Application Support/rtk/config.toml`

Example:

```toml
[hooks]
exclude_commands = ["curl", "playwright"]

[tee]
enabled = true
mode = "failures" # failures | always | never
```

When a command fails, RTK can save full raw output to tee logs for deeper debugging.

## Telemetry / Privacy

Telemetry is opt-in and disabled by default.
Manage with:

```bash
rtk telemetry status
rtk telemetry enable
rtk telemetry disable
rtk telemetry forget
```

Hard disable via env var:

```bash
export RTK_TELEMETRY_DISABLED=1
```

RTK docs claim it does not collect source code, file paths, command arguments,
secrets, env vars, or repository contents.

## Uninstall

```bash
rtk init -g --uninstall
cargo uninstall rtk
brew uninstall rtk
```

## References

- [GitHub repo](https://github.com/rtk-ai/rtk)
- [User guide](https://rtk-ai.app/guide)
- `INSTALL.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `SECURITY.md` in the RTK repository
