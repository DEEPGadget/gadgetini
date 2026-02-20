const m={};
data.series.forEach(s=>{
  if(!s.fields||s.fields.length<2)return;
  const f=s.fields[1];
  const metric=(f.labels||{}).metric||'';
  const vals=f.values;
  if(vals&&vals.length>0) m[metric]=vals[vals.length-1];
});

function fmt(v,d){return v!==undefined&&v!==null?v.toFixed(d!==undefined?d:1):'-';}
function cls(st){return 'sv '+st;}
function evalInlet(v){if(v===undefined)return'normal';if(v>45||v<18)return'critical';if(v>40||v<22)return'warning';return'normal';}
function evalOutlet(v){if(v===undefined)return'normal';if(v>65)return'critical';if(v>60)return'warning';return'normal';}
function evalDelta(v){if(v===undefined)return'normal';if(v>20)return'critical';if(v>15)return'warning';return'normal';}
function evalChasT(v){if(v===undefined)return'normal';if(v>50)return'critical';if(v>40)return'warning';return'normal';}
function evalChasH(v){if(v===undefined)return'normal';if(v>80||v<10)return'critical';if(v>60)return'warning';return'normal';}

function setEl(id,text,status){
  const e=htmlNode.querySelector('#'+id);if(!e)return;
  e.textContent=text;
  e.setAttribute('class',cls(status));
}

const i1=m['inlet1_temp'],i2=m['inlet2_temp'];
const o1=m['outlet1_temp'],o2=m['outlet2_temp'];
const d1=m['delta_t1'],d2=m['delta_t2'];
const lv=m['level_full'],lk=m['leak_detected'];
const ct=m['air_temp'],ch=m['air_humidity'];

setEl('sv-in1','Inlet 1: '+fmt(i1)+'\u00b0C',evalInlet(i1));
setEl('sv-in2','Inlet 2: '+fmt(i2)+'\u00b0C',evalInlet(i2));
setEl('sv-out1','Outlet 1: '+fmt(o1)+'\u00b0C',evalOutlet(o1));
setEl('sv-out2','Outlet 2: '+fmt(o2)+'\u00b0C',evalOutlet(o2));
setEl('sv-dt1',fmt(d1)+'\u00b0C',evalDelta(d1));
setEl('sv-dt2',fmt(d2)+'\u00b0C',evalDelta(d2));
setEl('sv-leak',lk===1?'LEAKED':'NORMAL',lk===1?'critical':'normal');
setEl('sv-lev','Coolant Level: '+(lv===1?'HIGH':'MIDDLE'),lv===0?'warning':'normal');
setEl('sv-ct',fmt(ct)+'\u00b0C',evalChasT(ct));
setEl('sv-ch',fmt(ch)+'%',evalChasH(ch));