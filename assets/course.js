'use strict';
// software-design-books-course/assets/course.js를 권별 설정(body data-*)으로 일반화한 것. 실험(lab)과 구버전 이전 코드는 뺐다.
(() => {
 const B=document.body.dataset, KEY=B.key, TOTAL=+B.total, TITLE=B.title, BRAND=B.brand, FIRST=B.first||'home';
 const $=(s,root=document)=>root.querySelector(s), $$=(s,root=document)=>[...root.querySelectorAll(s)];
 const fresh=()=>({version:1,done:[],notes:{},quizzes:{},last:FIRST});
 let state=fresh(),storageOK=true,active='home',toastTimer;
 const isLesson=id=>/^lesson-\d\d$/.test(id)&&!!document.getElementById(id);
 function validate(x){
  if(!x||x.version!==1||!Array.isArray(x.done)||typeof x.notes!=='object'||!x.notes||Array.isArray(x.notes)||typeof x.quizzes!=='object'||!x.quizzes||Array.isArray(x.quizzes))throw Error('올바른 학습 기록 형식이 아닙니다.');
  const out=fresh();out.done=[...new Set(x.done.filter(n=>Number.isInteger(n)&&n>=1&&n<=TOTAL))];
  for(const [k,v] of Object.entries(x.notes))if(/^(exercise|reflection)-\d{1,2}$/.test(k)&&typeof v==='string')out.notes[k]=v.slice(0,50000);
  for(const [k,v] of Object.entries(x.quizzes))if(/^\d{1,2}-\d$/.test(k)&&v&&Number.isInteger(v.choice)&&v.choice>=0&&v.choice<=4)out.quizzes[k]={choice:v.choice,submitted:v.submitted===true};
  if(typeof x.last==='string'&&isLesson(x.last))out.last=x.last;
  return out;
 }
 try{const raw=readRoadmapStorage(KEY);if(raw)state=validate(JSON.parse(raw));localStorage.setItem(KEY,JSON.stringify(state));}catch(e){storageOK=false;$('#storage-warning').hidden=false;}
 function save(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch(e){storageOK=false;$('#storage-warning').hidden=false;}}
 function toast(s){$('#toast').textContent=s;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,2600);}
 function progress(){
  $('#progress-label').textContent=`${state.done.length} / ${TOTAL} 완료`;
  $('#course-progress-bar').style.width=(state.done.length/TOTAL*100)+'%';
  $$('[data-complete]').forEach(b=>{const yes=state.done.includes(+b.dataset.complete);b.setAttribute('aria-pressed',String(yes));b.textContent=yes?'✓ 학습 완료 · 다시 누르면 취소':'이 강의 학습 완료';});
  $$('[data-nav]').forEach(a=>{const yes=state.done.includes(+a.dataset.nav);a.classList.toggle('is-done',yes);$('.done-mark',a).textContent=yes?'✓':'';});
  $$('[data-card]').forEach(a=>a.classList.toggle('is-done',state.done.includes(+a.dataset.card)));
  $('#resume-link').href='#'+state.last;
  $('#resume-link').textContent=state.done.length||Object.keys(state.notes).length||state.last!==FIRST?'이어서 학습하기 →':'첫 수업 시작하기 →';
 }
 function route(){
  const hash=decodeURIComponent(location.hash.slice(1)||'home');
  const m=hash.match(/^(lesson-\d\d)(?:-|$)/);
  const next=m&&isLesson(m[1])?m[1]:(['glossary','sources'].includes(hash)?hash:'home');
  const changed=active!==next; active=next;
  $$('.page').forEach(p=>p.hidden=p.id!==active);
  $$('.sidebar a').forEach(a=>{if(a.getAttribute('href')==='#'+active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  const p=$('#'+active),h=$('h1',p);
  $('#current-label').textContent=active==='home'?'수업 안내':(active.startsWith('lesson')?active.slice(-2)+'회 · ':'')+h.textContent;
  document.title=(active==='home'?TITLE:h.textContent+' · '+BRAND);
  if(active.startsWith('lesson')){state.last=active;save();}
  const outlineLink = $('#lesson-outline-link');
  const outline = document.getElementById(active + '-toc');
  outlineLink.hidden = !outline;
  if (outline) {
    outlineLink.href = '#' + outline.id;
    if (hash === outline.id) outline.open = true;
  }
  progress();
  const anchor=document.getElementById(hash);
  requestAnimationFrame(()=>{if(anchor&&hash!==active){anchor.scrollIntoView({behavior:'auto',block:'start'});}else{window.scrollTo({top:0,behavior:'auto'});if(changed)h.focus({preventScroll:true});}});
 }
 window.addEventListener('hashchange',route);
 $$('[data-complete]').forEach(b=>b.addEventListener('click',()=>{const n=+b.dataset.complete;state.done=state.done.includes(n)?state.done.filter(x=>x!==n):[...state.done,n];save();progress();toast(state.done.includes(n)?'오늘의 학습을 기록했어요.':'완료 표시를 취소했어요.');}));
 function feedback(form,choice){const correct=choice===+form.dataset.answer;const p=$('.feedback',form);p.hidden=false;p.className='feedback '+(correct?'correct':'wrong');p.textContent=(correct?'맞았어요. ':'다시 생각해 보세요. ')+$('.explanation',form).textContent;}
 function hydrate(){
  $$('[data-note]').forEach(el=>el.value=state.notes[el.dataset.note]||'');
  $$('[data-quiz]').forEach(form=>{const v=state.quizzes[form.dataset.quiz];$$('input',form).forEach(i=>i.checked=!!v&&+i.value===v.choice);$('.feedback',form).hidden=true;if(v?.submitted)feedback(form,v.choice);});progress();
 }
 $$('[data-note]').forEach(el=>el.addEventListener('input',()=>{state.notes[el.dataset.note]=el.value;save();}));
 $$('[data-quiz]').forEach(form=>{
  form.addEventListener('change',()=>{const input=$('input:checked',form);if(input){state.quizzes[form.dataset.quiz]={choice:+input.value,submitted:false};$('.feedback',form).hidden=true;save();}});
  form.addEventListener('submit',e=>{e.preventDefault();const input=$('input:checked',form);if(!input){const p=$('.feedback',form);p.hidden=false;p.textContent='답을 하나 선택해 주세요.';return;}state.quizzes[form.dataset.quiz]={choice:+input.value,submitted:true};feedback(form,+input.value);save();});
 });
 const searchIndex=$$('.lesson').map(p=>({id:+p.dataset.lesson,text:p.textContent.toLocaleLowerCase()}));
 $('#course-search').addEventListener('input',e=>{const q=e.target.value.trim().toLocaleLowerCase();const matches=searchIndex.filter(x=>!q||x.text.includes(q)).map(x=>x.id);$$('[data-nav]').forEach(a=>a.hidden=!matches.includes(+a.dataset.nav));$$('[data-card]').forEach(a=>a.hidden=!matches.includes(+a.dataset.card));$$('.nav-pending,.lesson-card.is-pending').forEach(a=>a.hidden=!!q);$('#search-count').textContent=q?matches.length+'개 강의에서 찾았어요.':'';});
 $('#glossary-search').addEventListener('input',e=>{let count=0;const q=e.target.value.trim().toLocaleLowerCase();$$('.glossary-item').forEach(g=>{g.hidden=!g.textContent.toLocaleLowerCase().includes(q);if(!g.hidden)count++;});$('#glossary-empty').hidden=count!==0;});
 $('#export-progress').addEventListener('click',()=>{const data={...state,exportedAt:new Date().toISOString()};const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=KEY+'-progress.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);$('#record-status').textContent='완료·문제 답·메모를 JSON 파일로 내보냈어요.';});
 $('#import-progress').addEventListener('click',()=>$('#import-file').click());
 $('#import-file').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;try{if(f.size>3000000)throw Error('기록 파일이 너무 큽니다.');const incoming=validate(JSON.parse(await f.text()));state={...state,done:[...new Set([...state.done,...incoming.done])],notes:{...incoming.notes,...state.notes},quizzes:{...incoming.quizzes,...state.quizzes},last:incoming.last};save();hydrate();$('#record-status').textContent='기록을 합쳤어요. 같은 항목에 현재 기록이 있으면 현재 값을 유지했어요.';}catch(err){$('#record-status').textContent='가져오지 못했어요: '+err.message;}e.target.value='';});
 let printOpen=[];
 function preparePrint(all=false){document.body.classList.toggle('print-all',all);printOpen=$$('details').filter(d=>d.open);$$('details').forEach(d=>d.open=true);}
 function finishPrint(){document.body.classList.remove('print-all');$$('details').forEach(d=>d.open=printOpen.includes(d));}
 window.addEventListener('beforeprint',()=>{if(!document.body.classList.contains('print-all'))preparePrint(false);});window.addEventListener('afterprint',finishPrint);
 $('#print-current').addEventListener('click',()=>window.print());
 $('#print-all').addEventListener('click',()=>{preparePrint(true);window.print();});
 // 시각 자료 슬롯: 그림을 읽을 수 있으면 표시한다.
 let visualCount=0;
 const updateVisualCount=()=>{const el=$('#visual-count');if(el)el.textContent=visualCount+' / '+$$('.visual-slot').length+' 장 표시 중';};
 $$('.visual-slot img').forEach(img=>{
  const slot=img.closest('.visual-slot');
  const show=()=>{slot.classList.add('has-image');visualCount++;updateVisualCount();};
  if(img.complete&&img.naturalWidth>0)show();else img.addEventListener('load',show,{once:true});
 });
 updateVisualCount();
 hydrate();route();
})();
