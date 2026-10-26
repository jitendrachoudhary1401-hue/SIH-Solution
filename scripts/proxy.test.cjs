const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
let handler;
test.before(async () => { handler = (await import('../frontend/api/proxy.js')).default; });

async function listen(server) { await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve)); return `http://127.0.0.1:${server.address().port}`; }
async function close(server) { await new Promise(resolve=>server.close(resolve)); }
function proxyServer() { return http.createServer((req,res)=>{
  req.query=Object.fromEntries(new URL(req.url,'http://localhost').searchParams);
  res.status=value=>{res.statusCode=value;return res;};
  res.json=value=>{res.setHeader('content-type','application/json');res.end(JSON.stringify(value));};
  res.send=value=>res.end(value);
  handler(req,res).catch(()=>{res.statusCode=500;res.end();});
}); }

test('server-only proxy forwards a session request and response cookie', async()=>{
  const saved={BACKEND_URL:process.env.BACKEND_URL,VERCEL:process.env.VERCEL,FRONTEND_PROXY_SECRET:process.env.FRONTEND_PROXY_SECRET};
  let received;
  const backend=http.createServer(async(req,res)=>{let body='';for await(const chunk of req)body+=chunk;received={url:req.url,headers:req.headers,body};res.setHeader('content-type','application/json');res.setHeader('set-cookie','onecase_session=synthetic-test-only; HttpOnly; Path=/; SameSite=Strict');res.end('{"ok":true}');});
  const proxy=proxyServer();
  try {
    process.env.BACKEND_URL=await listen(backend);delete process.env.VERCEL;process.env.FRONTEND_PROXY_SECRET='synthetic-proxy-fixture';
    const origin=await listen(proxy);
    const response=await fetch(origin+'/api/proxy?path=auth/login',{method:'POST',headers:{origin,'content-type':'application/json','x-csrf-token':'synthetic-csrf'},body:'{"email":"test@example.test"}'});
    assert.equal(response.status,200);assert.deepEqual(await response.json(),{ok:true});
    assert.equal(received.url,'/api/auth/login');assert.equal(received.headers.origin,process.env.BACKEND_URL);
    assert.equal(received.headers['x-onecase-proxy-key'],'synthetic-proxy-fixture');assert.equal(received.headers['x-csrf-token'],'synthetic-csrf');
    assert.match(response.headers.get('set-cookie'),/HttpOnly/);assert.match(response.headers.get('cache-control'),/no-store/);
  } finally {await close(proxy);await close(backend);for(const[key,value]of Object.entries(saved)){if(value===undefined)delete process.env[key];else process.env[key]=value;}}
});

test('proxy rejects a cross-origin write before reaching the backend',async()=>{
  const saved=process.env.BACKEND_URL;process.env.BACKEND_URL='https://backend.example.test';
  const proxy=proxyServer();
  try {const origin=await listen(proxy);const response=await fetch(origin+'/api/proxy?path=auth/login',{method:'POST',headers:{origin:'https://untrusted.example'}});assert.equal(response.status,403);}
  finally {await close(proxy);if(saved===undefined)delete process.env.BACKEND_URL;else process.env.BACKEND_URL=saved;}
});

test('proxy fails closed when backend environment configuration is absent',async()=>{
  const saved=process.env.BACKEND_URL;delete process.env.BACKEND_URL;const proxy=proxyServer();
  try {const origin=await listen(proxy);const response=await fetch(origin+'/api/proxy?path=health');assert.equal(response.status,503);}
  finally {await close(proxy);if(saved!==undefined)process.env.BACKEND_URL=saved;}
});
