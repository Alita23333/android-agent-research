// Isolated APK-owned Node process-control probe; no model tool registration.
const fs=require('node:fs'), assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
if(process.argv[2]==='--leaf') {
  process.on('SIGTERM',()=>{});setInterval(()=>{},1000);
} else if(process.argv[2]==='--worker') {
  process.on('SIGTERM',()=>{});
  const leaf=spawn(process.execPath,[__filename,'--leaf'],{stdio:'ignore'});
  console.log(JSON.stringify({leaf:leaf.pid}));setInterval(()=>{},1000);
} else {
  assert.equal(process.platform,'android','This probe is for assigned Android fixture execution only');
  const delay=ms=>new Promise(r=>setTimeout(r,ms));
  const results=[];const check=(name,data)=>{results.push({name,pass:true,evidence:data});};
  function running(pid) {
    try {const stat=fs.readFileSync('/proc/'+pid+'/stat','utf8');return stat.slice(stat.lastIndexOf(')')+2).split(' ')[0]!=='Z';}
    catch(e){if(e.code==='ENOENT')return false;throw e;}
  }
  function group(pid) {
    const stat=fs.readFileSync('/proc/'+pid+'/stat','utf8');
    return Number(stat.slice(stat.lastIndexOf(')')+2).split(' ')[2]);
  }
  async function ownedGroup(reason) {
    const child=spawn(process.execPath,[__filename,'--worker'],{detached:true,stdio:['ignore','pipe','pipe']});
    let leaf;const closed=new Promise(r=>child.once('close',(code,signal)=>r({code,signal})));
    try {
      leaf=await new Promise((resolve,reject)=>{
        let text='';const timer=setTimeout(()=>reject(Error('worker startup timeout')),3000);
        child.stdout.on('data',b=>{text+=b;const end=text.indexOf('\n');if(end>=0){clearTimeout(timer);resolve(JSON.parse(text.slice(0,end)).leaf);}});
        child.once('error',e=>{clearTimeout(timer);reject(e);});
      });
      assert.ok(child.pid>1 && leaf>1);assert.equal(group(child.pid),child.pid);assert.equal(group(leaf),child.pid);
      await delay(200);assert.ok(running(child.pid)&&running(leaf));
      // Only this newly spawned and positively verified process group is signalled.
      process.kill(-child.pid,'SIGTERM');await delay(120);
      assert.ok(running(child.pid)&&running(leaf),'fixtures intentionally ignore TERM');
      process.kill(-child.pid,'SIGKILL');
      const outcome=await Promise.race([closed,delay(3000).then(()=>{throw Error('cancel completion timeout');})]);
      for(let i=0;i<20 && running(leaf);i++)await delay(50);
      assert.ok(!running(child.pid)&&!running(leaf));assert.equal(outcome.signal,'SIGKILL');
      check(reason,{groupVerified:true,leaderStopped:true,descendantStopped:true,escalated:true});
    } finally {
      try {if(child.pid>1 && group(child.pid)===child.pid)process.kill(-child.pid,'SIGKILL');} catch {}
    }
  }
  (async()=>{
    const bounded=await new Promise((resolve,reject)=>{
      const child=spawn(process.execPath,['-e',"process.stdout.write(JSON.stringify({cwd:process.cwd(),marker:process.env.FIXTURE_MARKER})+'\\n');process.stdout.write('x'.repeat(250000));process.stderr.write('fixture-error');process.exitCode=7"],
        {cwd:process.cwd(),env:{...process.env,FIXTURE_MARKER:'isolated-command-test'},stdio:['ignore','pipe','pipe']});
      let output='',error='',seen=0;
      child.stdout.on('data',b=>{seen+=b.length;output+=b.subarray(0,Math.max(0,65536-Buffer.byteLength(output))).toString();});
      child.stderr.on('data',b=>error+=b.toString());child.once('error',reject);
      child.once('close',code=>resolve({code,output,error,seen}));
    });
    const head=JSON.parse(bounded.output.split('\n')[0]);assert.equal(head.cwd,process.cwd());assert.equal(head.marker,'isolated-command-test');
    assert.equal(bounded.code,7);assert.equal(bounded.error,'fixture-error');assert.ok(bounded.seen>65536);assert.equal(Buffer.byteLength(bounded.output),65536);
    check('cwd environment exit code and separate stderr',{exitCode:7,separateStderr:true,cwdVerified:true});
    check('bounded capture still drains excess output',{captured:65536,received:bounded.seen,truncated:true});
    await ownedGroup('explicit cancellation stops leader and descendant');
    await ownedGroup('bounded timeout escalation stops ignoring descendants');
    console.log(JSON.stringify({scope:'isolated groundwork; not a production tool',platform:process.platform,node:process.version,checks:results},null,2));
  })().catch(e=>{console.error(e);process.exitCode=1;});
}
