// Computed foreground/composited ancestor background, WCAG sRGB formula.
const {chromium}=require('playwright');const fs=require('fs');
const URL=process.env.CONTRAST_URL||'http://127.0.0.1:18507';const TAG=process.env.CONTRAST_TAG||'';const WIDTHS=process.env.CONTRAST_WIDTHS?process.env.CONTRAST_WIDTHS.split(',').map(Number):[320,390,768];
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
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});const reports=[];try{for(const scheme of ['light','dark'])for(const width of WIDTHS){
 const p=await b.newPage({viewport:{width,height:900},colorScheme:scheme});await p.goto(URL);await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);await p.waitForFunction(()=>getComputedStyle(document.querySelector('[data-testid=stApp]')).backgroundColor==='rgb(255, 255, 255)'&&document.querySelector('.st-key-seongsan_light'));
 reports.push(await measure(p,`${scheme}-${width}-welcome`));await p.screenshot({path:`/workspace/work/contrast/after${TAG}-${scheme}-${width}-welcome.png`,fullPage:true});
 await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).click();await p.getByRole('button',{name:'복지관 기존 회원이에요',exact:true}).waitFor();await idle(p);
 reports.push(await measure(p,`${scheme}-${width}-step`));if(await p.locator('.st-key-inst_instruction p').evaluate(e=>parseFloat(getComputedStyle(e).fontSize))<22)throw Error('Main instruction too small');await p.getByText('공식 출처·확인 범위',{exact:true}).click();await p.getByRole('link',{name:'이 단계의 공식 근거',exact:true}).waitFor();reports.push(await measure(p,`${scheme}-${width}-sources`));
 await p.screenshot({path:`/workspace/work/contrast/after${TAG}-${scheme}-${width}-step.png`,fullPage:true});
 const boxes=[];
 for(const btn of await p.locator('.stButton button,.stLinkButton a').all()){const box=await btn.boundingBox();if(box&&(box.height<48||box.x<0||box.x+box.width>width+1))throw Error('Button size/bounds '+width);if(box)boxes.push(box);}
 for(let i=1;i<boxes.length;i++)if(boxes[i].y<boxes[i-1].y+boxes[i-1].height-1)throw Error('Overlapping buttons');
 if(await p.locator('[data-testid=stException]').count())throw Error('Streamlit exception');
 await p.getByRole('textbox').fill('다음');await p.getByRole('button',{name:'질문 전송',exact:true}).click();await p.getByText(/복지관 회원인지 먼저 확인/).waitFor();
 await p.getByText('기존 기능 · 강서구 활동 검색',{exact:true}).click();await p.getByRole('button',{name:'강서구 기존 서비스 열기',exact:true}).click();await p.getByRole('button',{name:'성산복지관 신청 도우미로 돌아가기',exact:true}).waitFor();await idle(p);
 if(await p.locator('.st-key-seongsan_light').count())throw Error('Theme scope leaked to legacy');
 if(scheme==='dark'&&(await p.locator('[data-testid=stApp]').evaluate(e=>getComputedStyle(e).backgroundColor))==='rgb(255, 255, 255)')throw Error('Legacy dark theme changed');
 console.log('PASS light contrast/layout/inputs/step/gate/legacy isolation',scheme,width);await p.close();
 }
 fs.writeFileSync(`/workspace/work/contrast/report${TAG}.json`,JSON.stringify(reports,null,2));const failed=reports.flatMap(r=>r.failures.map(x=>({label:r.label,...x})));const small=reports.flatMap(r=>r.small.map(x=>({label:r.label,...x})));const overflow=reports.filter(r=>r.overflow||r.appBackground!=='rgb(255, 255, 255)');
 console.log(JSON.stringify({samples:reports.reduce((s,r)=>s+r.checks.length,0),minimum:Math.min(...reports.flatMap(r=>r.checks.map(x=>x.ratio))),failed,small,overflow},null,2));if(failed.length||small.length||overflow.length)throw Error('Contrast/font/layout regression');
 }finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
