#!/usr/bin/env python3
"""Generate a standalone particle Christmas tree that opens offline in Safari.

Run: python3 generate_tree.py
Custom path: python3 generate_tree.py --output /path/to/christmas_tree.html
Local camera launcher: python3 generate_tree.py --serve
"""

import argparse
import json
import math
import random
import re
import functools
import http.server
import webbrowser
from pathlib import Path


def make_particles(seed=1225):
    """Generate 3D branches, a spiral, a star, and a base; embed all coordinates in HTML."""
    rng = random.Random(seed)
    points = []
    tau = math.tau

    def add(x, y, z, kind=0, size=None, color=None):
        if color is None:
            color = rng.choices([0, 1, 2, 3], [44, 23, 24, 9])[0]
        points.append([
            round(x, 4), round(y, 4), round(z, 4),
            round(size if size is not None else rng.uniform(0.45, 1.0), 3),
            color, kind, round(rng.random() * tau, 3),
        ])

    # Layer radial branches with drooping strands and upward-curled tips.
    for layer in range(10):
        t = (layer + 1) / 10
        radius = 1.13 * t ** 0.90
        y_tip = -1.35 + 2.55 * t
        branches = 12 + layer * 3
        offset = rng.random() * tau
        for branch in range(branches):
            angle = offset + branch / branches * tau + rng.uniform(-0.025, 0.025)
            branch_radius = radius * rng.uniform(0.88, 1.06)
            for strand in range(2):
                for step in range(17):
                    u = (step + rng.uniform(-0.15, 0.15)) / 16
                    u = min(1, max(0, u))
                    r = branch_radius * (0.10 + 0.90 * u)
                    a = angle + (strand - 0.5) * 0.042 + 0.045 * math.sin(u * 5 + angle)
                    y = y_tip - (0.22 + t * 0.16) * (1 - u) ** 1.9
                    y -= 0.085 * t * u ** 10
                    y += strand * 0.023 + rng.gauss(0, 0.009)
                    add(math.cos(a) * r, y, math.sin(a) * r)
            # Small twigs give the outer edges a feathered outline.
            for twig in range(2):
                root_u = 0.52 + twig * 0.19
                for j in range(5):
                    v = j / 4
                    r = branch_radius * (root_u + v * 0.19)
                    a = angle + (1 if twig else -1) * v * 0.10
                    y = y_tip - (0.22 + t * 0.16) * (1 - root_u) ** 1.9 + v * 0.025
                    add(math.cos(a) * r, y, math.sin(a) * r, size=rng.uniform(0.42, 0.78))

    # Sparse interior dust adds depth while keeping the tree airy.
    for _ in range(1200):
        t = rng.random() ** 0.55
        r = 1.02 * t ** 0.90 * math.sqrt(rng.random())
        a = rng.random() * tau
        add(r * math.cos(a), -1.35 + 2.55 * t + rng.gauss(0, 0.02),
            r * math.sin(a), kind=1, size=rng.uniform(0.35, 0.8))

    # A champagne-gold ribbon spirals around the tree about four and a half times.
    for i in range(1350):
        t = i / 1349
        a = -t * tau * 4.35 + 0.8
        r = 0.04 + 1.22 * t ** 0.91
        r += rng.gauss(0, 0.005)
        add(r * math.cos(a), -1.37 + 2.56 * t + rng.gauss(0, 0.006),
            r * math.sin(a), kind=2, size=rng.uniform(0.65, 1.1),
            color=rng.choices([0, 1, 2], [56, 40, 4])[0])

    # Outline a five-point star with particles and add a little dust inside it.
    vertices = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 0.13 if i % 2 == 0 else 0.057
        vertices.append((math.cos(a) * r, math.sin(a) * r))
    for edge in range(10):
        ax, ay = vertices[edge]
        bx, by = vertices[(edge + 1) % 10]
        for j in range(17):
            f = j / 17
            add(ax + (bx - ax) * f, -1.56 + ay + (by - ay) * f,
                0, kind=3, size=rng.uniform(0.5, 0.85), color=1)
    for _ in range(100):
        a = rng.random() * tau
        r = rng.random() ** 0.7 * 0.06
        add(math.cos(a) * r, -1.56 + math.sin(a) * r, 0,
            kind=3, size=rng.uniform(0.4, 0.8), color=0)

    # Create a floating base of concentric dust rings.
    for i in range(1200):
        a = rng.random() * tau
        if i < 800:
            r = rng.choice([0.45, 0.72, 0.96, 1.17, 1.34]) + rng.gauss(0, 0.009)
        else:
            r = 1.38 * math.sqrt(rng.random())
        add(r * math.cos(a), 1.37 + rng.gauss(0, 0.012), r * math.sin(a),
            kind=4, size=rng.uniform(0.32, 0.72),
            color=rng.choices([0, 1, 2], [60, 20, 20])[0])
    return points


GESTURE_WORKER = r'''/* MediaPipe runs in this worker so hand inference does not block particle rendering. */
let detector=null;
const assetURLs=[];
function decode64(text) {
  const raw=atob(text),out=new Uint8Array(raw.length);
  for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);
  return out;
}
function blobURL(content,type) {
  const url=URL.createObjectURL(new Blob([content],{type}));assetURLs.push(url);return url;
}
self.onmessage=async event=>{
  const data=event.data;
  if(data.type==='init') {
    try {
      const pack=data.assets;
      importScripts(blobURL(pack.runtime,'text/javascript'));
      const files={wasmLoaderPath:blobURL(pack.loader,'text/javascript'),
        wasmBinaryPath:blobURL(decode64(pack.wasm),'application/wasm')};
      detector=await self.Vision.HandLandmarker.createFromOptions(files,{
        baseOptions:{modelAssetBuffer:decode64(pack.model),delegate:'CPU'},
        runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.55,
        minHandPresenceConfidence:.55,minTrackingConfidence:.50
      });
      self.postMessage({type:'ready'});
    } catch(error) {self.postMessage({type:'error',message:String(error.message||error)});}
  } else if(data.type==='frame') {
    try {
      if(!detector)throw Error('Hand detector is not ready.');
      const result=detector.detectForVideo(data.frame,data.timestamp);
      self.postMessage({type:'result',hands:result.landmarks,
        worldHands:result.worldLandmarks||[],timestamp:data.timestamp});
    } catch(error) {self.postMessage({type:'error',message:String(error.message||error)});}
    finally {data.frame.close();}
  }
};

'''

CAMERA_CODE = r'''// Camera access starts only after the camera button is pressed.
const cameraButton=document.getElementById('camera');
const cameraPanel=document.getElementById('cameraPanel');
const cameraStatus=document.getElementById('cameraStatus');
const cameraVideo=document.getElementById('cameraVideo');
const handOverlay=document.getElementById('handOverlay');
const camera={active:false,starting:false,session:0,stream:null,worker:null,url:null,
  detector:null,mode:null,stage:'permission',raf:0,busy:false,lastFrame:-Infinity,lastVideoTime:-1,rejectInit:null};
let mainLoadQueue=Promise.resolve();
const gestureGate={candidate:null,since:0,samples:0,accepted:null,lastChange:-Infinity,lastSeen:0,history:[]};
const shapeLabels={tree:'Christmas tree',text:'Merry Christmas',nebula:'Nebula'};
function resetGestureGate() {
  gestureGate.candidate=null;gestureGate.since=0;gestureGate.samples=0;
  gestureGate.accepted=null;gestureGate.lastChange=-Infinity;gestureGate.lastSeen=0;gestureGate.history=[];
}
function handDistance(a,b) {return Math.hypot(a.x-b.x,a.y-b.y,(a.z||0)-(b.z||0));}
function jointAngle(a,b,c) {
  const ux=a.x-b.x,uy=a.y-b.y,uz=(a.z||0)-(b.z||0);
  const vx=c.x-b.x,vy=c.y-b.y,vz=(c.z||0)-(b.z||0);
  return Math.acos(clamp((ux*vx+uy*vy+uz*vz)/(Math.hypot(ux,uy,uz)*Math.hypot(vx,vy,vz)||1),-1,1));
}
function classifyHand(landmarks,previous=null) {
  if(!landmarks||landmarks.length!==21||landmarks.some(p=>![p.x,p.y,p.z||0].every(Number.isFinite)))return null;
  const palm=(handDistance(landmarks[0],landmarks[9])+handDistance(landmarks[5],landmarks[17]))/2;
  if(palm<1e-5)return null;
  let extended=0,folded=0;
  for(const base of [5,9,13,17]) {
    const mcp=landmarks[base],pip=landmarks[base+1],tip=landmarks[base+3];
    const angle=jointAngle(mcp,pip,tip);
    if(angle>2.28&&handDistance(tip,landmarks[0])>handDistance(pip,landmarks[0])*1.035&&handDistance(tip,mcp)>palm*.55)extended++;
    if(angle<1.95||handDistance(tip,mcp)<palm*.53)folded++;
  }
  // A pinch can keep the other three fingers curled. Require the index tip
  // to remain outside the palm so contact inside a closed fist is ignored.
  const pinch=handDistance(landmarks[4],landmarks[8])/palm;
  const indexOutsidePalm=handDistance(landmarks[8],landmarks[0])>handDistance(landmarks[5],landmarks[0])*1.10;
  if(pinch<(previous==='text'?.48:.38)&&indexOutsidePalm)return 'text';
  if(extended<=1&&folded>=3)return 'tree';
  const thumbSpread=handDistance(landmarks[4],landmarks[5])/palm;
  if(extended>=3&&folded<=1&&(extended===4||thumbSpread>.58))return 'nebula';
  return null;
}
function consumeGesture(shape,timestamp) {
  gestureGate.history=gestureGate.history.filter(v=>timestamp-v.time<=900);
  if(!shape) {
    // A brief uncertain frame should not restart a deliberate gesture.
    if(timestamp-gestureGate.lastSeen>240){gestureGate.candidate=null;gestureGate.samples=0;gestureGate.history=[];}
    if(timestamp-gestureGate.lastSeen>800)gestureGate.accepted=null;
    return false;
  }
  gestureGate.lastSeen=timestamp;
  gestureGate.history.push({shape,time:timestamp});
  if(gestureGate.history.length>5)gestureGate.history.shift();
  const counts={tree:0,text:0,nebula:0};
  for(const vote of gestureGate.history)counts[vote.shape]++;
  let leader=gestureGate.accepted||gestureGate.history[0].shape;
  for(const target of ['tree','text','nebula'])if(counts[target]>counts[leader])leader=target;
  const support=gestureGate.history.filter(v=>v.shape===leader);
  gestureGate.candidate=leader;gestureGate.samples=support.length;gestureGate.since=support[0].time;
  if(shape!==leader||leader===gestureGate.accepted||timestamp-gestureGate.since<220||support.length<3||support.length/gestureGate.history.length<.72||timestamp-gestureGate.lastChange<420)return false;
  gestureGate.accepted=leader;gestureGate.lastChange=timestamp;
  requestShape(leader);
  return true;
}
function drawHand(landmarks) {
  const g=handOverlay.getContext('2d');
  g.clearRect(0,0,handOverlay.width,handOverlay.height);
  if(!landmarks)return;
  const chains=[[0,1,2,3,4],[0,5,6,7,8],[5,9,10,11,12],[9,13,14,15,16],[13,17,18,19,20],[0,17]];
  g.strokeStyle='rgba(237,207,161,.75)';g.lineWidth=1.5;
  for(const chain of chains) {
    g.beginPath();chain.forEach((index,i)=>{
      const p=landmarks[index];g[i?'lineTo':'moveTo'](p.x*handOverlay.width,p.y*handOverlay.height);
    });g.stroke();
  }
  g.fillStyle='#f4dec0';
  for(const p of landmarks){g.beginPath();g.arc(p.x*handOverlay.width,p.y*handOverlay.height,2.3,0,TAU);g.fill();}
}
function stopCamera(keepPanel=false) {
  camera.session++;camera.active=false;camera.starting=false;camera.busy=false;
  if(camera.raf)cancelAnimationFrame(camera.raf);camera.raf=0;
  if(camera.rejectInit){camera.rejectInit(Error('Camera stopped.'));camera.rejectInit=null;}
  if(camera.worker)camera.worker.terminate();camera.worker=null;
  if(camera.detector){try{camera.detector.close();}catch(error){console.warn(error);}}camera.detector=null;camera.mode=null;
  if(camera.url)URL.revokeObjectURL(camera.url);camera.url=null;
  if(camera.stream)camera.stream.getTracks().forEach(track=>track.stop());camera.stream=null;
  cameraVideo.pause();cameraVideo.srcObject=null;
  cameraButton.setAttribute('aria-pressed','false');cameraButton.setAttribute('aria-label','Enable camera gestures');
  cameraPanel.hidden=!keepPanel;
  if(!keepPanel)cameraStatus.textContent='Camera is off.';
  resetGestureGate();drawHand(null);
}
function cameraFailure(error) {
  const stage=camera.stage;
  const detail=((error.name||'Error')+': '+(error.message||'Unknown error')).slice(0,220);
  stopCamera(true);
  if(error.name==='NotAllowedError'||error.name==='SecurityError') {
    cameraStatus.textContent='Camera access was not allowed. Enable camera access for this page in Safari. If opened as a file, try the included local launcher.';
  } else if(error.name==='NotFoundError') {
    cameraStatus.textContent='No camera was found. Connect a camera and try again.';
  } else if(error.name==='NotReadableError') {
    cameraStatus.textContent='The camera could not be opened. Close other apps using it and try again. '+detail;
  } else if(stage==='model') {
    cameraStatus.textContent='The hand model could not load. '+detail+' Try the local launcher if this file is restricted by Safari.';
  } else if(stage==='frames') {
    cameraStatus.textContent='Hand tracking stopped. '+detail+' Press the camera button to retry.';
  } else {
    cameraStatus.textContent='Camera startup failed. '+detail+' Try the included local launcher.';
  }
  console.error('Hand tracking:',error);
}
function readHandAssets() {
  const assets=JSON.parse(document.getElementById('handAssets').textContent);
  if(!assets.runtime||!assets.loader||!assets.wasm||!assets.model)throw Error('The offline hand model is missing.');
  return assets;
}
function decodeHandAsset(text) {
  const raw=atob(text),bytes=new Uint8Array(raw.length);
  for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
  return bytes;
}
function loadHandScript(source) {
  return new Promise((resolve,reject)=>{
    const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
    const script=document.createElement('script');
    const finish=()=>{clearTimeout(timer);URL.revokeObjectURL(url);script.remove?.();};
    const timer=setTimeout(()=>{finish();reject(Error('Bundled hand runtime timed out.'));},15000);
    script.onload=()=>{finish();resolve();};
    script.onerror=()=>{finish();reject(Error('Bundled hand runtime could not load.'));};
    script.src=url;document.head.appendChild(script);
  });
}
function loadMainDetector(assets,session) {
  // Safari file pages can fail to fetch Blob WASM inside a worker. An explicit
  // HTMLCanvasElement keeps this path independent of worker OffscreenCanvas.
  const task=mainLoadQueue.then(async()=>{
    if(session!==camera.session)throw Error('Camera startup was cancelled.');
    if(!window.Vision?.HandLandmarker)await loadHandScript(assets.runtime);
    if(session!==camera.session)throw Error('Camera startup was cancelled.');
    const loader=URL.createObjectURL(new Blob([assets.loader],{type:'text/javascript'}));
    const wasm=URL.createObjectURL(new Blob([decodeHandAsset(assets.wasm)],{type:'application/wasm'}));
    let detector;
    try {
      const inferenceCanvas=document.createElement('canvas');inferenceCanvas.width=inferenceCanvas.height=1;
      detector=await window.Vision.HandLandmarker.createFromOptions({wasmLoaderPath:loader,wasmBinaryPath:wasm},{
        canvas:inferenceCanvas,baseOptions:{modelAssetBuffer:decodeHandAsset(assets.model),delegate:'CPU'},
        runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.55,minHandPresenceConfidence:.55,minTrackingConfidence:.50
      });
      if(session!==camera.session){detector.close();throw Error('Camera startup was cancelled.');}
      return detector;
    } finally {URL.revokeObjectURL(loader);URL.revokeObjectURL(wasm);}
  });
  mainLoadQueue=task.then(()=>{},()=>{});
  return task;
}
function selectTrackedHand(result) {
  const hands=result.hands||(result.landmarks?[result.landmarks]:[]);
  const worlds=result.worldHands||(result.world?[result.world]:[]);
  const aspect=handOverlay.width/handOverlay.height||4/3;
  let selected=null;
  for(let i=0;i<hands.length;i++) {
    const landmarks=hands[i];
    if(!landmarks||landmarks.length!==21||landmarks.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y)))continue;
    const image=landmarks.map(p=>({x:p.x*aspect,y:p.y,z:(p.z||0)*aspect}));
    const gesture=classifyHand(worlds[i],gestureGate.accepted)||classifyHand(image,gestureGate.accepted);
    const palm=(Math.hypot(image[0].x-image[9].x,image[0].y-image[9].y)+Math.hypot(image[5].x-image[17].x,image[5].y-image[17].y))/2;
    // Prefer the closer, clearly posed hand without using left/right labels.
    const score=palm*(gesture?1.15:.65)*(1-.12*Math.abs(landmarks[0].x-.5));
    if(!selected||score>selected.score)selected={landmarks,gesture,score};
  }
  return selected;
}
function processHandResult(result) {
  const selected=selectTrackedHand(result);
  drawHand(selected?.landmarks||null);
  const gesture=selected?.gesture||null;
  consumeGesture(gesture,result.timestamp);
  const label=gesture?{tree:'Fist',text:'Pinch',nebula:'Open palm'}[gesture]:'Show one hand';
  const target=gestureGate.accepted?shapeLabels[gestureGate.accepted]:'Waiting for a gesture';
  const text=label+' / '+target;
  if(cameraStatus.textContent!==text)cameraStatus.textContent=text;
}
async function startCamera() {
  const session=++camera.session;
  camera.starting=true;camera.stage='permission';cameraPanel.hidden=false;
  cameraButton.setAttribute('aria-pressed','true');cameraButton.setAttribute('aria-label','Turn off camera gestures');
  cameraStatus.textContent='Allow camera access to enable gestures.';
  try {
    if(!navigator.mediaDevices?.getUserMedia)throw Error('Camera access needs a secure local page.');
    const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user',width:{ideal:640},height:{ideal:480},frameRate:{ideal:24,max:30}}});
    if(session!==camera.session){stream.getTracks().forEach(track=>track.stop());return;}
    camera.stream=stream;camera.stage='video';cameraVideo.muted=true;cameraVideo.playsInline=true;cameraVideo.srcObject=stream;
    await cameraVideo.play();
    if(session!==camera.session)return;
    handOverlay.width=cameraVideo.videoWidth||640;handOverlay.height=cameraVideo.videoHeight||480;
    camera.stage='model';cameraStatus.textContent='Loading the offline hand model...';
    const assets=readHandAssets();let switching=null;
    const useMain=()=>{
      if(switching)return switching;
      switching=(async()=>{
        camera.mode='loading';camera.busy=false;camera.stage='model';
        if(camera.worker)camera.worker.terminate();camera.worker=null;
        if(camera.url)URL.revokeObjectURL(camera.url);camera.url=null;
        cameraStatus.textContent='Preparing compatible hand tracking...';
        const detector=await loadMainDetector(assets,session);
        if(session!==camera.session){detector.close();return;}
        camera.detector=detector;camera.mode='main';if(camera.active)camera.stage='frames';
      })().finally(()=>{switching=null;});
      return switching;
    };
    const safari=/Safari/.test(navigator.userAgent||'')&&!/Chrome|Chromium|CriOS|Edg/.test(navigator.userAgent||'');
    const canUseWorker=typeof Worker!=='undefined'&&typeof createImageBitmap!=='undefined'&&typeof OffscreenCanvas!=='undefined';
    if(safari||!canUseWorker)await useMain();
    else {
      try {
        camera.url=URL.createObjectURL(new Blob([document.getElementById('gestureWorker').textContent],{type:'text/javascript'}));
        const worker=new Worker(camera.url);camera.worker=worker;
        await new Promise((resolve,reject)=>{
          const timeout=setTimeout(()=>{camera.rejectInit=null;reject(Error('Hand worker initialization timed out.'));},20000);
          const finish=()=>{clearTimeout(timeout);camera.rejectInit=null;};
          camera.rejectInit=error=>{finish();reject(error);};
          const failure=error=>{finish();if(camera.active)useMain().catch(e=>{if(session===camera.session)cameraFailure(e);});else reject(error);};
          worker.onerror=event=>failure(Error(event.message||'Hand worker failed.'));
          worker.onmessage=event=>{
            if(session!==camera.session||camera.worker!==worker)return;
            const result=event.data;
            if(result.type==='ready'){finish();camera.mode='worker';resolve();return;}
            if(result.type==='error'){failure(Error(result.message));return;}
            if(result.type==='result'){camera.busy=false;processHandResult(result);}
          };
          worker.postMessage({type:'init',assets});
        });
      } catch(error) {if(session!==camera.session)return;await useMain();}
    }
    if(session!==camera.session)return;
    camera.starting=false;camera.active=true;camera.stage='frames';camera.lastFrame=-Infinity;camera.lastVideoTime=-1;
    cameraStatus.textContent='Show one hand and hold a gesture briefly.';
    for(const track of stream.getVideoTracks())track.addEventListener('ended',()=>{
      if(session===camera.session)cameraFailure(Error('Camera stream ended.'));
    });
    const capture=document.createElement('canvas');capture.width=480;
    capture.height=Math.round(480*(cameraVideo.videoHeight||480)/(cameraVideo.videoWidth||640));
    const input=capture.getContext('2d',{alpha:false});
    const loop=async timestamp=>{
      if(!camera.active||session!==camera.session)return;
      camera.raf=requestAnimationFrame(loop);
      if(document.hidden||camera.busy||!['main','worker'].includes(camera.mode)||timestamp-camera.lastFrame<(camera.mode==='main'?90:70)||cameraVideo.readyState<2||cameraVideo.currentTime===camera.lastVideoTime)return;
      camera.busy=true;camera.lastFrame=timestamp;camera.lastVideoTime=cameraVideo.currentTime;
      try {
        input.drawImage(cameraVideo,0,0,capture.width,capture.height);
        if(camera.mode==='main') {
          const result=camera.detector.detectForVideo(capture,timestamp);
          processHandResult({hands:result.landmarks,worldHands:result.worldLandmarks||[],timestamp});
          camera.busy=false;
        } else {
          const bitmap=await createImageBitmap(capture);
          if(session!==camera.session||!camera.worker){bitmap.close();camera.busy=false;return;}
          camera.worker.postMessage({type:'frame',frame:bitmap,timestamp},[bitmap]);
        }
      } catch(error) {if(session===camera.session)cameraFailure(error);}
    };
    camera.raf=requestAnimationFrame(loop);
  } catch(error) {if(session===camera.session)cameraFailure(error);}
}
cameraButton.addEventListener('click',()=>{
  if(camera.active||camera.starting)stopCamera();else startCamera();
});
window.addEventListener('pagehide',()=>stopCamera());
Object.defineProperty(window,'treeControls',{value:Object.freeze({setShape:requestShape,classifyHand,consumeGesture,resetGestureGate,selectTrackedHand,
  get positions(){return new Float32Array(currentPositions);},get cameraActive(){return camera.active;}})});


'''

HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<meta name="description" content="A 3D particle Christmas tree in champagne gold and soft blush pink. Click to form a cursive Merry Christmas message, then click again to restore the tree.">
<title>Stardust Christmas Tree - Champagne Wishes</title>
<style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}
body{background:#0d0c0b;color:#e5d6bf;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
canvas{display:block;width:100%;height:100%;touch-action:none;cursor:grab;outline:none;user-select:none;-webkit-user-select:none}
canvas:focus-visible{outline:1px solid #d2b897;outline-offset:-5px}
.tools{position:fixed;right:24px;top:max(20px,env(safe-area-inset-top));display:flex;gap:8px}
button{border:1px solid #e7c9a623;background:#17131080;color:#c9b59c;border-radius:50%;width:38px;height:38px;display:grid;place-items:center;cursor:pointer;transition:background .2s,color .2s;-webkit-tap-highlight-color:transparent}
button:hover{background:#e7c9a61b;color:#fff0d7}button:focus-visible{outline:2px solid #e5c09a;outline-offset:3px}
button svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}
button[aria-pressed="true"]{border-color:#e8c69599;background:#b58e6038;color:#fff0d7}
.camera-panel{position:fixed;right:24px;bottom:24px;width:248px;padding:12px;background:#15110fe8;border:1px solid #e7c9a633;border-radius:14px;color:#d9c5ac;box-shadow:0 12px 40px #0006}
.camera-panel[hidden]{display:none}.camera-view{position:relative;aspect-ratio:4/3;overflow:hidden;border-radius:8px;background:#080909}
.camera-view video,.camera-view canvas{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;transform:scaleX(-1);cursor:default;pointer-events:none}
.screen-reader-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:600px){.tools{right:15px;top:16px}}
</style>
</head>
<body>
<canvas id="scene" tabindex="0" role="button" aria-label="Particle Christmas tree. Hold the left mouse button and drag to rotate. Click or press Space to switch between the tree and a cursive Merry Christmas message."></canvas>
<div class="tools">
<button id="camera" aria-label="Enable camera gestures" aria-pressed="false"><svg viewBox="0 0 20 20"><rect x="2" y="5" width="10" height="10" rx="2"/><path d="M12 8l6-3v10l-6-3"/></svg></button>
<button id="nebula" aria-label="Show the nebula"><svg viewBox="0 0 20 20"><ellipse cx="10" cy="10" rx="8" ry="3.5" transform="rotate(-25 10 10)"/><path d="M6 6c-4 6 7 12 9 6M9 9h2v2H9z"/></svg></button>
<button id="replay" aria-label="Replay the particle gathering animation"><svg viewBox="0 0 20 20"><path d="M4 7a6.5 6.5 0 1 1-.5 5M4 3v4h4"/></svg></button>
<button id="pause" aria-label="Pause animation"><svg id="pauseIcon" viewBox="0 0 20 20"><path d="M7 5v10M13 5v10"/></svg></button>
</div>
<section id="cameraPanel" class="camera-panel" hidden aria-label="Camera gesture controls">
<div class="camera-view"><video id="cameraVideo" autoplay muted playsinline></video><canvas id="handOverlay" aria-hidden="true"></canvas></div>
<p id="cameraStatus" class="screen-reader-only" role="status" aria-live="polite">Camera is off.</p>
</section>
<script id="handAssets" type="application/json">__HAND_ASSETS__</script>
<script id="gestureWorker" type="text/plain">__GESTURE_WORKER__</script>
<script>
"use strict";
(() => {
const DATA = __PARTICLES__;
const canvas = document.getElementById('scene');
const ctx = canvas.getContext('2d', {alpha:false});
if (!ctx) return;
const TAU = Math.PI * 2;
const MESSAGE = 'Merry Christmas';
const colors = [[237,207,161],[255,235,203],[225,175,178],[205,153,165]];
let seed = 1225;
function random() { seed = (Math.imul(1664525, seed) + 1013904223) >>> 0; return seed / 4294967296; }
const points = DATA.map(p => {
  const a = random() * TAU, v = random() * 2 - 1;
  const r = 1.9 + random() * 2.7, ring = Math.sqrt(1 - v * v);
  return {x:p[0],y:p[1],z:p[2],s:p[3],c:p[4],k:p[5],phase:p[6],
    sx:Math.cos(a)*ring*r, sy:v*r*.78, sz:Math.sin(a)*ring*r,
    delay:random()*.7, drift:random()*.8+.3};
});
const snow = Array.from({length:155}, () => ({x:random(),y:random(),r:random(),v:.005+random()*.012,phase:random()*TAU}));
const stars = Array.from({length:115}, () => ({x:random(),y:random(),r:.3+random()*.7,phase:random()*TAU}));
const sprites = colors.map(c => {
  const sprite = document.createElement('canvas'); sprite.width=sprite.height=48;
  const g=sprite.getContext('2d');
  const glow=g.createRadialGradient(24,24,0,24,24,24);
  const rgb=c.join(',');
  glow.addColorStop(0,`rgba(${rgb},1)`);
  glow.addColorStop(.065,`rgba(${rgb},.95)`);
  glow.addColorStop(.13,`rgba(${rgb},.40)`);
  glow.addColorStop(.30,`rgba(${rgb},.10)`);
  glow.addColorStop(.65,`rgba(${rgb},.025)`);
  glow.addColorStop(1,`rgba(${rgb},0)`);
  g.fillStyle=glow;g.fillRect(0,0,48,48);return sprite;
});
let w=0,h=0,dpr=1,scale=1,cx=0,cy=0,background;
let clock=0,lastTime=null,rotation=0,paused=false,hidden=document.hidden;
let state='intro',stateStart=0,burstId=0,renderedFrames=0;
let pitch=0,drag=null,suppressClick=false;
let textTargets=[],textBounds=null;
const currentPositions=new Float32Array(points.length*6);
let bridgeFrom=null,bridgeTarget='tree',bridgeDuration=1.8,bridgeText=0,bridgeNebula=0;
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let introDuration=reduced ? 1.0 : 4.5;
const morphDuration=reduced?.45:1.35,returnDuration=reduced?.45:3;
// Emit sparse dust only while the message is shown, using a separate sequence.
const textRadiance=Array.from({length:64},(_,id)=>({
  id,delay:id/64*2.6,life:2.4+(id*37%19)/19*1.2,
  angle:((id*.61803398875)%1)*TAU
}));
// Sample text on an offscreen canvas; the original particles draw every stroke.
function makeTextTargets() {
  const mask=document.createElement('canvas');
  const lines=w<640?MESSAGE.split(' '):[MESSAGE];
  mask.width=1600;mask.height=lines.length===1?420:800;
  const g=mask.getContext('2d',{willReadFrequently:true});
  let fontSize=210;
  const font=size=>`${size}px "Snell Roundhand", "Apple Chancery", "Brush Script MT", cursive`;
  g.font=font(fontSize);
  const widest=Math.max(...lines.map(line=>g.measureText(line).width));
  fontSize*=Math.min(1,(mask.width-160)/widest);
  g.font=font(fontSize);g.textAlign='center';g.textBaseline='alphabetic';
  g.fillStyle='#fff';g.strokeStyle='#fff';g.lineWidth=.65;
  const rowHeight=mask.height/lines.length;
  lines.forEach((line,i)=>{
    const metrics=g.measureText(line);
    const ascent=metrics.actualBoundingBoxAscent||fontSize*.9;
    const descent=metrics.actualBoundingBoxDescent||fontSize*.3;
    const baseline=rowHeight*(i+.5)+(ascent-descent)/2;
    g.fillText(line,mask.width/2,baseline);
    g.strokeText(line,mask.width/2,baseline);
  });
  const pixels=g.getImageData(0,0,mask.width,mask.height).data;
  const samples=[];
  let left=mask.width,right=0,top=mask.height,bottom=0;
  for(let y=0;y<mask.height;y+=2)for(let x=0;x<mask.width;x+=2) {
    if(pixels[(y*mask.width+x)*4+3]<96)continue;
    samples.push([x,y]);
    left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);
  }
  if(!samples.length)return;
  // Seed the shuffle for stable layouts and an even distribution across strokes.
  let localSeed=1225;
  const rnd=()=>{localSeed=(Math.imul(localSeed,1664525)+1013904223)>>>0;return localSeed/4294967296;};
  for(let i=samples.length-1;i>0;i--){const j=Math.floor(rnd()*(i+1));[samples[i],samples[j]]=[samples[j],samples[i]];}
  const fit=Math.min(w*.84/Math.max(1,right-left),h*.42/Math.max(1,bottom-top));
  const midX=(left+right)/2,midY=(top+bottom)/2;
  textTargets=points.map((p,i)=>{
    const sample=samples[i%samples.length];
    // Float a few particles around the strokes while keeping the lettering clear.
    const halo=i%6===0;
    const distance=halo?3+rnd()*9:0;
    return [w/2+(sample[0]-midX+(rnd()-.5)*.6)*fit+Math.cos(p.phase)*distance,
      h*.50+(sample[1]-midY+(rnd()-.5)*.6)*fit+Math.sin(p.phase)*distance,halo];
  });
  textBounds={left:w/2+(left-midX-.3)*fit-15,right:w/2+(right-midX+.3)*fit+15,
    top:h*.5+(top-midY-.3)*fit-15,bottom:h*.5+(bottom-midY+.3)*fit+15};
}
function resize() {
  const oldW=w,oldH=h;
  w=window.innerWidth;h=window.innerHeight;
  if(bridgeFrom&&oldW&&oldH)for(let i=0;i<points.length;i++){bridgeFrom[i*6]*=w/oldW;bridgeFrom[i*6+1]*=h/oldH;}
  dpr=Math.min(window.devicePixelRatio||1,2);
  canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  scale=Math.min(w*.315,h*.255);cx=w*.5;cy=h*.485;
  background=ctx.createRadialGradient(cx,h*.5,0,cx,h*.5,Math.max(w,h)*.7);
  background.addColorStop(0,'#18130f');background.addColorStop(.42,'#100e0c');background.addColorStop(1,'#080909');
  makeTextTargets();
  if (paused) render();
}
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v,0,1);return v*v*(3-2*v);};
function amount(p) {
  const t=clock-stateStart;
  if(state==='intro') {
    const u=clamp((t-p.delay)/(introDuration-p.delay),0,1);
    return Math.pow(1-u,3);
  }
  if(state==='morphing'&&!reduced) {
    const delay=p.delay*.06;
    const u=clamp((t-delay)/(morphDuration-delay),0,1);
    // Apply a brief random pulse while forming the text, without a waiting stage.
    const kick=u/.15;
    return .30*kick*Math.exp(1-kick)*smooth((1-u)/.2);
  }
  // Preserve the gentle three-second return, with dust curving back into the tree.
  if(state==='returning')return 1-smooth(t/returnDuration);
  return 0;
}
// Start with momentum toward the targets, followed by a slight overshoot and settle.
function flight(p,duration) {
  const delay=p?p.delay*.045:0;
  const u=clamp((clock-stateStart-delay)/(duration-delay),0,1);
  if(reduced)return 1-Math.pow(1-u,3);
  const v=u-1;
  return 1+1.65*v*v*v+.65*v*v;
}
function textTravel(p=null) {
  if(state==='message')return 1;
  if(state==='morphing')return flight(p,morphDuration);
  if(state==='returning')return 1-smooth((clock-stateStart)/returnDuration);
  if(state==='bridge')return bridgeText+((bridgeTarget==='text'?1:0)-bridgeText)*bridgeProgress();
  return 0;
}
function textBlend(p=null) {return clamp(textTravel(p),0,1);}
function setState(next) {state=next;stateStart=clock;}
function bridgeProgress(p=null) {
  const delay=p?p.delay*.10:0;
  return smooth((clock-stateStart-delay)/(bridgeDuration-delay));
}
function nebulaBlend() {
  if(state==='nebula')return 1;
  if(state==='bridge')return bridgeNebula+((bridgeTarget==='nebula'?1:0)-bridgeNebula)*bridgeProgress();
  return 0;
}
function requestedShape() {
  if(state==='bridge')return bridgeTarget;
  if(state==='message'||state==='morphing')return 'text';
  if(state==='nebula')return 'nebula';
  return 'tree';
}
function requestShape(target) {
  if(!['tree','text','nebula'].includes(target)||requestedShape()===target)return;
  if(paused)setPaused(false);
  if(state==='idle'&&target==='text'){setState('morphing');burstId++;return;}
  if(state==='message'&&target==='tree'){setState('returning');return;}
  render();
  bridgeFrom=new Float32Array(currentPositions);
  bridgeText=textBlend();bridgeNebula=nebulaBlend();bridgeTarget=target;
  bridgeDuration=reduced?.5:target==='tree'?3:target==='text'?1.8:1.8;
  setState('bridge');
}
const projected=new Float64Array(4);
function project(x,y,z,cos,sin,cosTilt,sinTilt) {
  const rx=x*cos+z*sin;
  const rz=-x*sin+z*cos;
  const ry=y*cosTilt-rz*sinTilt;
  const depth=y*sinTilt+rz*cosTilt;
  const perspective=7/(7+depth);
  projected[0]=cx+rx*scale*perspective;projected[1]=cy+ry*scale*perspective;
  projected[2]=perspective;projected[3]=depth;return projected;
}
function nebulaPoint(p,q) {
  // Preserve the free-scatter cloud while making its independent motion clearer.
  const drift=reduced?0:.16;
  const x=p.x+p.sx+Math.sin(clock*.65+p.phase)*drift;
  const y=p.y+p.sy+Math.cos(clock*.55+p.phase)*drift;
  const z=p.z+p.sz+Math.sin(clock*.43+p.phase)*drift;
  const c=Math.cos(rotation),s=Math.sin(rotation),ct=Math.cos(-.10+pitch),st=Math.sin(-.10+pitch);
  const rx=x*c+z*s,rz=-x*s+z*c,ry=y*ct-rz*st,depth=y*st+rz*ct;
  const perspective=7/(7+depth);
  q[0]=cx+rx*scale*perspective;q[1]=cy+ry*scale*perspective;
  q[2]=perspective;q[3]=depth;
}
function sparkle(x,y,r,opacity,color=1) {
  ctx.globalAlpha=opacity;ctx.drawImage(sprites[color],x-r*4,y-r*4,r*8,r*8);
  ctx.strokeStyle=`rgba(${colors[color].join(',')},${opacity*.65})`;
  ctx.lineWidth=.6;ctx.beginPath();ctx.moveTo(x-r*2,y);ctx.lineTo(x+r*2,y);
  ctx.moveTo(x,y-r*3);ctx.lineTo(x,y+r*3);ctx.stroke();
}
function drawTextRadiance() {
  if(state!=='message'||reduced||textTargets.length!==points.length)return;
  const elapsed=clock-stateStart,screenScale=clamp(w/1100,.65,1.15);
  for(const emitter of textRadiance) {
    const age=elapsed-emitter.delay;
    if(age<0)continue;
    const cycle=Math.floor(age/emitter.life),u=age/emitter.life-cycle;
    let index=(emitter.id*239+cycle*997+49)%points.length;
    // Emit from the strokes without changing the particles that form the lettering.
    while(textTargets[index][2])index=(index+1)%points.length;
    const target=textTargets[index],p=points[index];
    const angle=emitter.angle+cycle*2.39996323;
    const distance=(32+(emitter.id*17%37)*1.35)*screenScale*(u+.18*u*u);
    const x=target[0]+Math.cos(angle)*distance;
    const y=target[1]+Math.sin(angle)*distance-u*u*3*screenScale;
    const diameter=(7+(emitter.id%4)*1.25)*screenScale*(1-.22*u);
    ctx.globalAlpha=Math.pow(Math.sin(Math.PI*u),1.3)*(.42+emitter.id%3*.065);
    ctx.drawImage(sprites[p.c],x-diameter/2,y-diameter/2,diameter,diameter);
  }
}
function render() {
  renderedFrames++;
  ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;
  ctx.fillStyle=background;ctx.fillRect(0,0,w,h);
  ctx.globalCompositeOperation='lighter';
  for(const s of stars) {
    const a=.18+.16*(.5+.5*Math.sin(clock*.7+s.phase));
    ctx.globalAlpha=a;ctx.drawImage(sprites[0],s.x*w-3,s.y*h-3,6,6);
  }
  for(const s of snow) {
    const x=(s.x+.006*Math.sin(clock*.18+s.phase))*w;
    const y=((s.y+clock*s.v)%1.08-.04)*h;
    const r=2.2+s.r*4.8;
    ctx.globalAlpha=.17+s.r*.22;ctx.drawImage(sprites[s.r>.85?2:1],x-r/2,y-r/2,r,r);
  }
  const angle=rotation, cos=Math.cos(angle),sin=Math.sin(angle);
  const tilt=-.10+pitch;
  const cosTilt=Math.cos(tilt),sinTilt=Math.sin(tilt),particleScale=clamp(scale/210,.68,1.65);
  const stateAge=clock-stateStart;
  // Add a faint ground glow to suggest a subtle reflection beneath the base.
  const floor=project(0,1.37,0,cos,sin,cosTilt,sinTilt);
  const settled=(state==='intro'?smooth(stateAge/introDuration):1)*(1-textBlend())*(1-nebulaBlend());
  ctx.save();ctx.translate(floor[0],floor[1]);ctx.scale(1,.15);
  const halo=ctx.createRadialGradient(0,0,0,0,0,scale*1.5);
  halo.addColorStop(0,`rgba(191,140,100,${.08*settled})`);halo.addColorStop(1,'rgba(191,140,100,0)');
  ctx.fillStyle=halo;ctx.globalAlpha=1;ctx.fillRect(-scale*1.5,-scale*1.5,scale*3,scale*3);ctx.restore();
  for(let i=0;i<points.length;i++) {
    const p=points[i],spread=amount(p),travel=textTargets.length?textTravel(p):0;
    const blend=clamp(travel,0,1);
    // Keep the star facing the viewer while branches and ribbon share a rotation axis.
    let x=p.x, y=p.y, z=p.z;
    if(p.k===3) { x=p.x*cos; z=p.x*sin; }
    const flutter=Math.sin(clock*.65+p.phase)*.003*(p.k===4?.3:1);
    x+=p.sx*spread; y+=p.sy*spread+flutter; z+=p.sz*spread;
    const q=project(x,y,z,cos,sin,cosTilt,sinTilt);
    let textAlpha=1;
    if(travel!==0&&state!=='bridge') {
      const target=textTargets[i];
      const halo=target[2],motion=reduced?0:1;
      const drift=(halo?4.2:1.15)*motion;
      const tx=target[0]+Math.sin(clock*(.48+p.drift*.2)+p.phase)*drift;
      const ty=target[1]+Math.cos(clock*(.38+p.drift*.16)+p.phase)*drift*.72;
      // Form text during the brief scatter; preserve the soft arcs on the return.
      q[0]+=(tx-q[0])*travel;q[1]+=(ty-q[1])*travel;
      if(state==='returning') {
        const arc=Math.sin(Math.PI*blend)*Math.min(w,h)*.065*motion;
        q[0]+=Math.cos(p.phase+blend*3)*arc;
        q[1]+=Math.sin(p.phase+blend*3)*arc*.6;
      }
      q[2]+=(1-q[2])*blend;q[3]*=1-blend;
      const shimmer=.5+.5*Math.sin(clock*(1.3+p.drift)+p.phase);
      textAlpha=halo?.12+.18*shimmer:.32+.43*shimmer;
    }
    const twinkle=.78+.22*Math.sin(clock*(1.1+p.drift)+p.phase);
    const depth=clamp(.78-q[3]*.18,.36,1);
    let alpha=depth*twinkle*(p.k===1?.55:p.k===4?.51:p.k===2?.98:.82);
    alpha=(alpha*(1-spread*.36))*(1-blend)+textAlpha*blend;
    const size=p.s*particleScale*q[2];
    let diameter=size*((p.k===2?12:10)*(1-blend)+7.0*blend);
    if(state==='nebula') {
      nebulaPoint(p,q);alpha=(.35+.35*twinkle)*clamp(.85-q[3]*.22,.4,1);
      diameter=p.s*particleScale*8.5*q[2];
    }
    if(state==='bridge') {
      let targetAlpha=alpha,targetSize=p.s*particleScale*q[2]*(p.k===2?12:10);
      if(bridgeTarget==='text') {
        const t=textTargets[i],drift=reduced?0:t[2]?4.2:1.15;
        q[0]=t[0]+Math.sin(clock*(.48+p.drift*.2)+p.phase)*drift;
        q[1]=t[1]+Math.cos(clock*(.38+p.drift*.16)+p.phase)*drift*.72;
        q[2]=1;q[3]=0;
        const shimmer=.5+.5*Math.sin(clock*(1.3+p.drift)+p.phase);
        targetAlpha=t[2]?.12+.18*shimmer:.32+.43*shimmer;
        targetSize=p.s*particleScale*7;
      } else if(bridgeTarget==='nebula') {
        nebulaPoint(p,q);targetAlpha=(.35+.35*twinkle)*clamp(.85-q[3]*.22,.4,1);
        targetSize=p.s*particleScale*8.5*q[2];
      } else {
        const targetDepth=clamp(.78-q[3]*.18,.36,1);
        targetAlpha=targetDepth*twinkle*(p.k===1?.55:p.k===4?.51:p.k===2?.98:.82);
      }
      const u=bridgeProgress(p),offset=i*6;
      const arc=reduced?0:Math.sin(Math.PI*u)*(1-u)*Math.min(w,h)*.035;
      q[0]=bridgeFrom[offset]+(q[0]-bridgeFrom[offset])*u+Math.cos(p.phase+u*3)*arc;
      q[1]=bridgeFrom[offset+1]+(q[1]-bridgeFrom[offset+1])*u+Math.sin(p.phase+u*3)*arc*.65;
      q[2]=bridgeFrom[offset+2]+(q[2]-bridgeFrom[offset+2])*u;
      q[3]=bridgeFrom[offset+3]+(q[3]-bridgeFrom[offset+3])*u;
      alpha=bridgeFrom[offset+4]+(targetAlpha-bridgeFrom[offset+4])*u;
      diameter=bridgeFrom[offset+5]+(targetSize-bridgeFrom[offset+5])*u;
    }
    const offset=i*6;
    currentPositions[offset]=q[0];currentPositions[offset+1]=q[1];
    currentPositions[offset+2]=q[2];currentPositions[offset+3]=q[3];
    currentPositions[offset+4]=alpha;currentPositions[offset+5]=diameter;
    if(q[0]<-30||q[0]>w+30||q[1]<-30||q[1]>h+30)continue;
    ctx.globalAlpha=alpha;
    ctx.drawImage(sprites[p.c],q[0]-diameter/2,q[1]-diameter/2,diameter,diameter);
    if(state!=='bridge'&&state!=='nebula'&&p.k===2&&i%91===0&&spread<.4&&blend<.75) sparkle(q[0],q[1],size*2.2,alpha*.7*(1-blend));
    if(state!=='bridge'&&state!=='nebula'&&p.k===0&&i%379===0&&spread<.25&&blend<.75) sparkle(q[0],q[1],size*1.8,alpha*.65*(1-blend),p.c);
    if(((state!=='bridge'&&state!=='nebula'&&blend>.7)||state==='nebula')&&i%113===0&&Math.sin(clock*2+p.phase)>.94) {
      sparkle(q[0],q[1],size*1.7,alpha*.55*(state==='nebula'?.65:blend),p.c);
    }
  }
  drawTextRadiance();
  const starScatter=amount(points.find(p=>p.k===3));
  const starVisibility=(1-textBlend())*(1-nebulaBlend())*clamp(1-starScatter/.3,0,1);
  if(starVisibility>0) {
    const top=project(0,-1.56,0,cos,sin,cosTilt,sinTilt);
    const r=scale*.13;
    ctx.globalAlpha=starVisibility*(.60+.12*Math.sin(clock*1.8));
    ctx.drawImage(sprites[0],top[0]-r*2,top[1]-r*2,r*4,r*4);
    sparkle(top[0],top[1],scale*.018,starVisibility*.75);
  }
  ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
}
function frame(timestamp) {
  if(lastTime===null)lastTime=timestamp;
  const dt=Math.min((timestamp-lastTime)/1000,.10);lastTime=timestamp;
  if(!paused&&!hidden) {
    clock+=dt;
    if(!reduced&&!drag&&(state==='intro'||state==='idle'))rotation+=dt*.085;
    if(state==='intro'&&clock-stateStart>=introDuration)setState('idle');
    if(state==='morphing'&&clock-stateStart>=morphDuration)setState('message');
    if(state==='returning'&&clock-stateStart>=returnDuration)setState('idle');
    if(state==='bridge'&&clock-stateStart>=bridgeDuration){const target=bridgeTarget;bridgeFrom=null;setState(target==='tree'?'idle':target==='text'?'message':'nebula');}
    render();
  }
  requestAnimationFrame(frame);
}
function setPaused(value) {
  paused=value;
  const button=document.getElementById('pause');
  button.setAttribute('aria-label',paused?'Resume animation':'Pause animation');
  document.getElementById('pauseIcon').innerHTML=paused?'<path d="M7 4.5l8 5.5-8 5.5z"/>':'<path d="M7 5v10M13 5v10"/>';
}
function burst() {
  if(state==='message')requestShape('tree');
  else if(state==='idle')requestShape('text');
  else if(state==='nebula')requestShape('tree');
}
canvas.addEventListener('click',event=>{
  if(suppressClick){suppressClick=false;event.preventDefault();return;}
  burst();
});
canvas.addEventListener('keydown',event=>{
  const target={Digit1:'tree',Digit2:'text',Digit3:'nebula'}[event.code];
  if(target){event.preventDefault();requestShape(target);return;}
  if(event.code==='Space'||event.code==='Enter'){event.preventDefault();burst();}
});
canvas.addEventListener('pointerdown',event=>{
  if(event.button!==0||event.isPrimary===false||drag)return;
  suppressClick=false;
  drag={id:event.pointerId,x:event.clientX,y:event.clientY,rotation,pitch,moved:false};
  canvas.setPointerCapture(event.pointerId);
  canvas.style.cursor='grabbing';
});
function updateDrag(event) {
  if(!drag||event.pointerId!==drag.id)return;
  const dx=event.clientX-drag.x,dy=event.clientY-drag.y;
  if(Math.hypot(dx,dy)>5)drag.moved=true;
  if(!drag.moved)return;
  rotation=drag.rotation-dx/w*TAU;
  pitch=clamp(drag.pitch+dy/h*2,-.38,.42);
  // Update the view immediately while dragging, including when animation is paused.
  render();
}
function endDrag(event,cancelled=false) {
  if(!drag||event.pointerId!==drag.id)return;
  if(!cancelled)updateDrag(event);
  suppressClick=drag.moved||cancelled;
  const id=drag.id;drag=null;
  canvas.style.cursor='grab';
  if(canvas.hasPointerCapture(id))canvas.releasePointerCapture(id);
}
canvas.addEventListener('pointermove',event=>{
  if(!drag||event.pointerId!==drag.id)return;
  if(event.pointerType==='mouse'&&(event.buttons&1)===0){endDrag(event,true);return;}
  updateDrag(event);
});
canvas.addEventListener('pointerup',event=>endDrag(event));
canvas.addEventListener('pointercancel',event=>endDrag(event,true));
canvas.addEventListener('lostpointercapture',event=>endDrag(event,true));
window.addEventListener('blur',()=>{if(drag)endDrag({pointerId:drag.id},true);});
document.getElementById('pause').addEventListener('click',()=>setPaused(!paused));
document.getElementById('replay').addEventListener('click',()=>{
  bridgeFrom=null;setState('intro');if(paused)setPaused(false);
});
document.getElementById('nebula').addEventListener('click',()=>requestShape('nebula'));
document.addEventListener('visibilitychange',()=>{
  hidden=document.hidden;lastTime=null;
  if(hidden&&drag)endDrag({pointerId:drag.id},true);
});
window.addEventListener('resize',resize);
// Expose read-only animation state; hand-tracking assets are embedded for offline use.
Object.defineProperty(window,'treeState',{get:()=>({state,shape:requestedShape(),time:clock,rotation,pitch,dragging:!!drag,paused,burstCount:burstId,particles:points.length,frames:renderedFrames,message:MESSAGE,textParticles:textTargets.length,textBlend:textBlend(),nebulaBlend:nebulaBlend(),scatter:amount(points[0]),textBounds})});
__CAMERA_CODE__
resize();render();requestAnimationFrame(frame);
})();
</script>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().with_name('christmas_tree.html'))
    parser.add_argument('--hand-assets', type=Path, help='Optional offline MediaPipe asset pack (JSON).')
    parser.add_argument('--serve', action='store_true', help='Serve locally for camera access and open Safari.')
    parser.add_argument('--port', type=int, default=8765, help='Local server port; 0 selects a free port.')
    parser.add_argument('--no-open', action='store_true', help='Start the local server without opening a browser.')
    args = parser.parse_args()
    assets = {}
    if args.hand_assets:
        assets = json.loads(args.hand_assets.read_text(encoding='utf-8'))
    elif args.output.exists():
        old_document = args.output.read_text(encoding='utf-8')
        match = re.search(r'<script id="handAssets" type="application/json">(.*?)</script>', old_document, re.S)
        if match:
            assets = json.loads(match.group(1))
    particles = make_particles()
    document = HTML.replace('__PARTICLES__', json.dumps(particles, separators=(',', ':')))
    document = document.replace('__CAMERA_CODE__', CAMERA_CODE)
    document = document.replace('__GESTURE_WORKER__', GESTURE_WORKER)
    packed_assets = json.dumps(assets, separators=(',', ':'), ensure_ascii=True).replace('<', '\\u003c')
    document = document.replace('__HAND_ASSETS__', packed_assets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding='utf-8')
    print(f'Generated: {args.output.resolve()}')
    print(f'Particles: {len(particles):,}; no dependencies required. Open directly in Safari.')
    if assets:
        print('Offline camera hand tracking is included. Open the camera button to enable it.')
    if args.serve:
        class LocalHandler(http.server.SimpleHTTPRequestHandler):
            def end_headers(self):
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Permissions-Policy', 'camera=(self), microphone=()')
                super().end_headers()

        handler = functools.partial(LocalHandler, directory=str(args.output.resolve().parent))
        try:
            server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), handler)
        except OSError:
            if args.port == 0:
                raise
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        from urllib.parse import quote
        url = f'http://localhost:{server.server_address[1]}/{quote(args.output.name)}'
        print(f'Local camera page: {url}', flush=True)
        print('Keep this window open. Press Ctrl+C to stop.', flush=True)
        if not args.no_open:
            try:
                webbrowser.get('safari').open(url)
            except webbrowser.Error:
                webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('\nLocal camera server stopped.')
        finally:
            server.server_close()


if __name__ == '__main__':
    main()
