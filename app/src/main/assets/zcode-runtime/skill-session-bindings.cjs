// Host metadata/configuration boundary. ZCode retains discovery/Skill/context/tool execution.
// Uses supported skills.roots + the existing host sessions-index.json; no Core patch or new journal.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
function atomicWrite(file, bytes) {
  fs.mkdirSync(path.dirname(file), {recursive:true});
  if(fs.existsSync(file) && fs.lstatSync(file).isSymbolicLink()) throw Error('SKILL_METADATA_LINK');
  const temp=file+'.'+crypto.randomUUID()+'.tmp';
  let fd;
  try {
    fd=fs.openSync(temp,'wx',0o600);fs.writeFileSync(fd,bytes);fs.fsyncSync(fd);fs.closeSync(fd);fd=undefined;
    fs.renameSync(temp,file);
  } finally {if(fd!==undefined)fs.closeSync(fd);try{fs.unlinkSync(temp);}catch(e){if(e.code!=='ENOENT')throw e;}}
}
function readJson(file, missing, maxBytes=1048576) {
  try {const s=fs.lstatSync(file);if(!s.isFile()||s.size>maxBytes)throw Error('SKILL_METADATA_INVALID');return JSON.parse(fs.readFileSync(file,'utf8'));}
  catch(e){if(e.code==='ENOENT' && missing!==undefined)return missing;throw e;}
}
function hashTree(dir) {
  const files=[];let count=0,total=0;
  function walk(base) {
    const stat=fs.lstatSync(base);if(!stat.isDirectory()||stat.isSymbolicLink())throw Error('SKILL_PACKAGE_LINK');
    for(const entry of fs.readdirSync(base,{withFileTypes:true})) {
      const full=path.join(base,entry.name);if(++count>500)throw Error('SKILL_PACKAGE_LIMIT');
      if(entry.isSymbolicLink())throw Error('SKILL_PACKAGE_LINK');
      if(entry.isDirectory())walk(full);
      else if(entry.isFile()) {total+=fs.statSync(full).size;if(total>20*1024*1024)throw Error('SKILL_PACKAGE_LIMIT');files.push(full);}
      else throw Error('SKILL_PACKAGE_TYPE');
    }
  }
  walk(dir);files.sort((a,b)=>{a=path.relative(dir,a).split(path.sep).join('/');b=path.relative(dir,b).split(path.sep).join('/');return a<b?-1:a>b?1:0;});
  const digest=crypto.createHash('sha256').update('AndroidCoreSkill-content-v1\n');
  for(const file of files) {
    const name=Buffer.from(path.relative(dir,file).split(path.sep).join('/'));const size=fs.statSync(file).size;
    const len=Buffer.alloc(4);len.writeInt32BE(name.length);const bytes=Buffer.alloc(8);bytes.writeBigInt64BE(BigInt(size));
    digest.update(len).update(name).update(bytes);
    const fd=fs.openSync(file,'r');try {const buffer=Buffer.alloc(8192);let n;while((n=fs.readSync(fd,buffer,0,buffer.length,null))>0)digest.update(buffer.subarray(0,n));}finally{fs.closeSync(fd);}
  }
  return digest.digest('hex');
}
class SkillSessionBindings {
  constructor({root,workspace,invoke,onFatal,timeoutMs=120000,providerBindings=null}) {
    this.root=fs.realpathSync(root);this.workspace=fs.realpathSync(workspace);this.invoke=invoke;this.onFatal=onFatal;
    this.timeoutMs=timeoutMs;this.index=path.join(this.root,'sessions-index.json');
    // A host-owned projection of explicitly reviewed providers. Never supplied by
    // Core/model RPC parameters, package active pointers or provider self-description.
    // The production adapter is read-only; absent review metadata selects nothing.
    this.providerBindings=providerBindings;
    this.inventory=path.join(this.root,'core-skill-inventory.json');this.packages=path.join(this.root,'core-skill-packages');
    this.config=path.join(this.workspace,'.zcode','config.json');this.txn=path.join(this.root,'skill-config-transaction.json');
    this.tail=Promise.resolve();this.poisoned=false;this.recover();
  }
  rows() {const rows=readJson(this.index,[]);if(!Array.isArray(rows)||rows.some(r=>!r||typeof r.sessionId!=='string'))throw Error('SKILL_SESSION_INDEX_INVALID');return rows;}
  writeRows(rows) {const bytes=Buffer.from(JSON.stringify(rows,null,2));if(bytes.length>1048576)throw Error('SKILL_SESSION_INDEX_LIMIT');atomicWrite(this.index,bytes);}
  providerSnapshot(value) {
    if(!Array.isArray(value)||value.length>32)throw Error('PROVIDER_SESSION_SNAPSHOT_INVALID');
    const pins=JSON.parse(JSON.stringify(value)),ids=new Set(),wireIds=new Set();
    for(const pin of pins) {
      if(!pin||Object.keys(pin).sort().join(',')!=='contentHash,definitionHash,id,toolIds,version'||
          typeof pin.id!=='string'||!/^[a-zA-Z][a-zA-Z0-9_-]{1,48}$/.test(pin.id)||
          ['device_info','text_digest','ui','workspace','web'].includes(pin.id.toLowerCase())||
          typeof pin.version!=='string'||!pin.version.length||pin.version.length>128||/[\x00-\x1f\x7f]/.test(pin.version)||
          typeof pin.contentHash!=='string'||!/^[a-f0-9]{64}$/.test(pin.contentHash)||
          typeof pin.definitionHash!=='string'||!/^[a-f0-9]{64}$/.test(pin.definitionHash)||
          !Array.isArray(pin.toolIds)||!pin.toolIds.length||pin.toolIds.length>16||ids.has(pin.id.toLowerCase()))
        throw Error('PROVIDER_SESSION_SNAPSHOT_INVALID');
      ids.add(pin.id.toLowerCase());
      for(const id of pin.toolIds) {
        if(typeof id!=='string'||!id.startsWith(pin.id+'.')||!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id.slice(pin.id.length+1)))
          throw Error('PROVIDER_SESSION_SNAPSHOT_INVALID');
        const wire=id.replaceAll('.','_');
        if(/^(ui|workspace|web)_/i.test(wire)||wireIds.has(wire))throw Error('PROVIDER_SESSION_TOOL_COLLISION');
        wireIds.add(wire);
      }
    }
    return pins;
  }
  verifyProviders(value) {
    const pins=this.providerSnapshot(value);
    for(const pin of pins) {
      // Verification must include original package bytes and reviewed declaration
      // identity in the host adapter. A promise/truthy value is not verification.
      if(typeof this.providerBindings?.verify!=='function'||
          this.providerBindings.verify(JSON.parse(JSON.stringify(pin)))!==true)
        throw Error('PROVIDER_SESSION_PIN_UNAVAILABLE');
    }
    return pins;
  }
  selectedProviders() {
    if(this.providerBindings===null)return [];
    if(typeof this.providerBindings?.selected!=='function'||typeof this.providerBindings?.verify!=='function')
      throw Error('PROVIDER_SESSION_ADAPTER_INVALID');
    return this.verifyProviders(this.providerBindings.selected());
  }
  providersForRow(record) {
    if(record.managedProviders===undefined&&record.managedProviderBindingVersion===undefined)return [];
    if(record.managedProviderBindingVersion!==1)throw Error('PROVIDER_SESSION_BINDING_VERSION');
    return this.verifyProviders(record.managedProviders);
  }
  providerPin(sessionId,toolId) {
    if(this.poisoned)throw Error('SKILL_ROUTER_RESTART_REQUIRED');
    const record=this.rows().find(r=>r.sessionId===sessionId);
    if(!record)throw Error('PROVIDER_SESSION_UNINDEXED');
    if(record.managedProviderWorkspace!==this.workspace)throw Error('PROVIDER_SESSION_WORKSPACE_MISMATCH');
    const pins=this.providersForRow(record),pin=pins.find(p=>p.toolIds.includes(toolId));
    if(!pin)throw Error('PROVIDER_SESSION_TOOL_UNBOUND');
    return pin; // A fresh clone; callers cannot mutate the durable row or verifier input.
  }
  recover() {
    const txn=readJson(this.txn,null,2*1048576);if(!txn)return;
    if(txn.schemaVersion!==1||typeof txn.workspace!=='string'||typeof txn.existed!=='boolean'||typeof txn.base64!=='string')throw Error('SKILL_RECOVERY_INVALID');
    if(Number.isSafeInteger(txn.ownerPid)&&txn.ownerPid!==process.pid) {
      try {process.kill(txn.ownerPid,0);throw Error('SKILL_BINDER_ALREADY_ACTIVE');}
      catch(e){if(e.code!=='ESRCH')throw e;}
    }
    const allowed=path.join(this.root,'workspaces');const real=fs.realpathSync(txn.workspace);
    if(real!==this.workspace && !real.startsWith(allowed+path.sep))throw Error('SKILL_RECOVERY_SCOPE');
    const target=path.join(real,'.zcode','config.json');this.checkConfigPath(target);
    const bytes=Buffer.from(txn.base64,'base64');if(hash(bytes)!==txn.sha256)throw Error('SKILL_RECOVERY_HASH');
    if(txn.existed)atomicWrite(target,bytes);else if(fs.existsSync(target))fs.unlinkSync(target);
    fs.unlinkSync(this.txn);
  }
  checkConfigPath(file=this.config) {
    let current=file;
    while(current!==path.dirname(current)) {if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink())throw Error('SKILL_CONFIG_LINK');current=path.dirname(current);}
  }
  admitted() {
    const inv=readJson(this.inventory);if(inv.schemaVersion!==1||!Array.isArray(inv.packages)||inv.packages.length>128)throw Error('SKILL_INVENTORY_INVALID');
    const map=new Map(),selected=[];
    for(const pkg of inv.packages) {
      if(!/^[a-z0-9][a-z0-9_-]{0,79}$/.test(pkg.id)||!Array.isArray(pkg.versions)||pkg.versions.length>128)throw Error('SKILL_INVENTORY_INVALID');
      const home=path.join(this.packages,pkg.id);const index=readJson(path.join(home,'package.json'));
      if(index.schemaVersion!==1||index.id!==pkg.id||index.candidate!==pkg.candidate||index.removed!==pkg.removed||Boolean(index.enabled)!==pkg.enabled)throw Error('SKILL_INVENTORY_STALE');
      if(fs.lstatSync(home).isSymbolicLink()||fs.lstatSync(path.join(home,'versions')).isSymbolicLink())throw Error('SKILL_PACKAGE_SCOPE');
      for(const version of pkg.versions) {
        if(!/^[a-f0-9]{64}$/.test(version.hash)||typeof version.name!=='string'||!version.name||typeof version.source!=='string')throw Error('SKILL_INVENTORY_INVALID');
        const directory=path.join(home,'versions',version.hash);
        if(version.directory!==fs.realpathSync(directory)||directory!==fs.realpathSync(directory)||index.origins?.[version.hash]!==version.source)throw Error('SKILL_PACKAGE_SCOPE');
        if(fs.realpathSync(home)!==home||fs.realpathSync(this.packages)!==this.packages)throw Error('SKILL_PACKAGE_SCOPE');
        const pin={id:pkg.id,hash:version.hash,name:version.name,version:version.version,source:version.source,directory};
        const key=pkg.id+':'+version.hash;if(map.has(key))throw Error('SKILL_INVENTORY_DUPLICATE');
        map.set(key,{pin,available:version.available===true});
        if(pkg.enabled&&!pkg.removed&&pkg.candidate===version.hash)selected.push(pin);
      }
      if(pkg.enabled&&!pkg.removed&&!map.has(pkg.id+':'+pkg.candidate))throw Error('SKILL_INVENTORY_INVALID');
    }
    this.verify(selected,map);return {map,selected};
  }
  verify(pins,map=this.admitted().map) {
    if(!Array.isArray(pins)||pins.length>32)throw Error('SKILL_SELECTION_LIMIT');
    const names=new Set();
    for(const pin of pins) {
      const entry=map.get(pin.id+':'+pin.hash);
      if(!entry||!entry.available||Object.keys(entry.pin).some(k=>entry.pin[k]!==pin[k])||Object.keys(pin).length!==Object.keys(entry.pin).length)throw Error('SKILL_UNAVAILABLE');
      if(names.has(pin.name))throw Error('SKILL_NAME_COLLISION');names.add(pin.name);
      if(hashTree(pin.directory)!==pin.hash)throw Error('SKILL_HASH_MISMATCH');
    }
  }
  async raw(method,params) {
    let timer;
    try {
      return await Promise.race([this.invoke(method,params),new Promise((_,reject)=>{
        timer=setTimeout(()=>{this.poisoned=true;this.onFatal?.('SKILL_RPC_UNCERTAIN');reject(Error('SKILL_RPC_UNCERTAIN'));},this.timeoutMs);
      })]);
    } finally {clearTimeout(timer);}
  }
  async transaction(pins,fn) {
    this.checkConfigPath();const existed=fs.existsSync(this.config);const bytes=existed?fs.readFileSync(this.config):Buffer.from('{}');
    const base=JSON.parse(bytes);if(!base||typeof base!=='object'||Array.isArray(base))throw Error('SKILL_CONFIG_INVALID');
    if(pins.length && (base.plugins?.enabled===true||base.hooks?.enabled===true||base.features?.memory===true||
      base.memory?.extractionEnabled===true||Object.keys(base.mcp?.servers||{}).length||base.skills?.roots?.length))throw Error('SKILL_PROJECT_OVERRIDE');
    if(existed&&bytes.length>1048576)throw Error('SKILL_CONFIG_LIMIT');
    atomicWrite(this.txn,Buffer.from(JSON.stringify({schemaVersion:1,ownerPid:process.pid,workspace:this.workspace,existed,base64:bytes.toString('base64'),sha256:hash(bytes)})));
    try {
      // Empty managed snapshots must not inherit newly enabled managed versions on resume.
      // Existing explicitly configured roots are legacy Core configuration. Managed versions
      // never enter that base file, so an empty managed snapshot may preserve it unchanged.
      if(pins.length)atomicWrite(this.config,Buffer.from(JSON.stringify({...base,skills:{...(base.skills||{}),roots:pins.map(p=>p.directory)}},null,2)));
      return await fn();
    } finally {
      try {if(existed)atomicWrite(this.config,bytes);else if(fs.existsSync(this.config))fs.unlinkSync(this.config);fs.unlinkSync(this.txn);}
      catch(e){this.poisoned=true;this.onFatal?.('SKILL_CONFIG_RESTORE_FAILED');throw e;}
    }
  }
  async lifecycle(method,params) {
    const {map,selected}=this.admitted();let pins=selected;
    let providerPins;
    const rows=this.rows();let record;
    if(method==='session/resume') {
      record=rows.find(r=>r.sessionId===params.sessionId);if(!record)throw Error('SKILL_SESSION_UNINDEXED');
      pins=record.managedSkills||[];this.verify(pins,map);
      providerPins=this.providersForRow(record);
      if(providerPins.length&&record.managedProviderWorkspace!==this.workspace)throw Error('PROVIDER_SESSION_WORKSPACE_MISMATCH');
    }
    else providerPins=this.selectedProviders();
    if(providerPins.length&&params.workspace?.workspacePath&&fs.realpathSync(params.workspace.workspacePath)!==this.workspace)
      throw Error('PROVIDER_SESSION_WORKSPACE_MISMATCH');
    if(pins.length) {
      const target=params.workspace?.workspacePath||record?.managedSkillWorkspace;
      if(!target||fs.realpathSync(target)!==this.workspace)throw Error('SKILL_WORKSPACE_MISMATCH');
    }
    return this.transaction(pins,async()=>{
      const result=await this.raw(method,params);if(result.error)return result;
      const id=result.result?.session?.sessionId;if(typeof id!=='string')throw Error('SKILL_SESSION_ID_MISSING');
      if(providerPins.length&&method==='session/resume'&&id!==params.sessionId)throw Error('PROVIDER_SESSION_ID_MISMATCH');
      // Recheck after asynchronous Core calls; never persist a revoked/tampered pin.
      this.verifyProviders(providerPins);
      if(pins.length) {
        const catalog=await this.raw('skills/referenceCatalog',{workspace:params.workspace||{workspacePath:this.workspace,workspaceKey:path.basename(this.workspace)},sessionId:id});
        if(catalog.error||!Array.isArray(catalog.result?.skills))throw Error('SKILL_CATALOG_FAILED');
        for(const pin of pins) {
          const matches=catalog.result.skills.filter(s=>s.name===pin.name);
          if(matches.length!==1||fs.realpathSync(matches[0].path)!==path.join(pin.directory,'SKILL.md'))throw Error('SKILL_CATALOG_MISMATCH');
        }
      }
      // Re-read after asynchronous Core calls; preserve title/other host metadata.
      const latest=this.rows();const old=latest.find(r=>r.sessionId===id);
      const binding={...(old||{sessionId:id,mode:params.mode||'build',title:'',createdAt:Date.now()}),managedSkills:pins,
        managedSkillWorkspace:this.workspace,managedSkillBindingVersion:1,
        managedProviders:providerPins,managedProviderWorkspace:this.workspace,managedProviderBindingVersion:1};
      if(old)latest[latest.indexOf(old)]=binding;else latest.push(binding);
      try {this.writeRows(latest);}catch(e){this.poisoned=true;this.onFatal?.('SKILL_BINDING_WRITE_FAILED');throw e;}
      return result;
    });
  }
  dispatch(method,params={}) {
    // Cancellation never waits behind configuration/lifecycle I/O.
    if(method==='session/stop')return this.raw(method,params);
    const run=async()=>{
      if(this.poisoned)throw Error('SKILL_ROUTER_RESTART_REQUIRED');
      if(method==='session/create'||method==='session/resume')return this.lifecycle(method,params);
      if(method==='session/send') {
        const row=this.rows().find(r=>r.sessionId===params.sessionId);
        if(!row)throw Error('SKILL_SESSION_UNINDEXED');
        this.verify(row.managedSkills||[]);
        const providers=this.providersForRow(row);
        if(providers.length&&row.managedProviderWorkspace!==this.workspace)throw Error('PROVIDER_SESSION_WORKSPACE_MISMATCH');
      }
      if(method==='session/fork'||method==='workspace/generateText') {
        if(this.admitted().selected.length||this.rows().some(r=>r.managedSkills?.length))throw Error('SKILL_UNBOUND_CHILD_DEFERRED');
        if(this.selectedProviders().length||this.rows().some(r=>r.managedProviders?.length))throw Error('PROVIDER_UNBOUND_CHILD_DEFERRED');
      }
      if(method==='skills/referenceCatalog'&&!params.sessionId) {
        const pins=this.admitted().selected;
        if(pins.length&&fs.realpathSync(params.workspace?.workspacePath||'')!==this.workspace)throw Error('SKILL_WORKSPACE_MISMATCH');
        return this.transaction(pins,()=>this.raw(method,params));
      }
      return this.raw(method,params);
    };
    const job=this.tail.then(run);this.tail=job.catch(()=>{});return job;
  }
}
module.exports={SkillSessionBindings,atomicWrite,readJson,hashTree};
