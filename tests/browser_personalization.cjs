// Local keyless Streamlit + desktop Chromium mobile viewports. Not Safari/API validation.
const {chromium}=require('playwright');
async function idle(p){await p.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function send(p,text){const before=await p.evaluate(()=>[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1)?.id||null);await p.getByRole('textbox').fill(text);await p.getByRole('button',{name:'질문 전송',exact:true}).click();await p.waitForFunction(old=>{const e=[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1);return e&&e.id!==old;},before);await idle(p);}
const last=p=>p.locator('[data-testid=stChatMessage]').last();
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});try{for(const width of [320,390,768]){
 const p=await b.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await p.goto('http://127.0.0.1:18502');await p.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
 await send(p,'65세인데 집에만 있어서 가볍게 운동하고 싶어요. 강서구에 살아요.');
 await last(p).getByRole('heading',{name:/파크골프/}).waitFor();if(!(await last(p).innerText()).includes('원하신 강도에 맞는지는 확인이 필요해요'))throw Error('No honest profile explanation');
 await send(p,'오후가 좋아요');await last(p).getByRole('heading',{name:/파크골프/}).waitFor();
 await send(p,'무료로 찾아줘');if(!(await last(p).innerText()).includes('접수 마감'))throw Error('Free closed reference missing');
 await send(p,'수영 말고 다른 운동은요?');const choices=await last(p).getByRole('button').allTextContents();if(choices.some(x=>x.includes('초보 수영')))throw Error('Rejected activity returned');
 await send(p,'처음부터 다시');await send(p,'운동 추천해 줘');const gentle=last(p).getByRole('button',{name:'가볍게요',exact:true});await gentle.waitFor();const box=await gentle.boundingBox();if(box.height<48)throw Error('Small choice');await gentle.click();await last(p).getByText(/어느 지역/).waitFor();
 await send(p,'강서구요');await last(p).getByRole('heading',{name:/파크골프/}).waitFor();
 await send(p,'강서구 걷기 프로그램 찾아줘');await last(p).getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}).waitFor();const buttons=await last(p).locator('.stButton button').allTextContents();if(buttons[0].trim()!=='슬로우조깅 정보 보기 →')throw Error('Wrong ranking');
 await send(p,'인접 지역도 찾아줘');await last(p).getByText(/동의하셔야/).waitFor();await last(p).getByRole('button',{name:'네, 인접 지역도 확인',exact:true}).click();await last(p).getByText(/현재 확인된 인접 지역 프로그램 자료가 없습니다/).waitFor();await idle(p);if(await last(p).getByRole('heading',{name:/슬로우조깅/}).count())throw Error('Local reused');
 if(await p.locator('[data-testid=stException]').count())throw Error('Streamlit exception');if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Overflow');console.log('PASS session profile/preferences/reset/followup/ranked choices/consent',width);await p.close();
 }}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
