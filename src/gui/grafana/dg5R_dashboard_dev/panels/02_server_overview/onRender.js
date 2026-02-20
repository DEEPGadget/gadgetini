const m={};
const nicMap={};
function medianOf(a){const s=a.slice().sort((x,y)=>x-y);const m=Math.floor(s.length/2);return s.length%2?s[m]:(s[m-1]+s[m])/2;}
function lastValid(vals,n,maxDev){if(!vals||!vals.length)return undefined;const s=vals.slice(-n).filter(v=>v!==null&&v!==undefined);if(!s.length)return undefined;if(s.length===1)return s[0];const med=medianOf(s);for(let i=s.length-1;i>=0;i--){if(Math.abs(s[i]-med)<=maxDev)return s[i];}return med;}
function majorityVote(vals,n){if(!vals||!vals.length)return undefined;const s=vals.slice(-n).filter(v=>v!==null&&v!==undefined);if(!s.length)return undefined;return medianOf(s);}
data.series.forEach(s=>{
  if(!s.fields||s.fields.length<2)return;
  const f=s.fields[1];
  const labels=f.labels||{};
  const component=labels.component||'';
  const metric=labels.metric||'';
  const extra=labels.extra||'';
  const vals=f.values;
  if(vals&&vals.length>0){
    let val;
    if(component==='cooling'||component==='environment'){
      if(metric==='leak_detected'||metric==='level_full') val=majorityVote(vals,10);
      else if(metric==='air_humidity') val=lastValid(vals,10,20);
      else val=lastValid(vals,10,10);
    } else {
      val=vals[vals.length-1];
    }
    if(component==='network'&&metric==='link_status'){nicMap[extra]=val;}
    else m[component+'_'+metric]=val;
  }
});

function fmt(v,u,d){return v!==undefined&&v!==null?v.toFixed(d!==undefined?d:1)+u:'-';}
function el(id){return htmlNode.querySelector('#'+id);}
function setV(id,text,cls){
  const e=el(id); if(!e)return;
  e.textContent=text;
  e.className='vl '+(cls||'normal');
}

function evalInlet(v){if(v===undefined)return'normal';if(v>45||v<18)return'critical';if(v>40||v<22)return'warning';return'normal';}
function evalOutlet(v){if(v===undefined)return'normal';if(v>65)return'critical';if(v>60)return'warning';return'normal';}
function evalChasT(v){if(v===undefined)return'normal';if(v>50)return'critical';if(v>40)return'warning';return'normal';}
function evalChasH(v){if(v===undefined)return'normal';if(v>80||v<10)return'critical';if(v>60)return'warning';return'normal';}
function evalGpuT(v){if(v===undefined)return'normal';if(v>90)return'critical';if(v>75)return'warning';return'normal';}
function evalCpuT(v){if(v===undefined)return'normal';if(v>95)return'critical';if(v>85)return'warning';return'normal';}
function evalIbTemp(v){if(v===undefined)return'normal';if(v>=115)return'critical';if(v>=105)return'warning';return'normal';}
function evalMemAvail(total,avail){if(!total||!avail)return'normal';const p=avail/total*100;if(p<5)return'critical';if(p<20)return'warning';return'normal';}

const sts=[];
const i1=m['cooling_inlet1_temp'],i2=m['cooling_inlet2_temp'];
const o1=m['cooling_outlet1_temp'],o2=m['cooling_outlet2_temp'];
const lv=m['cooling_level_full'],lk=m['cooling_leak_detected'];
const ct=m['environment_air_temp'],ch=m['environment_air_humidity'];

let s;
s=evalInlet(i1);sts.push(s);setV('v-inlet1',fmt(i1,'\u00b0C'),s);
s=evalInlet(i2);sts.push(s);setV('v-inlet2',fmt(i2,'\u00b0C'),s);
s=evalOutlet(o1);sts.push(s);setV('v-outlet1',fmt(o1,'\u00b0C'),s);
s=evalOutlet(o2);sts.push(s);setV('v-outlet2',fmt(o2,'\u00b0C'),s);
s=lv<0.5?'warning':'normal';sts.push(s);setV('v-level',lv>=0.5?'HIGH':'MIDDLE',s);
s=lk>=0.5?'critical':'normal';sts.push(s);setV('v-leak',lk>=0.5?'LEAKED':'NORMAL',s);
s=evalChasT(ct);sts.push(s);setV('v-ctemp',fmt(ct,'\u00b0C'),s);
s=evalChasH(ch);sts.push(s);setV('v-chumid',fmt(ch,'%'),s);

const gpuTs=[],gpuPs=[],gpuMs=[],gpuCs=[];
Object.keys(m).forEach(k=>{
  if(k.match(/^gpu\d+_temperature$/))gpuTs.push(m[k]);
  if(k.match(/^gpu\d+_power_current$/))gpuPs.push(m[k]);
  if(k.match(/^gpu\d+_memory_available$/))gpuMs.push(m[k]);
});
function avg(a){return a.length?a.reduce((s,v)=>s+v,0)/a.length:undefined;}
const gaT=avg(gpuTs),gaP=avg(gpuPs),gaM=avg(gpuMs),gaC=avg(gpuCs);
s=evalGpuT(gaT);sts.push(s);setV('v-gpu-temp',fmt(gaT,'\u00b0C'),s);
setV('v-gpu-pwr',fmt(gaP,'W'),'normal');
setV('v-gpu-mem',fmt(gaM,'%'),'normal');

const cpuTs=[],cpuPs=[];
Object.keys(m).forEach(k=>{
  if(k.match(/^cpu\d+_temperature$/))cpuTs.push(m[k]);
  if(k.match(/^cpu\d+_power$/))cpuPs.push(m[k]);
});
const caT=avg(cpuTs),caP=avg(cpuPs),cuU=m['cpu_usage_total'];
s=evalCpuT(caT);sts.push(s);setV('v-cpu-temp',fmt(caT,'\u00b0C'),s);
setV('v-cpu-pwr',fmt(caP,'W'),'normal');
setV('v-cpu-util',fmt(cuU,'%'),'normal');

const mT=m['memory_total'],mA=m['memory_available'];
s=evalMemAvail(mT,mA);sts.push(s);setV('v-mem-avail',mT&&mA?((mA/mT*100).toFixed(1)+'%'):'-',s);

const ibT=m['ib_temperature'];
const ibEl=el('v-ib-temp');
if(ibEl){
  if(ibT===undefined||ibT===null){ibEl.className='vl na';ibEl.textContent='-';}
  else{
    const st=evalIbTemp(ibT);sts.push(st);
    ibEl.className='vl '+st;
    ibEl.textContent=ibT.toFixed(1)+'\u00b0C';
  }
}

const nicsEl=el('v-nics');
if(nicsEl){
  const nics=Object.keys(nicMap).sort();
  if(!nics.length){nicsEl.innerHTML='-';}
  else{
    let html='';
    let anyDown=false;
    nics.forEach(nic=>{
      const v=nicMap[nic];
      const st=v===1?'normal':'normal';
      if(v!==1)anyDown=true;
      html+='<div class="mr"><span class="lb">'+nic+'</span><span class="vl '+st+'">'+(v===1?'UP':'DOWN')+'</span></div>';
    });
    nicsEl.innerHTML=html;
    sts.push(anyDown?'normal':'normal');
  }
}

let worst='normal';
sts.forEach(v=>{if(v==='critical')worst='critical';else if(v==='warning'&&worst!=='critical')worst='warning';});
const ov=el('ov');if(ov)ov.className='overview '+worst;
const sb=el('sb');if(sb)sb.className='status-bar '+worst;
const stEl=el('st');if(stEl)stEl.textContent=worst==='critical'?'Critical':worst==='warning'?'Warning':'Normal';