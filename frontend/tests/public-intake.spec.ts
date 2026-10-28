import { test, expect } from './fixtures';

test('stakeholder submits proof, follows actions and downloads the frozen watermarked PDF', async ({ page, browser }) => {
  test.setTimeout(120000); // Eight independent staff sessions and the full evidence-backed decision path.
  await page.setViewportSize({width: 390, height: 900});
  const email = `intake-${Date.now()}@example.com`;
  const register = await page.request.post('/api/auth/register', {data: {name: 'Browser Complainant', email, password: 'PersonalPassphrase!2026', confirm_password: 'PersonalPassphrase!2026', account_type: 'student', faculty_name:'Dr. Test Faculty', admission_year:2026, passout_year:2030}});
  expect(register.status()).toBe(201);
  await page.goto('/officer/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password', {exact:true}).fill('PersonalPassphrase!2026');
  await page.getByRole('button', {name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading', {name:'Register a complaint'})).toBeVisible();
  await page.getByLabel('Institution name', {exact:true}).fill('Browser Technical College');
  await page.getByLabel('State / region').fill('Rajasthan');
  await page.getByLabel('Incident location', {exact: true}).fill('Synthetic main campus, accounts office');
  await page.getByLabel('Complaint summary').fill('Refund is still outstanding');
  await page.getByLabel('What happened?').fill('My fee refund has not been processed after withdrawal. Please review my withdrawal and payment proof.');
  await page.getByLabel('Photos, videos and documents as proof').setInputFiles('tests/fixtures/synthetic-outcome.png');
  await page.getByRole('checkbox').check();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/intake-mobile.png', fullPage:true});
  await page.getByRole('button', {name:'Register complaint', exact:true}).click();
  await expect(page.getByText('Uploaded - awaiting scan', {exact:false})).toBeVisible();
  await page.getByRole('link', {name:'View complaint and action timeline'}).click();
  await expect(page.getByRole('heading', {name:/^OC-/})).toBeVisible();
  const url = page.url();
  const id = Number(url.split('/').at(-1));
  const reference = await page.getByRole('heading', {name:/^OC-/}).innerText();
  await expect(page.getByRole('heading', {name:'Complaint action timeline'})).toBeVisible();
  await expect(page.getByRole('heading', {name:'Initial faculty / grievance review'})).toBeVisible();
  await expect(page.locator('.complaint-timeline').getByText('Browser Complainant', {exact:false}).first()).toBeVisible();
  for (const width of [320, 768, 1024]) {
    await page.setViewportSize({width, height:900});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  const adminContext = await browser.newContext({baseURL:'http://127.0.0.1:5174'});
  const admin = adminContext.request;
  const signed = await admin.post('/api/auth/login', {data:{email:'admin@onecase.demo',password:'OneCaseDemo!2026'}});
  const adminHeaders = {'X-CSRF-Token':(await signed.json()).csrf};
  let current = await (await admin.get(`/api/complaints/${id}`)).json();
  expect(current.reference).toBe(reference);
  const directory = await (await admin.get('/api/directory')).json();
  const lead = directory.officers.find((u:{email:string}) => u.email === 'lead.rb@onecase.demo');
  expect((await admin.post(`/api/complaints/${id}/transfer`, {headers:adminHeaders,data:{version:current.version,owner_id:lead.id,reason:'Assigning the public intake for review'}})).status()).toBe(200);
  const officerContext = await browser.newContext({baseURL:'http://127.0.0.1:5174'});
  const officer = officerContext.request;
  const auth = await officer.post('/api/auth/login', {data:{email:lead.email,password:'OneCaseDemo!2026'}});
  const headers = {'X-CSRF-Token':(await auth.json()).csrf};
  current = await (await officer.get(`/api/complaints/${id}`)).json();
  const proof = current.attachments[0];
  expect(proof.scan_state).toBe('clean');
  expect((await officer.post(`/api/complaints/${id}/actions`, {headers,data:{version:current.version,reason:'Reviewed the payment proof and resolved the refund',evidence_ids:[proof.id]}})).status()).toBe(200);
  current = await (await officer.get(`/api/complaints/${id}`)).json();
  // Provision synthetic approved participants, then exercise the real gated handling path.
  const people: Record<string,{id:number;email:string}> = {};
  for (const role of ['faculty_reviewer','lead','committee','reviewer','verifier','auditor','executive']) {
    const email = `handling-${id}-${role}@example.com`;
    const made = await admin.post('/api/admin/users', {headers:adminHeaders,data:{name:`Browser ${role}`,email,password:'OneCaseDemo!2026',role,
      bureau_id:role === 'lead' ? lead.bureau_id : null,approval_reference:'SYNTHETIC-BROWSER-APPROVAL',reason:'Appoint isolated synthetic workflow participants'}});
    expect(made.status()).toBe(201); people[role] = {id:(await made.json()).id,email};
  }
  let handling = await (await admin.get(`/api/complaints/${id}/case-workflow`)).json();
  expect((await admin.post(`/api/complaints/${id}/case-workflow/team`, {headers:adminHeaders,data:{version:handling.version,
    ...Object.fromEntries(Object.entries(people).map(([role,u])=>[role+'_id',u.id])),approval_reference:'SYNTHETIC-BROWSER-TEAM',reason:'Approved independent handling team'}})).status()).toBe(200);
  const contexts = [];
  const actors: Record<string,{request:typeof officer; headers:Record<string,string>}> = {officer:{request:officer,headers}};
  for (const [role,u] of Object.entries(people)) {
    const context = await browser.newContext({baseURL:'http://127.0.0.1:5174'}); contexts.push(context);
    const signed = await context.request.post('/api/auth/login', {data:{email:u.email,password:'OneCaseDemo!2026'}});
    expect(signed.status()).toBe(200); actors[role] = {request:context.request,headers:{'X-CSRF-Token':(await signed.json()).csrf}};
  }
  const facultyPage = await contexts[0].newPage(); await facultyPage.goto(`/complaints/${id}`);
  await facultyPage.getByLabel('Stage report / handover reason').fill('Faculty reviewed the complaint and forwarded the initial findings to the officer.');
  await facultyPage.getByRole('button',{name:'Complete stage and hand over'}).click();
  await expect(facultyPage.getByRole('heading',{name:'Officer review and triage',level:2})).toBeVisible();
  for (const [role, endpoint] of [['officer','advance'],['committee','reports'],['lead','advance'],['reviewer','reports'],['auditor','reports'],['verifier','advance']]) {
    const a = actors[role]; handling = await (await a.request.get(`/api/complaints/${id}/case-workflow`)).json();
    const result = await a.request.post(`/api/complaints/${id}/case-workflow/${endpoint}`, {headers:a.headers,
      data:{version:handling.version,report:`The ${role} reviewed the recorded evidence and submitted a reasoned assessment.`,evidence_ids:[proof.id]}});
    expect(result.status()).toBe(200);
  }
  const executive = actors.executive;
  handling = await (await executive.request.get(`/api/complaints/${id}/case-workflow`)).json();
  const closed = await executive.request.post(`/api/complaints/${id}/case-workflow/advance`, {headers:executive.headers,data:{version:handling.version,
    report:'Fee refund settled and independently verified. The executive has approved the outcome.',outcome_document_id:proof.id,communication:'Browser Complainant notified via the portal, REF-BROWSER-001'}});
  expect(closed.status()).toBe(200);
  await page.reload();
  await expect(page.getByText('Reviewed the payment proof and resolved the refund', {exact:true})).toBeVisible();
  const download = page.getByRole('link', {name:/Download closure PDF/});
  await expect(download).toBeVisible();
  await expect(page.getByText('Resolved', {exact:true})).toBeVisible();
  await expect(page.getByText('Request an appeal review', {exact:true})).toBeVisible();
  const reportPath = await download.getAttribute('href');
  const pdf = await page.request.get(reportPath!);
  expect(pdf.headers()['content-type']).toContain('application/pdf');
  expect((await pdf.body()).subarray(0,5).toString()).toBe('%PDF-');
  expect((await admin.get(reportPath!)).status()).toBe(200);
  await page.screenshot({path:'test-results/complaint-closed-tablet.png', fullPage:true});
  for (const context of contexts) await context.close();
  await adminContext.close(); await officerContext.close();
});
