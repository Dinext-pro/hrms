# Dinext source upgrade

Selected upstream release: [v15.64.5](https://github.com/frappe/hrms/releases/tag/v15.64.5).
Immutable upstream commit: `e58e0c22ecb6c2d7f3f3b4d5b70cc426d59e0ee9`.
Dinext integration line: `dinext/main/version-15`.

`dinext/vendor/version-15` was fast-forwarded from `24bac85c1b6aa1fe9298bf54963a19a8906aa282` (`v15.60.1`) to the selected tag. The merge parents are the previous Dinext tip `cdd0b71d6ad90ea333211e579564ab8f4daf302a` and that vendor tip.

## Preserved company changes

Keep the existing Dinext CI profile (`.github/dinext-ci.json` mode `repository`), policy workflow, validation workflow and the README note that names `dinext/main/version-15`. Upstream product workflows that were already disabled stay under `.github/imported-workflows-disabled/`. There is no product patch on top of the selected tag.

## Verification and activation

This pull request does not change a running site, a Support or Prod manifest, or an existing tag.

Compatibility acceptance installs this revision on Frappe `dinext/upgrade/v15.123.0` and ERPNext `dinext/upgrade/v15.123.0`, then migrates, builds and pings. Cypress acceptance completes setup on that disposable site and runs the upstream Frappe `cypress/integration/awesome_bar.js` spec. A skipped job is not acceptance.

## Verification record

The result of this revision is the GitHub check runs on this pull request: `Validation / Repository checks`, `Compatibility acceptance` and `Cypress acceptance`. This file does not claim those runs passed before they complete.
