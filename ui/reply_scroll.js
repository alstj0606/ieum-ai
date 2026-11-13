// Fixed UI-only controller. Tracks scroll positions/anchor IDs, never question/audio text.
(() => {
  if(window.ieumReplyScroller)return;
  window.ieumReplyScroller=true;
  const seen=new Set();
  let pending=null,active=null,frame=0,readingHistory=false;
  const main=()=>document.querySelector('.stMain')||document.scrollingElement;
  const position=()=>({main:main()?.scrollTop||0,window:scrollY});
  const stop=()=>{if(active){active.resize?.disconnect();clearTimeout(active.end);}active=null;};
  const popup=()=>document.querySelector('[data-testid=stPopoverButton][aria-expanded=true]');
  const request=()=>{stop();readingHistory=false;pending={manual:false,position:position(),messages:document.querySelectorAll('[data-testid=stChatMessage]').length,frozen:false};};
  const interact=event=>{
    stop();
    const button=event.target.closest?.('button');
    if(button&&!button.disabled&&button.matches('.stButton button,.stFormSubmitButton button,[data-testid=stChatInputSubmitButton],[data-testid=stChatInputApproveButton]'))request();
  };
  document.addEventListener('pointerdown',interact,{capture:true,passive:true});
  document.addEventListener('click',event=>{if(event.detail===0&&event.isTrusted)interact(event);},{capture:true,passive:true});
  document.addEventListener('keydown',event=>{
    stop();
    if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&event.target.matches?.('[data-testid=stChatInputTextArea]'))request();
    else if(['PageUp','PageDown','Home','End','ArrowUp','ArrowDown'].includes(event.key)&&!event.target.matches?.('textarea,input'))manual();
  },{capture:true,passive:true});
  const manual=()=>{
    readingHistory=true;stop();
    if(pending){pending.manual=true;pending.position=position();requestAnimationFrame(()=>{if(pending?.manual)pending.position=position();});}
  };
  // Native wheel/touch scrolling is applied after the input event; observe its result.
  document.addEventListener('scroll',event=>{
    if(pending?.manual&&!pending.frozen&&(event.target===main()||event.target===document))
      pending.position=position();
    if(active&&(event.target===main()||event.target===document))schedule();
  },{capture:true,passive:true});
  document.addEventListener('wheel',manual,{capture:true,passive:true});
  document.addEventListener('touchmove',manual,{capture:true,passive:true});
  const align=()=>{
    if(!active||popup())return;
    const anchor=document.getElementById(active.id);
    if(!anchor){stop();return;}
    if(active.preserve){
      if(main())main().scrollTop=active.preserve.main;
      if(Math.abs(scrollY-active.preserve.window)>2)window.scrollTo({top:active.preserve.window,behavior:'auto'});
    }else if(Math.abs(anchor.getBoundingClientRect().top-70)>3){
      anchor.scrollIntoView({block:'start',behavior:'auto'});
    }
  };
  const schedule=()=>{if(frame)cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{frame=0;align();});};
  const follow=(id,preserve=null)=>{
    stop();active={id,preserve};
    if(typeof ResizeObserver!=='undefined'){
      active.resize=new ResizeObserver(schedule);
      const reply=document.getElementById(id)?.closest('[data-testid=stChatMessage]');
      if(reply)active.resize.observe(reply);
      const content=document.querySelector('.stMainBlockContainer');
      if(content)active.resize.observe(content);
    }
    active.end=setTimeout(stop,3000);
    for(const ms of [0,150,450,900,1600,2400])setTimeout(()=>{if(active?.id===id)schedule();},ms);
  };
  const scan=()=>{
    if(pending&&document.querySelectorAll('[data-testid=stChatMessage]').length>pending.messages)pending.frozen=true;
    const anchor=[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1);
    if(anchor&&!seen.has(anchor.id)){
      seen.add(anchor.id);if(seen.size>40)seen.delete(seen.values().next().value);
      window.ieumLatest=Number(anchor.id.replace('latest-reply-',''))||0;
      if(pending){const preserve=pending.manual?pending.position:null;pending=null;follow(anchor.id,preserve);}
      else if(anchor.id.startsWith('latest-reply-welcome-'))follow(anchor.id);
    }
    if(active)schedule();
  };
  new MutationObserver(scan).observe(document.body,{childList:true,subtree:true});
  const viewport=()=>{
    if(readingHistory||active?.preserve||!document.activeElement?.matches('[data-testid=stChatInputTextArea]')||popup())return;
    const id=[...document.querySelectorAll('[id^="latest-reply-"]')].at(-1)?.id;
    if(id)follow(id);
  };
  window.visualViewport?.addEventListener('resize',viewport);
  window.addEventListener('resize',viewport);
  scan();
})();
