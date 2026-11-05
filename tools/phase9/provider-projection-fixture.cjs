// Test fixture writer only. Never imported by production runtime.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const runtime=process.env.TEST_RUNTIME||path.resolve(__dirname,'../../app/src/main/assets/zcode-runtime');
const {ProviderReviewBindings,canonical,inputSchema}=require(path.join(runtime,'provider-review-bindings.cjs'));
function publish(root,version='v1',id='fixture',description='计算 / Android 🧪 </script>') {
  const adapter=new ProviderReviewBindings({root}),stage=path.join(root,'stage-'+crypto.randomUUID());fs.mkdirSync(stage);
  const definition={id:id+'.compute',version:'1',description,inputSchema,capabilities:['data-transform'],sideEffect:'NONE',supportsCancellation:true};
  const script=`const readline=require('node:readline'),crypto=require('node:crypto');\nreadline.createInterface({input:process.stdin}).on('line',line=>{const r=JSON.parse(line);const d=${JSON.stringify(definition)};const bytes=Buffer.from(r.params?.arguments?.base64||'','base64');const result=r.method==='initialize'?{protocolVersion:'1.0',tools:[{...d,name:'compute'}]}:{ok:true,data:{version:${JSON.stringify(version)},bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),uid:process.getuid(),pid:process.pid}};process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:r.id,result})+'\\n');});`;
  fs.writeFileSync(path.join(stage,'provider.json'),JSON.stringify({id,version,command:['${APK_NODE}','${DIR}/provider.cjs']}));fs.writeFileSync(path.join(stage,'provider.cjs'),script);
  const contentHash=adapter.packageHash(stage),directory=path.join(root,'tool-providers',id,'versions',contentHash);
  fs.mkdirSync(path.dirname(directory),{recursive:true});fs.renameSync(stage,directory);
  const snapshot={id,version,contentHash,definitionHash:crypto.createHash('sha256').update(canonical([definition])).digest('hex'),toolIds:[definition.id]};
  let data={schemaVersion:1,reviews:[],selected:[]};if(fs.existsSync(adapter.file))data=JSON.parse(fs.readFileSync(adapter.file));
  data.reviews.push({snapshot,definitions:[definition],revoked:false});data.selected=[snapshot];fs.writeFileSync(adapter.file,JSON.stringify(data));
  fs.writeFileSync(path.join(root,'tool-providers',id,'active'),contentHash);
  return {snapshot,definition,directory,adapter};
}
module.exports={publish};
