// Vercel server-only API proxy. Credentials never enter the browser bundle.
// Same-origin cookies avoid cross-site cookie failures between Vercel and Render.
const MAX_BODY = 4 * 1024 * 1024;

module.exports = async function handler(req, res) {
  const configured = process.env.BACKEND_URL;
  if (!configured) return res.status(503).json({error:{message:'Backend connection is not configured.'}});
  let base;
  try {
    base = new URL(configured);
    if (!['https:', 'http:'].includes(base.protocol) || base.username || base.password) throw new Error();
    if (process.env.VERCEL && base.protocol !== 'https:') throw new Error();
  } catch { return res.status(503).json({error:{message:'Backend connection configuration is invalid.'}}); }
  const incoming = new URL(req.url, `https://${req.headers.host}`);
  const path = String(req.query?.path || incoming.searchParams.get('path') || '');
  if (!path || path.split('/').some(segment=>segment==='..'||segment==='.') || !/^[a-zA-Z0-9/_\-.]+$/.test(path)) return res.status(400).end();
  const mutating = !['GET','HEAD','OPTIONS'].includes(req.method);
  if (mutating) {
    let sameOrigin = true;
    try { if (req.headers.origin) sameOrigin = new URL(req.headers.origin).host === req.headers.host; } catch { sameOrigin = false; }
    if (req.headers['sec-fetch-site'] === 'cross-site' || !sameOrigin) return res.status(403).json({error:{message:'Cross-origin write request rejected.'}});
  }
  incoming.searchParams.delete('path');
  const target = new URL('/api/'+path, base);
  target.search = incoming.searchParams.toString();
  const headers = {};
  for (const name of ['content-type','accept','cookie','x-csrf-token','idempotency-key']) if (req.headers[name]) headers[name]=req.headers[name];
  if (mutating) headers.origin = base.origin;
  if (process.env.FRONTEND_PROXY_SECRET) headers['x-onecase-proxy-key']=process.env.FRONTEND_PROXY_SECRET;
  let body;
  try {
    if (!['GET','HEAD'].includes(req.method)) {
      if (Buffer.isBuffer(req.body)) body=req.body;
      else if (typeof req.body==='string') body=Buffer.from(req.body);
      else if (req.body!==undefined) body=Buffer.from(JSON.stringify(req.body));
      else { const chunks=[]; let length=0; for await (const chunk of req) {length+=chunk.length;if(length>MAX_BODY)return res.status(413).end();chunks.push(chunk);} body=Buffer.concat(chunks); }
      if (body.length>MAX_BODY) return res.status(413).json({error:{message:'Upload exceeds the deployed API limit.'}});
    }
    const upstream=await fetch(target,{method:req.method,headers,body,redirect:'manual',signal:AbortSignal.timeout(25000)});
    for(const name of ['content-type','content-disposition','x-request-id','retry-after','x-ratelimit-limit','x-ratelimit-remaining','x-ratelimit-reset']) {const value=upstream.headers.get(name);if(value)res.setHeader(name,value);}
    const cookies=upstream.headers.getSetCookie();if(cookies.length)res.setHeader('set-cookie',cookies);
    res.setHeader('cache-control','private, no-store');
    res.status(upstream.status).send(Buffer.from(await upstream.arrayBuffer()));
  } catch { res.status(502).json({error:{message:'The backend is unavailable. Please retry shortly.'}}); }
};
