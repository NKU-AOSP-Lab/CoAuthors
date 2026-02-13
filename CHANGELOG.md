# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-02-13

### Added
- Added full bilingual UI support (English/Chinese) with a top-bar language selector.
- Added unified style selector in top bar across user, advanced console, and bootstrap pages.
- Added status metadata fields in query pages:
  - Data Source (`DBLP`)
  - Data Date (auto-detected from data files, override via `DATA_DATE`)
- Added project footer block on all pages with:
  - Developer and Maintainer: Nankai University AOSP Laboratory
  - Version
  - Current feature summary
  - Open-source license
- Added `bootstrap` page navigation into the same multi-page experience (`/`, `/console`, `/bootstrap`).

### Changed
- Set default UI style to `Campus Modern`.
- Set default UI language to English.
- Upgraded integrated app architecture in `bootstrap_console/app.py` to serve both query and bootstrap workflows.
- Updated Docker defaults to build with `fullmeta` mode for query compatibility.
- Updated README for open-source publication and deployment guidance.

### Fixed
- Normalized UI/JS text to avoid encoding/mixed-language issues in bootstrap scripts.
- Ensured coauthor query flow remains compatible with organization-stripping input behavior.

## [2.0.0] - 2026-02-13

### Added
- Introduced combined query + bootstrap web application in `bootstrap_console`.
- Added user-facing query page (`/`) and advanced query console (`/console`).
- Added bootstrap pipeline page (`/bootstrap`) with task controls and live logs.
- Added metadata-aware coauthor result rendering (`title`, `year`, `venue`, `pub_type`).

### Changed
- Refactored static assets into dedicated query/bootstrap bundles.

## [1.0.0] - 2026-02-13

### Added
- Initial bootstrap console with DBLP XML/DTD download, decompression, and SQLite build pipeline.
- Task state APIs (`/api/start`, `/api/stop`, `/api/reset`, `/api/state`, `/api/files`).
