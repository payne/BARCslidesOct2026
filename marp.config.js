// Marp CLI config (auto-loaded by `marp`). Replaces {{BUILD_TIMESTAMP}} in any
// deck with the time it was rendered plus the commit it was built from.
const { execSync } = require('child_process')
const { Marp } = require('@marp-team/marp-core')

const commit = () => {
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA.slice(0, 7)
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return ''
  }
}

const stamp = () => {
  const when = new Date().toLocaleString('en-US', {
    timeZone: process.env.BUILD_TZ || 'America/Denver',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  })
  const sha = commit()
  return sha ? `${when} · ${sha}` : when
}

module.exports = {
  engine: (opts) => {
    const marp = new Marp(opts)
    const render = marp.render.bind(marp)
    marp.render = (markdown, env) => render(markdown.replaceAll('{{BUILD_TIMESTAMP}}', stamp()), env)
    return marp
  },
}
