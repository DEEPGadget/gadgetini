const m={};
function medianOf(a){const s=a.slice().sort((x,y)=>x-y);const mid=Math.floor(s.length/2);return s.length%2?s[mid]:(s[mid-1]+s[mid])/2;}
function medianLast(vals,n){if(!vals||!vals.length)return undefined;const s=vals.slice(-n).filter(v=>v!==null&&v!==undefined);if(!s.length)return undefined;return medianOf(s);}
function maxLast(vals,n){if(!vals||!vals.length)return undefined;const s=vals.slice(-n).filter(v=>v!==null&&v!==undefined);if(!s.length)return undefined;return Math.max(...s);}
function minLast(vals,n){if(!vals||!vals.length)return undefined;const s=vals.slice(-n).filter(v=>v!==null&&v!==undefined);if(!s.length)return undefined;return Math.min(...s);}
data.series.forEach(s=>{
  if(!s.fields||s.fields.length<2)return;
  const f=s.fields[1];
  const metric=(f.labels||{}).metric||'';
  const vals=f.values;
  if(vals&&vals.length>0){
    if(metric==='leak_detected') m[metric]=maxLast(vals,10);
    else if(metric==='level_full') m[metric]=minLast(vals,10);
    else m[metric]=medianLast(vals,10);
  }
});

function fmt(v,d){return v!==undefined&&v!==null?v.toFixed(d!==undefined?d:1):'-';}
function cls(st){return 'sv '+st;}
function evalInlet(v){if(v===undefined)return'normal';if(v>45||v<18)return'critical';if(v>40||v<22)return'warning';return'normal';}
function evalOutlet(v){if(v===undefined)return'normal';if(v>65||v<18)return'critical';if(v>60||v<22)return'warning';return'normal';}
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
setEl('sv-leak',lk>=0.5?'LEAKED':'NORMAL',lk>=0.5?'critical':'normal');
setEl('sv-lev','Coolant Level: '+(lv>=0.5?'HIGH':'MIDDLE'),lv<0.5?'warning':'normal');
setEl('sv-ct',fmt(ct)+'\u00b0C',evalChasT(ct));
setEl('sv-ch',fmt(ch)+'%',evalChasH(ch));
