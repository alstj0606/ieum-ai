// Opt-in report on local Streamlit only. No production credentials or private input.
const {chromium}=require('playwright');const assert=require('assert/strict');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function tap(p,name){const old=await p.locator('[id^=latest-reply-inst-]').count()?await p.locator('[id^=latest-reply-inst-]').getAttribute('id'):null;await p.getByRole('button',{name,exact:true}).tap();await p.waitForFunction(id=>document.querySelector('[id^=latest-reply-inst-]')?.id!==id,old);await idle(p);}
async function report(p,source){await p.waitForFunction(source=>{try{const data=JSON.parse([...document.querySelectorAll('pre')].at(-1).textContent);return data.trace.some(e=>e.phase==='after_action'&&e.source===source)&&data.current_state.membership===false;}catch{return false;}},source);return JSON.parse(await p.locator('pre').last().innerText());}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const width of [320,390,768])for(const mode of ['normal','visual']){
 const p=await b.newPage({viewport:{width,height:850},hasTouch:true,isMobile:true,colorScheme:mode==='visual'?'dark':'light'});
 try{
 await p.goto('http://127.0.0.1:18507/?diagnostics=1');await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);await p.getByText('임시 진단 · member-trace-1',{exact:true}).waitFor();
 if(mode==='visual'){await p.getByText('실험 · 버튼 찾기 예시',{exact:true}).tap();await tap(p,'버튼 찾기 예시 시작');}else await tap(p,'온라인 신청 도와주세요');
 await tap(p,'복지관 비회원이에요');await p.getByRole('heading',{name:'비회원 · 방문 회원등록 안내',exact:true}).waitFor();
 let data=await report(p,'inst_nonmember');assert.equal(data.build.diagnostic_version,'member-trace-1');assert.match(data.build.working_tree_commit,/^[0-9a-f]{40,64}$/);assert.ok(Object.values(data.build.loaded_functions_match_files).every(v=>v===true));
 const before=data.trace.find(e=>e.phase==='before_action'&&e.source==='inst_nonmember');const after=data.trace.find(e=>e.phase==='after_action'&&e.source==='inst_nonmember');assert.equal(before.state.membership,null);assert.equal(after.state.membership,false);assert.ok(after.state.seq>before.state.seq);
 const later=data.trace.filter(e=>e.event>after.event&&['entry','render','post_render'].includes(e.phase));assert.ok(later.length);assert.ok(later.every(e=>e.state.membership===false));assert.ok(later.some(e=>e.phase==='render'&&e.screen==='membership_registration'));
 await tap(p,'다시 설명');data=await report(p,'inst_nonmember');assert.equal(data.current_state.membership,false);assert.equal(data.current_state.view,'membership_registration');
 assert.equal(await p.locator('[data-testid=stException]').count(),0);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await p.mouse.wheel(0,1800);await p.getByText('임시 진단 · member-trace-1',{exact:true}).scrollIntoViewIfNeeded();await p.screenshot({path:`/workspace/work/member-diagnostics/${width}-${mode}.png`});
 await p.goto('http://127.0.0.1:18507/');await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);assert.equal(await p.getByText('임시 진단 · member-trace-1',{exact:true}).count(),0);
 console.log('PASS opt-in revision/runtime code checks/callback and rerun trace/default hidden',width,mode);
 }catch(error){await p.screenshot({path:`/workspace/work/member-diagnostics/failure-${width}-${mode}.png`,fullPage:true});throw error;}finally{await p.close();}
 }}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
