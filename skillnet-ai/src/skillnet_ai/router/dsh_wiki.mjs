// The SDK loads this dependency-free Cordis plugin in a fresh sdk-minimal home.
import fs from 'node:fs';
import path from 'node:path';

export const name = 'skillnet-wiki';
export const inject = ['tools'];

export function apply(ctx) {
  const root = fs.realpathSync(process.env.SKILLNET_WIKI_ROOT);
  const readLimit = Number(process.env.SKILLNET_WIKI_READ_LIMIT);
  const stepLimit = Number(process.env.SKILLNET_WIKI_MAX_STEPS);
  if (![readLimit, stepLimit].every(value => Number.isSafeInteger(value) && value > 0)) {
    throw new Error('Invalid SkillNet Wiki budgets.');
  }
  let reads = 0;
  let listings = 0;
  let steps = 0;
  const inside = target => {
    const relative = path.relative(root, target);
    if (relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
      throw new Error('Path is outside the task Wiki.');
    }
    return target;
  };
  const locate = args => {
    if (!args || typeof args.path !== 'string' || path.isAbsolute(args.path)) {
      throw new Error('Use a relative Wiki path.');
    }
    const candidate = inside(path.resolve(root, args.path));
    return inside(fs.realpathSync(candidate));
  };
  const output = {
    schema: {type: 'string'},
    render: (_args, value) => [{type: 'text', text: value}],
  };
  ctx.tools.register({
    name: 'read_wiki',
    description: 'Read a UTF-8 Wiki file. Paths are relative; offset/limit count characters.',
    parameters: {
      type: 'object',
      properties: {
        path: {type: 'string'},
        offset: {type: 'integer', minimum: 0},
        limit: {type: 'integer', minimum: 1, maximum: 64000},
      },
      required: ['path'], additionalProperties: false,
    },
    output,
    execute(args, exec) {
      exec.signal.throwIfAborted();
      const offset = args.offset ?? 0;
      const limit = args.limit ?? 64000;
      if (!Number.isSafeInteger(offset) || offset < 0 || !Number.isSafeInteger(limit) || limit < 1 || limit > 64000) {
        throw new Error('Invalid Wiki read range.');
      }
      const target = locate(args);
      if (!fs.statSync(target).isFile()) throw new Error('Expected a regular Wiki file.');
      if (reads >= readLimit) throw new Error('Wiki read budget exceeded.');
      reads += 1;
      const text = fs.readFileSync(target, 'utf8');
      const end = Math.min(text.length, offset + limit);
      const content = text.slice(offset, end);
      return end < text.length ? content + `\n[More content: use offset ${end}.]` : content;
    },
  });
  ctx.tools.register({
    name: 'list_wiki',
    description: 'List one Wiki directory. Use path "." for its root.',
    parameters: {
      type: 'object', properties: {path: {type: 'string'}},
      required: ['path'], additionalProperties: false,
    },
    output,
    execute(args, exec) {
      exec.signal.throwIfAborted();
      const target = locate(args);
      if (listings >= 3) throw new Error('Wiki listing budget exceeded.');
      listings += 1;
      return fs.readdirSync(target, {withFileTypes: true})
        .map(entry => entry.name + (entry.isDirectory() ? '/' : '')).join('\n');
    },
  });
  // This denial is monotonic even if a future minimal profile adds other tools.
  ctx.tools.guard(exec => ['read_wiki', 'list_wiki'].includes(exec.name)
    ? undefined : 'Only read-only Wiki tools are allowed.');
  ctx.on('agent/pre-step', (_event, next) => {
    if (++steps > stepLimit) throw new Error('Wiki exploration step budget exceeded.');
    return next();
  });
}
