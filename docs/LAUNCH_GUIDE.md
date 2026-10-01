# Public Project Launch Guide — v3

Reusable instructions for creating, moving, documenting, validating, and releasing public repositories like SpotMenu.

Prepared: **2026-10-01**. Default workflow: **local verification and releases; GitHub Actions disabled**. Platform and marketplace requirements must be checked again for each release.

## 1. How to use this document

Copy this guide into each project's documentation and fill in the project card. Complete the common phases and only the applicable platform branches. Keep the decision log, capability matrix, validation evidence, and release record with that project.

For every checklist item, record **done + evidence**, **N/A + reason**, or leave it **open**. An unchecked item is not complete. No template item or example is evidence for a future project.

The normal sequence is:

**Configure → inventory → scaffold or migrate → implement → document and capture screenshots → verify → commit → tag → build tagged source → upload draft → validate downloads → publish → verify public access → record and maintain.**

Choose checks according to the product and distribution route. Source-only, experimental binary, supported binary, website, and store releases have different acceptance requirements. Narrow the scope when evidence is missing; do not invent results.

## 2. Project card

| Field | Fill in for this project |
| --- | --- |
| Product and audience | Name; one-sentence problem; intended user; first successful action |
| Owner and support | GitHub owner/team; maintainer; public issue/contact route; private security route |
| Source location | Current absolute folder; actual Git root; remotes; default branch |
| Final destination | Absolute local folder; GitHub owner/name; final remote URL |
| Repository structure | Standalone or monorepo; reason; shared components if any |
| Visibility | Intended public/private visibility; when a visibility change is authorized |
| Presentation reference | Reference repository; layout/features to emulate; material that must not be copied |
| Platforms | OS/browser/host versions; CPU architectures; devices; minimum supported versions |
| Release scope | Source-only, experimental binary, supported binary, website, store, or combination |
| Distribution channels | GitHub release, download URL, domain, store/Marketplace; owner of each |
| Automation mode | Local/no Actions by default; any explicit alternative |
| Identity | Product slug; bundle/package ID; executable name; publisher; icon |
| Version | Authoritative version location; initial version; build number if needed |
| Signing | Unsigned/ad-hoc/Developer ID/other signing; notarization; available account access |
| License and rights | Proposed license; code ownership; dependencies/assets; unresolved questions |
| Data | Collected, stored, transmitted, logged, retained, deleted; third parties |
| Feature evidence | Capability matrix location; supported, experimental, unverified, unsupported |
| Publication authorization | Prepare only, draft upload, push/tag, publish, visibility change; who authorized and where |
| Dates | Intended launch date; time zone; validation date |
| Maintenance | Release lead; support owner; review cadence; rollback owner |

### Decision log

| Decision | Reason | Alternatives | Evidence or remaining risk | Revisit trigger |
| --- | --- | --- | --- | --- |
| _Repository, license, platforms, signing, automation, or distribution_ | _Why_ | _Other options_ | _Link or open issue_ | _Condition/date_ |

### Working and approval rules

- Inspect available context and proceed with authorized, reversible preparation. Ask only for missing information that affects the result or actions outside the established authorization.
- Record authorization once and respect it across the task. Do not ask again merely because the work reaches tagging or publication when those actions were already authorized.
- Before any approval that is still needed, complete the repository, documentation, assets, validation, and draft so the owner can review concrete results.
- Preparing this guide or a release draft does not itself authorize publishing, changing visibility, deleting repositories, rewriting history, or contacting others.
- Preserve uncommitted user work. Do not delete, overwrite, or omit it silently. Identify which work belongs in the release before committing.
- Use absolute local paths in handoffs. After a move, update the workspace/project location and verify commands run in the destination.

## 3. Product truth and release scope

- [ ] State the core job, audience, first-use outcome, and success criteria.
- [ ] Map discovery → download/open → prerequisites → permissions/sign-in → first success → help/reporting.
- [ ] Inventory claims in README, screenshots, listings, release notes, and announcements: functionality, privacy, performance, compatibility, and integrations.
- [ ] Separate implementation, automated tests, real usage, experimental status, and unsupported status. Several can apply to one feature.
- [ ] Record prerequisites, failure cases, unsupported combinations, and known limitations where users can see them before installing.
- [ ] Assign an owner to each unproven claim. Qualify or remove unsupported claims; describe deferred work as planned.
- [ ] Select the release scope. For supported binaries, validate the primary journey and installation on claimed environments. Experimental builds must state exactly what remains unverified. Source-only publication must not imply that downloadable binaries were validated.

### Capability matrix template

| Feature/environment | Implemented | Automated evidence | Real-use evidence | Public status/limitation |
| --- | --- | --- | --- | --- |
| _Feature or OS/CPU/device combination_ | _Yes/no_ | _Command/result/commit_ | _Machine/version/date/result_ | _Supported, experimental, unverified, unsupported_ |

Build success proves compilation. Mocked tests prove the behavior they exercise. Cross-compilation does not prove target-hardware runtime behavior. Screenshot fixtures do not prove sign-in or a live integration. Measure performance claims under recorded conditions rather than describing an unmeasured change as instant or reliable.

For apps with background detection or integrations, test event delivery, closed/open UI behavior, polling fallback, stale data, concurrent requests, expired sessions, disconnect/reconnect, service absence, sleep/wake, and retry/rate-limit recovery where applicable.

## 4. Repository creation, migration, and history

- [ ] Inspect Git root, status, tracked/untracked/ignored files, branches, tags, remotes, submodules, and worktrees.
- [ ] Inventory source, tests, assets, configuration, generated output, private data, and unrelated projects before moving files.
- [ ] Use a standalone repository for independent ownership and releases. Use a monorepo when shared code and maintenance justify it; document per-project versions, commands, paths, and tag conventions.
- [ ] For an existing product, plan which relevant history and tags to preserve. A subdirectory extraction can require a deliberate subtree/history migration rather than copying files and losing provenance.
- [ ] Review public author names/emails and relevant history. Obtain authorization before identity changes or destructive history rewrites; preserve a recoverable backup.
- [ ] Move to the agreed absolute destination. Exclude unrelated apps, caches, dependency folders, credentials, and generated builds. Regenerate necessary outputs from source.
- [ ] Compare the destination with the inventory. Verify Git history, source inputs, branch, remote, and build commands.
- [ ] Update old clone/download/issue links, badges, metadata, documentation, and workspace settings. Record whether the old location stays, redirects, archives, or is removed; do not delete it by assumption.
- [ ] Create the remote with the intended visibility and verify its actual owner/name/visibility. A push does not make a private repository public.

### Reusable starter repository

For new products, maintain a neutral GitHub template containing the scaffold, blank records, and adaptable scripts. GitHub templates can reproduce the directory structure and files. [GitHub template documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository)

Template-generated repositories begin with new history; use a history-preserving migration for existing products when appropriate. [Creating a repository from a template](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)

Reset every product-specific value: name, slug, owner URLs, bundle/package ID, publisher, OAuth configuration, support contact, copyright, license decision, versions, signing settings, platforms, screenshots, release notes, changelog, and validation results. Search for leftover placeholders and old names. Do not carry SpotMenu-specific SDK workarounds, credentials, test counts, or compatibility claims into another app.

## 5. License, assets, secrets, dependencies, and privacy

- [ ] Confirm rights to publish the code. Select a license based on ownership, intended reuse, and dependency obligations; include its full text when licensing the project.
- [ ] Review third-party source/packages, fonts, icons, artwork, datasets, model assets, screenshots, and trademarks. Record required attribution and redistribution conditions.
- [ ] Use a reference repository for presentation inspiration. Do not automatically copy its code, screenshots, branding, or license. MIT may suit original permissively licensed code when obligations allow; a reference using GPL does not decide this project's license.
- [ ] Inspect the current tree and relevant Git history for keys, passwords, tokens, certificates, user data, internal URLs, logs, device identifiers, and local settings. Review archive contents too.
- [ ] Rotate exposed credentials. Deleting a secret from the latest file does not remove it from history; plan remediation deliberately.
- [ ] Store credentials in the OS credential store, protected signing storage, or scoped account/secret facilities appropriate to the chosen runner. Keep them outside Git, screenshots, logs, provenance, and packages. Do not print authentication tokens during checks.
- [ ] Review direct/transitive dependencies, advisories, native libraries, network endpoints, permissions, integrity, and update policy. Commit lockfiles where appropriate or document deterministic resolution.
- [ ] Document actual collection, storage, transmission, logs, retention, deletion, third-party access, and analytics. Match privacy disclosures to implementation and network behavior.
- [ ] Tests and previews use isolated fixtures and fictional data where possible. Keep real accounts, production APIs, and credential stores out of mocked test/screenshot paths.

## 6. Repository structure and documentation

Use ecosystem conventions; this is an adaptable scaffold, not a requirement to rename every existing project:

```text
project/
  README.md
  LICENSE
  .gitignore
  VERSION                     # or an authoritative manifest field
  BUILD_NUMBER                # only if the platform needs it
  CHANGELOG.md
  AGENTS.md                   # verified commands and project constraints
  CONTRIBUTING.md             # if contributions are welcome
  SECURITY.md                 # appropriate private reporting route
  Sources/                    # or src/, apps/, packages/
  Tests/
  Resources/                  # or assets/
  Scripts/
    verify.sh
    screenshots.sh
    package.sh
    prepare-release.sh
    draft-release.sh
  Docs/
    SETUP.md
    DEVELOPMENT.md
    RELEASING.md
    PRIVACY.md
    CAPABILITY_MATRIX.md
    VALIDATION.md
    RELEASE_NOTES.md
    ATTRIBUTIONS.md            # when applicable
    LAUNCH_CHECKLIST.md        # filled project copy
  screenshots/
    README.md                 # capture method and fixture disclosure
  .github/
    ISSUE_TEMPLATE/
    PULL_REQUEST_TEMPLATE.md
  dist/                       # generated, ignored; release staging
```

Script extensions and document names can follow the stack. In a monorepo, explain shared versus per-app files and commands. With no Actions, do not create `.github/workflows/`.

- [ ] Keep source, tests, assets, documentation, and scripts organized; remove unused examples and stale files.
- [ ] Ignore builds, caches, logs, temporary files, local settings, and generated dependencies; verify required source/assets remain tracked.
- [ ] Document prerequisites, toolchain versions, configuration, clean setup, build/run/test/package commands, and troubleshooting.
- [ ] Maintain one authoritative version. Align manifests, bundle metadata, package filenames, changelog, release notes, and tags; define monorepo conventions explicitly.
- [ ] Include contribution expectations, meaningful checks, redacted logs, and maintainer merge authority if contributions are welcome.
- [ ] Provide a working private vulnerability route and supported-version policy where needed. Do not request secrets in public bug reports.
- [ ] Issue templates collect version, OS/architecture, reproduction, expected/actual behavior, and safely redacted diagnostics. PR templates request change purpose and relevant validation.
- [ ] Verify all links, filenames, badges, commands, and images. Show only current badges backed by evidence; do not leave CI badges when Actions is disabled.

### README layout

1. Product name/icon and one-sentence description.
2. Clear current release/download or deployed link, with platform choices.
3. A small set of useful screenshots.
4. Shipped features, prerequisites, supported environments, and visible limitations.
5. Installation and first-use instructions, including permissions/sign-in and signing friction.
6. Brief build-from-source commands linked to development details.
7. Help, private security reporting, privacy, attribution, and license links.

Keep protocol details, architecture, extensive matrices, and advanced troubleshooting in linked docs. Do not describe planned functionality as shipped. If there is no published binary yet, link to source or label the download as forthcoming rather than creating a broken release link.

### Screenshot requirements

- [ ] Capture the actual current UI. Automated fixture renders may use native views with fictional data; label them as sample/preview screens.
- [ ] Cover first use, the main workflow, and relevant additional screens. Include light/dark, compact/expanded, or mobile layouts only when useful and supported.
- [ ] Remove tokens, real emails, private playlists, messages, device IDs, internal paths, and other personal data.
- [ ] Use readable, consistently sized images with descriptive filenames and alt text. Review crop, contrast, text, and overflow visually.
- [ ] Keep the capture command and fixture setup documented and repeatable. Update screenshots when the UI changes.
- [ ] Confirm branding/artwork rights. Never use generated mockups as proof of functionality or undisclosed screenshots from another app.

## 7. Local automation contract — no GitHub Actions

The following commands are a contract to implement for the project; they are not guaranteed to exist in a new repository. Equivalent stack-native commands are acceptable if documented.

| Command | Required behavior |
| --- | --- |
| `verify` | Run applicable formatting/lint/type checks, meaningful tests, build checks, and packaging checks; fail clearly on errors |
| `screenshots` | Produce current UI captures from documented, isolated data; require visual review |
| `package` | Build a fresh release bundle, validate metadata/architecture/signing/licenses, inspect contents, extract it again, and calculate hashes |
| `prepare-release` | Run verification; stage every required platform artifact, notes, hashes, and provenance from the exact clean release source |
| `draft-release` | Validate source/tag/version/provenance/assets, then upload an explicit draft; refuse accidental overwrite or publication |

- [ ] Disable GitHub Actions in repository settings and confirm its state when authorized. Remove workflow files for this mode.
- [ ] Keep local scripts version-controlled and runnable without GitHub authentication until upload. Use only the credentials necessary for the chosen operation.
- [ ] Document the exact command set and toolchain. Scripts honor intentional environment overrides and do not reuse stale artifacts as fresh build evidence.
- [ ] Clean or isolate staging for each build. Never mix old platform packages into a new release directory. Only upload an explicit validated asset list.
- [ ] Capture commands, exit status, test pass/fail/skip counts, toolchain/SDK, architecture, environment, and relevant logs without secrets.
- [ ] State what each skip means. Do not silently skip failed checks or claim tests on platforms the runner did not execute.
- [ ] Use branch rules appropriate to the team and available checks. Do not require nonexistent GitHub Actions checks.

If CI is explicitly chosen for another project, apply the same contract on its runner, use minimum token permissions and protected secrets, and record what CI did and did not exercise. CI does not replace install or real-use validation.

## 8. Build and behavior verification

- [ ] Start from a fresh checkout or isolated clean source directory, install documented prerequisites, and execute applicable checks.
- [ ] Test meaningful risks: data handling, permissions, authentication, concurrency, migrations, error recovery, and primary workflows. Do not fabricate coverage or add tests that merely mirror implementation.
- [ ] Run the primary journey with a clean profile/account/device where relevant. Record actual prerequisites, permission prompts, first launch, first success, and result.
- [ ] Exercise denied permissions, absent devices/services/network, invalid input, expired sessions, retry/recovery, corrupt/missing data, and offline behavior where applicable.
- [ ] Check upgrade from a real previous release, data migration, uninstall/removal, and downgrade compatibility when relevant.
- [ ] Review keyboard access, screen-reader labels, focus, contrast, resizing, reduced motion, localization, and performance for claimed surfaces.
- [ ] Record OS/device/browser/host/CPU combinations actually tested. Identify emulation, cross-compilation, physical hardware, and external user reports separately.
- [ ] Review logs, crash reports, local storage, network traffic, retention, and permission requests for unexpected sensitive behavior.
- [ ] Update the capability matrix, README, notes, and claims from the results.

### Validation entry template

| Field | Value |
| --- | --- |
| Date/time zone | _When_ |
| Commit/version/build | _Exact tested source or artifact_ |
| Environment | _OS, CPU/device/browser/host, compiler/SDK_ |
| Method | _Automated/mock/live/clean install/upgrade/cross-compile/user report_ |
| Command or steps | _Repeatable procedure_ |
| Result | _Pass/fail; actual counts and skips_ |
| Evidence | _Log, image, artifact hash, report link_ |
| Limits | _What this does not establish_ |

Never copy filled validation entries from a template or earlier version and present them as current results.

## 9. Release preparation, tagging, and packages

- [ ] Confirm the distribution scope and required artifacts per channel. Choose the next version/build and update notes and compatibility language.
- [ ] Verify final source and reviewed screenshots. Commit all intended source, documentation, and assets; generated `dist/` content remains ignored.
- [ ] Push the source when authorized. Confirm the source commit, clean tracked/untracked state, and correct remote/default branch.
- [ ] Create an annotated version tag on that exact source commit. Confirm the tag does not already exist locally/remotely; never silently reuse or move a published version tag.
- [ ] Push the tag when authorized and verify the remote tag resolves to the intended commit.
- [ ] Build release packages from clean source at that tag, preferably an isolated checkout. Scripts must not modify tracked source during this final build. If generated screenshots or source change, finalize those changes before creating the tag and rebuild.
- [ ] Verify release configuration, production endpoints/dependencies/flags, app identity, permissions/entitlements, architecture, icon, license, version/build, and signing state.
- [ ] Inspect archive paths and contents against the intended allowlist. Exclude credentials, personal data, debug output, local configuration, and unrelated files. Check runtime resources and redistribution notices are present.
- [ ] Name artifacts by product, version, platform, and architecture as needed. Extract the final archives and verify the extracted app/package, not only the pre-archive staging bundle.
- [ ] Generate SHA-256 hashes for every shipped binary; include other uploaded files in the manifest where useful. Do not include the checksum manifest's own hash in itself.
- [ ] Record full commit, tag, version/build, clean state, build time/time zone, runner OS/CPU, toolchain/SDK, dependencies, signing/notarization status, and verification results in build information.
- [ ] Write notes covering changes, installation/update, requirements, actual validation, limitations, signing friction, support, and rollback guidance.
- [ ] Retain the previous good release and define hotfix/rollback steps, migration limits, responsible owner, and user notice route.

Checksums establish file identity/integrity against the recorded digest. They do not alone establish publisher authenticity, cryptographic attestation, or byte-for-byte reproducible builds. Do not claim those properties without their separate verification.

Suggested staging layout:

```text
dist/release-<version>/
  <product>-<version>-<platform>-<architecture>.<zip|dmg|exe|vsix|other>
  SHA256SUMS.txt
  BUILD_INFO.txt
  RELEASE_NOTES.md
```

### GitHub CLI sequence

This example assumes the project implements the documented script contract and uses `VERSION`. Set the correct owner/repository first. Check all gates and recorded authorization before mutation commands. Do not execute placeholders blindly.

```sh
# Run from the actual repository root after final source is committed.
release_repo='OWNER/REPOSITORY'
release_version="$(cat VERSION)"
release_tag="v${release_version}"

git status --short
git rev-parse HEAD
git remote -v
./Scripts/verify.sh

# Proceed only if clean, verified, authorized, and the tag is new.
git push origin HEAD
git tag -a "$release_tag" -m "Release ${release_version}"
git push origin "$release_tag"

# Build the exact tagged source in a clean/isolated environment.
./Scripts/prepare-release.sh
./Scripts/draft-release.sh
```

The draft script should use `gh release create --draft --verify-tag`, the explicit repository, an explicit asset list, and `--notes-file` pointing to reviewed notes. `--verify-tag` prevents release creation against an absent remote tag; separately check that the tag identifies the intended source. [GitHub CLI release creation](https://cli.github.com/manual/gh_release_create)

## 10. Draft validation, publication, and visibility

- [ ] Upload all verified artifacts, notes, build information, and hashes to a draft or staged channel. Refuse accidental overwrite of an existing release.
- [ ] Download every uploaded asset into a separate empty directory. Compare it to the local staged file and verify the hash manifest.
- [ ] Extract/install/open the downloaded artifacts and smoke-test the primary flow on environments required by the chosen scope. Record failures or narrower experimental claims before publication.
- [ ] Review the concrete draft, tag, filenames, notes, compatibility, signing language, support links, and previous version/rollback path.
- [ ] Confirm publication authorization covers this channel and version. If missing, request it now with the ready draft; if already given, proceed within that scope.
- [ ] Publish the reviewed draft or approved deployment/store submission. Set Latest or prerelease intentionally; do not mark an experimental prerelease as stable by accident.
- [ ] Verify the release is actually published, points to the intended immutable tag, and exposes all required assets.
- [ ] Confirm actual repository visibility from GitHub and, for public distribution, a logged-out browser. Check owner/name/description/topics/website/default branch/license detection and public access.
- [ ] Re-download public artifacts after publication and verify hashes; check the public installation and support links. For a website, run production smoke checks after deployment.
- [ ] Record completion. Distinguish submission pending, draft, published, private-only, and publicly available accurately.

For an authorized stable GitHub release, publication can use:

```sh
gh release edit "$release_tag" --repo "$release_repo" --draft=false --latest
gh release view "$release_tag" --repo "$release_repo"
gh release download "$release_tag" --repo "$release_repo" --dir /ABSOLUTE/EMPTY/DOWNLOAD-DIRECTORY
```

Choose prerelease/Latest settings appropriate to the actual release. [GitHub CLI release editing](https://cli.github.com/manual/gh_release_edit)

Public URL verification happens after public publication. Before publication, validate draft downloads through authorized access; do not create an impossible requirement to verify a public URL that does not exist yet.

## 11. GitHub settings and support

- [ ] Confirm repository owner, final name, visibility, collaborators, default branch, description, topics, website, and license.
- [ ] Apply appropriate review/force-push/deletion rules and collaborator access. Required checks must match the chosen automation mode and available account features.
- [ ] Verify Actions remains disabled for the local workflow. Remove stale workflows, permissions, CI badges, and CI-dependent release instructions.
- [ ] Review supported secret scanning/push protection, dependency alerts, and update tools. Do not claim enabled protections without checking the account/repository settings.
- [ ] Enable issues/discussions only when someone will maintain them; verify bug and private vulnerability routes.
- [ ] Check public README images/download links, templates, source tags, release notes, package names, license, and old-repository references.

## 12. Platform branches

Complete relevant branches. Mark unused branches N/A with a reason. Recheck official platform rules for the actual channel; this guide does not freeze store requirements.

### A. Website or web app

- [ ] Compare preview/production environment variables, feature flags, API URLs, secret handling, deployment permissions, and data isolation.
- [ ] Verify domain ownership/renewal access, DNS, redirects, TLS/HTTPS, canonical URL, and mixed content.
- [ ] Test relevant authentication, session expiry, reset/logout, role boundaries, and unauthorized access.
- [ ] Verify schema migrations, backup/restore, rollback compatibility, and deployment ordering for stateful services.
- [ ] Check CDN/cache invalidation and stale assets where used.
- [ ] Test critical paths and links on claimed browsers/viewports; review accessibility and relevant performance measurements.
- [ ] Reconcile analytics/cookies/consent with actual requests if tracking exists.
- [ ] Check titles, metadata, indexing controls, sitemap, canonical URLs, and preview cards when discoverability matters.
- [ ] Verify production error monitoring without sensitive payloads; run new-visitor smoke checks and confirm rollback after deployment.

### B. Desktop and mobile apps

- [ ] List actual OS/minimum version/CPU/device/channel/package format; test the exact downloaded installer or bundle on the required clean environment.
- [ ] Verify install location, identity/icon/version, launch, permissions and denied access, default handlers/integrations, background helpers, and native dependencies.
- [ ] Test clean install, upgrade from an actual prior release, settings/data migration, update failure, uninstall, and data removal where promised. Document downgrade limits.
- [ ] Verify diagnostics and crash reporting do not expose sensitive data.
- [ ] Apply signing, installer, sandbox, and review requirements for the chosen route. On macOS, distinguish ad-hoc signing, Developer ID signing, and notarization; do not call ad-hoc builds Apple verified. Verify entitlements and downloaded trust/install behavior. [Apple Developer ID documentation](https://developer.apple.com/developer-id/)
- [ ] If automatic updates exist, verify their source, transport, signature/trust checks, and recovery. Otherwise describe the manual update process.
- [ ] For Windows/Linux distribution, verify the chosen installer/package, permissions, dependencies, signing/trust where applicable, desktop integration, and removal on claimed environments.
- [ ] For mobile stores, verify current account access, bundle/package identity, test tracks, screenshots, age/content information, privacy/data disclosures, review instructions, and actual submission status.
- [ ] Install from the actual public download or approved store/test track and test the main journey. Record pending versus approved review separately.

### C. VS Code extension

- [ ] Verify manifest identity/version/publisher, description, host compatibility, commands, activation, dependencies, extension kind, and desktop/web/remote claims.
- [ ] Confirm publisher ownership and current supported publishing authentication. Keep credentials outside source/packages and check current requirements before every publication.
- [ ] Package with the supported tooling, inspect the exact VSIX for runtime files, correct paths, icon/license/README/changelog, and absence of development files/secrets.
- [ ] Install that VSIX in a clean profile at claimed host versions. Test activation, commands, settings, trust/permissions, errors, update, and uninstall.
- [ ] Test desktop, web, and remote hosts separately when claimed; document limitations.
- [ ] Verify live Marketplace identity/version, README/images, privacy/support/license, and public installation after publication. [Official extension publishing guide](https://code.visualstudio.com/api/working-with-extensions/publishing-extension)

### D. Chrome extension

- [ ] Check current manifest and Web Store requirements, supported browser versions, identity/version, action, scripts, icons, target sites, and update route.
- [ ] Confirm single purpose and necessary API/host permissions; explain prompts and test optional/denied access.
- [ ] Review current code packaging and remote-code/execution policies rather than assuming old rules still apply.
- [ ] Reconcile collection/transmission/storage/third-party access with declarations, privacy policy where required, and listing claims.
- [ ] Install in a clean browser profile and test intended sites, first use, permissions, invalid pages/network failures, disabled state, update, and uninstall/data cleanup.
- [ ] Inspect and test the exact packed ZIP for correct paths/version, required files, and absence of secrets/development output.
- [ ] Verify publisher access, listing/screenshots/support, review instructions/test access, submission status, and live listing after approval. [Publishing guide](https://developer.chrome.com/docs/webstore/publish), [Program policies](https://developer.chrome.com/docs/webstore/program-policies/policies)

## 13. Go/no-go gates and owner handoff

Do not publish beyond the recorded scope until every applicable prepublication gate passes with evidence. N/A requires a reason. Unresolved ownership, secrets, or inaccurate claims cannot be dismissed by calling a binary experimental.

| Prepublication gate | Pass requires |
| --- | --- |
| Scope and claims | Public language matches evidence; unsupported/unverified features are qualified or removed |
| Rights and secrets | Tree/history/assets are publishable; chosen license is appropriate; exposed credentials addressed |
| Source and build | Clean exact source/tag; version alignment; applicable checks passed; environment and limits recorded |
| Artifacts | Required assets uploaded to draft/staging; downloaded files verified; install/behavior checks satisfy stated scope |
| User instructions | Accurate requirements, installation, privacy, signing, limitations, and reporting paths |
| Ownership and authorization | Correct account/visibility/channel; publication authorized; support/rollback owner available |

If approval is still needed, hand over the repository URL/path, diff or final commit, license/rights decisions, draft URL, artifact list/hashes, test evidence, compatibility/signing limitations, privacy summary, and exact intended publication action. State only the missing decision; do not repeat settled questions.

After publication, the completion gate requires public access for public channels, correct tag/notes/assets, matching public-download hashes, working installation/help links, and production smoke checks applicable to the route. If that gate fails, record the failed launch step and take the documented corrective action; do not report completion.

## 14. Release record and maintenance

| Field | Fill in after each release |
| --- | --- |
| Version/build | _Authoritative values_ |
| Source and tag | _Full commit; immutable tag; tag URL_ |
| Build evidence | _Local log or CI URL; clean state; OS/CPU/toolchain/SDK; build time_ |
| Signing/trust | _Actual signing/notarization/store status_ |
| Artifacts | _Filename, size, public URL, SHA-256 for every binary_ |
| Download checks | _Draft/public retrieval date and comparison result_ |
| Actually tested | _Version/environment/method/date/result/evidence_ |
| Limits | _Known issues; experimental/unverified combinations; public disclosure link_ |
| Repository | _Owner/name; actual visibility at final verification; Actions state_ |
| Publication | _Date/time/time zone; publisher; channel; draft/pending/published status_ |
| Support/rollback | _Owner, route, previous good version, data migration limits_ |
| Next review | _Owner; date or trigger; dependencies/support/production checks_ |

- [ ] Run a stranger test: find the product, choose a download, install/use it, understand its limits, and report a problem without owner context or sharing secrets.
- [ ] Assign a realistic cadence for local checks or CI, uptime/crashes where relevant, dependency advisories, store review, and issue triage. Use privacy-conscious monitoring.
- [ ] Refresh capability evidence, screenshots, links, and docs when behavior changes.
- [ ] Publish hotfixes under new traceable versions. Do not silently replace published tags or packages; explain a withdrawn/bad release and the recommended replacement.
- [ ] Maintain an incident contact and verify rollback/restore when risk warrants it. Do not assume an older binary can read newer data.
- [ ] Announce shipped/tested/experimental/unsupported/planned work accurately and link to the real release and limitations. Send announcements only with authorization.

## 15. Copyable instruction for a future project

Fill the brackets and remove unused options before handing this to a collaborator or coding agent:

> Prepare **[PRODUCT]** using Public Project Launch Guide v3. The source is **[ABSOLUTE SOURCE PATH]** and the destination is **[ABSOLUTE DESTINATION PATH]**, with GitHub repository **[OWNER/NAME]**, **[PUBLIC/PRIVATE]** visibility, and **[STANDALONE/MONOREPO]** structure. Preserve relevant history and existing user work. Use **[REFERENCE URL]** for presentation inspiration while keeping this project's own code, branding, rights, and license decisions.
>
> Use local verification, screenshot capture, packaging, and release scripts. Keep GitHub Actions disabled; do not add workflows or CI badges. Adapt the scaffold and commands to the stack. Create concise user documentation, actual or labeled fixture screenshots, support templates, a capability matrix, validation records, release notes, and a documented maintenance/rollback path. Review code/assets/dependency rights, secrets including history, and privacy behavior before public exposure.
>
> The target platforms are **[PLATFORMS/MINIMUM VERSIONS/ARCHITECTURES]** and the release scope is **[SOURCE-ONLY/EXPERIMENTAL BINARY/SUPPORTED BINARY/WEBSITE/STORE]**. Record real test evidence; distinguish compilation, mocks, screenshots, cross-compilation, real usage, and clean installation. Do not invent compatibility, signing, notarization, performance, or privacy claims.
>
> Publication authorization covers **[PREPARE ONLY / PUSH SOURCE AND TAG / UPLOAD DRAFT / PUBLISH RELEASE / CHANGE VISIBILITY — SELECT EXPLICITLY]**. Complete the concrete reviewable work and execute already-authorized steps. Ask only for unresolved material decisions or actions outside that scope. If publishing, build the clean exact tagged source, upload an explicit draft asset list with SHA-256 hashes and build provenance, validate actual downloads and installation for the chosen scope, publish, then verify public visibility/links/assets and record the outcome. Leave any unverified behavior clearly open.

**Final standard:** A stranger can understand the product, know whether their environment is supported, install or run it, see its limitations, and report a problem without contacting the owner first.
