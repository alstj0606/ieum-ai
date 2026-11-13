const {chromium}=require('playwright');const fs=require('fs');const assert=require('assert/strict');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function measure(p,label){await idle(p);return p.evaluate(label=>{
 const rgb=s=>{const a=s.match(/[\d.]+/g)?.map(Number);return a&&a.length>=3?[a[0],a[1],a[2],a[3]??1]:[0,0,0,0]};
 const blend=(f,b)=>f.slice(0,3).map((v,i)=>v*f[3]+b[i]*(1-f[3]));
 const bg=e=>{const chain=[];for(let n=e;n;n=n.parentElement)chain.unshift(n);let c=[255,255,255];for(const n of chain)c=blend(rgb(getComputedStyle(n).backgroundColor),c);return c};
 const lum=c=>c.map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0);
 const checks=[];const w=document.createTreeWalker(document.querySelector('[data-testid=stApp]'),NodeFilter.SHOW_TEXT);
 for(let n;n=w.nextNode();){const e=n.parentElement,t=n.textContent.trim();if(!/[가-힣a-zA-Z0-9]/.test(t)||!e.getClientRects().length||e.closest('script,style,[aria-hidden=true],[data-testid=stIconMaterial]'))continue;const s=getComputedStyle(e);if(s.visibility!=='visible')continue;const b=bg(e);const color=rgb(s.color);for(let ancestor=e;ancestor;ancestor=ancestor.parentElement)color[3]*=Number(getComputedStyle(ancestor).opacity);const f=blend(color,b);const a=[lum(f),lum(b)].sort((a,b)=>b-a);checks.push({text:t.slice(0,60),ratio:(a[0]+.05)/(a[1]+.05),font:parseFloat(s.fontSize),fg:s.color,bg:b});}
 const input=document.querySelector('textarea');if(input){const b=bg(input);for(const pseudo of [null,'::placeholder']){const s=getComputedStyle(input,pseudo);const a=[lum(blend(rgb(s.color),b)),lum(b)].sort((a,b)=>b-a);checks.push({text:pseudo||'input',ratio:(a[0]+.05)/(a[1]+.05),font:parseFloat(s.fontSize),fg:s.color,bg:b});}}
 return {label,checks,failures:checks.filter(x=>x.ratio<4.5),small:checks.filter(x=>x.font<18&&!['Deploy'].includes(x.text)),overflow:document.documentElement.scrollWidth>innerWidth,appBackground:getComputedStyle(document.querySelector('[data-testid=stApp]')).backgroundColor};
 },label);}

(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});const reports=[];try{
for(const width of [320,390,768])for(const scheme of ['light','dark'])for(const service of ['discovery','institution']){
 const p=await b.newPage({viewport:{width,height:900},colorScheme:scheme});
 await p.goto('http://127.0.0.1:'+(service==='discovery'?18517:18507));
 await p.getByRole(service==='discovery'?'heading':'button',{name:service==='discovery'?'오늘은 무엇을 해보고 싶으세요?':'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);
 await p.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--ieum-red').trim()==='#ea002c');
 const primary=p.locator('.stButton button:not(:disabled)').first();assert.equal(await primary.evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(234, 0, 44)');
 if(service==='institution'){await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).click();await p.getByRole('button',{name:'복지관 비회원이에요',exact:true}).waitFor();await idle(p);}
 const r=await measure(p,`${service}-${width}-${scheme}`);reports.push(r);assert.equal(r.overflow,false);assert.equal(r.appBackground,'rgb(255, 255, 255)');assert.deepEqual(r.failures,[]);
 for(const e of await p.locator('.stButton button,.stLinkButton a').all()){const box=await e.boundingBox();if(box){assert.ok(box.height>=44);assert.ok(box.x>=0&&box.x+box.width<=width+1);}}

 if(service==='discovery'&&width===390){
  await p.getByRole('textbox').fill('강서구 걷기 프로그램 찾아줘');await p.getByRole('textbox').press('Enter');
  const latest=p.locator('[data-testid=stChatMessage]').last();await latest.getByRole('heading',{name:/슬로우조깅/}).waitFor();await idle(p);
  let extra=await measure(p,`recommendations-${scheme}`);reports.push(extra);assert.deepEqual(extra.failures,[]);
  const old=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await latest.getByRole('button',{name:'자세히 보기 →',exact:true}).first().click();await p.waitForFunction(id=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==id,old);await idle(p);await latest.getByText('상세 정보 · 신청 방법·공식 근거',{exact:true}).waitFor();await idle(p);
  extra=await measure(p,`details-${scheme}`);reports.push(extra);assert.deepEqual(extra.failures,[]);
  assert.ok(await p.locator('[data-testid=stChatMessage]').last().getByRole('link',{name:'공식 사이트 이동 →',exact:true}).getAttribute('href'));
  await p.screenshot({path:`/workspace/work/sk-theme/details-390-${scheme}.png`,fullPage:true});
 }
 await p.screenshot({path:`/workspace/work/sk-theme/${service}-${width}-${scheme}.png`,fullPage:true});console.log('PASS palette/contrast/layout',r.label);await p.close();
}
fs.writeFileSync('/workspace/work/sk-theme/contrast.json',JSON.stringify(reports,null,2));console.log('minimum contrast',Math.min(...reports.flatMap(r=>r.checks.map(x=>x.ratio))));
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
