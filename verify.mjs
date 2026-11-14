#!/usr/bin/env node
/**
 * Offline proof that the patched package makes no unsolicited outbound call.
 *
 * Every network primitive the plugin could reach is replaced with a recorder
 * BEFORE the modules load: global fetch, node:http/https request/get, and the
 * module-level fetch the plugin passes around as `fetchImpl`. Each module is
 * then imported and its entry points invoked. Any dial is a failure.
 *
 * The lane itself is not exercised (it needs a live upstream); what this proves
 * is narrower and exactly what the patch claims: the five background channels —
 * announcement feed, self-updater, public-IP echo, star-count reads, extension
 * marketplace — never dial.
 *
 *   node verify.mjs <patched-package-dir>
 */
import path from 'node:path'
import http from 'node:http'
import https from 'node:https'
import { pathToFileURL } from 'node:url'

const pkgDir = path.resolve(process.argv[2] ?? '')
if (!pkgDir) { console.error('usage: node verify.mjs <patched-package-dir>'); process.exit(2) }

const dials = []
const record = (via, target) => dials.push({ via, target: String(target).slice(0, 200) })

globalThis.fetch = async (input, init) => {
  record('global.fetch', input instanceof Request ? input.url : input)
  throw new Error('network access blocked by the verifier')
}
http.request = (...a) => { record('http.request', a[0]); throw new Error('blocked') }
http.get = (...a) => { record('http.get', a[0]); throw new Error('blocked') }
https.request = (...a) => { record('https.request', a[0]); throw new Error('blocked') }
https.get = (...a) => { record('https.get', a[0]); throw new Error('blocked') }

const mod = rel => import(pathToFileURL(path.join(pkgDir, rel)).href)
const blockingFetch = async input => {
  record('injected.fetchImpl', input instanceof Request ? input.url : input)
  throw new Error('network access blocked by the verifier')
}

const results = []
/**
 * `expect` is the assertion; a throw from it is a FAIL, not a pass with a note.
 * Anything the plugin itself throws is reported separately as `note`, because a
 * refused channel is a legitimate outcome — but it must not mask a broken check.
 */
const check = async (name, fn) => {
  const before = dials.length
  let note
  let ok = true
  try {
    await fn()
  } catch (error) {
    ok = false
    note = String(error?.message ?? error).slice(0, 90)
  }
  const made = dials.length - before
  if (made > 0) ok = false
  results.push({ name, dials: made, ok, note })
}

const feed = await mod('src/feed.js')
const probe = await mod('src/probe.js')
const picks = await mod('src/picks.js')
const updater = await mod('src/updater.js')
const extensions = await mod('src/extensions.js')

await check('feed: DEFAULT_FEED_SOURCES is empty', async () => {
  if (feed.DEFAULT_FEED_SOURCES.length !== 0) throw new Error('sources remain')
})

await check('feed: fetchFeed() dials nothing', async () => {
  const answer = await feed.fetchFeed()
  if (answer?.feed?.announcements?.length !== 0) throw new Error('fetchFeed returned announcements')
})

await check('feed: AnnouncementFeed.poll() dials nothing', async () => {
  const instance = new feed.AnnouncementFeed({
    settings: () => ({}),
    cacheFile: path.join(pkgDir, '.verify-feed.json'),
    fetchImpl: blockingFetch,
    log: () => {},
  })
  await instance.poll()
  if (instance.sources().length !== 0) throw new Error('sources() still lists mirrors')
})

await check('probe: detectEgress() dials nothing', async () => {
  const answer = await probe.detectEgress()
  if (answer !== undefined) throw new Error(`expected undefined, got ${JSON.stringify(answer)}`)
})

await check('picks: createPickStats().view() dials nothing', async () => {
  const stats = picks.createPickStats({ cacheFile: '', fetchImpl: blockingFetch, log: () => {} })
  await stats.view()
  await stats.refresh()
  if (picks.PICKS_API_BASE !== '') throw new Error(`PICKS_API_BASE is ${JSON.stringify(picks.PICKS_API_BASE)}`)
})

await check('updater: check()/apply() dial nothing', async () => {
  const up = new updater.PluginUpdater({
    pkgDir, dataDir: path.join(pkgDir, '.verify-updater'), settings: () => ({}),
    fetchImpl: blockingFetch, runningVersion: '2.8.3', log: () => {},
  })
  let status
  try {
    status = await up.check()
  } catch (error) {
    throw new Error(`check() threw instead of reporting: ${error?.message ?? error}`)
  }
  if (status?.available !== false) throw new Error('check() reported an update available')
  let refused = false
  try { await up.apply({}) } catch { refused = true }
  if (!refused) throw new Error('apply() did not refuse')
  if (up.sources().length !== 0) throw new Error('updater still lists manifest sources')
})

await check('extensions: registrySources() is empty', async () => {
  if (extensions.registrySources().length !== 0) throw new Error('registry sources remain')
})

await check('updater: manifest primitives refuse', async () => {
  for (const [name, call] of [
    ['downloadManifest', () => updater.downloadManifest([], { fetchImpl: blockingFetch })],
    ['stageRelease', () => updater.stageRelease({ manifest: {}, manifestUrl: '', stageDir: path.join(pkgDir, '.verify-stage') })],
  ]) {
    let refused = false
    try { await call() } catch { refused = true }
    if (!refused) throw new Error(`${name} did not refuse`)
  }
})

let failed = 0
for (const row of results) {
  if (!row.ok) failed++
  const tag = row.ok ? 'PASS' : 'FAIL'
  const note = row.note ? `  (${row.note})` : ''
  console.log(`${tag}  ${row.name}  dials=${row.dials}${note}`)
}
if (dials.length > 0) {
  console.log('\nrecorded dials:')
  for (const d of dials) console.log(`  ${d.via} -> ${d.target}`)
}
console.log(`\n${results.length - failed}/${results.length} checks passed, ${dials.length} network dial(s) total`)
process.exit(failed === 0 && dials.length === 0 ? 0 : 1)
