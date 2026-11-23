// App-owned role markers, actual computed colours/geometry, native widgets intact.
const {chromium}=require('playwright');const assert=require('assert/strict');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function send(p,text){await idle(p);const old=await p.locator('[id^=latest-reply-]').last().getAttribute('id');await p.getByRole('textbox').fill(text);await p.getByRole('textbox').press('Enter');await p.waitForFunction(id=>[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.id!==id,old);await idle(p);}
async function check(p,width){
 await p.waitForFunction(()=>{const u=[...document.querySelectorAll('[data-testid=stChatMessage]')].findLast(e=>e.querySelector('[data-ieum-role=user]'));const a=[...document.querySelectorAll('[class*=st-key-assistant_bubble_]')].at(-1);return u&&a&&getComputedStyle(u).backgroundColor==='rgb(255, 122, 0)'&&getComputedStyle(a).backgroundColor==='rgb(234, 0, 44)'});
 const report=await p.evaluate(()=>{
  const users=[...document.querySelectorAll('[data-testid=stChatMessage]')].filter(e=>e.querySelector('[data-ieum-role=user]'));
  const assistants=[...document.querySelectorAll('[data-testid=stChatMessage]')].filter(e=>e.querySelector('[data-ieum-role=assistant]'));
  const details=e=>({x:e.getBoundingClientRect().x,right:e.getBoundingClientRect().right,bg:getComputedStyle(e).backgroundColor,fg:getComputedStyle(e.querySelector('.ieum-speaker')).color,name:e.querySelector('.ieum-speaker').textContent,width:e.clientWidth,scroll:e.scrollWidth});
  return {users:users.map(details),assistants:assistants.map(e=>details(e.querySelector('[class*=st-key-assistant_bubble_]'))),overflow:document.documentElement.scrollWidth>innerWidth};
 });
 assert.equal(report.overflow,false);assert.ok(report.users.length);
 for(const u of report.users){assert.equal(u.name,'나');assert.equal(u.bg,'rgb(255, 122, 0)');assert.equal(u.fg,'rgb(17, 17, 17)');assert.ok(u.scroll<=u.width+1);assert.ok(u.right<=width+1);}
 for(const a of report.assistants){assert.equal(a.name,'이음 AI');assert.equal(a.bg,'rgb(234, 0, 44)');assert.equal(a.fg,'rgb(255, 255, 255)');assert.ok(a.scroll<=a.width+1);assert.ok(a.right<=width+1);}
 assert.ok(report.users.at(-1).x>report.assistants.at(-1).x+5);
 assert.equal(await p.locator('[data-testid=stException]').count(),0);
}
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
for(const width of [320,390,768])for(const scheme of ['light','dark']){
 const p=await b.newPage({viewport:{width,height:900},hasTouch:true,isMobile:true,colorScheme:scheme});try{
 await p.goto('http://127.0.0.1:18517');await p.getByRole('heading',{name:'오늘은 어떤 활동을 해보고 싶으세요?',exact:true}).waitFor();
 await send(p,'수영을 배우고 싶어요');await send(p,'강서구요');await check(p,width);
 const latest=p.locator('[data-testid=stChatMessage]').last();const bubble=latest.locator('[class*=st-key-assistant_bubble_]');const card=latest.locator('[class*=st-key-activity_card_]').first();
 assert.ok((await card.boundingBox()).y>=(await bubble.boundingBox()).y+(await bubble.boundingBox()).height);
 assert.ok(await latest.getByRole('button',{name:'자세히 보기 →',exact:true}).count());
 await p.mouse.move(width/2,400);await p.mouse.wheel(0,-10000);await p.waitForFunction(()=>(document.querySelector('.stMain')||document.scrollingElement).scrollTop<2);await p.screenshot({path:`/workspace/work/speaker-bubbles/chat-${width}-${scheme}.png`});
 const long='긴 문장도 말풍선 안에서 읽을 수 있는지 확인해요. '.repeat(8)+'LongUnbrokenText'.repeat(12);
 await send(p,long);await check(p,width);
 console.log('PASS role names/orange user/red assistant/alignment/wrapping/cards',width,scheme);
 }finally{await p.close()}
}
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
