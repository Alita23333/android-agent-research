const assert=require('node:assert/strict');
const http=require('node:http');
const path=require('node:path');
const {spawn}=require('node:child_process');
let closed=false,received=false;
const server=http.createServer((req,res)=>{
  assert.equal(req.headers['x-bridge-token'],'fixture');
  req.resume(); req.on('end',()=>{received=true; res.on('close',()=>{closed=true});});
});
server.listen(0,'127.0.0.1',()=>{
  const child=spawn(process.execPath,[path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime/android-carrier.cjs')],{
    env:{...process.env,SPIKE_HTTP_PORT:String(server.address().port),BRIDGE_TOKEN:'fixture'},stdio:['pipe','pipe','pipe']});
  let buffer=''; const watchdog=setTimeout(()=>finish(Error('cancellation watchdog expired')),4000);
  const finish=error=>{clearTimeout(watchdog); child.kill();server.closeAllConnections();server.close();
    if(error){console.error(error);process.exitCode=1}else console.log('PASS: MCP notification cancels the actual carrier HTTP request before a result');};
  child.stdout.on('data',chunk=>{buffer+=chunk;for(;;){const i=buffer.indexOf('\n');if(i<0)break;
    const m=JSON.parse(buffer.slice(0,i));buffer=buffer.slice(i+1);
    if(m.id==='boot'){
      child.stdin.write(JSON.stringify({jsonrpc:'2.0',id:10,method:'tools/call',params:{name:'ui_screenshot',arguments:{}}})+'\n');
      const poll=setInterval(()=>{if(received){clearInterval(poll);
        child.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/cancelled',params:{requestId:10}})+'\n');}},20);
    }
    if(m.id===10){try{assert.equal(m.result.isError,true); assert.match(m.result.content[0].text,/cancelled/);
      setTimeout(()=>{try{assert.equal(closed,true);finish()}catch(e){finish(e)}},50);}catch(e){finish(e)}}
  }});
});
