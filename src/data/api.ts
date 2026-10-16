import { buildings, campus } from './demo';
export type DataSource={kind:'demo'|'live';message:string};
export async function loadTwinData():Promise<{source:DataSource;buildings:typeof buildings;campus:typeof campus}>{
 const url=import.meta.env.VITE_API_BASE_URL as string|undefined;
 if(!url)return {source:{kind:'demo',message:'Simulated deterministic dataset'},buildings,campus};
 const abort=new AbortController(); const timer=setTimeout(()=>abort.abort(),5000);
 try { const r=await fetch(`${url.replace(/\/$/,'')}/health`,{signal:abort.signal}); if(!r.ok)throw new Error('unavailable'); return {source:{kind:'demo',message:'Backend reachable; adapter mapping not configured'},buildings,campus}; }
 catch { return {source:{kind:'demo',message:'API unavailable — simulated deterministic dataset'},buildings,campus}; }
 finally{clearTimeout(timer)}
}
