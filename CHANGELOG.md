# Changelog

## 2.3.0

- Add reproducible Release archives, source manifests and integrity verification.
- Add isolated installation acceptance and repeatable fresh-process recovery demo.
- Publish cross-platform acceptance evidence after the nine-job CI matrix succeeds.
- Exclude local build outputs from installation and upgrade baselines.
- Fix an installer variable collision that could unnecessarily replace an identical installed package.

## 2.2.1

- Reject Windows symbolic links and reparse-point files without relying on O_NOFOLLOW.
- Check file identity around reads and preserve binary CRLF bytes.
- Pass the Linux/macOS/Windows × Python 3.11–3.13 unit-test matrix.

## 2.2

- Add deployment diagnosis, safe uninstall, upgrade baselines and portable locks.

## 2.1

- Add <=5% remaining-quota guard, emergency index and model handoff instructions.

## 2.0

- Initial Skill, project-local snapshots, semantic progress and resume workflow.
