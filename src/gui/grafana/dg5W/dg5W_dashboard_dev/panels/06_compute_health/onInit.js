htmlNode._doRender=function(data){
var m={};
data.series.forEach(function(s){if(!s.fields||s.fields.length<2)return;var f=s.fields[1];var labels=f.labels||{};var key=(labels.component||'')+'_'+(labels.metric||'');var vals=f.values;if(vals&&vals.length>0)m[key]=vals[vals.length-1];});
function fmt(v,d){return v!==undefined&&v!==null?Number(v).toFixed(d!==undefined?d:1):'-';}
function evalGpuT(v){if(v===undefined)return'normal';if(v>90)return'critical';if(v>75)return'warning';return'normal';}
function evalCpuT(v){if(v===undefined)return'normal';if(v>95)return'critical';if(v>85)return'warning';return'normal';}
function evalMemA(p){if(p===undefined)return'normal';if(p<5)return'critical';if(p<20)return'warning';return'normal';}
var isBar=(htmlNode.querySelector('input[name=viewMode]:checked')||{}).value==='bar';
var groupBy=(htmlNode.querySelector('input[name=groupBy]:checked')||{}).value||'device';
var showGpu=htmlNode.querySelector('#cb-gpu')?htmlNode.querySelector('#cb-gpu').checked:true;
var showCpu=htmlNode.querySelector('#cb-cpu')?htmlNode.querySelector('#cb-cpu').checked:true;
var showMem=htmlNode.querySelector('#cb-mem')?htmlNode.querySelector('#cb-mem').checked:true;
function chk(id){var e=htmlNode.querySelector('#'+id);return e?e.checked:true;}
var gpuMbar=htmlNode.querySelector('#gpu-metrics'),cpuMbar=htmlNode.querySelector('#cpu-metrics'),memMbar=htmlNode.querySelector('#mem-metrics');
if(gpuMbar)gpuMbar.style.display=showGpu?'':'none';
if(cpuMbar)cpuMbar.style.display=showCpu?'':'none';
if(memMbar)memMbar.style.display=showMem?'':'none';
var gpus={};
Object.keys(m).forEach(function(k){var x;
if(x=k.match(/^(gpu\d+)_temperature$/)){gpus[x[1]]=gpus[x[1]]||{};gpus[x[1]].temp=m[k];}
if(x=k.match(/^(gpu\d+)_power_current$/)){gpus[x[1]]=gpus[x[1]]||{};gpus[x[1]].power=m[k];}
if(x=k.match(/^(gpu\d+)_memory_available$/)){gpus[x[1]]=gpus[x[1]]||{};gpus[x[1]].memU=m[k];}
});
var cpuD={};
Object.keys(m).forEach(function(k){var x;
if(x=k.match(/^(cpu\d+)_temperature$/)){cpuD[x[1]]=cpuD[x[1]]||{};cpuD[x[1]].temp=m[k];}
if(x=k.match(/^(cpu\d+)_power$/)){cpuD[x[1]]=cpuD[x[1]]||{};cpuD[x[1]].power=m[k];}
});
var cpuU=m['cpu_usage_total'];
Object.keys(cpuD).forEach(function(k){cpuD[k].util=cpuU;});
var mT=m['memory_total'],mA=m['memory_available'];
var maPct=mT&&mA?(mA/mT*100):undefined;
var bMax={gt:99,gp:770,gm:110,ct:104.5,cp:330,cu:110,ma:110};
var bClr={temp:'#4A9BF5',power:'#73BF69',memU:'#B877D9',util:'#FFD664'};
var content=htmlNode.querySelector('#content-area');if(!content)return;
var h='';
function barRow(lb,val,unit,max,color,ev){var pct=(val!==undefined&&val!==null&&max)?Math.min(Math.abs(val)/max*100,100):0;var cls=ev?ev(val):'normal';var clr=cls==='critical'?'#F2495C':cls==='warning'?'#FADE2A':color;return '<div class="bar-row"><span class="bar-label">'+lb+'</span><div class="bar-track"><div class="bar-fill" style="width:'+pct+'%;background:'+clr+'"></div></div><span class="bar-val '+cls+'">'+fmt(val)+unit+'</span></div>';}
if(!isBar){
if(groupBy==='device'){
if(showGpu){h+='<div class="card"><h4>AI Processors</h4>';var gc=[];if(chk('gm-temp'))gc.push({k:'temp',l:'Temp',u:'\u00b0C',ev:evalGpuT});if(chk('gm-power'))gc.push({k:'power',l:'Power',u:'W',ev:null});if(chk('gm-mem'))gc.push({k:'memU',l:'Mem%',u:'%',ev:null});h+='<table class="tbl"><tr><th>Device</th>';gc.forEach(function(c){h+='<th>'+c.l+'</th>';});h+='</tr>';var gk=Object.keys(gpus).sort();gk.forEach(function(n){var g=gpus[n];h+='<tr><td>'+n+'</td>';gc.forEach(function(c){var v=g[c.k];var cl=c.ev?c.ev(v):'normal';h+='<td class="'+cl+'">'+fmt(v)+c.u+'</td>';});h+='</tr>';});if(!gk.length)h+='<tr><td colspan="'+(gc.length+1)+'" style="color:#666">No data</td></tr>';h+='</table></div>';}
if(showCpu){h+='<div class="card"><h4>CPUs</h4>';var cc=[];if(chk('cm-temp'))cc.push({k:'temp',l:'Temp',u:'\u00b0C',ev:evalCpuT});if(chk('cm-power'))cc.push({k:'power',l:'Power',u:'W',ev:null});if(chk('cm-util'))cc.push({k:'util',l:'Util%',u:'%',ev:null});h+='<table class="tbl"><tr><th>Device</th>';cc.forEach(function(c){h+='<th>'+c.l+'</th>';});h+='</tr>';var ck=Object.keys(cpuD).sort();ck.forEach(function(n){var c2=cpuD[n];h+='<tr><td>'+n+'</td>';cc.forEach(function(c){var v=c2[c.k];var cl=c.ev?c.ev(v):'normal';h+='<td class="'+cl+'">'+fmt(v)+c.u+'</td>';});h+='</tr>';});if(!ck.length)h+='<tr><td colspan="'+(cc.length+1)+'" style="color:#666">No data</td></tr>';h+='</table></div>';}
if(showMem){h+='<div class="card"><h4>Memory</h4><table class="tbl">';if(chk('mm-avail'))h+='<tr><td>Available</td><td class="'+evalMemA(maPct)+'">'+fmt(maPct)+'%</td></tr>';h+='</table></div>';}
}else{
if(showGpu){h+='<div class="card"><h4>AI Processors</h4>';var gk=Object.keys(gpus).sort();h+='<table class="tbl"><tr><th>Metric</th>';gk.forEach(function(n){h+='<th>'+n+'</th>';});h+='</tr>';var gm=[];if(chk('gm-temp'))gm.push({k:'temp',l:'Temp',u:'\u00b0C',ev:evalGpuT});if(chk('gm-power'))gm.push({k:'power',l:'Power',u:'W',ev:null});if(chk('gm-mem'))gm.push({k:'memU',l:'Mem%',u:'%',ev:null});gm.forEach(function(r){h+='<tr><td>'+r.l+'</td>';gk.forEach(function(n){var v=gpus[n][r.k];var cl=r.ev?r.ev(v):'normal';h+='<td class="'+cl+'">'+fmt(v)+r.u+'</td>';});h+='</tr>';});if(!gk.length)h+='<tr><td colspan="2" style="color:#666">No data</td></tr>';h+='</table></div>';}
if(showCpu){h+='<div class="card"><h4>CPUs</h4>';var ck=Object.keys(cpuD).sort();h+='<table class="tbl"><tr><th>Metric</th>';ck.forEach(function(n){h+='<th>'+n+'</th>';});h+='</tr>';var cm=[];if(chk('cm-temp'))cm.push({k:'temp',l:'Temp',u:'\u00b0C',ev:evalCpuT});if(chk('cm-power'))cm.push({k:'power',l:'Power',u:'W',ev:null});if(chk('cm-util'))cm.push({k:'util',l:'Util%',u:'%',ev:null});cm.forEach(function(r){h+='<tr><td>'+r.l+'</td>';ck.forEach(function(n){var v=cpuD[n][r.k];var cl=r.ev?r.ev(v):'normal';h+='<td class="'+cl+'">'+fmt(v)+r.u+'</td>';});h+='</tr>';});if(!ck.length)h+='<tr><td colspan="2" style="color:#666">No data</td></tr>';h+='</table></div>';}
if(showMem){h+='<div class="card"><h4>Memory</h4><table class="tbl">';if(chk('mm-avail'))h+='<tr><td>Available</td><td class="'+evalMemA(maPct)+'">'+fmt(maPct)+'%</td></tr>';h+='</table></div>';}
}
}else{
if(showGpu){h+='<div class="card"><h4>AI Processors</h4>';var gm=[];if(chk('gm-temp'))gm.push({k:'temp',l:'Temp',u:'\u00b0C',mx:bMax.gt,c:bClr.temp,ev:evalGpuT});if(chk('gm-power'))gm.push({k:'power',l:'Power',u:'W',mx:bMax.gp,c:bClr.power,ev:null});if(chk('gm-mem'))gm.push({k:'memU',l:'Mem%',u:'%',mx:bMax.gm,c:bClr.memU,ev:null});h+='<div class="bar-legend">';gm.forEach(function(x){h+='<span class="bar-lg"><span class="bar-swatch" style="background:'+x.c+'"></span>'+x.l+'</span>';});h+='</div>';Object.keys(gpus).sort().forEach(function(n){var g=gpus[n];h+='<div class="bar-group-label">'+n+'</div>';gm.forEach(function(x){h+=barRow(x.l,g[x.k],x.u,x.mx,x.c,x.ev);});});h+='</div>';}
if(showCpu){h+='<div class="card"><h4>CPUs</h4>';var cm=[];if(chk('cm-temp'))cm.push({k:'temp',l:'Temp',u:'\u00b0C',mx:bMax.ct,c:bClr.temp,ev:evalCpuT});if(chk('cm-power'))cm.push({k:'power',l:'Power',u:'W',mx:bMax.cp,c:bClr.power,ev:null});if(chk('cm-util'))cm.push({k:'util',l:'Util%',u:'%',mx:bMax.cu,c:bClr.util,ev:null});h+='<div class="bar-legend">';cm.forEach(function(x){h+='<span class="bar-lg"><span class="bar-swatch" style="background:'+x.c+'"></span>'+x.l+'</span>';});h+='</div>';Object.keys(cpuD).sort().forEach(function(n){var c2=cpuD[n];h+='<div class="bar-group-label">'+n+'</div>';cm.forEach(function(x){h+=barRow(x.l,c2[x.k],x.u,x.mx,x.c,x.ev);});});h+='</div>';}
if(showMem){h+='<div class="card"><h4>Memory</h4>';if(chk('mm-avail'))h+=barRow('Available',maPct,'%',bMax.ma,bClr.temp,evalMemA);h+='</div>';}
}
content.innerHTML=h;
};
htmlNode.querySelectorAll('input[type=radio],input[type=checkbox]').forEach(function(inp){inp.addEventListener('change',function(){if(htmlNode._lastData)htmlNode._doRender(htmlNode._lastData);});});