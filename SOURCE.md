# Corresponding source

This package redistributes the unmodified official SimpleX Chat client under
AGPL-3.0. The full license is installed at /usr/share/doc/simplex-chat/LICENSE.

The exact upstream release, binary hash and source commit are recorded in
upstream.lock.json, also installed beside the license in the image.
The generated SOURCE.txt beside it supplies an immutable download URL for that
exact commit.

The upstream cabal.project records dependency source repositories, exact
commits and the package index timestamp. Upstream Dockerfile.build and
scripts/simplex-chat-reproduce-builds.sh describe its build environment.
The upstream executable was built on Ubuntu; this package runs it on Debian.
No upstream source modifications are made.

Packaging source:
https://github.com/voboshi/simplex-chat-docker

Retain the licenses and these source directions when redistributing. Maintain
equivalent access to the exact corresponding source for as long as required by
AGPL section 6(d), including dependency sources and build scripts. Debian package
copyright and source directions are retained in /usr/share/doc.
