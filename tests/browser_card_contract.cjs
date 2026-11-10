// All real records plus explicit old-formatter fixture; no real API requests.
const {chromium}=require('playwright');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function send(p,text){await p.getByRole('textbox').fill(text);await p.getByRole('button',{name:'질문 전송',exact:true}).click();await p.getByText(text,{exact:true}).last().waitFor();await idle(p);}
async function actionStyle(button){return button.evaluate(e=>{const p=e.querySelector('p')||e,s=getComputedStyle(e),t=getComputedStyle(p);return{bg:s.backgroundColor,fg:t.color,weight:Number(t.fontWeight),height:e.getBoundingClientRect().height}});}
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{for(const width of [320,390,768]){
  const p=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});
  await p.goto('http://127.0.0.1:18502');await p.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
  await send(p,'강서구 걷기 프로그램 찾아줘');
  const similar=p.getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}),other=p.getByRole('button',{name:'파크골프 정보 보기 →',exact:true});
  await similar.waitFor();await other.waitFor();await idle(p);
  const order=await similar.evaluate((a)=>{const b=[...document.querySelectorAll('button')].find(e=>e.textContent.includes('파크골프 정보 보기'));return Boolean(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING)});if(!order)throw Error('Availability incorrectly outranks walking relevance');
  const style=await actionStyle(similar);if(style.height<48||style.weight<700)throw Error('Choice accessibility');
  const idea=p.getByRole('button',{name:/가벼운 체조 알아보기|수중운동 알아보기/}).first();const istyle=await actionStyle(idea);if(style.bg!==istyle.bg||style.fg!==istyle.fg||istyle.height<48||istyle.weight<700)throw Error('Choice designs differ');
  await similar.click();const last=p.locator('[data-testid=stChatMessage]').last();await last.getByRole('heading',{name:/슬로우조깅/}).waitFor();await idle(p);
  let text=await last.innerText();if(!text.includes('접수 마감')||!text.includes('2026.08.18 ~ 08.21')||text.includes('2026-08-18T'))throw Error('Archived detail/date');
  if(await last.getByRole('button',{name:'이 활동 신청 방법',exact:true}).count())throw Error('Closed application action');
  await send(p,'다른 활동');const resetChoice=p.getByRole('button',{name:'다른 활동 찾기',exact:true});await resetChoice.waitFor();if((await actionStyle(resetChoice)).bg!==style.bg)throw Error('Followup design differs');
  await send(p,'강서구 걷기 프로그램 찾아줘');await other.waitFor();await other.click();
  await p.locator('[data-testid=stChatMessage]').last().getByRole('heading',{name:/서남센터/}).waitFor();await idle(p);
  await p.getByRole('button',{name:'이 활동 신청 방법',exact:true}).click();
  await p.getByText('아직 신청·예약·결제가 완료된 것은 아니에요.',{exact:false}).last().waitFor();
  if(await p.locator('[data-testid=stException]').count())throw Error('Flow exception');await p.close();
  for(const mode of ['', '?legacy=1']){
   const gallery=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await gallery.goto('http://127.0.0.1:18506/'+mode);
   await gallery.waitForFunction(()=>document.querySelectorAll('[data-testid=stChatMessage] h3').length===10);await idle(gallery);
   if(await gallery.locator('[data-testid=stException]').count())throw Error('All-record gallery exception');
   const body=await gallery.locator('body').innerText();if(/\d{4}-\d{2}-\d{2}/.test(body))throw Error('ISO exposed in cards');
   if((body.match(/다음 접수 일정 미정/g)||[]).length!==10)throw Error('Unknown next dates missing');
   if(await gallery.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Gallery horizontal overflow');
   await gallery.screenshot({path:`/workspace/work/card-contract-${width}${mode?'legacy':''}.png`});await gallery.close();
  }
  console.log('PASS relevance/consistent buttons -> archived detail -> open alternative/application; all 10 cards + legacy/None formatter/no ISO/no KeyError',width);
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
