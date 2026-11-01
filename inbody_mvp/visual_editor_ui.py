"""Client-side bounding-box editor for Gradio 6 gr.HTML."""
HTML_TEMPLATE = """
<div class="hj-editor">
  <div class="hj-toolbar">
    <label>Página <select id="hj-page"></select></label>
    <label>Sección <select id="hj-kind"></select></label>
    <button id="hj-add" type="button">Dibujar nueva</button>
    <button id="hj-delete" type="button">Eliminar</button>
    <label><input id="hj-include" type="checkbox" checked /> Incluir</label>
    <span id="hj-help">Selecciona una caja o dibuja una nueva.</span>
  </div>
  <div class="hj-stage"><canvas id="hj-canvas"></canvas></div>
  <div class="hj-foot">Arrastra dentro de una caja para moverla; usa la esquina inferior derecha para redimensionar.</div>
</div>
"""
CSS_TEMPLATE = """
.hj-editor {font-family:system-ui,sans-serif;color:var(--body-text-color,#222)}
.hj-toolbar {display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:10px}
.hj-toolbar select,.hj-toolbar button {padding:6px;border:1px solid #999;border-radius:6px;background:var(--body-background-fill,#fff);color:inherit}
.hj-stage {overflow:auto;max-height:740px;background:#555;padding:8px}
#hj-canvas {display:block;max-width:100%;height:auto;margin:auto;touch-action:none;cursor:crosshair}
.hj-foot {font-size:12px;color:#888;margin-top:8px}
"""
JS_ON_LOAD = """
const canvas = element.querySelector('#hj-canvas');
const ctx = canvas.getContext('2d');
const pageSelect = element.querySelector('#hj-page');
const kindSelect = element.querySelector('#hj-kind');
const include = element.querySelector('#hj-include');
const help = element.querySelector('#hj-help');
const kinds = ['header','body_composition','muscle_fat','obesity','segmental_lean',
               'segmental_fat','research','impedance','history','other'];
for (const k of kinds) { const option=document.createElement('option'); option.value=k; option.textContent=k; kindSelect.append(option); }
let state={pages:[],rows:[],metadata:{}}, page=1, selected=-1, mode='select', drag=null, image=new Image();
function publish() {
  props.value=JSON.stringify(state);
}
function pageInfo(){return state.pages.find(x=>x.number===page);}
function setPage(n) {
  page=n; selected=-1; const p=pageInfo(); if (!p) return;
  image.onload=draw;
  image.src=p.url;
  pageSelect.value=String(n);
}
function draw(){
  const p=pageInfo(); if(!p || !image.complete || !image.naturalWidth) return;
  canvas.width=image.naturalWidth; canvas.height=image.naturalHeight;
  ctx.drawImage(image,0,0,canvas.width,canvas.height);
  const sx=canvas.width/p.width, sy=canvas.height/p.height;
  state.rows.forEach((r,i)=>{
    if(Number(r[0])!==page)return;
    const [x0,y0,x1,y1]=r.slice(2,6).map(Number);
    ctx.strokeStyle=i===selected?'#22c55e':'#2563eb';ctx.lineWidth=i===selected?4:2;
    ctx.strokeRect(x0*sx,y0*sy,(x1-x0)*sx,(y1-y0)*sy);
    ctx.fillStyle=ctx.strokeStyle;
    ctx.fillRect(x0*sx,Math.max(0,y0*sy-19),Math.min(210,(x1-x0)*sx+30),18);
    ctx.fillStyle='#fff';ctx.font='12px sans-serif';
    ctx.fillText(String(r[1])+' #'+(i+1),x0*sx+3,Math.max(13,y0*sy-6));
    if(i===selected){ctx.fillStyle='#22c55e';ctx.fillRect(x1*sx-7,y1*sy-7,14,14);}
  });
  if (drag?.type==='create' && drag.current){
    ctx.strokeStyle='#22c55e';ctx.setLineDash([5,4]);
    ctx.strokeRect(drag.x,drag.y,drag.current[0]-drag.x,drag.current[1]-drag.y);
    ctx.setLineDash([]);
  }
}
function coords(evt){
  const box=canvas.getBoundingClientRect();
  return [(evt.clientX-box.left)*canvas.width/box.width,
          (evt.clientY-box.top)*canvas.height/box.height];
}
function hit(x,y){
  const p=pageInfo(); if(!p)return -1;
  const sx=canvas.width/p.width,sy=canvas.height/p.height;
  for(let i=state.rows.length-1;i>=0;i--){
    const r=state.rows[i];if(Number(r[0])!==page)continue;
    if(x>=Number(r[2])*sx&&x<=Number(r[4])*sx&&y>=Number(r[3])*sy&&y<=Number(r[5])*sy)return i;
  }
  return -1;
}
function updateSelected(){
  const r=state.rows[selected];
  if(r){kindSelect.value=r[1];include.checked=Boolean(r[6]);}
  help.textContent=r?'Región '+(selected+1)+' seleccionada':'Arrastra para dibujar una caja.';
  draw();
}
canvas.addEventListener('pointerdown',e=>{
  const p=pageInfo();if(!p)return;
  canvas.setPointerCapture(e.pointerId);
  const [x,y]=coords(e), target=mode==='create'?-1:hit(x,y);
  if(target<0){selected=-1;mode='create';drag={type:'create',x,y};}
  else{
    selected=target;const r=state.rows[selected],sx=canvas.width/p.width,sy=canvas.height/p.height;
    const resize=Math.abs(x-Number(r[4])*sx)<18&&Math.abs(y-Number(r[5])*sy)<18;
    drag={type:resize?'resize':'move',x,y,initial:r.slice(2,6).map(Number)};
  }
  updateSelected();
});
canvas.addEventListener('pointermove',e=>{
  if(!drag)return;
  const p=pageInfo();if(!p)return;
  const [x,y]=coords(e),dx=(x-drag.x)*p.width/canvas.width,dy=(y-drag.y)*p.height/canvas.height;
  if(drag.type==='create'){drag.current=[x,y];draw();return;}
  const r=state.rows[selected], a=drag.initial;
  if(drag.type==='move'){
    const w=a[2]-a[0],h=a[3]-a[1];
    r[2]=Math.round(Math.max(0,Math.min(p.width-w,a[0]+dx)));
    r[3]=Math.round(Math.max(0,Math.min(p.height-h,a[1]+dy)));
    r[4]=r[2]+w;r[5]=r[3]+h;
  }else{
    r[4]=Math.round(Math.max(a[0]+8,Math.min(p.width,a[2]+dx)));
    r[5]=Math.round(Math.max(a[1]+8,Math.min(p.height,a[3]+dy)));
  }
  draw();
});
canvas.addEventListener('pointerup',e=>{
  if(!drag)return;
  if(drag.type==='create'){
    const p=pageInfo(),[x,y]=coords(e),sx=p.width/canvas.width,sy=p.height/canvas.height;
    const a=[Math.round(Math.min(x,drag.x)*sx),Math.round(Math.min(y,drag.y)*sy),
             Math.round(Math.max(x,drag.x)*sx),Math.round(Math.max(y,drag.y)*sy)];
    if(a[2]-a[0]>=8&&a[3]-a[1]>=8 && state.rows.length<50){
      state.rows.push([page,kindSelect.value,...a,true,null]);selected=state.rows.length-1;
    }
  }
  drag=null;mode='select';updateSelected();publish();
});
element.querySelector('#hj-add').addEventListener('click',()=>{mode='create';selected=-1;help.textContent='Dibuja una región nueva sobre la página.';});
element.querySelector('#hj-delete').addEventListener('click',()=>{if(selected>=0){state.rows.splice(selected,1);selected=-1;publish();updateSelected();}});
kindSelect.addEventListener('change',()=>{if(selected>=0){state.rows[selected][1]=kindSelect.value;publish();draw();}});
include.addEventListener('change',()=>{if(selected>=0){state.rows[selected][6]=include.checked;publish();}});
pageSelect.addEventListener('change',()=>setPage(Number(pageSelect.value)));
function load(){
  try{
    const next=JSON.parse(props.value||'{}');
    if(!Array.isArray(next.pages)||!Array.isArray(next.rows))return;
    state=next;pageSelect.replaceChildren();
    next.pages.forEach(p=>{const o=document.createElement('option');o.value=String(p.number);o.textContent=String(p.number);pageSelect.append(o);});
    setPage(next.pages[0]?.number||1);
  }catch(_){}
}
watch('value',load);
load();
"""
