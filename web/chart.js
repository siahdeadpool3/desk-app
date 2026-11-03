/* Hand-drawn canvas charts: balance line, 1-min candles with Risk line, score ring. */
const Chart={
 setup(cv,h){const d=devicePixelRatio||1,w=cv.clientWidth||358;cv.width=w*d;cv.height=h*d;cv.style.height=h+'px';const x=cv.getContext('2d');x.scale(d,d);return[x,w,h]},
 line(cv,pts,start){const[x,w,h]=this.setup(cv,120);const v=[start,...pts.map(p=>p.balance)];if(v.length<2){x.strokeStyle='#222a38';x.setLineDash([4,4]);x.beginPath();x.moveTo(0,h/2);x.lineTo(w,h/2);x.stroke();return}
  const lo=Math.min(...v),hi=Math.max(...v),r=hi-lo||1,X=i=>i/(v.length-1)*w,Y=y=>h-8-(y-lo)/r*(h-16);const up=v[v.length-1]>=start,col=up?'#2fe08a':'#ff4d5e';
  const g=x.createLinearGradient(0,0,0,h);g.addColorStop(0,up?'rgba(47,224,138,.28)':'rgba(255,77,94,.28)');g.addColorStop(1,'rgba(0,0,0,0)');
  x.beginPath();v.forEach((y,i)=>i?x.lineTo(X(i),Y(y)):x.moveTo(0,Y(y)));x.lineTo(w,h);x.lineTo(0,h);x.fillStyle=g;x.fill();
  x.beginPath();v.forEach((y,i)=>i?x.lineTo(X(i),Y(y)):x.moveTo(0,Y(y)));x.strokeStyle=col;x.lineWidth=2;x.stroke()},
 candles(cv,cs,riskLine,entry){const[x,w,h]=this.setup(cv,220);if(!cs.length)return;const ps=cs.flatMap(c=>[c.h,c.l]).concat(riskLine?[riskLine]:[]).concat(entry?[entry]:[]);
  const lo=Math.min(...ps),hi=Math.max(...ps),r=hi-lo||hi*.01||1,Y=y=>h-14-(y-lo)/r*(h-28),bw=Math.max(2,Math.min(10,w/cs.length*.7)),st=w/Math.max(cs.length,1);
  x.strokeStyle='#161b26';for(let i=1;i<4;i++){x.beginPath();x.moveTo(0,h*i/4);x.lineTo(w,h*i/4);x.stroke()}
  cs.forEach((c,i)=>{const cx=i*st+st/2,col=c.c>=c.o?'#2fe08a':'#ff4d5e';x.strokeStyle=x.fillStyle=col;x.beginPath();x.moveTo(cx,Y(c.h));x.lineTo(cx,Y(c.l));x.stroke();
   const t=Y(Math.max(c.o,c.c)),b=Y(Math.min(c.o,c.c));x.fillRect(cx-bw/2,t,bw,Math.max(1,b-t))});
  if(entry){x.setLineDash([2,4]);x.strokeStyle='#8691a6';x.beginPath();x.moveTo(0,Y(entry));x.lineTo(w,Y(entry));x.stroke()}
  if(riskLine){x.setLineDash([6,4]);x.strokeStyle='#ff8a3d';x.lineWidth=1.5;x.beginPath();x.moveTo(0,Y(riskLine));x.lineTo(w,Y(riskLine));x.stroke();x.setLineDash([]);
   x.fillStyle='#ff8a3d';x.font='600 10px -apple-system';x.fillText('Risk trailing stop',6,Y(riskLine)-4)}},
 ring(cv,score,min){const[x,w,h]=this.setup(cv,64);const r=26,c=32;x.lineWidth=6;x.strokeStyle='#222a38';x.beginPath();x.arc(c,c,r,0,7);x.stroke();
  if(score!=null){x.strokeStyle=score>=min?'#2fe08a':'#ffb020';x.beginPath();x.arc(c,c,r,-Math.PI/2,-Math.PI/2+2*Math.PI*score/100);x.stroke();
  x.fillStyle='#eef2f8';x.font='700 16px ui-monospace,Menlo';x.textAlign='center';x.textBaseline='middle';x.fillText(score,c,c)}},
 disc(cv,layers){const[x,w,h]=this.setup(cv,150);const c=75;for(let i=0;i<8;i++){const L=layers[i]||{},a0=-Math.PI/2+i*Math.PI/4+.04,a1=a0+Math.PI/4-.08;
  x.lineWidth=14;x.strokeStyle=L.pass===true?'#2fe08a':L.pass===false?'#ff4d5e':'#222a38';x.beginPath();x.arc(c,c,60,a0,a1);x.stroke()}
  const n=layers.filter(l=>l.pass===true).length;x.fillStyle='#eef2f8';x.font='700 22px ui-monospace,Menlo';x.textAlign='center';x.textBaseline='middle';x.fillText(n+'/8',c,c)}
};
