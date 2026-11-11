// Read-only public-page probe (--official) or deterministic browser policy fixtures.
// No login, form interaction, proxying of official HTML, or security-header removal.
const {chromium}=require('playwright');
const http=require('http');const fs=require('fs');const assert=require('assert/strict');
const listen=server=>new Promise(resolve=>server.listen(0,'127.0.0.1',()=>resolve(server.address().port)));
const close=server=>new Promise(resolve=>server.close(resolve));
const targets=['https://sssenior.e-ncom.co.kr/','https://sssenior.e-ncom.co.kr/member/login.do','https://sssenior.e-ncom.co.kr/member/memberAuth.do'];
(async()=>{
 const official=process.argv.includes('--official');let src='';
 const child=http.createServer((req,res)=>{if(req.url==='/deny')res.setHeader('X-Frame-Options','DENY');if(req.url==='/sameorigin')res.setHeader('X-Frame-Options','SAMEORIGIN');if(req.url==='/csp')res.setHeader('Content-Security-Policy',"frame-ancestors 'none'");res.setHeader('Content-Type','text/html');res.setHeader('Access-Control-Allow-Origin','*');res.end('<h1 id="fixture">Public policy fixture</h1>');});
 const cp=await listen(child);
 const parent=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(`<h1>Read-only embedding experiment</h1><iframe title="Public test page" referrerpolicy="no-referrer" src="${src}" onload="this.dataset.loaded='yes'"></iframe>`);});
 const pp=await listen(parent);const reports=[];
 // Retain inherited managed network routing. Never bypass TLS or browser policies.
 const proxy=official&&(process.env.HTTPS_PROXY||process.env.https_proxy);
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox'],...(proxy?{proxy:{server:proxy,bypass:'127.0.0.1,localhost'}}:{})});
 try{
  for(const target of (official?targets:['/allow','/deny','/sameorigin','/csp'])){
   src=official?target:`http://127.0.0.1:${cp}${target}`;
   const page=await browser.newPage();const headers=[];const failures=[];const policies=[];
   page.on('response',r=>{if(r.url().startsWith(official?'https://sssenior.e-ncom.co.kr/':`http://127.0.0.1:${cp}/`)){const h=r.headers();headers.push({status:r.status(),x_frame_options:h['x-frame-options']??null,content_security_policy:h['content-security-policy']??null});}});
   page.on('requestfailed',r=>{if(r.url().startsWith(src))failures.push(r.failure()?.errorText);});
   page.on('console',m=>{if(m.type()==='error'&&/frame|ancestor/i.test(m.text()))policies.push('browser_frame_policy_error');});
   await page.goto(`http://127.0.0.1:${pp}`);
   if(official){
    let publicContentVisible=false;
    try{await page.frameLocator('iframe').getByText('성산노인종합복지관',{exact:false}).first().waitFor({timeout:6000});publicContentVisible=true;}catch{}
    reports.push({url:target,headers,network_errors:failures,policy_errors:policies,public_content_visible:publicContentVisible,embedding_status:publicContentVisible?'initial_public_page_rendered':'unverified',scope:'Local parent origin only; login/authentication/payment and Cloud not tested'});
   }else{
    if(target==='/allow'){
     await page.frameLocator('iframe').locator('#fixture').waitFor();
     assert.equal(await page.evaluate(()=>document.querySelector('iframe').contentDocument),null);
     assert.equal(await page.evaluate(()=>{try{document.querySelector('iframe').contentWindow.document;return 'accessible';}catch(e){return e.name;}}),'SecurityError');
    }else{
     await page.waitForFunction(()=>document.querySelector('iframe').dataset.loaded==='yes');
     assert.equal(await page.frameLocator('iframe').locator('#fixture').count(),0);assert.ok(policies.length);
    }
    assert.equal(headers[0].status,200);reports.push({fixture:target,pass:true});
   }
   await page.close();
  }
  const output=process.env.FRAME_REPORT;
  if(output)fs.writeFileSync(output,JSON.stringify(reports,null,2));
  console.log(JSON.stringify(reports,null,2));
 }finally{await browser.close();await close(parent);await close(child);}
})().catch(e=>{console.error(e);process.exit(1)});
