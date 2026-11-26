# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - 2026-11-26

### Added
- `scripts/generate.py`: a stdlib-only Python generator that renders every profile SVG (stats, top languages, streak, activity graph, header, typing and footer) from the GitHub GraphQL API.
- `.github/workflows/profile-assets.yml`: a GitHub Action that regenerates and commits `assets/*.svg` on a daily schedule, manual dispatch, or pushes to `scripts/**` / the workflow file.
- `assets/*.svg` (generated output): self-hosted replacements for the previously external stats, streak, activity, banner and typing widgets.
- `CHANGELOG.md`.

### Changed
- README now loads every generated graphic from `./assets/*.svg` instead of third-party hosted widgets (github-readme-stats, streak-stats, github-profile-trophy, activity-graph, capsule-render, readme-typing-svg).
- Updated the about object, tech stack and pinned projects to reflect current work, adding Go, TypeScript, Kotlin, Dart, Rust, Solidity, FastAPI, PyTorch, Hugging Face, Flutter, Jetpack Compose, Next.js, Foundry, Redis, Keycloak and Kubernetes.
- LinkedIn badge now uses an inline base64 SVG logo (simple-icons removed the LinkedIn icon).
- Updated the footer line to "82 public repositories · pinned 5 above".
- Theme switched from green to blue (#58a6ff).
- Stats card redesigned with icons, 8 metrics and an activity grade ring.
- Streak card restored to the three-column layout with dividers and a fire icon.
- Stats and top languages cards (both 495x195, bordered) share one row at 49% width; the streak card has its own row below.
- Activity graph redesigned as a year view with gradient line, last-year comparison and today marker.
- Activity graph title centered; added axis titles, y-axis ticks and a centered legend.

### Removed
- Trophies section and its generator.

### Fixed
- Replaced the broken "Could not fetch total commits" stats card with an in-repo equivalent.
- Removed the two outdated e-commerce pinned cards.
