import {InteractionStage} from './interaction-stage.js';
const $=selector=>document.querySelector(selector);
try {
  const response=await fetch('./interaction-catalog.json');if(!response.ok)throw Error(`Catalog request failed: ${response.status}`);
  const catalog=await response.json();
  const params=new URLSearchParams(location.search);
  // Preserve the original sequential peer replay as a directly addressable regression fixture.
  if(params.get('scene')==='peer') {
    const peer=await(await fetch('./interaction-replay-data.json')).json();
    catalog.cases.push({...peer,id:'peer_sequence',title:'Peer Interaction Sequence',category:'Social',actions:[]});
  }
  const view=new InteractionStage($('#scene'));view.resize();view.setZoom(innerWidth<850?2.5:4);
  let data=catalog.cases[0],index=0,state,playing=false,timer=null;
  const hints={housing_loss:'A 60-day rent-arrears scenario ends the tenancy. Full bladder is a separate condition. The last step shows the person leaving while the waste remains.',street_accident:'Watch the squat and the waste appearing beside the feet. Low cash or lack of housing alone does not cause this event.',stepped_in_waste:'Only the person making contact recoils. The pile flattens and stays flattened.',fatal_collapse:'Actual collapse casualties produce a fall and a small blood impact. Surviving witnesses have separate injury outcomes.',health_failure:'This death has a health cause; the replay does not add a traumatic blood impact.',offer_housing:'An offer is pending until the recipient independently accepts or rejects it.',offer_job:'The offer is recorded; the recipient has not automatically accepted the job.',offer_investment:'The investment proposal remains pending until the recipient decides.'};
  function list(){
    const search=$('#search').value.trim().toLowerCase();$('#cases').replaceChildren();
    for(const category of [...new Set(catalog.cases.map(c=>c.category))]) {
      const cases=catalog.cases.filter(c=>c.category===category&&`${c.title} ${c.category} ${c.id}`.toLowerCase().includes(search));
      if(!cases.length)continue;
      const section=document.createElement('section'),heading=document.createElement('h3');heading.textContent=category;section.append(heading);
      for(const item of cases){const button=document.createElement('button');button.className='case';button.dataset.case=item.id;button.setAttribute('aria-current',String(item.id===data.id));button.textContent=item.title;button.onclick=()=>select(item.id);section.append(button);}
      $('#cases').append(section);
    }
  }
  function stop(){playing=false;clearTimeout(timer);timer=null;$('#play').textContent='▶ Play';}
  function schedule(){timer=setTimeout(()=>{if(index<data.frames.length-1){show(index+1);schedule();}else{stop();view.setPaused(true);}},2800);}
  function play(){if(playing){stop();view.setPaused(true);return;}if(index===data.frames.length-1)show(0);playing=true;view.setPaused(false);$('#play').textContent='Ⅱ Pause';schedule();}
  function select(id){stop();data=catalog.cases.find(c=>c.id===id)||catalog.cases[0];view.focus=data.focus||{x:745,y:400};$('#title').textContent=data.title;$('#category').textContent=data.category;$('#hint').textContent=hints[data.id]||'Step through the recorded decision and its engine result. Limb gestures are shared where an action has no dedicated animation.';list();show(0);const url=new URL(location);url.searchParams.set('case',data.id);history.replaceState(null,'',url);}
  function show(next){
    index=Math.max(0,Math.min(data.frames.length-1,next));const frame=data.frames[index];state=frame.state;
    view.prime(data.frames[Math.max(0,index-1)].state);
    $('#frame-title').textContent=frame.title;$('#status').textContent=`${index+1} / ${data.frames.length}`;
    $('#timeline').max=data.frames.length-1;$('#timeline').value=index;
    $('#previous').disabled=index===0;$('#next').disabled=index===data.frames.length-1;
    const before=data.frames[0].state,oldIds=new Set((before.events||[]).map(e=>e.id));
    const events=(state.events||[]).filter(e=>!oldIds.has(e.id));
    $('#event').textContent=index?events.at(-1)?.public_text||'The chosen action is in progress.':'Starting conditions';
    $('#events').replaceChildren();for(const event of events.slice(-7)){const li=document.createElement('li');li.textContent=event.public_text;$('#events').append(li);}
    $('#evidence').textContent=frame.evidence||`World objects: ${before.objects.length} → ${state.objects.length} · Completed decisions: ${state.agents.reduce((sum,a)=>sum+a.decision_count,0)}`;
    $('#people').replaceChildren();
    const visible=state.agents.filter(a=>Math.hypot(a.position.x-view.focus.x,a.position.y-view.focus.y)<130);
    for(const agent of visible){
      const detail=state.demo_details?.[agent.id],original=before.demo_details?.[agent.id];
      const card=document.createElement('div');card.className='person';const name=document.createElement('strong');name.textContent=agent.name;card.append(name);
      const status=document.createElement('p');status.textContent=`${agent.current_action} · Health ${Math.round(agent.health)} · ${agent.has_home?'Has a home':'No home'}`;card.append(status);
      if(detail){const facts=document.createElement('p');facts.textContent=`Cash ${original.credits.toFixed(2)} → ${detail.credits.toFixed(2)} · Energy ${original.energy.toFixed(0)} → ${detail.energy.toFixed(0)} · Bladder ${original.bladder.toFixed(0)} → ${detail.bladder.toFixed(0)} · Bag: ${detail.bag.join(', ')||'empty'}`;card.append(facts);const result=document.createElement('p');result.className='result';result.textContent=detail.action_result;card.append(result);}
      $('#people').append(card);
    }
    $('#raw').textContent=JSON.stringify({economy:state.economy,objects:state.objects.filter(o=>!before.objects.some(p=>p.id===o.id&&JSON.stringify(p)===JSON.stringify(o))).map(o=>({name:o.name,kind:o.kind,metadata:o.metadata}))},null,2);
  }
  $('#search').oninput=list;$('#play').onclick=play;
  $('#previous').onclick=()=>{stop();show(index-1);};$('#next').onclick=()=>{stop();show(index+1);};$('#replay').onclick=()=>{stop();show(index);};
  $('#timeline').oninput=event=>{stop();show(Number(event.target.value));};
  $('#zoom-in').onclick=()=>view.setZoom(view.zoom+.5);$('#zoom-out').onclick=()=>view.setZoom(view.zoom-.5);
  window.addEventListener('resize',()=>view.resize());
  $('#coverage').textContent=`${catalog.action_count} actions · ${catalog.cases.length} scenes`;
  window.interactionReplay={view,catalog,select,show,play,stop,get data(){return data;},get index(){return index;},get playing(){return playing;}};
  select(params.get('case')||(params.get('scene')==='sanitation'?'housing_loss':params.get('scene')==='peer'?'peer_sequence':'street_accident'));
  function draw(){view.draw(state,state.agents[0]?.id);requestAnimationFrame(draw);}draw();
}catch(error){$('#error').hidden=false;$('#error').textContent=`Could not load the interaction lab: ${error.message}`;throw error;}
