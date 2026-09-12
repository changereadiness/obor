(()=>{
  const cardHtml=(s)=>`<article class="signal-card"><div class="meta"><span class="tag">${s.opportunity_or_risk}</span><span class="score">OBOR ${s.relevance_score}/100</span></div><h3><a href="/signals/${s.slug}/" style="color:inherit;text-decoration:none">${s.title}</a></h3><p>${s.summary}</p><p class="why"><strong>Why it matters</strong>${s.canadian_relevance}</p></article>`;

  const dateKey=(d)=>{
    const y=d.getFullYear();
    const m=String(d.getMonth()+1).padStart(2,'0');
    const day=String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${day}`;
  };

  const formatDate=(key)=>{
    if(!key)return '';
    const [y,m,d]=key.split('-').map(Number);
    if(!y||!m||!d)return key;
    return new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'long',day:'numeric'}).format(new Date(y,m-1,d));
  };

  const liveSignals=(signals)=>signals
    .filter(s=>s.status!=='suppressed'&&s.status!=='demo')
    .filter(s=>s.slug&&s.published_at);

  const byNewestThenRelevance=(a,b)=>{
    const dateCompare=String(b.published_at).localeCompare(String(a.published_at));
    if(dateCompare!==0)return dateCompare;
    return Number(b.relevance_score||0)-Number(a.relevance_score||0);
  };

  async function renderHome(){
    const todayDate=document.querySelector('#today-date');
    const todayState=document.querySelector('#today-state');
    const todayGrid=document.querySelector('#today-signal-grid');
    const latestDate=document.querySelector('#latest-date');
    const latestGrid=document.querySelector('#latest-signal-grid');
    if(!todayDate||!todayState||!todayGrid||!latestDate||!latestGrid)return;

    const todayKey=dateKey(new Date());
    todayDate.textContent=formatDate(todayKey);

    try{
      const r=await fetch('/data/signals.json',{cache:'no-store'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      const signals=liveSignals(await r.json()).sort(byNewestThenRelevance);
      const todays=signals.filter(s=>String(s.published_at).slice(0,10)===todayKey);

      if(todays.length){
        todayState.textContent=todays.length===1?'1 major signal detected today.':`${todays.length} major signals detected today.`;
        todayGrid.innerHTML=todays.slice(0,6).map(cardHtml).join('');
      }else{
        todayState.textContent='No major signals detected today.';
        todayGrid.innerHTML='';
      }

      const latestPool=todays.length
        ? signals.filter(s=>String(s.published_at).slice(0,10)!==todayKey)
        : signals;
      const latest=latestPool.slice(0,6);
      const latestKey=latest.length?String(latest[0].published_at).slice(0,10):'';
      latestDate.textContent=latestKey?formatDate(latestKey):'No archived signals yet';
      latestGrid.innerHTML=latest.length
        ? latest.map(cardHtml).join('')
        : '<p class="daily-status">No archived signals available.</p>';
    }catch(e){
      todayState.textContent='Today’s intelligence is temporarily unavailable.';
      todayGrid.innerHTML='';
      latestDate.textContent='Archive unavailable';
      latestGrid.innerHTML='<p class="daily-status">Latest signals could not be loaded.</p>';
    }
  }

  renderHome();
})();
