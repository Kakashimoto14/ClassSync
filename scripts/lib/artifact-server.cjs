const { createServer } = require('node:http');
const { existsSync, statSync, createReadStream } = require('node:fs');
const { resolve, sep, extname } = require('node:path');

function artifactServer(root, config) {
  const rewrites = config.rewrites.map(({ source, destination }) => ({
    pattern: new RegExp(
      '^' +
        source
          .split(':path*')
          .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
          .join('.*') +
        '$',
    ),
    destination,
  }));
  const types = {
    '.html': 'text/html; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.svg': 'image/svg+xml',
    '.woff2': 'font/woff2',
    '.webmanifest': 'application/manifest+json',
  };
  return createServer((req, res) => {
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    } catch {
      res.writeHead(400);
      return res.end('Bad request');
    }
    let target = resolve(root, '.' + pathname);
    if (!target.startsWith(root + sep) && target !== root) {
      res.writeHead(403);
      return res.end('Forbidden');
    }
    // Existing files take precedence, matching Vercel's documented rewrite behavior.
    if (!existsSync(target) || !statSync(target).isFile()) {
      const match = rewrites.find(({ pattern }) => pattern.test(pathname));
      if (match) target = resolve(root, '.' + match.destination);
    }
    if (!existsSync(target) || !statSync(target).isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('NOT_FOUND');
    }
    res.writeHead(200, {
      'Content-Type': types[extname(target)] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    createReadStream(target).pipe(res);
  });
}
module.exports = { artifactServer };
