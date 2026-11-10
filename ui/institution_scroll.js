// Owned step anchors only. No question, credentials, audio or external page access.
(() => {
  if(window.ieumInstitutionScroll)return;
  window.ieumInstitutionScroll=true;
  let seen=null,active=null,frame=null;
  const stop=()=>{active=null;};
  document.addEventListener('wheel',stop,{capture:true,passive:true});
  document.addEventListener('touchmove',stop,{capture:true,passive:true});
  const align=()=>{
    frame=null;
    if(!active||performance.now()>active.until)return;
    const node=document.getElementById(active.id);
    if(node&&Math.abs(node.getBoundingClientRect().top-70)>3)node.scrollIntoView({block:'start',behavior:'auto'});
  };
  const schedule=()=>{if(frame)cancelAnimationFrame(frame);frame=requestAnimationFrame(align);};
  const scan=()=>{
    const node=document.querySelector('[id^="latest-reply-inst-"]');
    if(node&&node.id!==seen){seen=node.id;active={id:node.id,until:performance.now()+3000};
      for(const delay of [0,120,350,700,1200,2000,2800])setTimeout(schedule,delay);
    }
    if(active)schedule();
  };
  new MutationObserver(scan).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['id']});
  document.addEventListener('scroll',schedule,{capture:true,passive:true});
  scan();
})();
