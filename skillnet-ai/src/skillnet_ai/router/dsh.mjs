// Read-only Wiki tools for the SDK's isolated sdk-minimal runtime.
import fs from 'node:fs'
import path from 'node:path'

export const name = 'skillnet-wiki'
export const inject = ['tools']

export function apply(ctx) {
  const root = fs.realpathSync(process.env.SKILLNET_WIKI_ROOT)
  const readLimit = Number(process.env.SKILLNET_WIKI_READ_LIMIT)
  const stepLimit = Number(process.env.SKILLNET_WIKI_MAX_STEPS)
  let reads = 0
  let listings = 0
  let steps = 0

  const locate = (relativePath) => {
    if (path.isAbsolute(relativePath)) throw new Error('Use a relative Wiki path.')
    // Resolve symlinks before checking containment.
    const target = fs.realpathSync(path.resolve(root, relativePath))
    const relative = path.relative(root, target)
    if (relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
      throw new Error('Path is outside the task Wiki.')
    }
    return target
  }
  const parameters = {
    type: 'object',
    properties: { path: { type: 'string' } },
    required: ['path'],
    additionalProperties: false,
  }
  const output = {
    schema: { type: 'string' },
    render: (_args, value) => [{ type: 'text', text: value }],
  }

  ctx.tools.register({
    name: 'read_wiki',
    description: 'Read a UTF-8 Wiki file using a relative path.',
    parameters,
    output,
    execute(args, exec) {
      exec.signal.throwIfAborted()
      if (reads >= readLimit) throw new Error('Wiki read budget exceeded.')
      const target = locate(args.path)
      if (!fs.statSync(target).isFile()) throw new Error('Use a regular Wiki file.')
      reads += 1
      return fs.readFileSync(target, 'utf8')
    },
  })
  ctx.tools.register({
    name: 'list_wiki',
    description: 'List one Wiki directory. Use path "." for its root.',
    parameters,
    output,
    execute(args, exec) {
      exec.signal.throwIfAborted()
      if (listings >= 3) throw new Error('Wiki listing budget exceeded.')
      const target = locate(args.path)
      listings += 1
      return fs
        .readdirSync(target, { withFileTypes: true })
        .map((entry) => entry.name + (entry.isDirectory() ? '/' : ''))
        .join('\n')
    },
  })
  ctx.tools.guard((exec) =>
    ['read_wiki', 'list_wiki'].includes(exec.name)
      ? undefined
      : 'Only read-only Wiki tools are allowed.',
  )
  ctx.on('agent/pre-step', (_event, next) => {
    if (++steps > stepLimit) throw new Error('Wiki exploration step budget exceeded.')
    return next()
  })
}
