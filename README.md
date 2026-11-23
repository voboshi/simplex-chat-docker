# SimpleX Chat in Docker

The official SimpleX Chat command-line client in a non-root Debian slim image.
Initial platform: linux/amd64. Profiles and databases persist in /data.
This is a chat client, not an SMP or XFTP server. Attachment handling is outside
the initial tested scope.

## Local build

```sh
docker compose build --pull
docker compose up -d
```

The example uses a named volume and creates a generic profile on first start.
Back up the volume before upgrading: database migrations may prevent downgrades.
The volume contains sensitive profile and message data; protect it and backups.
No database encryption key is baked into the image.

## Control socket

The upstream server binds 127.0.0.1:5225 inside the container. It has no
authentication. There are no published host ports. Do not add a reverse proxy,
a port forwarder, or host networking.

A trusted client in a separate container can use Docker's
`--network container:<simplex-container>` or Compose's
`network_mode: service:simplex` and connect to ws://127.0.0.1:5225.
This shares the network namespace only; do not share the state volume or Docker
socket. Every process in that namespace must be trusted.

The dedicated bridge permits outbound relay connections. It is intentionally
not an `internal: true` network, which would prevent normal relay access.
Unrelated bridge peers cannot reach the loopback listener.

Upstream prints raw control commands to stdout. The entrypoint discards stdout
and stderr before starting it, and Compose additionally disables retained logs.
Exit status and container state remain available; message-bearing diagnostics
are not retained. Overriding the entrypoint removes that protection.

## Verification and updates

Build both test images, then run the synthetic check:

```sh
docker build --platform linux/amd64 --target runtime -t simplex-chat:test .
docker build --platform linux/amd64 --target smoke -t simplex-chat:smoke .
sh tests/smoke.sh
```

This tests startup, loopback-only reachability, profile and local text
persistence after container recreation, non-root execution, and no published
ports, using only synthetic data.

The upstream version, source commit, binary checksum and signed-checksum
material move together in upstream.lock.json. Build verification fails closed
on a checksum or signature mismatch.

Renovate proposes Docker base tag/digest and GitHub Action SHA updates in a
weekly Tuesday 05:00–09:00 UTC window, and tracks other supported manifests. A separate
trusted scheduled workflow proposes verified upstream lock updates. Neither
auto-merges changes nor publishes a dependency update. Review and merge an
update, then create a versioned release.

Debian packages are installed from signed Debian repositories at build time.
Clean scheduled builds and release builds upgrade the base system packages and
refresh installed dependencies; they are not
bit-for-bit reproducible across repository updates. The upstream executable
itself is deterministically pinned and verified.

Release publication requires a successful build, smoke tests, and a fresh
vulnerability scan rejecting fixable HIGH/CRITICAL findings. Scanners do not
fully inventory statically linked Haskell code or detect every upstream flaw.
Review upstream security advisories and release notes as well as scanner results.

See [SOURCE.md](SOURCE.md) for licenses and corresponding-source access.

## Release operation

Create a release tag such as v7.1.4-r1 from a reviewed commit on main.
The workflow publishes only after testing and scanning the image, then attaches
provenance and a CycloneDX SBOM to its exact digest. It attempts a separate
credential-free pull of every image layer and reports the digest and platform.
A push is not proof of public access: newly created GHCR packages may require
their package visibility to be set to public. Never use credentials in a pull
test intended to verify anonymous access.

Dependency automation needs Actions enabled and repository permission for
Actions to create pull requests. The upstream updater uses only GITHUB_TOKEN.
Its actions:write permission dispatches the read-only build workflow because
GITHUB_TOKEN-created pull requests do not themselves trigger another PR run.
The updater never executes the downloaded client. Review all proposed changes
and passing checks before merging, and explicitly publish a new release.

Docker, Python and GPG on CI hosts follow GitHub's hosted-runner updates.
The smoke-test image uses only Debian's Python standard library; there are no
pip dependencies. Skopeo is installed from the runner's signed distribution
repositories solely for the anonymous publication check.

## Renovate activation

Add this repository to the existing Renovate GitHub App installation's selected
repositories. No additional account-wide access or post-upgrade command execution
is required. Configuration alone is not proof that Renovate is running: confirm
its onboarding or dependency dashboard and first repository run.

SimpleX's upstream lock is excluded from Renovate. Its release-attachment
datasource can discover hashes, but does not verify the release's OpenPGP
signature or update this complete signed lock and source commit as one verified
operation. Only the narrow upstream workflow owns that lock.

Unversioned Debian packages in apt-get install are not individually tracked by
Renovate. The weekly clean CI build refreshes packages and scans with the current
vulnerability database. A new reviewed release is required to ship these fixes;
scheduled CI does not silently replace published image tags.
