(function(){
  'use strict';
  const months=['gennaio','febbraio','marzo','aprile','maggio','giugno','luglio','agosto','settembre','ottobre','novembre','dicembre'];
  const weekdays=['Lun','Mar','Mer','Gio','Ven','Sab','Dom'];
  const pad=n=>String(n).padStart(2,'0');
  const key=d=>d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());
  const esc=s=>String(s||'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const niceDate=d=>new Intl.DateTimeFormat('it-IT',{weekday:'long',day:'numeric',month:'long',year:'numeric'}).format(d);
  const niceTime=d=>new Intl.DateTimeFormat('it-IT',{hour:'2-digit',minute:'2-digit'}).format(d);

  document.querySelectorAll('.csl-calendar').forEach(init);
  function init(root){
    let shown=new Date(); shown=new Date(shown.getFullYear(),shown.getMonth(),1);
    let events=[];
    root.querySelector('.csl-prev').addEventListener('click',()=>{shown=new Date(shown.getFullYear(),shown.getMonth()-1,1);load();});
    root.querySelector('.csl-next').addEventListener('click',()=>{shown=new Date(shown.getFullYear(),shown.getMonth()+1,1);load();});
    const exportButton=root.querySelector('.csl-export'); if(exportButton) exportButton.addEventListener('click',exportCsv);
    root.querySelector('.csl-close').addEventListener('click',()=>root.querySelector('.csl-dialog').close());
    load();

    async function load(){
      root.querySelector('.csl-month').textContent=months[shown.getMonth()]+' '+shown.getFullYear();
      const first=new Date(shown.getFullYear(),shown.getMonth(),1), offset=(first.getDay()+6)%7;
      const from=new Date(shown.getFullYear(),shown.getMonth(),1-offset);
      const to=new Date(from.getFullYear(),from.getMonth(),from.getDate()+42);
      setStatus('Caricamento eventi…');
      try{
        const url=new URL(root.dataset.endpoint); url.searchParams.set('id',root.dataset.calendarId); url.searchParams.set('from',from.toISOString()); url.searchParams.set('to',to.toISOString());
        const response=await fetch(url.toString(),{credentials:'same-origin'}); const data=await response.json();
        if(!response.ok) throw new Error(data.message||'Errore');
        events=(data.events||[]).map(e=>Object.assign({},e,{startDate:new Date(e.start),endDate:new Date(e.end)}));
        render(from); setStatus(data.stale?'Google non è raggiungibile: sono mostrati gli ultimi dati disponibili.':'',data.stale?'csl-stale':'');
      }catch(error){events=[];hideViews();setStatus('Il calendario non è temporaneamente disponibile.','csl-error');}
    }
    function setStatus(message,cls){const el=root.querySelector('.csl-status');el.textContent=message;el.className='csl-status '+(cls||'');}
    function hideViews(){root.querySelector('.csl-grid').hidden=true;root.querySelector('.csl-agenda').hidden=true;}
    function render(from){renderGrid(from);renderAgenda();root.querySelector('.csl-grid').hidden=false;root.querySelector('.csl-agenda').hidden=false;}
    function dayEvents(day){const start=new Date(day.getFullYear(),day.getMonth(),day.getDate()),end=new Date(day.getFullYear(),day.getMonth(),day.getDate()+1);return events.filter(e=>e.startDate<end&&e.endDate>start);}
    function renderGrid(from){const grid=root.querySelector('.csl-grid');grid.innerHTML=weekdays.map(d=>'<div class="csl-weekday">'+d+'</div>').join('');for(let i=0;i<42;i++){const day=new Date(from.getFullYear(),from.getMonth(),from.getDate()+i);const cell=document.createElement('div');cell.className='csl-day'+(day.getMonth()!==shown.getMonth()?' csl-outside':'');cell.innerHTML='<span class="csl-date">'+day.getDate()+'</span>';dayEvents(day).forEach(e=>cell.appendChild(eventButton(e)));grid.appendChild(cell);}}
    function renderAgenda(){const agenda=root.querySelector('.csl-agenda');agenda.innerHTML='';let count=0;const last=new Date(shown.getFullYear(),shown.getMonth()+1,0).getDate();for(let n=1;n<=last;n++){const day=new Date(shown.getFullYear(),shown.getMonth(),n),list=dayEvents(day);if(!list.length)continue;count++;const wrap=document.createElement('section');wrap.className='csl-agenda-day';wrap.innerHTML='<h4>'+esc(niceDate(day))+'</h4>';list.forEach(e=>wrap.appendChild(eventButton(e)));agenda.appendChild(wrap);}if(!count)agenda.innerHTML='<p class="csl-empty">Nessun evento in questo mese.</p>';}
    function eventButton(event){const b=document.createElement('button');b.type='button';b.className='csl-event';b.textContent=(event.allDay?'':niceTime(event.startDate)+' · ')+event.title;b.addEventListener('click',()=>detail(event));return b;}
    function detail(e){const time=e.allDay?'Tutto il giorno':niceTime(e.startDate)+' – '+niceTime(e.endDate);root.querySelector('.csl-detail').innerHTML='<h3>'+esc(e.title)+'</h3><p class="csl-detail-time">'+esc(niceDate(e.startDate))+' · '+esc(time)+'</p>'+(e.description?'<p>'+esc(e.description)+'</p>':'');const d=root.querySelector('.csl-dialog');if(typeof d.showModal==='function')d.showModal();else d.setAttribute('open','');}
    function exportCsv(){const inMonth=events.filter(e=>e.startDate.getFullYear()===shown.getFullYear()&&e.startDate.getMonth()===shown.getMonth());const rows=[['Titolo','Data inizio','Ora inizio','Data fine','Ora fine','Descrizione']];inMonth.forEach(e=>{const visibleEnd=e.allDay?new Date(e.endDate.getFullYear(),e.endDate.getMonth(),e.endDate.getDate()-1):e.endDate;rows.push([e.title,key(e.startDate),e.allDay?'':niceTime(e.startDate),key(visibleEnd),e.allDay?'':niceTime(e.endDate),e.description]);});const csv='\ufeff'+rows.map(row=>row.map(v=>'"'+String(v||'').replace(/"/g,'""')+'"').join(';')).join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));a.download='calendario-'+shown.getFullYear()+'-'+pad(shown.getMonth()+1)+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500);}
  }
})();
