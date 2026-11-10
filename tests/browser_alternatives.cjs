// Local official JSON and keyless deterministic flow; no real API or Safari claim.
const {chromium}=require('playwright');
async function idle(page){await page.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
async function send(page,text){const before=await page.evaluate(()=>[...document.querySelectorAll('[id^=\"latest-reply-\"]')].at(-1)?.id||null);await page.getByRole('textbox').fill(text);await page.getByRole('button',{name:'질문 전송',exact:true}).click();await page.waitForFunction(previous=>{const node=[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1);return node&&node.id!==previous;},before);await page.getByText(text,{exact:true}).last().waitFor();await idle(page);}
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  for(const width of [320,390,768]){
   const page=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});
   await page.goto('http://127.0.0.1:18502');
   await page.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
   await send(page,'가벼운 걷기 프로그램을 찾아주세요');
   await page.getByRole('button',{name:'서울 강서구에서 찾기',exact:true}).click();
   const alternative=page.getByRole('button',{name:'파크골프 정보 보기 →',exact:true});await alternative.waitFor();await idle(page);
   const box=await alternative.boundingBox();if(box.height<56||box.x<0||box.x+box.width>width+1)throw Error('Alternative target is inaccessible');
   await page.getByRole('button',{name:'아니요, 이 지역만 볼게요',exact:true}).click();
   await page.getByText('지역을 넓히지 않을게요.',{exact:false}).waitFor();await idle(page);
   await alternative.click();
   await page.getByRole('heading',{name:/서남센터/}).last().waitFor();await idle(page);
   await page.getByText('주의사항·공식 출처',{exact:true}).last().click();
   await page.getByRole('button',{name:'신청 도와주세요 →',exact:true}).click();
   await page.getByText('아직 신청·예약·결제가 완료된 것은 아니에요.',{exact:false}).last().waitFor();
   await send(page,'강서구 걷기 프로그램 찾아줘');
   // Prior refusal is respected; use a new session for a fresh consent question.
   await page.close();
   const yes=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await yes.goto('http://127.0.0.1:18502');
   await yes.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();await send(yes,'강서구 걷기 프로그램 찾아줘');
   await yes.getByRole('button',{name:'네, 인접 지역도 확인',exact:true}).click();
   await yes.getByText('현재 확인된 인접 지역 프로그램 자료가 없습니다',{exact:false}).waitFor();await idle(yes);
   await yes.getByRole('button',{name:'강서구 추천 다시 보기',exact:true}).click();
   await yes.getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true}).click();
   await yes.getByRole('heading',{name:/슬로우조깅/}).last().waitFor();await idle(yes);
   await yes.getByText('접수 마감',{exact:false}).last().waitFor();
   if(await yes.getByRole('button',{name:'신청 도와주세요 →',exact:true}).count())throw Error('Closed program has an application action');
   await yes.getByText('주의사항·공식 출처',{exact:true}).last().click();
   await yes.getByRole('link',{name:'공식 출처 확인',exact:true}).last().waitFor();
   if(await yes.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');
   if(await yes.locator('[data-testid=stException]').count())throw Error('Streamlit exception');
   await yes.screenshot({path:`/workspace/work/alternatives-${width}.png`});
   console.log('PASS walking -> local alternative -> refuse -> official application; consent -> missing neighbour data -> closed reference',width);
   await yes.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
