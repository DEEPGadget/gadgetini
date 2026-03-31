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
function evalChasT(v){if(v===undefined)return'normal';if(v>50)return'critical';if(v>40)return'warning';return'normal';}
function evalChasH(v){if(v===undefined)return'normal';if(v>80)return'critical';if(v>60)return'warning';return'normal';}
function setEl(id,text,status){const e=htmlNode.querySelector('#'+id);if(!e)return;e.textContent=text;e.setAttribute('class',cls(status));}
const i1=m['inlet1_temp'];
const stab=m['stability'];
const lv=m['level_full'],lk=m['leak_detected'];
const ct=m['air_temp'],ch=m['air_humidity'];
setEl('sv-in1','Inlet 1: '+fmt(i1)+'\u00b0C',evalInlet(i1));
setEl('sv-lev','Level: '+(lv===undefined||lv===null?'-':lv>=0.5?'HIGH':'MIDDLE'),lv===undefined||lv===null?'normal':lv<0.5?'warning':'normal');
setEl('sv-leak',lk===undefined||lk===null?'-':lk>=0.5?'LEAKED':'NORMAL',lk===undefined||lk===null?'normal':lk>=0.5?'critical':'normal');
setEl('sv-stab',stab===undefined||stab===null?'-':stab>=0.5?'STABLE':'UNSTABLE',stab===undefined||stab===null?'normal':stab<0.5?'critical':'normal');
setEl('sv-ct',fmt(ct)+'\u00b0C',evalChasT(ct));
setEl('sv-ch',fmt(ch)+'%',evalChasH(ch));