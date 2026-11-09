// Starts a NEW Streamlit process, then opens a real browser session so app.py runs.
// A successful /_stcore/health alone does not prove app imports are valid.
const {spawn}=require('node:child_process');
const net=require('node:net');
const {chromium}=require('playwright');
(async()=>{
 const port=await new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const p=server.address().port;server.close(()=>resolve(p));});});
 const env={...process.env};for(const key of ['GEMINI_API_KEY','GOOGLE_API_KEY','OPENAI_API_KEY'])delete env[key];
 const child=spawn(process.env.PYTHON||'python',['-m','streamlit','run','app.py',`--server.port=${port}`,'--server.address=127.0.0.1','--server.headless=true','--browser.gatherUsageStats=false'],{env,stdio:'ignore'});
 let browser;
 try{
  let healthy=false;
  for(let attempt=0;attempt<100;attempt++){
   if(child.exitCode!==null)throw Error('Streamlit exited before startup');
   try{if((await fetch(`http://127.0.0.1:${port}/_stcore/health`)).ok){healthy=true;break;}}catch{}
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(!healthy)throw Error('Streamlit health timeout');
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:390,height:850}});
  await page.goto(`http://127.0.0.1:${port}`);
  await page.getByRole('heading',{name:'이음 AI',exact:true}).waitFor();
  await page.getByRole('button',{name:'마이크로 말하기',exact:true}).waitFor();
  if(await page.locator('[data-testid=stException]').count())throw Error('App startup exception');
  await page.getByRole('textbox').fill('강서구 걷기 프로그램 찾아줘');
  await page.getByRole('button',{name:'질문 전송',exact:true}).click();
  await page.getByRole('button',{name:'파크골프 대안 보기',exact:true}).waitFor();
  if(await page.locator('[data-testid=stException]').count())throw Error('Alternative flow exception');
  console.log('PASS fresh server + browser session: imports/startup/microphone/text/official alternatives');
 }finally{
  if(browser)await browser.close();
  if(child.exitCode===null){
   const closed=new Promise(resolve=>child.once('close',resolve));
   child.kill('SIGTERM');
   const force=setTimeout(()=>child.kill('SIGKILL'),5000);
   await closed;clearTimeout(force);
  }
 }
})().catch(()=>{console.error('FAIL fresh Streamlit browser startup (no raw runtime logs exposed)');process.exitCode=1;});
