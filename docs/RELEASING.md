# Local release process

Current scope: prepare a source-only preview. Version: `VERSION` (0.2.0). Repository: `heyaaakash/roastmyaudio`, public, default branch main. Existing historical tag `v1.0` is not changed. There is no supported native binary pipeline; signing, installers, notarization, stores, domain/TLS, and production deployment are N/A for this scope.

Use [the supplied launch guide](LAUNCH_GUIDE.md) and [filled checklist](LAUNCH_CHECKLIST.md). Preparation does not authorize pushing, tagging, uploading, publishing, history rewriting, or changing settings. Complete reversible work first; request only the actual missing authorization when release work is requested.

1. Resolve rights/history audio review and establish a private vulnerability reporting route. Recheck dependencies/advisories, actual platform evidence, screenshots, and support ownership. Keep public language aligned with evidence.
2. Run `make verify` and `make screenshots`. Test real microphone/native/AI flows for any claim you intend to make. Update validation, capabilities, release notes, and VERSION before committing.
3. Review/commit all intended files. The launch record must identify the exact source, new immutable tag, environment, toolchain, dependencies, validation, limitations, and publication authority.
4. When authorized, push the reviewed source and create a new annotated version tag on that commit. Check local/remote tag absence first; never reuse/move `v1.0` or another existing tag. Push and verify the tag.
5. From an isolated clean checkout at that tag, install the documented dependencies and run `make prepare-release`. The script requires clean exact tagged source and fresh staging. `make package` alone can produce a dirty review archive and reports that fact; dirty archives are not draft-eligible.
6. Inspect `dist/release-<version>/`: source ZIP, BUILD_INFO.json, RELEASE_NOTES.md, SHA256SUMS.txt. The packager excludes legacy prototypes, runtime files, caches, private data, and dependencies; re-extracts and byte-compares every source file. Include required redistribution notices if scope changes to binaries.
7. When draft upload is authorized, run `make draft-release`. It checks clean HEAD/tag/version/provenance, exact asset hashes, remote tag identity, and existing release state. It creates a **draft prerelease** only and refuses overwrite. It never publishes.
8. Download every draft asset into a new empty directory, compare hashes, inspect/extract, and run documented source setup from the downloaded archive. Record results, including narrower environment claims. Request publication approval only if it was not already given.
9. Publish the reviewed prerelease only when authorized. Recheck public access, owner/tag/assets, download hashes, images, setup links, and support/private report route. Record the published URL/time in the release record. Do not claim publication from preparation or a draft.

Actions was checked disabled during this preparation; no workflow files are retained. Recheck settings each release. The source dependency ranges are not a reproducibility lock: BUILD_INFO records resolved package versions, and every release needs a new compatibility/advisory review. Checksums show integrity, not signing/authenticity or byte-reproducible builds.

## Maintenance and rollback

Aakash owns source releases, issues, support, and rollback. Before the next release, re-run verification, review dependency updates and changed model APIs, refresh affected screenshots, and check privacy claims. Review reported issues at least monthly while the project is actively maintained; this is a maintainer expectation, not an automated reminder or SLA.

Keep the previous reviewed source/tag/artifacts. Stop apps and back up local data before downgrading. New history metadata may differ from old prototypes, so test compatibility with fictional data first. Publish hotfixes under new immutable versions. Mark broken releases explicitly and link to the replacement. Contact/announcement actions need authorization.
