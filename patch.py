#!/usr/bin/env python3
"""Local egress hardening for dsh-our-free-model.

Turns every "phone home" channel off and leaves the model lane alone:

  1. announcement feed      raw.githubusercontent / jsdelivr / gcore / gh-proxy
  2. self-updater           GitHub manifest + release download/install
  3. public-IP echo         api.ipify.org / ipinfo.io / ipapi.co
  4. recommended-projects   api.github.com/repos/* (star counts)
  5. first-run modal        settings.onboarding announcement gate
  6. sponsor banner         beichenapi.com referral link (?aff=…, 10% cashback)
  7. star buttons           5 render sites across the settings pages
  8. update/reload routes   POST /update, POST /update/apply, POST /reload

What it does NOT touch: the EAC co-paid lane and its server-side GitHub gate.
That gate is the author's, it lives on his gateway, and disabling a star button
in a locally-patched copy neither reaches nor bypasses it.

Usage:
    python3 patch.py --check <package-dir>    verify every anchor, write nothing
    python3 patch.py         <package-dir>    apply in place

Written against 2.8.3. A different version fails loudly at the first anchor
instead of producing a half-patched package.
"""
import re
import sys
from pathlib import Path

TARGET_VERSION = "2.8.3"
S = re.S


def sub(text, old, new, count=1, label=""):
    n = text.count(old)
    if n != count:
        raise SystemExit(f"[FAIL] {label}: expected {count} occurrence(s), found {n}")
    return text.replace(old, new)


def replace_between(text, start, end, new, label=""):
    i = text.find(start)
    if i < 0:
        raise SystemExit(f"[FAIL] {label}: start marker not found")
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f"[FAIL] {label}: end marker not found")
    return text[:i] + new + text[j:]


def patch_feed(s):
    s = re.sub(r"export const DEFAULT_FEED_SOURCES = \[.*?\n\]",
               "export const DEFAULT_FEED_SOURCES = []", s, count=1, flags=S)
    if "export const DEFAULT_FEED_SOURCES = []" not in s:
        raise SystemExit("[FAIL] feed: DEFAULT_FEED_SOURCES was not emptied")

    s = replace_between(
        s, "export async function fetchFeed(",
        "\n/**\n * The poll loop's state:",
        "export async function fetchFeed() {\n"
        "  // local policy: the announcement feed is disabled; no remote read.\n"
        "  return { feed: { announcements: [] }, source: '' }\n"
        "}\n", "feed.fetchFeed")

    s = replace_between(
        s, "  /** Read the cached copy from disk;", "  readDisk() {",
        "  /** local policy: no remotely published copy is loaded. */\n"
        "  load() {\n"
        "    this.cache = { at: 0, source: '', announcements: [] }\n"
        "    this.knownIds = new Set()\n"
        "    return this.cache\n"
        "  }\n\n  ", "feed.load")

    s = replace_between(
        s, "  sources() {", "  /**\n   * One poll.",
        "  sources() {\n    return []\n  }\n\n  ", "feed.sources")

    s = replace_between(
        s, "  poll() {", "  /** Write the last good copy;",
        "  /** local policy: nothing to poll. */\n"
        "  poll() {\n"
        "    return Promise.resolve({ arrived: [], total: 0, source: '' })\n"
        "  }\n\n  ", "feed.poll")
    return s


def patch_probe(s):
    s = replace_between(
        s, "/** Public-echo sources, tried in order; any one answering is enough. */",
        "\n/** Verdicts the probe can return",
        "/** local policy: no third-party public-IP echo. */\nconst ECHO_SOURCES = []\n",
        "probe.echoSources")
    s = sub(s, "export async function detectEgress({ signal, timeoutMs = 8000 } = {}) {\n",
            "export async function detectEgress({ signal, timeoutMs = 8000 } = {}) {\n"
            "  // local policy: no public-IP echo, so egress changes are never detected.\n"
            "  return undefined\n", label="probe.detectEgress")
    return s


def patch_picks(s):
    s = sub(s,
            "export const PICKS_API_BASE = process.env.OFM_PICKS_API_BASE ?? 'https://api.github.com'",
            "export const PICKS_API_BASE = ''", label="picks.apiBase")
    s = sub(s,
            "export function createPickStats({ repos = PICK_REPOS, fetchImpl = fetch, cacheFile = '', now = Date.now, log = () => {} } = {}) {\n",
            "export function createPickStats({ repos = PICK_REPOS, fetchImpl = fetch, cacheFile = '', now = Date.now, log = () => {} } = {}) {\n"
            "  // local policy: no GitHub reads. The recommended-projects page is gone.\n"
            "  const empty = () => ({ fetchedAt: 0, ok: false, repos: [] })\n"
            "  return { view: async () => empty(), refresh: async () => empty(), snapshot: empty }\n",
            label="picks.createPickStats")
    return s


def patch_updater(s):
    s = re.sub(r"export const DEFAULT_MANIFEST_SOURCES = \[.*?\n\]",
               "export const DEFAULT_MANIFEST_SOURCES = []", s, count=1, flags=S)
    s = sub(s, "  sources() {\n    return this.deps.defaultSources\n  }",
            "  sources() {\n    return []\n  }", label="updater.sources")
    s = sub(s, "  async check() {\n    try {",
            "  async check() {\n"
            "    // local policy: the self-update channel is disabled; nothing is fetched.\n"
            "    const current = this.deps.runningVersion ?? this.currentVersion()\n"
            "    return { available: false, current, latest: '' }\n"
            "    /* eslint-disable no-unreachable */\n"
            "    try {", label="updater.check")
    s = sub(s, "  async apply({ version, onProgress = () => {}, activate } = {}) {\n",
            "  async apply({ version, onProgress = () => {}, activate } = {}) {\n"
            "    throw new Error('in-app upgrade is disabled by local policy')\n",
            label="updater.apply")

    # Make the network primitives unreachable a second time and empty the
    # endpoint literals, so no remote address survives in the shipped file.
    s = sub(s, "const RAW_PROXY = 'https://gh-proxy.com'", "const RAW_PROXY = ''",
            label="updater.rawProxy")
    s = sub(s, "export async function downloadManifest(sources, { timeoutMs = 15000, fetchImpl = fetch, verifyKey = PINNED_MANIFEST_PUBLIC_KEY } = {}) {\n",
            "export async function downloadManifest(sources, { timeoutMs = 15000, fetchImpl = fetch, verifyKey = PINNED_MANIFEST_PUBLIC_KEY } = {}) {\n"
            "  throw new Error('update channel is disabled by local policy')\n",
            label="updater.downloadManifest")
    s = sub(s, "export async function stageRelease({ manifest, manifestUrl, stageDir, fetchImpl = fetch, concurrency = 4, onProgress = () => {}, timeoutMs = 30000 }) {\n",
            "export async function stageRelease({ manifest, manifestUrl, stageDir, fetchImpl = fetch, concurrency = 4, onProgress = () => {}, timeoutMs = 30000 }) {\n"
            "  throw new Error('update channel is disabled by local policy')\n",
            label="updater.stageRelease")
    s = sub(s, "export async function installStaged(stageDir, pkgDir, files) {\n",
            "export async function installStaged(stageDir, pkgDir, files) {\n"
            "  throw new Error('in-app install is disabled by local policy')\n",
            label="updater.installStaged")
    for label, lit in [
        ("updater.url.api", "https://api.github.com/repos/${REPO}/commits/${encodeURIComponent(ref)}"),
        ("updater.url.refs", "https://github.com/${REPO}/info/refs?service=git-upload-pack"),
        ("updater.url.atom", "https://github.com/${REPO}/commits/${encodeURIComponent(ref)}.atom"),
        ("updater.url.raw", "https://raw.githubusercontent.com/${REPO}/${sha}/${rest}"),
    ]:
        s = sub(s, lit, "", label=label)
    return s


def patch_extensions(s):
    """The extension marketplace: an auto-refresh on boot plus every six hours
    that pulls a signed index from a *second* repository, and — when the setting
    is on — installs and runs JavaScript from it. The README's "this table is
    every outbound target" does not list it."""
    s = sub(s,
            "export function registrySources() {\n"
            "  const override = process.env.OFM_EXTENSIONS_REGISTRY\n"
            "  if (override !== undefined && override !== '') return [String(override)]\n"
            "  return [",
            "export function registrySources() {\n"
            "  // local policy: no marketplace index, so no installable third-party code.\n"
            "  return []\n"
            "  /* eslint-disable no-unreachable */\n"
            "  const override = process.env.OFM_EXTENSIONS_REGISTRY\n"
            "  if (override !== undefined && override !== '') return [String(override)]\n"
            "  return [", label="extensions.registrySources")
    return s


def patch_index(s):
    s = replace_between(
        s, "  // Feed poll: shortly after boot, then on the configured period.",
        "  /**\n   * Run one task every `ms`",
        "  // local policy: no announcement-feed poll and no update check.\n",
        "index.firstFeedPoll")

    s = replace_between(
        s, "  if (!managed) {\n    every(() => {\n      void feed.poll()",
        "  // Automatic availability probing is disabled by owner policy.",
        "  // local policy: the periodic feed/update round is removed; catalog refresh stays below.\n",
        "index.feedLoop")

    s = replace_between(
        s, "  // The first update check waits for the boot refresh to settle,",
        "  // Keep the module-level \"notified\" marker in sync",
        "  // local policy: no first update check.\n\n",
        "index.firstUpdateCheck")

    s = sub(s,
            "        const acknowledged = deps.managedDistribution === true || deps.settings.get().announcementAck === ANNOUNCEMENT_VERSION\n"
            "        return send(200, { version: ANNOUNCEMENT_VERSION, acknowledged })",
            "        // local policy: the first-run announcement never blocks the shell.\n"
            "        return send(200, { version: ANNOUNCEMENT_VERSION, acknowledged: true })",
            label="index.announcementRoute")

    s = sub(s, "        if (deps.managedDistribution !== true) await deps.announcements.refresh()\n", "",
            label="index.announcementsRefresh")

    s = sub(s,
            "        const result = await deps.update.check()\n"
            "        return send(200, { ...result, status: deps.update.status() })",
            "        return send(200, { available: false, current: deps.update.status().current, latest: '', status: deps.update.status(), disabled: true })",
            label="index.updateCheck")

    s = sub(s,
            "        const body = await readJson(req)\n"
            "        const result = await deps.update.apply(body?.version === undefined ? undefined : String(body.version))\n"
            "        return send(200, { ok: true, ...result })",
            "        return send(409, { error: 'in-app upgrade is disabled by local policy' })",
            label="index.updateApply")

    s = sub(s, "      if (method === 'POST' && routePath === '/reload') {\n",
            "      if (method === 'POST' && routePath === '/reload') {\n"
            "        return send(409, { error: 'hot reload is disabled by local policy; restart the host to load installed files' })\n",
            label="index.reload")

    # The extension marketplace: no registry read on boot, no six-hourly poll,
    # and therefore nothing for the auto-updater to install.
    s = sub(s,
            "    void extensions.refreshRegistry().catch(() => {})\n"
            "    // The marketplace index refreshes on its own cadence too:",
            "    // local policy: no marketplace registry read.\n"
            "    // The marketplace index refreshes on its own cadence too:",
            label="index.extensionsBoot")
    s = sub(s,
            "    const registryTimer = setInterval(() => {\n"
            "      void extensions.refreshRegistry().catch(() => {})\n",
            "    const registryTimer = setInterval(() => {\n"
            "      // local policy: the marketplace never refreshes and never auto-updates.\n",
            label="index.extensionsTimer")
    s = sub(s,
            "      if (settings.get().autoUpdateExtensions === true) void extensions.autoUpdate().catch(() => {})\n",
            "", label="index.extensionsAutoUpdate")
    return s


def patch_client(s):
    # 1) startup announcement gate (the splash)
    s = replace_between(
        s, "      ctx.slots.inject('settings.onboarding', () => ctx.slots.register({",
        "    }\n    /**\n     * Owns the announcement's readiness.",
        "      // local policy: no first-run announcement step.\n", "client.onboarding")

    # 2) settings tabs: drop upgrade + picks
    s = sub(s,
            "        ['upgrade', t('nav.tab.upgrade'), null],\n"
            "        ['picks', t('nav.tab.picks'), null],\n",
            "", label="client.tabs")

    s = sub(s,
            "                    : tab === 'upgrade'\n"
            "                      ? h(UpgradePage, { t, settings: data.settings, onApply: apply, busy })\n"
            "                    : tab === 'picks'\n"
            "                      ? h(PicksPage, { t, effects })\n"
            "                    : tab === 'eac'",
            "                    : tab === 'eac'", label="client.pages")

    # 3) affiliate sponsor banner (a referral link with 10% cashback)
    s = sub(s, "        h(SponsorBanner, { t }),\n", "", count=2, label="client.sponsorBanner")
    s = sub(s, "'https://beichenapi.com/register?aff=DL49WAC2DQNG'", "''", label="client.sponsorUrl")

    # 4) star buttons (5 render sites)
    before = len(re.findall(r"h\(StarButton, \{[^}]*\}\)", s))
    if before != 5:
        raise SystemExit(f"[FAIL] client.starButtons: expected 5, found {before}")
    s = re.sub(r"h\(StarButton, \{[^}]*\}\)", "null", s)

    # 5) saved-tab allowlist: drop the removed pages too
    s = sub(s,
            "    const TABS = ['free', 'eac', 'channels', 'aggregate', 'workspace', 'extensions', 'saver', 'routing', 'ledger', 'logs', 'gateway', 'upgrade', 'picks']",
            "    const TABS = ['free', 'eac', 'channels', 'aggregate', 'workspace', 'extensions', 'saver', 'routing', 'ledger', 'logs', 'gateway']",
            label="client.TABS")
    return s


TARGETS = [
    ("src/feed.js", patch_feed),
    ("src/probe.js", patch_probe),
    ("src/picks.js", patch_picks),
    ("src/updater.js", patch_updater),
    ("src/extensions.js", patch_extensions),
    ("index.js", patch_index),
    ("client.js", patch_client),
]


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    check_only = "--check" in sys.argv[1:]
    d = Path(args[0] if args else "package")

    pkg = d / "package.json"
    if not pkg.exists():
        raise SystemExit(f"[FAIL] {pkg} not found — point me at the extracted package dir")
    version = re.search(r'"version"\s*:\s*"([^"]+)"', pkg.read_text(encoding="utf-8"))
    found = version.group(1) if version else "unknown"
    if found != TARGET_VERSION:
        raise SystemExit(f"[FAIL] version: patched for {TARGET_VERSION}, package is {found}")

    for rel, fn in TARGETS:
        p = d / rel
        if not p.exists():
            raise SystemExit(f"[FAIL] {rel} not found")
        original = p.read_text(encoding="utf-8")
        patched = fn(original)
        if patched == original:
            raise SystemExit(f"[FAIL] {rel}: patch produced no change")
        if check_only:
            print(f"  ok  {rel}")
        else:
            p.write_text(patched, encoding="utf-8")
            print(f"  patched  {rel}")

    print(("checked: " if check_only else "patched: ") + str(d))


if __name__ == "__main__":
    main()
