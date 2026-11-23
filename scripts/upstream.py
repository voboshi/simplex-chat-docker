#!/usr/bin/env python3
"""Verify a pinned release or prepare its complete lock update."""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.request

REPO = "simplex-chat/simplex-chat"
ROOT = pathlib.Path(__file__).resolve().parent
LOCK = ROOT / "upstream.lock.json"
if not LOCK.exists():
    LOCK = ROOT.parent / "upstream.lock.json"
FINGERPRINT = "BBDF7BDAD1548B16836AF5B9D53BDFD153C366BA"
ASSET = "simplex-chat-ubuntu-22_04-x86_64"

def download(url, path):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as response, path.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    return hashlib.sha256(path.read_bytes()).hexdigest()

def api(path):
    req = urllib.request.Request("https://api.github.com/repos/" + REPO + path)
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)

def verify(lock, out):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", lock["version"]):
        raise ValueError("Invalid stable release version")
    if not re.fullmatch(r"[0-9a-f]{40}", lock["source_commit"]):
        raise ValueError("Invalid source commit")
    if lock["asset"] != ASSET:
        raise ValueError("Unexpected executable asset")
    if lock["signed_asset"] != lock["version"] + "/" + ASSET:
        raise ValueError("Unexpected signed manifest filename")
    out.mkdir(parents=True, exist_ok=True)
    base = "https://github.com/" + REPO + "/releases/download/" + lock["version"] + "/"
    for remote, field, local in [
        (ASSET, "binary_sha256", "simplex-chat"),
        ("_sha256sums", "checksums_sha256", "_sha256sums"),
        ("_sha256sums.asc", "signature_sha256", "_sha256sums.asc"),
        ("LICENSE", "license_sha256", "LICENSE"),
    ]:
        if not re.fullmatch(r"[0-9a-f]{64}", lock[field]):
            raise ValueError("Invalid SHA-256 pin")
        if download(base + remote, out / local) != lock[field]:
            raise RuntimeError("Upstream integrity verification failed")
    key = out / "release-key.asc"
    download("https://keys.openpgp.org/vks/v1/by-fingerprint/" + FINGERPRINT, key)
    with tempfile.TemporaryDirectory() as home:
        prefix = ["gpg", "--batch", "--homedir", home]
        subprocess.run(prefix + ["--import", str(key)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(prefix + ["--status-fd", "1", "--verify",
                                str(out / "_sha256sums.asc"), str(out / "_sha256sums")],
                                check=True, capture_output=True, text=True)
        if any(status in result.stdout for status in ("EXPKEYSIG", "EXPSIG", "REVKEYSIG", "KEYREVOKED")):
            raise RuntimeError("Release signing key is expired or revoked")
        valid = [line.split() for line in result.stdout.splitlines()
                 if line.startswith("[GNUPG:] VALIDSIG ")]
        if not any(line[2] == FINGERPRINT or (len(line) == 12 and line[11] == FINGERPRINT)
                   for line in valid):
            raise RuntimeError("Unexpected release signing key")
    matches = []
    for line in (out / "_sha256sums").read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].removeprefix("*") == lock["signed_asset"]:
            matches.append(parts[0])
    if matches != [lock["binary_sha256"]]:
        raise RuntimeError("Signed manifest does not match the selected binary")
    if api("/commits/" + lock["version"])["sha"] != lock["source_commit"]:
        raise RuntimeError("Upstream tag moved")
    key.unlink()
    source = "https://github.com/" + REPO + "/archive/" + lock["source_commit"] + ".tar.gz"
    (out / "SOURCE.txt").write_text("SimpleX Chat corresponding source\n" + source + "\n")
    (out / "upstream.lock.json").write_text(json.dumps(lock, indent=2) + "\n")
    print("Upstream binary, signature, license and source commit verified.")

def update():
    release = api("/releases/latest")
    tag = release["tag_name"]
    if release["draft"] or release["prerelease"] or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise RuntimeError("A stable upstream release is required")
    assets = {a["name"]: a for a in release["assets"]}
    lock = {"version": tag, "source_commit": api("/commits/" + tag)["sha"],
            "asset": ASSET, "signed_asset": tag + "/" + ASSET}
    for name, field in [(ASSET, "binary_sha256"), ("_sha256sums", "checksums_sha256"),
                        ("_sha256sums.asc", "signature_sha256"), ("LICENSE", "license_sha256")]:
        digest = assets[name].get("digest", "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise RuntimeError("Upstream release lacks integrity metadata")
        lock[field] = digest.removeprefix("sha256:")
    previous = json.loads(LOCK.read_text())
    if previous["version"] == tag and previous != lock:
        raise RuntimeError("Pinned release material changed; manual review is required")
    with tempfile.TemporaryDirectory() as temp:
        verify(lock, pathlib.Path(temp))
    LOCK.write_text(json.dumps(lock, indent=2) + "\n")
    print("Complete upstream lock prepared for review.")

if __name__ == "__main__":
    if sys.argv[1:] == ["update"]:
        update()
    elif len(sys.argv) == 3 and sys.argv[1] == "verify":
        verify(json.loads(LOCK.read_text()), pathlib.Path(sys.argv[2]).resolve())
    else:
        raise SystemExit("Usage: upstream.py update | verify OUTPUT_DIRECTORY")
