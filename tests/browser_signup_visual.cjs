// Local Streamlit diagrams only. Never clicks official links or enters credentials.
const {chromium}=require('playwright');const assert=require('assert/strict');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function change(p,action){const old=await p.locator('[id^=latest-reply-inst-]').count()?await p.locator('[id^=latest-reply-inst-]').getAttribute('id'):null;await action();await p.waitForFunction(before=>{const n=document.querySelector('[id^=latest-reply-inst-]');return n&&n.id!==before;},old);await idle(p);}
async function click(p,name){await change(p,()=>p.getByRole('button',{name,exact:true}).click());}
async function send(p,text){await p.getByRole('textbox').fill(text);await change(p,()=>p.getByRole('button',{name:'질문 전송',exact:true}).click());}
async function diagram(p,id){await p.locator(`[data-guide-step=${id}]`).waitFor();await idle(p);assert.equal(await p.locator('.ieum-signup-visual').count(),1);assert.equal(await p.locator('.ieum-signup-visual :is(input,form,iframe,script,button,a,img)').count(),0);
 const result=await p.evaluate(()=>{const root=document.querySelector('.ieum-signup-visual');const box=root.getBoundingClientRect();const target=root.querySelector('.ieum-visual-target');const t=target.getBoundingClientRect();const lum=s=>s.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4}).reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);const style=getComputedStyle(target);const l=[lum(style.color),lum(style.backgroundColor)].sort((a,b)=>b-a);
 return {overflow:document.documentElement.scrollWidth>innerWidth,contained:box.x>=0&&box.right<=innerWidth&&t.x>=box.x&&t.right<=box.right,ratio:(l[0]+.05)/(l[1]+.05),mainFont:parseFloat(getComputedStyle(root.querySelector('h4')).fontSize),bodyFont:parseFloat(getComputedStyle(root.querySelector('p')).fontSize),switchHeight:document.querySelector('.st-key-inst_visual_guide label').getBoundingClientRect().height};});
 assert.equal(result.overflow,false);assert.equal(result.contained,true);assert.ok(result.ratio>=4.5);assert.ok(result.mainFont>=22&&result.bodyFont>=20);assert.ok(result.switchHeight>=48);
 await p.waitForFunction(()=>{const y=document.querySelector('[id^=latest-reply-inst-]')?.getBoundingClientRect().y;return y>=0&&y<170;},null,{timeout:6000});assert.equal(await p.locator('[data-testid=stException]').count(),0);
}
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const scheme of ['light','dark'])for(const width of [320,390,768]){
 const p=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true,colorScheme:scheme});
 try{await p.goto('http://127.0.0.1:18507');await p.getByRole('button',{name:'온라인 신청 도와주세요',exact:true}).waitFor();await idle(p);
 assert.equal(await p.locator('.ieum-signup-visual').count(),0);await p.getByText('실험 · 버튼 찾기 예시',{exact:true}).click();await click(p,'버튼 찾기 예시 시작');await p.getByRole('heading',{name:'1단계 / 6단계 · 복지관 회원이신가요?',exact:true}).waitFor();assert.equal(await p.locator('.ieum-signup-visual').count(),0);
 await click(p,'복지관 기존 회원이에요');await p.getByRole('button',{name:'아이디가 없어요 · 온라인 아이디 만들기',exact:true}).waitFor();await click(p,'아이디가 없어요 · 온라인 아이디 만들기');await diagram(p,'signup_open');await click(p,'다음 단계 →');await diagram(p,'signup_menu');
 const cases=[['signup_id','아래쪽'],['signup_terms','체크박스'],['signup_verify','영역']];
 for(const[id,word]of cases){await click(p,'다음 단계 →');await diagram(p,id);await send(p,'버튼이 안 보여요');await diagram(p,id);assert.ok((await p.locator('[data-testid=stChatMessage]').innerText()).includes(word));await send(p,'어디를 눌러요?');await diagram(p,id);await click(p,'다시 설명');await diagram(p,id);}
 assert.ok(await p.getByRole('button',{name:'다음 단계 →',exact:true}).isDisabled());assert.ok((await p.locator('[data-testid=stChatMessage]').innerText()).includes('인증 이후 화면'));
 await p.screenshot({path:`/workspace/work/visual-guide/prototype-${scheme}-${width}.png`});await click(p,'이전 단계');await diagram(p,'signup_terms');
 const toggle=p.getByRole('switch',{name:'버튼 찾기 예시 보기 · 실제 사이트 아님',exact:true});await p.locator('.st-key-inst_visual_guide label').click();await p.locator('.ieum-signup-visual').waitFor({state:'detached'});await idle(p);await toggle.focus();await toggle.press('Space');await diagram(p,'signup_terms');
 await click(p,'처음으로');await p.getByRole('heading',{name:/^1단계 \/ 6단계/}).waitFor();assert.equal(await p.locator('.ieum-signup-visual').count(),0);
 console.log('PASS visual guide/current-step help/verification boundary/toggle/reset/contrast/layout',width,scheme);
 }catch(error){await p.screenshot({path:`/workspace/work/visual-guide/failure-${scheme}-${width}.png`,fullPage:true});throw error;}finally{await p.close();}
 }}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
