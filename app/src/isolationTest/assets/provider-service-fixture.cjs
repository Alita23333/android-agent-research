'use strict';
const fs=require('node:fs'),net=require('node:net'),crypto=require('node:crypto');
const lines=require('node:readline').createInterface({input:process.stdin});
async function network(port){return await new Promise(resolve=>{
  const socket=net.connect({host:'127.0.0.1',port});
  socket.once('connect',()=>{socket.destroy();resolve({allowed:true})});
  socket.once('error',error=>resolve({allowed:false,code:error.code}));
  socket.setTimeout(1000,()=>{socket.destroy();resolve({allowed:false,code:'TIMEOUT'})});
})}
lines.on('line',async line=>{
  const request=JSON.parse(line);let result;
  if(request.method==='initialize')result={protocolVersion:'1.0',tools:[{
    name:'probe',version:'1.0.0',description:'isolated product fixture',inputSchema:{type:'object'},
    capabilities:[],sideEffect:'NONE',supportsCancellation:true}]};
  else {
    const a=request.params.arguments;
    if(a.wait)await new Promise(resolve=>setTimeout(resolve,30000));
    let privateRead,privateWrite;
    try{fs.readFileSync(a.privatePath);privateRead={allowed:true}}catch(e){privateRead={allowed:false,code:e.code}}
    try{fs.writeFileSync(a.privatePath,'BAD');privateWrite={allowed:true}}catch(e){privateWrite={allowed:false,code:e.code}}
    const limits=fs.readFileSync('/proc/self/limits','utf8');
    const limit=name=>{const line=limits.split('\n').find(row=>row.startsWith(name));return line.trim().split(/\s+/).slice(-3,-1)};
    result={ok:true,data:{uid:process.getuid(),pid:process.pid,node:process.version,
      privateRead,privateWrite,network:await network(a.port),unicode:'安卓🧪',
      fdLimits:limit('Max open files'),coreLimits:limit('Max core file size'),
      heapLimit:require('node:v8').getHeapStatistics().heap_size_limit,envKeys:Object.keys(process.env).sort(),
      sha256:crypto.createHash('sha256').update('product-service-fixture').digest('hex')}};
  }
  process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:request.id,result})+'\n');
});
