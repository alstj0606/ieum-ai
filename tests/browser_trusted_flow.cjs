// Actual Streamlit text submissions; localhost keyless and intentionally wrong Gemini mock.
const {chromium}=require('playwright');
const QUERY='강서구 걷기 프로그램 찾아줘';
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function send(p,text){const before=await p.evaluate(()=>[...document.querySelectorAll('[id^=\"latest-reply-\"]')].at(-1)?.id||null);await p.getByRole('textbox').fill(text);await p.getByRole('button',{name:'질문 전송',exact:true}).click();await p.waitForFunction(previous=>{const node=[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1);return node&&node.id!==previous;},before);await p.getByText(text,{exact:true}).last().waitFor();await idle(p);}
function last(p){return p.locator('[data-testid=stChatMessage]').last();}
async function firstChoice(p){await last(p).getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}).waitFor();await idle(p);const choices=await last(p).locator('.stButton button').allTextContents();if(choices[0].trim()!=='슬로우조깅 정보 보기 →')throw Error('Actual first selection is '+choices[0]);if(choices.some(s=>s.includes('알아보기')))throw Error('Parallel generic list overrides programme ranking');}
async function atStart(p){await p.waitForFunction(()=>{const a=[...document.querySelectorAll('[id^=latest-reply-]')].at(-1)?.getBoundingClientRect();return a&&a.y>=0&&a.y<160;},null,{timeout:6000});}
(async()=>{const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  if(!process.env.TEST_HISTORY_ONLY)for(const width of [320,390,768])for(const [mode,port] of [['basic',18502],['gemini-mock',18504]]){
   const p=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await p.goto(`http://127.0.0.1:${port}`);await p.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
   await send(p,QUERY);await firstChoice(p);await atStart(p);
   const preview=last(p).getByText('2026년 하반기 생활체육교실 슬로우조깅 (40세 이상)',{exact:false}).first();
   const box=await preview.boundingBox();if(!box||box.y<0||box.y>680){await p.screenshot({path:'/workspace/work/trusted-preview-debug.png'});throw Error('First recommendation is not initially visible '+JSON.stringify({width,mode,box,text:await last(p).innerText()}));}
   await last(p).getByRole('button',{name:'네, 인접 지역도 확인',exact:true}).click();await last(p).getByText('현재 확인된 인접 지역 프로그램 자료가 없습니다.',{exact:false}).waitFor();await idle(p);await atStart(p);
   if(await last(p).getByRole('heading',{name:/슬로우조깅|서남센터/}).count())throw Error('Gangseo reused as a new neighbour');
   if(await last(p).getByRole('button',{name:/정보 보기 →/}).count())throw Error('Old local choices reused');
   const historical=last(p).getByText('이전에 찾은 강서구 활동 · 새 인접 지역 결과 아님',{exact:true});await historical.waitFor();
   await last(p).getByRole('button',{name:'강서구 추천 다시 보기',exact:true}).click();await firstChoice(p);
   await last(p).getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}).click();await last(p).getByRole('heading',{name:/슬로우조깅/}).waitFor();await idle(p);await atStart(p);
   const text=await last(p).innerText();if(!text.includes('2026.08.18 ~ 08.21')||!text.includes('접수 마감')||!text.includes('다음 접수 일정 미정'))throw Error('Fact/date regression');
   if(/\d{4}-\d{2}-\d{2}T/.test(text))throw Error('ISO leaked');
   await p.screenshot({path:`/workspace/work/trusted-${width}-${mode}.png`});
   if(await p.locator('[data-testid=stException]').count())throw Error('Streamlit exception');
   if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');
   console.log('PASS actual first choice=slow jogging; reply start/preview/detail; isolated empty neighbour/history/restore; dates/KeyError',width,mode);await p.close();
  }
  const p=await browser.newPage({viewport:{width:390,height:850},isMobile:true,hasTouch:true});await p.goto('http://127.0.0.1:18504');await p.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
  await send(p,QUERY);await firstChoice(p);await last(p).getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}).click();await last(p).getByRole('heading',{name:/슬로우조깅/}).waitFor();
  await send(p,QUERY);await firstChoice(p);
  const slow='강서구 걷기 프로그램 천천히 찾아줘';await p.getByRole('textbox').fill(slow);await p.getByRole('button',{name:'질문 전송',exact:true}).click();
  await p.mouse.move(140,240);await p.mouse.wheel(0,-1500);await p.waitForTimeout(200);
  const before=await p.locator('.stMain').evaluate(e=>e.scrollTop);
  await p.getByText(slow,{exact:true}).last().waitFor();await firstChoice(p);await p.waitForTimeout(1300);
  const after=await p.locator('.stMain').evaluate(e=>e.scrollTop);if(Math.abs(after-before)>100)throw Error('Reading history forced away '+JSON.stringify({before,after}));
  console.log('PASS manual history reading while a delayed mock response arrives');await p.close();
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
