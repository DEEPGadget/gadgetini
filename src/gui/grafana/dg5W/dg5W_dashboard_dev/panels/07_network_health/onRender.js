const nicMap={};
let ibTemp=undefined;
data.series.forEach(s=>{
  if(!s.fields||s.fields.length<2)return;
  const f=s.fields[1];
  const labels=f.labels||{};
  const component=labels.component||'';
  const metric=labels.metric||'';
  const extra=labels.extra||'';
  const vals=f.values;
  if(!vals||!vals.length)return;
  const val=vals[vals.length-1];
  if(component==='network'&&metric==='link_status'){nicMap[extra]=val;}
  else if(component==='ib'&&metric==='temperature'){ibTemp=val;}
});
const listEl=htmlNode.querySelector('#nic-list');
if(listEl){
  const nics=Object.keys(nicMap).sort();
  if(!nics.length){listEl.innerHTML='<span style="color:#aaa;font-size:13px">No data</span>';}
  else{
    let html='';
    nics.forEach(nic=>{
      const up=nicMap[nic]===1;
      html+='<div class="nic-row"><span class="nic-name">'+nic+'</span><span class="nic-badge"><span class="dot '+(up?'up':'down')+'"></span><span class="badge-'+(up?'up':'down')+'">'+(up?'UP':'DOWN')+'</span></span></div>';
    });
    listEl.innerHTML=html;
  }
}
const ibEl=htmlNode.querySelector('#ib-temp');
if(ibEl){
  if(ibTemp===undefined||ibTemp===null){ibEl.className='vl na';ibEl.textContent='N/A';}
  else{const cls=ibTemp>=115?'critical':ibTemp>=105?'warning':'normal';ibEl.className='vl '+cls;ibEl.textContent=ibTemp.toFixed(1)+'\u00b0C';}
}