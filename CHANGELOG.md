# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-11-26

### Added
- `scripts/generate.py`: a stdlib-only Python generator that renders every profile SVG (stats, top languages, streak, activity graph, trophies, header, typing and footer) from the GitHub GraphQL API.
- `.github/workflows/profile-assets.yml`: a GitHub Action that regenerates and commits `assets/*.svg` on a daily schedule, manual dispatch, or pushes to `scripts/**` / the workflow file.
- `assets/*.svg` (generated output): self-hosted replacements for the previously external stats, streak, activity, trophy, banner and typing widgets.
- `CHANGELOG.md`.

### Changed
- README now loads every generated graphic from `./assets/*.svg` instead of third-party hosted widgets (github-readme-stats, streak-stats, github-profile-trophy, activity-graph, capsule-render, readme-typing-svg).
- Updated the about object, tech stack and pinned projects to reflect current work, adding Go, TypeScript, Kotlin, Dart, Rust, Solidity, FastAPI, PyTorch, Hugging Face, Flutter, Jetpack Compose, Next.js, Foundry, Redis, Keycloak and Kubernetes.
- LinkedIn badge now uses an inline base64 SVG logo (simple-icons removed the LinkedIn icon).
- Updated the footer line to "82 public repositories · pinned 5 above".

### Fixed
- Replaced the broken "Could not fetch total commits" stats card and broken trophy image with in-repo equivalents.
- Removed the two outdated e-commerce pinned cards.
