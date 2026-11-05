// Read-only projection of the Kotlin host's existing review file/catalog.
// It never installs, approves, registers or executes a provider.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const fail=()=>{throw Error('PROVIDER_SESSION_REVIEW_INVALID');};
const keys=(v,names)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join(',')===names.split(',').sort().join(',');
// Android JSONObject.quote (SDK JSONStringer): slash escaping and ', ' joins
// are part of the already persisted Kotlin declaration identity.
function canonical(v) {
  if(typeof v==='string') {if(!v.isWellFormed())fail();return JSON.stringify(v).replaceAll('/','\\/');}
  if(Array.isArray(v))return '['+v.map(canonical).join(', ')+']';
  if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>canonical(k)+':'+canonical(v[k])).join(', ')+'}';
  if(v===null||typeof v==='boolean'||Number.isSafeInteger(v))return String(v);
  fail();
}
const inputSchema={type:'object',required:['base64'],additionalProperties:false,properties:{base64:{type:'string',maxLength:21848}}};
function snapshot(v) {
  if(!keys(v,'id,version,contentHash,definitionHash,toolIds')||typeof v.id!=='string'||! /^[A-Za-z][A-Za-z0-9_-]{1,48}$/.test(v.id)||
      ['device_info','text_digest','ui','workspace','web'].includes(v.id.toLowerCase())||
      typeof v.version!=='string'||!v.version.length||v.version.length>128||/[\x00-\x1f\x7f]/.test(v.version)||
      ![v.contentHash,v.definitionHash].every(h=>typeof h==='string'&&/^[a-f0-9]{64}$/.test(h))||
      !Array.isArray(v.toolIds)||!v.toolIds.length||v.toolIds.length>16||new Set(v.toolIds).size!==v.toolIds.length)fail();
  for(const id of v.toolIds)if(typeof id!=='string'||!id.startsWith(v.id+'.')||! /^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id.slice(v.id.length+1))||/^(ui|workspace|web)_/i.test(id.replaceAll('.','_')))fail();
  canonical(v);return structuredClone(v);
}
class ProviderReviewBindings {
  constructor({root}) {this.root=fs.realpathSync(root);this.file=path.join(this.root,'provider-reviews.json');}
  checked(file) {
    const relative=path.relative(this.root,file);
    if(!relative||path.isAbsolute(relative)||relative.split(path.sep).includes('..'))fail();
    let current=this.root;
    for(const part of relative.split(path.sep)) {
      current=path.join(current,part);
      try {if(fs.lstatSync(current).isSymbolicLink())fail();}catch(e){if(e.code!=='ENOENT')throw e;}
    }
    return file;
  }
  json(file,max=1048576) {
    this.checked(file);const stat=fs.lstatSync(file);
    if(!stat.isFile()||stat.size<1||stat.size>max)fail();
    return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(fs.readFileSync(file)));
  }
  read() {
    let data;try {data=this.json(this.file);}catch(e){if(e.code==='ENOENT')return {schemaVersion:1,reviews:[],selected:[]};throw e;}
    if(!keys(data,'schemaVersion,reviews,selected')||data.schemaVersion!==1||!Array.isArray(data.reviews)||data.reviews.length>128||!Array.isArray(data.selected)||data.selected.length>32)fail();
    const seen=new Set();
    for(const e of data.reviews) {
      if(!keys(e,'snapshot,definitions,revoked')||typeof e.revoked!=='boolean')fail();
      const p=snapshot(e.snapshot),key=p.id+':'+p.contentHash+':'+p.definitionHash;
      if(seen.has(key))fail();seen.add(key);this.declarations(e);
    }
    const ids=new Set(),wire=new Set();
    for(const value of data.selected) {
      const p=snapshot(value);if(ids.has(p.id.toLowerCase()))fail();ids.add(p.id.toLowerCase());
      if(!data.reviews.some(e=>!e.revoked&&canonical(e.snapshot)===canonical(p)))fail();
      for(const id of p.toolIds){const name=id.replaceAll('.','_');if(wire.has(name))fail();wire.add(name);}
    }
    return data;
  }
  declarations(entry) {
    const p=entry.snapshot,defs=entry.definitions;
    if(!Array.isArray(defs)||defs.length<1||defs.length>16)fail();
    for(const d of defs)if(!keys(d,'id,version,description,inputSchema,capabilities,sideEffect,supportsCancellation')||
        typeof d.id!=='string'||!p.toolIds.includes(d.id)||typeof d.version!=='string'||!d.version.length||d.version.length>128||
        typeof d.description!=='string'||!d.description.length||d.description.length>4096||
        canonical(d.inputSchema)!==canonical(inputSchema)||canonical(d.capabilities)!==canonical(['data-transform'])||d.sideEffect!=='NONE'||d.supportsCancellation!==true)fail();
    if(new Set(defs.map(d=>d.id)).size!==defs.length||canonical(defs.map(d=>d.id).sort())!==canonical([...p.toolIds].sort())||
        sha(Buffer.from(canonical([...defs].sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0))))!==p.definitionHash)fail();
    return defs;
  }
  packageHash(directory) {
    this.checked(directory);let count=0,total=0;const files=[];
    const walk=dir=>{
      const st=fs.lstatSync(dir);if(!st.isDirectory()||st.isSymbolicLink())fail();
      for(const name of fs.readdirSync(dir)) {
        if(++count>400)fail();const file=this.checked(path.join(dir,name)),s=fs.lstatSync(file);
        if(s.isDirectory())walk(file);else if(s.isFile()){total+=s.size;if(total>20*1024*1024)fail();files.push(file);}else fail();
      }
    };walk(directory);
    files.sort((a,b)=>{a=path.relative(directory,a).split(path.sep).join('/');b=path.relative(directory,b).split(path.sep).join('/');return a<b?-1:a>b?1:0;});
    const digest=crypto.createHash('sha256').update('AndroidLocalProvider-content-v2\n');
    let actualBytes=0;
    for(const file of files) {
      const name=Buffer.from(path.relative(directory,file).split(path.sep).join('/')),length=fs.statSync(file).size;
      const n=Buffer.alloc(4),size=Buffer.alloc(8);n.writeInt32BE(name.length);size.writeBigInt64BE(BigInt(length));digest.update(n).update(name).update(size);
      const fd=fs.openSync(file,'r');let readBytes=0;
      try {const buffer=Buffer.alloc(8192);let count;while((count=fs.readSync(fd,buffer,0,buffer.length,null))>0){actualBytes+=count;readBytes+=count;if(actualBytes>20*1024*1024)fail();digest.update(buffer.subarray(0,count));}}
      finally {fs.closeSync(fd);}if(readBytes!==length)fail();
    }
    return digest.digest('hex');
  }
  resolve(value) {
    const pin=snapshot(value),data=this.read(),entry=data.reviews.find(e=>!e.revoked&&canonical(e.snapshot)===canonical(pin));
    if(!entry)fail();
    const directory=path.join(this.root,'tool-providers',pin.id,'versions',pin.contentHash);
    if(this.packageHash(directory)!==pin.contentHash)fail();
    const manifest=this.json(path.join(directory,'provider.json'),65536);
    if(manifest.id!==pin.id||(manifest.version??'1.0.0')!==pin.version||!Array.isArray(manifest.command)||manifest.command.length!==2||manifest.command[0]!=='${APK_NODE}'||
        typeof manifest.command[1]!=='string'||!manifest.command[1].startsWith('${DIR}/'))fail();
    const relative=manifest.command[1].slice(7);
    if(!relative.endsWith('.cjs')||relative.split('/').some(s=>!s||s==='.'||s==='..')||/[\\:\x00-\x1f]/.test(relative))fail();
    const file=this.checked(path.join(directory,...relative.split('/'))),s=fs.lstatSync(file);
    if(!s.isFile()||s.size<1||s.size>262144)fail();const bytes=fs.readFileSync(file);
    if(bytes.includes(0))fail();new TextDecoder('utf-8',{fatal:true}).decode(bytes);
    if(this.packageHash(directory)!==pin.contentHash)fail();
    return {pin,definitions:structuredClone(this.declarations(entry))};
  }
  selected() {return this.read().selected.map(pin=>this.resolve(pin).pin);}
  verify(pin) {try {this.resolve(pin);return true;}catch{return false;}}
  route(sessionPin,registered,call) {
    const {pin,definitions}=this.resolve(sessionPin),id=registered.metadata?.canonicalToolId;
    const definition=definitions.find(d=>d.id===id);
    if(!definition||registered.toolId!==id.replaceAll('.','_')||registered.readOnly!==true||
        typeof registered.metadata?.providerDefinitionHash!=='string'||!/^[a-f0-9]{64}$/.test(registered.metadata.providerDefinitionHash)||
        canonical(registered.inputSchema)!==canonical(definition.inputSchema)||canonical(registered.metadata?.capabilities)!==canonical(['data-transform']))fail();
    call.meta={...call.meta,providerContentHash:pin.contentHash,providerDefinitionHash:pin.definitionHash};
    return pin;
  }
}
module.exports={ProviderReviewBindings,canonical,inputSchema};
