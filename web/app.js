/* Plan B client: polls /d/{DATA_PATH}/*.json every 60s, cache-busted. FOMO links come only from the JSON (links.py). */
(function(){
const h0=new URLSearchParams(location.hash.slice(1));
if(h0.get('d')){localStorage.setItem('d',h0.get('d'));history.replaceState(null,'',location.pathname+location.search+'#/home')}
const D=localStorage.getItem('d'),V=document.getElementById('view'),cache={},err={};
const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=(n,d=2)=>n==null?'—':'$'+Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=n=>n==null?'—':(n>=0?'+':'')+Number(n).toFixed(1)+'%';
const ago=t=>{if(!t)return'never';const s=(Date.now()-new Date(t))/1000;return s<60?Math.round(s)+'s ago':s<3600?Math.round(s/60)+'m ago':Math.round(s/3600)+'h ago'};
const tm=t=>t?new Date(t).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'';
async function get(f){if(!D)throw'nolink';const r=await fetch('d/'+D+'/'+f+'?_='+Date.now(),{cache:'no-store'});if(!r.ok)throw r.status;return r.json()}
async function load(f){try{cache[f]=await get(f);delete err[f]}catch(e){err[f]=e}return cache[f]}
const empty=(t,s)=>`<div class="card state"><div style="font-size:34px">◌</div><h3>${E(t)}</h3><div>${E(s)}</div></div>`;
const error=(f)=>`<div class="card state err"><div style="font-size:34px">⚠︎</div><h3>${!D||err[f]==='nolink'?'Private link needed':"Can't reach the desk"}</h3><div>${!D||err[f]==='nolink'?'Open the app once with your private link from Telegram.':'Last try failed ('+E(err[f])+'). Retrying every 60s.'}</div></div>`;
const loading=()=>`<div class="card"><div class="skel" style="width:40%"></div><div class="skel" style="height:34px;width:70%"></div><div class="skel"></div></div>`;
function badge(s){const b=document.getElementById('badge');if(!s)return;b.textContent=s.mode;b.className='badge'+(s.mode==='LIVE'?' live':'')}
const actRow=a=>`<a class="row" style="color:inherit;text-decoration:none" href="${E(a.link||'#')}" target="_blank"><div><div class="t">${E(a.title)}</div><div class="s">${E(a.agent_line)} · ${tm(a.ts)}</div></div><div class="num ${/^\+|Sold|Bought/.test(a.right+a.title)?'':'mute'} ${a.kind==='stop'?'down':a.kind==='sell'?'up':''}">${E(a.right)}</div></a>`;
function agentCards(ag){const up=a=>`<span class="dot ${a.ts&&Date.now()-new Date(a.ts)<120e3&&!a.paused?'':'off'}"></span>`;
 const s=ag.scanner,au=ag.auditor,an=ag.analyst,ex=ag.executor,r=ag.risk,last=(au.last||[])[0];
 return `<div class="grid">
 <a class="agent" href="#/agents"><h4>Scanner ${up(s)}</h4><div class="num big" style="font-size:22px">${s.pools}</div><div class="s mute">pools · ${s.killed} cut · ${s.waiting} waiting</div></a>
 <a class="agent" href="${last?'#/auditor/'+E(last.mint):'#/agents'}"><h4>Auditor ${up(au)}</h4><div class="num big" style="font-size:22px">${au.taken}</div><div class="s mute">taken apart · ${au.rejected} rejected</div>
  <div class="strips">${[0,1,2,3,4,5,6,7].map(i=>{const L=last&&last.layers[i];return`<i class="${L?L.pass===true?'p':L.pass===false?'f':'':''}"></i>`}).join('')}</div>
  <div class="s mute" style="margin-top:6px">${last?(last.passed?'8/8 → Executor':E(last.reason)):'waiting for a coin'}</div></a>
 <a class="agent" href="#/agents"><h4>Analyst ${up(an)}</h4><canvas class="ring" data-score="${(an.last||[])[0]?.score??''}" data-min="${an.minScore}"></canvas><div class="s mute">Scoring · ${an.mode==='rules'?'rules':'Jev'}</div></a>
 <a class="agent" href="#/agents"><h4>Executor ${up(ex)}</h4><div class="num big" style="font-size:22px">${ex.trades}</div><div class="s mute">trades · ${ex.stackPct}% of stack</div></a>
 <a class="agent" href="#/agents" style="grid-column:span 2"><h4>Risk ${up(r)}</h4><div class="s">${r.open?'Guarding '+r.open+' open':r.lastExit==='trail'?'Trailed out':r.lastExit==='stop'?'Stopped':'Nothing open'}</div>
  <span class="pill r">stop -${r.stopPct}%</span><span class="pill g">trail ${r.trailPct}%</span></a></div>`}
function rings(){document.querySelectorAll('canvas.ring').forEach(c=>Chart.ring(c,c.dataset.score===''?null:+c.dataset.score,+c.dataset.min))}
const R={
async home(){const[s,ch,ag,ac]=await Promise.all(['state.json','chart.json','agents.json','activity.json'].map(load));
 if(!s)return err['state.json']?error('state.json'):loading();badge(s);
 const pos=s.openPositions||[];
 return `<div class="card"><div class="label">${s.mode==='PAPER'?'PAPER balance':'Stack'}</div><div class="big">${$(s.balance)}</div>
  <div class="num ${s.pnlToday>=0?'up':'down'}">${s.pnlToday>=0?'+':''}${$(s.pnlToday)} since start · <span class="mute">updated ${ago(s.ts)}</span></div><canvas id="bal"></canvas></div>
  <div class="card"><div class="label">Open positions</div>${pos.length?pos.map(p=>`<div class="row"><a href="#/coin/${E(p.mint)}" style="color:inherit;text-decoration:none"><div class="t">${E(p.name)}</div><div class="s">${$(p.size_usd)} · stop -${p.stop_pct}% · ${E(p.status)}</div></a><a class="pill c" href="${E(p.link)}" target="_blank">Sell on FOMO</a></div>`).join(''):'<div class="s mute" style="padding:10px 0">No open positions. The desk is watching.</div>'}</div>
  ${ag?agentCards(ag):''}
  <div class="card"><div class="label">Latest</div>${ac&&ac.length?ac.slice(0,5).map(actRow).join(''):'<div class="s mute" style="padding:10px 0">Nothing has happened yet tonight.</div>'}</div>`},
async agents(){const ag=await load('agents.json');if(!ag)return err['agents.json']?error('agents.json'):loading();
 const sf=ag.scanner.feed||[],af=ag.auditor.feed||[],nf=ag.analyst.feed||[];
 return agentCards(ag)+`<div class="card"><div class="label">Scanner feed</div>${sf.length?sf.slice(0,20).map(x=>`<a class="row ${x.verdict}" style="color:inherit;text-decoration:none" href="#/coin/${E(x.mint)}"><div><div class="t">${E(x.name)}</div><div class="s">${tm(x.ts)} · liq ${$(x.liq,0)}</div></div><div class="s ${x.verdict==='kill'?'down':'up'}">${x.verdict==='kill'?E(x.reason):'→ auditor'}</div></a>`).join(''):'<div class="s mute" style="padding:10px 0">No pools yet tonight.</div>'}</div>
 <div class="card"><div class="label">Auditor</div>${af.length?af.slice(0,15).map(a=>`<a class="row" style="color:inherit;text-decoration:none" href="#/auditor/${E(a.mint)}"><div class="t">${E(a.name)}</div><div class="s ${a.passed?'up':'down'}">${a.passed?'8/8':E(a.reason)}</div></a>`).join(''):'<div class="s mute" style="padding:10px 0">Nothing taken apart yet.</div>'}</div>
 <div class="card"><div class="label">Analyst (${E(ag.analyst.mode)})</div>${nf.length?nf.slice(0,15).map(a=>`<a class="row" style="color:inherit;text-decoration:none" href="#/coin/${E(a.mint)}"><div class="t">${E(a.name)}</div><div class="s ${a.passed?'up':'down'}">${a.score} · ${a.passed?'pass':E(a.failed[0])}</div></a>`).join(''):'<div class="s mute" style="padding:10px 0">No coins scored yet.</div>'}</div>`},
async activity(){const ac=await load('activity.json');if(!ac)return err['activity.json']?error('activity.json'):loading();
 return ac.length?`<div class="card">${ac.map(actRow).join('')}</div>`:empty('No activity yet','Buys, sells, stops and rejects show up here.')},
async auditor(m){const a=await load('audit/'+m+'.json');if(!a)return err['audit/'+m+'.json']===404?empty('No audit for this coin','Scanner never passed it to Auditor.'):err['audit/'+m+'.json']?error('audit/'+m+'.json'):loading();
 return `<a class="back" href="#/agents">‹ Agents</a><div class="card"><div class="label">Auditor</div><h2 style="margin:4px 0">${E(a.name)}</h2><canvas class="disc" id="disc"></canvas>
 <div class="s ${a.passed?'up':'down'}" style="text-align:center;font-weight:700">${a.passed?'8/8 → Executor':'Rejected · '+E(a.reason)}</div>
 ${a.layers.map(L=>`<div class="layer ${L.pass===true?'p':L.pass===false?'f':'n'}"><b>${L.pass===true?'✓':L.pass===false?'✕':L.n}</b><div style="flex:1"><div class="t">${E(L.name)}</div><div class="s mute">${E(L.source)}</div></div><div class="num s">${E(L.value)}</div></div>`).join('')}
 <div class="s mute" style="margin-top:8px">${a.holders!=null?a.holders+' holders · ':''}${tm(a.ts)}</div><a class="btn ghost" href="${E(a.link)}" target="_blank">Open on FOMO</a></div>`},
async coin(m){const c=await load('coin/'+m+'.json');if(!c)return err['coin/'+m+'.json']===404?empty('Coin not on the desk','It was not seen in the last 24h.'):err['coin/'+m+'.json']?error('coin/'+m+'.json'):loading();
 const p=c.position,last=c.candles.length?c.candles[c.candles.length-1].c:null;
 return `<a class="back" href="#/home">‹ Home</a><div class="card"><div class="label">${E(c.symbol||'')}</div><h2 style="margin:4px 0">${E(c.name||c.mint.slice(0,6))}</h2>
 <div class="big" style="font-size:26px">${last!=null?'$'+Number(last).toPrecision(4):'—'}</div>
 ${c.candles.length?'<canvas id="cdl"></canvas>':'<div class="state" style="padding:30px">No price candles yet.</div>'}
 <div class="s mute">1-min candles${c.riskLine?' · <span style="color:var(--orange)">— — Risk trailing stop</span>':''}</div></div>
 <div class="card"><div class="row"><span class="mute">Holders</span><span class="num">${c.holders??'—'}</span></div>
 <div class="row"><span class="mute">Scanner</span><span class="s">${c.scan?(c.scan.verdict==='kill'?E(c.scan.reason):'passed'):'—'}</span></div>
 <div class="row"><span class="mute">Auditor</span><a class="s cyan" href="#/auditor/${E(c.mint)}">${c.audit?(c.audit.passed?'8/8':E(c.audit.reason)):'—'}</a></div>
 <div class="row"><span class="mute">Analyst</span><span class="s">${c.analysis?c.analysis.score+' · '+(c.analysis.passed?'pass':E(c.analysis.failed[0])):'—'}</span></div>
 ${p?`<div class="row"><span class="mute">Position</span><span class="num s">${$(p.size_usd)} @ ${Number(p.entry_price).toPrecision(4)} · ${E(p.status)}${p.pnl_usd!=null?' · '+$(p.pnl_usd):''}</span></div>`:''}
 <a class="btn" href="${E(c.link)}" target="_blank">${p&&p.status!=='closed'?'Sell on FOMO':'Open on FOMO'}</a></div>`},
async account(){const a=await load('account.json');if(!a)return err['account.json']?error('account.json'):loading();const S=a.settings,g={};
 Object.keys(S).forEach(k=>{const[s,n]=k.split('.');(g[s]=g[s]||[]).push([n,S[k]])});
 return `<div class="card"><div class="label">FOMO</div><div class="row"><span>Handle</span><a class="cyan" href="${E(a.profileUrl)}" target="_blank">${E(a.handle)}</a></div>
 <div class="row"><span>Invite a friend</span><a class="cyan" href="${E(a.signupUrl)}" target="_blank">Signup link</a></div></div>
 <div class="card"><div class="label">Alerts</div><div class="row"><span>Telegram</span><span class="up">On</span></div><div class="row"><span>Web push</span><span class="mute">Not available</span></div><div class="s mute">${E(a.pushNote)}</div></div>
 <div class="card"><div class="s mute">${E(a.changeNote)}</div></div>
 ${Object.entries(g).map(([s,rows])=>`<div class="card"><div class="label">${E(s==='analyst'&&S['analyst.mode']==='rules'?'Analyst (rules)':s)}</div>${rows.map(([n,v])=>`<div class="row"><span class="s">${E(n)}</span><span class="num s">${E(v)}</span></div>`).join('')}</div>`).join('')}`}
};
let busy=false;
async function render(){if(busy)return;busy=true;const[_,t,arg]=(location.hash||'#/home').split('/');const tab=t||'home';
 document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('on',a.dataset.t===tab||(tab==='coin'||tab==='auditor')&&a.dataset.t==='agents'));
 if(!V.innerHTML)V.innerHTML=loading();
 try{V.innerHTML=await (R[tab]||R.home)(arg)}catch(e){V.innerHTML=error('x')}
 const s=cache['state.json'];if(s)badge(s);
 const b=document.getElementById('bal');if(b&&cache['chart.json'])Chart.line(b,cache['chart.json'].points,cache['chart.json'].start);
 const d=document.getElementById('disc');if(d&&cache['audit/'+arg+'.json'])Chart.disc(d,cache['audit/'+arg+'.json'].layers);
 const cd=document.getElementById('cdl'),c=cache['coin/'+arg+'.json'];if(cd&&c)Chart.candles(cd,c.candles,c.riskLine,c.position&&c.position.entry_price);
 rings();busy=false}
addEventListener('hashchange',()=>{V.innerHTML='';render()});render();setInterval(render,60000);
})();
