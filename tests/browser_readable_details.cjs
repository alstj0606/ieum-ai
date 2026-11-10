// Local Chromium layout/interaction only. No Safari/device/provider claim.
const {chromium}=require('playwright');
async function idle(page){await page.waitForFunction(()=>document.querySelector('[data-testid=stApp]')?.getAttribute('data-test-script-state')==='notRunning');}
function luminance(rgb){return rgb.match(/\d+/g).slice(0,3).map(x=>{x=Number(x)/255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((sum,x,i)=>sum+x*[.2126,.7152,.0722][i],0);}
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{for(const width of [320,390,768]){
  const page=await browser.newPage({viewport:{width,height:850},isMobile:true,hasTouch:true});await page.goto('http://127.0.0.1:18502');
  await page.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
  await page.getByRole('textbox').fill('강서구 걷기 프로그램 찾아줘');await page.getByRole('button',{name:'질문 전송',exact:true}).click();
  const choice=page.getByRole('button',{name:'슬로우조깅 정보 보기 →',exact:true});await choice.waitFor();await idle(page);
  const box=await choice.boundingBox();if(box.height<48||box.x<0||box.x+box.width>width+1)throw Error('Alternative touch target');
  const style=await choice.evaluate(el=>{let p=el.querySelector('p');return {bg:getComputedStyle(el).backgroundColor,fg:getComputedStyle(p||el).color,weight:getComputedStyle(p||el).fontWeight,margin:getComputedStyle(el).marginBottom}});
  const colors=[luminance(style.bg),luminance(style.fg)].sort((a,b)=>b-a);if((colors[0]+.05)/(colors[1]+.05)<4.5||Number(style.weight)<700||parseFloat(style.margin)<8)throw Error('Choice contrast/weight/spacing '+JSON.stringify(style));
  await choice.click();
  const latest=page.locator('[data-testid=stChatMessage]').last();const title=latest.getByRole('heading',{name:/슬로우조깅/});await title.waitFor();await idle(page);await page.waitForFunction(()=>{const heading=[...document.querySelectorAll('[data-testid=stChatMessage]')].at(-1)?.querySelector('h3');const box=heading?.getBoundingClientRect();return box&&box.y>=0&&box.y<350;},null,{timeout:5000});
  const titleBox=await title.boundingBox();if(titleBox.y<0||titleBox.y>350)throw Error('Selected card was not brought into view '+JSON.stringify(titleBox));
  await page.screenshot({path:`/workspace/work/readable-details-${width}.png`});
  const text=(await latest.locator('[data-testid=stChatMessageContent]').innerText()).trim();const name=(await title.innerText()).trim();
  if(!text.startsWith(name)||await title.count()!==1)throw Error('Card not first/duplicated');
  if(text.includes('같은 지역의 대안 · 공식 자료 있음')||text.includes('일반 활동 제안 · 실제 모집 프로그램 아님')||text.includes('찾지 못했어요'))throw Error('Repeated recommendation before details');
  for(const label of ['참가 비용','모집 대상','지역','상세 주소','운영 시간','접수 기간','다음 접수 예정일','신청 방법','준비물']){
   const field=latest.getByText(label,{exact:false}).first();if(!await field.isVisible())throw Error('Essential field hidden '+label);
  }
  if(!text.includes('2026.08.18 ~ 08.21')||!text.includes('다음 접수 일정 미정')||!text.includes('공식 자료 확인 필요')||text.includes('2026-08-18T'))throw Error('Unsafe or raw date formatting');
  if(await latest.getByRole('button',{name:/정보 보기 →/}).count())throw Error('Alternatives duplicated in detail answer');
  if(await page.locator('[data-testid=stChatMessage]').count()<4)throw Error('History removed');
  const detail=latest.getByText('주의사항·공식 출처',{exact:true});await detail.click();await latest.getByRole('link',{name:'공식 출처 확인',exact:true}).waitFor();
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');
  const overflow=await latest.locator('p,h3,button').evaluateAll(nodes=>nodes.some(el=>{const r=el.getBoundingClientRect();return r.width&&(r.x<0||r.right>innerWidth+1)}));if(overflow)throw Error('Card content overflows');
  await detail.click();await title.scrollIntoViewIfNeeded();
  console.log('PASS accessible alternative -> first card/scroll -> visible facts/compact dates/no duplicates/history/source',width);await page.close();
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
